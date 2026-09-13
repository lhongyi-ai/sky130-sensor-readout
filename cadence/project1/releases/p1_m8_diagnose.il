; Focused diagnostic, not an OTA generator or simulation.
; Set p1dRoot to the upload directory before loading this file.
unless(boundp('p1dRoot) error("Set p1dRoot to the directory containing this file.\n"))

procedure(p1dDump(stage cdf)
  let((p)
    fprintf(p1dLog "\nSTAGE %s\n" stage)
    printf("P1D_STAGE %s\n" stage)
    foreach(name list("w" "fw" "l" "fingers" "m" "simW" "simM" "as" "ad" "ps" "pd")
      p=cdfFindParamByName(cdf name)
      when(p
        fprintf(p1dLog "%s value=%L default=%L callback=%L\n" name p->value p->defValue p->callback)
        when(member(name list("w" "fw" "l" "fingers" "m"))
          printf("  %s=%L\n" name p->value))))
    drain(p1dLog)))

procedure(p1dRun()
  let((inst props cdfgData cdfgForm p cb initProc value typ)
    unless(ddGetObj("project1") error("project1 library is missing.\n"))
    when(ddGetObj("project1" "p1b_m8_cdf_probe_v1")
      error("Diagnostic cell already exists; do not overwrite. Return the existing log.\n"))
    p1dMaster=dbOpenCellViewByType("sky130_fd_pr_main" "pfet_01v8" "symbol" "" "r")
    unless(p1dMaster error("PMOS symbol unavailable.\n"))
    p1dCv=dbOpenCellViewByType("project1" "p1b_m8_cdf_probe_v1" "schematic" "schematic" "w")
    unless(p1dCv error("Cannot create diagnostic cell.\n"))
    dbReplaceProp(p1dCv "project1Qualification" "string" "CDF_DIAGNOSTIC_ONLY_UNCONNECTED_NOT_FOR_SIMULATION")
    inst=dbCreateInst(p1dCv p1dMaster "M8" 0:0 "R0")
    unless(inst error("Cannot create diagnostic M8.\n"))
    ; Save the instance immediately, so an error does not leave only an empty cell.
    dbSave(p1dCv)
    props=list(list("w" "7.22005u") list("fw" "7.22005u") list("l" "0.8u") list("fingers" "1") list("m" "1"))
    p1dDump("01_DEFAULT" cdfGetInstCDF(inst))
    foreach(pair props dbReplaceProp(inst car(pair) "string" cadr(pair)))
    cdfgData=cdfGetInstCDF(inst)
    p1dDump("02_REQUEST_WRITTEN" cdfgData)
    initProc=cdfgData->formInitProc
    fprintf(p1dLog "formInitProc=%L\n" initProc) drain(p1dLog)
    unless(and(stringp(initProc) strlen(initProc)>0) error("Missing formInitProc.\n"))
    unless(errset(apply(concat(initProc) list(cdfgData)) t) error("Initialization failed; see CIW.\n"))
    p1dDump("03_AFTER_INITIALIZATION" cdfgData)
    foreach(pair props
      p=cdfFindParamByName(cdfgData car(pair))
      unless(p error("Missing requested parameter.\n"))
      p->value=cadr(pair))
    p1dDump("04_REQUEST_REAPPLIED" cdfgData)
    foreach(name list("fingers" "l" "fw" "m")
      p=cdfFindParamByName(cdfgData name)
      unless(p error("Missing callback parameter.\n"))
      cb=p->callback
      fprintf(p1dLog "CALLBACK_BEGIN %s %L\n" name cb) drain(p1dLog)
      when(and(stringp(cb) strlen(cb)>0)
        unless(errset(evalstring(cb) t) error("Callback failed: %s. See CIW.\n" name)))
      p1dDump(strcat("05_AFTER_CALLBACK_" name) cdfgData))
    foreach(p cdfgData->parameters
      value=p->value
      typ=if(or(value==t value==nil) then "boolean"
        else case(type(value) (string "string") (fixnum "int") (flonum "float") (t nil)))
      when(typ dbReplaceProp(inst p->name typ value)))
    p1dDump("06_DATABASE_READBACK" cdfGetInstCDF(inst))
    foreach(pair props
      p=cdfFindParamByName(cdfGetInstCDF(inst) car(pair))
      fprintf(p1dLog "COMPARE %s requested=%L actual=%L\n" car(pair) cadr(pair) p->value))
    drain(p1dLog)
    dbSave(p1dCv)
    t))

p1dCv=nil
p1dMaster=nil
p1dLog=outfile(strcat(p1dRoot "/p1_m8_diagnose.txt") "a")
unless(p1dLog error("Cannot open diagnostic log.\n"))
fprintf(p1dLog "\nBEGIN M8_DIAGNOSTIC_V1\n") drain(p1dLog)
p1dResult=errset(p1dRun() t)
fprintf(p1dLog "RESULT %L; this is a diagnostic, not simulation qualification.\n" p1dResult)
drain(p1dLog)
when(p1dCv
  p1dSaved=errset(dbSave(p1dCv) t)
  fprintf(p1dLog "FINAL_SAVE %L\n" p1dSaved)
  dbClose(p1dCv))
when(p1dMaster dbClose(p1dMaster))
close(p1dLog)
printf("P1D_REPORT: %s/p1_m8_diagnose.txt\n" p1dRoot)
unless(p1dResult printf("Diagnostic stopped early; return the log and CIW error text.\n"))
