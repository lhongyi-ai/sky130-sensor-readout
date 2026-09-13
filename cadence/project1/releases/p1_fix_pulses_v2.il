; Repair the two generated pulse-source instances, not the DUT or PDK.
; Load this file in the existing Virtuoso CIW. No Python/package edits.
; analogLib CDF -> Spectre mapping:
; v1 -> val0, v2 -> val1, td -> delay, tr -> rise, tf -> fall,
; pw -> width, per -> period. Check all CDF names before any mutation.
; V2: use database property enumeration, not an unavailable lookup function.
; Release only the read reference retained by the previous failed preflight.
; Never discard an editable cell that may contain unsaved changes.
when(boundp('p1pOpenCv)
  when(p1pOpenCv
    if(p1pOpenCv~>mode=="r" then
      dbClose(p1pOpenCv) p1pOpenCv=nil
      printf("P1_PULSE_PREVIOUS_READ_REFERENCE_CLOSED\n")
    else
      error("Previous repair has an editable cell open. Preserve its changes and CIW text before retrying.\n"))))

p1pRoot=strcat(getShellEnvVar("HOME") "/cadence_skywater/project1_handoff/basic_design_v1_0_4")
p1pTargets=list(
  list("p1b_tb_rc" "VIN"
    list(list("v1" "val0" "0") list("v2" "val1" "0.1")
         list("td" "delay" "1n") list("tr" "rise" "1p")
         list("tf" "fall" "1p") list("pw" "width" "5n")
         list("per" "period" "10n")))
  list("p1b_tb_step" "VINP"
    list(list("v1" "val0" "0.8") list("v2" "val1" "1.2")
         list("td" "delay" "1u") list("tr" "rise" "20n")
         list("tf" "fall" "20n") list("pw" "width" "2u")
         list("per" "period" "5u"))))

procedure(p1pFindProp(obj name)
  car(setof(prop obj~>prop prop~>name==name)))

procedure(p1pSameNumber(actual expected)
  let((a b)
    if(and(stringp(actual) strlen(actual)>0 stringp(expected)) then
      a=cdfParseFloatString(actual) b=cdfParseFloatString(expected)
      and(numberp(a) numberp(b) abs(a-b)<=max(1e-18 abs(b)*1e-9))
    else nil)))

procedure(p1pTargetInstance(cv target)
  let((owned matches inst cdf old param)
    owned=p1pFindProp(cv "project1HandoffVersion")
    unless(and(owned owned->value=="basic_1.0.4")
      error("Refuse unowned cell %s; expected basic_1.0.4 provenance.\n" car(target)))
    matches=setof(obj cv~>instances obj~>name==cadr(target))
    unless(length(matches)==1 error("Expected one instance %s/%s\n" car(target) cadr(target)))
    inst=car(matches)
    unless(and(inst~>master~>libName=="analogLib" inst~>master~>cellName=="vpulse")
      error("Target is not analogLib/vpulse: %s/%s\n" car(target) cadr(target)))
    cdf=cdfGetInstCDF(inst)
    unless(cdf error("Pulse instance CDF missing\n"))
    foreach(field caddr(target)
      param=cdfFindParamByName(cdf car(field))
      unless(param
        foreach(p cdf->parameters fprintf(p1pLog "AVAILABLE_CDF %s %L\n" p->name p->value))
        drain(p1pLog)
        error("Required pulse CDF parameter missing: %s. No guessed property written.\n" car(field)))
      ; Old values must still be the generator's exact requested stimulus.
      ; Retain these unused properties for traceability; write the real CDF names.
      old=p1pFindProp(inst cadr(field))
      unless(and(old p1pSameNumber(old->value caddr(field)))
        error("Original stimulus changed: %s/%s %s. Preserve for review.\n" car(target) cadr(target) cadr(field)))
      fprintf(p1pLog "CDF_BEFORE %s/%s %s=%L desired=%L old_property=%s\n"
        car(target) cadr(target) car(field) param->value caddr(field) cadr(field))
      ; Do not overwrite a conflicting user-entered real CDF value.
      unless(or(param->value==nil param->value==""
                p1pSameNumber(param->value "0")
                p1pSameNumber(param->value caddr(field)))
        error("Conflicting CDF value %s/%s %s=%L. Preserve for review.\n"
          car(target) cadr(target) car(field) param->value)))
    drain(p1pLog)
    inst))

procedure(p1pRepair()
  let((inst cdf param)
    ; Preflight BOTH cells before changing either one.
    foreach(target p1pTargets
      unless(ddGetObj("project1" car(target) "schematic")
        error("Existing schematic missing: project1/%s\n" car(target)))
      p1pOpenCv=dbOpenCellViewByType("project1" car(target) "schematic" "" "r")
      unless(p1pOpenCv error("Cannot read target schematic\n"))
      p1pTargetInstance(p1pOpenCv target)
      dbClose(p1pOpenCv) p1pOpenCv=nil)
    fprintf(p1pLog "PREFLIGHT_PASS both generated pulse sources\n") drain(p1pLog)
    foreach(target p1pTargets
      p1pOpenCv=dbOpenCellViewByType("project1" car(target) "schematic" "" "a")
      unless(p1pOpenCv error("Cannot edit target schematic; close its editor and retry\n"))
      inst=p1pTargetInstance(p1pOpenCv target)
      foreach(prop inst~>prop
        fprintf(p1pLog "DATABASE_BEFORE %s/%s %s=%L\n" car(target) cadr(target) prop->name prop->value))
      drain(p1pLog)
      foreach(field caddr(target)
        unless(dbReplaceProp(inst car(field) "string" caddr(field))
          error("Failed to set pulse parameter %s\n" car(field))))
      ; analogLib pulse fields are direct instance properties; no MOS/PAS callbacks.
      cdf=cdfGetInstCDF(inst)
      foreach(field caddr(target)
        param=cdfFindParamByName(cdf car(field))
        unless(and(param p1pSameNumber(param->value caddr(field)))
          error("Pulse CDF readback mismatch: %s/%s %s\n" car(target) cadr(target) car(field)))
        fprintf(p1pLog "CDF_AFTER %s/%s %s=%L\n" car(target) cadr(target) car(field) param->value))
      dbReplaceProp(p1pOpenCv "project1PulseMappingRepair" "string" "pulse_cdf_v2")
      dbReplaceProp(p1pOpenCv "project1Qualification" "string" "PULSE_REPAIRED_PENDING_NATIVE_NETLIST_AUDIT_AND_SIMULATION")
      schCheck(p1pOpenCv)
      unless(dbSave(p1pOpenCv) error("Could not save pulse source repair\n"))
      fprintf(p1pLog "CELL_SAVED %s\n" car(target)) drain(p1pLog)
      printf("P1_PULSE_SOURCE_SAVED: project1/%s/%s\n" car(target) cadr(target))
      dbClose(p1pOpenCv) p1pOpenCv=nil)
    t))

p1pOpenCv=nil
p1pLog=outfile(strcat(p1pRoot "/runs/p1_pulse_repair_v2.log") "a")
unless(p1pLog error("Cannot write repair log; expected existing package runs/ directory\n"))
fprintf(p1pLog "\nBEGIN PULSE_CDF_REPAIR_V2\n") drain(p1pLog)
p1pResult=errset(p1pRepair() t)
fprintf(p1pLog "RESULT %L\n" p1pResult) drain(p1pLog)
when(p1pOpenCv
  if(p1pOpenCv~>mode=="r" then
    dbClose(p1pOpenCv) p1pOpenCv=nil
    fprintf(p1pLog "STOPPED_DURING_PREFLIGHT; read reference closed, no cells changed.\n")
  else
    fprintf(p1pLog "STOPPED_WITH_CELL_OPEN; last parameter snapshot is preserved above.\n")
    printf("Repair stopped with a cell open; preserve the CIW text and runs/p1_pulse_repair_v2.log.\n")))
close(p1pLog)
if(p1pResult then
  printf("P1_PULSE_REPAIR_V2_DONE: 2 sources saved. Next rerun native audits; NOT A SIMULATION PASS.\n")
else
  error("Pulse repair stopped. Return CIW text and runs/p1_pulse_repair_v2.log.\n"))
