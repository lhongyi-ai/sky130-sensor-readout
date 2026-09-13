; project1 basic design: load this file through the generated CIW command.
; p1bRoot is supplied by prepare. No remote desktop automation, no PDK writes.
unless(boundp('p1bRoot) error("Use the CIW command printed by python3 run.py prepare.\n"))
load(strcat(p1bRoot "/design.il"))

procedure(p1bMaster(lib cell view)
  let((m)
    m=dbOpenCellViewByType(lib cell view "" "r")
    unless(m error("Missing master %s/%s/%s\n" lib cell view))
    m))
procedure(p1bPin(inst name)
  let((term pin)
    term=dbFindTermByName(inst~>master name)
    unless(term error("Missing terminal %s on %s\n" name inst~>name))
    pin=car(term~>pins)
    unless(pin error("No symbol pin for %s\n" name))
    dbTransformPoint(centerBox(pin~>fig~>bBox) inst~>transform)))
procedure(p1bLabel(cv start finish net)
  let((wire)
    wire=schCreateWire(cv "draw" "full" list(start finish) 0.0625 0.0625 0.0)
    unless(wire error("Wire creation failed\n"))
    unless(schCreateWireLabel(cv car(wire) finish net "lowerLeft" "R0" "stick" 0.0625 nil)
      error("Wire label failed: %s\n" net))))

; SKILL's type() returns symbols; do not invent Common Lisp-style predicates.
procedure(p1bPropType(value)
  if(or(value==t value==nil) then "boolean"
  else case(type(value)
    (string "string")
    (fixnum "int")
    (flonum "float")
    (t nil))))
procedure(p1bTypeSelfCheck()
  unless(and(p1bPropType("5u")=="string"
             p1bPropType(1)=="int"
             p1bPropType(1.5)=="float"
             p1bPropType(t)=="boolean"
             p1bPropType(nil)=="boolean")
    error("Property type self-check failed before any cell creation.\n"))
  printf("P1B_TYPE_CHECK_PASS\n"))

; Limited adapter for the observed school's MOS CDF. If form-dependent callbacks
; cannot run, stop and retain the partial cell. Never silently use default sizes.
procedure(p1bSize(inst props)
  let((cdfgData cdfgForm p cb value typ initProc)
    foreach(pair props dbReplaceProp(inst car(pair) "string" cadr(pair)))
    cdfgData=cdfGetInstCDF(inst)
    unless(cdfgData error("MOS CDF missing\n"))
    ; PAS requires its instance-CDF form initialization before PasCdfCommitValue.
    ; Keep the PDK-created form context dynamically scoped across initialization,
    ; parameter callbacks and property persistence. Do not use a stale GUI form.
    initProc=cdfgData->formInitProc
    fprintf(p1bCdfLog "%s\tformInitProc\t%L\n" inst~>name initProc) drain(p1bCdfLog)
    unless(and(stringp(initProc) strlen(initProc)>0)
      error("Missing PAS formInitProc for %s; no parameter callbacks executed.\n" inst~>name))
    unless(errset(apply(concat(initProc) list(cdfgData)) t)
      error("CDF form initialization failed: %s %L\n" inst~>name initProc))
    ; A form initializer may restore defaults. Reapply requested values to its
    ; live instance CDF before committing the parameters in the specified order.
    foreach(pair props
      p=cdfFindParamByName(cdfgData car(pair))
      unless(p error("Required CDF parameter missing after initialization\n"))
      p->value=cadr(pair))
    foreach(name list("fingers" "l" "fw" "m")
      p=cdfFindParamByName(cdfgData name)
      unless(p error("Required CDF parameter missing: %s\n" name))
      cb=p->callback
      when(and(stringp(cb) strlen(cb)>0)
        unless(errset(evalstring(cb) t) error("CDF callback failed: %s %s\n" inst~>name name))))
    foreach(p cdfgData->parameters
      value=p->value
      typ=p1bPropType(value)
      when(typ dbReplaceProp(inst p->name typ value)))
    ; Record readback BEFORE a strict mismatch can abort the generator.
    foreach(pair props
      p=cdfFindParamByName(cdfGetInstCDF(inst) car(pair))
      when(p
        fprintf(p1bCdfLog "%s\t%s\trequested=%L actual=%L\n" inst~>name car(pair) cadr(pair) p->value)))
    drain(p1bCdfLog)
    foreach(pair props
      p=cdfFindParamByName(cdfGetInstCDF(inst) car(pair))
      unless(p error("CDF value lost\n"))
      unless(abs(cdfParseFloatString(p->value)-cdfParseFloatString(cadr(pair)))<1e-12
        error("CDF changed requested size: %s/%s requested=%L actual=%L. Preserve for review.\n" inst~>name car(pair) cadr(pair) p->value)))
    foreach(name list("w" "fw" "l" "fingers" "m" "as" "ad" "ps" "pd")
      p=cdfFindParamByName(cdfGetInstCDF(inst) name)
      when(p fprintf(p1bCdfLog "%s\t%s\t%L\n" inst~>name name p->value)))
    drain(p1bCdfLog)))

procedure(p1bStamp(cv)
  dbReplaceProp(cv "project1HandoffVersion" "string" "basic_1.0.4")
  dbReplaceProp(cv "project1Qualification" "string" "GENERATED_PENDING_NETLIST_AUDIT_AND_SIMULATION"))

procedure(p1bSymbol(name ports)
  let((cv master idx pt)
    cv=dbOpenCellViewByType("project1" name "symbol" "schematicSymbol" "w")
    unless(cv error("Cannot create symbol\n"))
    master=p1bMaster("basic" "sympin" "symbolNN")
    dbCreateRect(cv list("device" "drawing") list(0:0 1.5:2.5))
    idx=0
    foreach(port ports
      pt=list(0 2.25-idx*0.375)
      unless(schCreateSymbolPin(cv master port "inputOutput" pt "R0") error("Symbol pin failed\n"))
      dbCreateLabel(cv list("device" "drawing") list(0.125 yCoord(pt)) port "centerLeft" "R0" "stick" 0.1)
      idx=idx+1)
    dbCreateLabel(cv list("device" "drawing") 0.75:2.75 name "centerCenter" "R0" "stick" 0.125)
    p1bStamp(cv) dbSave(cv) dbClose(cv) dbClose(master)))

procedure(p1bCell(record)
  let((cv name ports objects master inst pt finish idx pm pinInst)
    name=car(record) ports=cadr(record) objects=caddr(record)
    cv=dbOpenCellViewByType("project1" name "schematic" "schematic" "w")
    unless(cv error("Cannot create %s\n" name))
    ; Set provenance before doing any work; an exception preserves the partial cell.
    p1bStamp(cv)
    dbSave(cv)
    foreach(obj objects
      master=p1bMaster(cadr(obj) caddr(obj) "symbol")
      inst=dbCreateInst(cv master car(obj) nth(3 obj) "R0")
      unless(inst error("Instance creation failed\n"))
      dbSave(cv)
      if(and(cadr(obj)=="sky130_fd_pr_main" member(caddr(obj) list("nfet_01v8" "pfet_01v8"))) then
        unless(errset(p1bSize(inst nth(5 obj)) t)
          dbSave(cv) dbClose(cv) dbClose(master)
          error("Sizing stopped on %s. Partial cell and parameter readback preserved.\n" car(obj)))
      else
        foreach(pair nth(5 obj) dbReplaceProp(inst car(pair) "string" cadr(pair))))
      foreach(pair nth(4 obj)
        pt=p1bPin(inst car(pair))
        ; Dedicated outward stubs avoid crossings within each tile.
        cond((car(pair)=="G" finish=list(xCoord(pt)-0.75 yCoord(pt)))
             (car(pair)=="B" finish=list(xCoord(pt)+0.75 yCoord(pt)))
             (member(car(pair) list("D" "S"))
               finish=list(xCoord(pt) yCoord(pt)+if(yCoord(pt)>yCoord(nth(3 obj)) 0.5 -0.5)))
             (cadr(obj)=="project1" finish=list(xCoord(pt)-0.75 yCoord(pt)))
             (car(pair)=="PLUS" finish=list(xCoord(pt) yCoord(pt)+0.5))
             (t finish=list(xCoord(pt) yCoord(pt)-0.5)))
        if(cadr(pair)=="0" then
          pinInst=dbCreateInst(cv p1bMaster("analogLib" "gnd" "symbol") nil finish "R0")
          schCreateWire(cv "draw" "full" list(pt finish) 0.0625 0.0625 0.0)
        else p1bLabel(cv pt finish cadr(pair))))
      dbClose(master) dbSave(cv))
    when(ports
      pm=p1bMaster("basic" "iopin" "symbol")
      idx=0
      foreach(port ports
        pt=list(-3 2-idx*0.75)
        unless(schCreatePin(cv pm port "inputOutput" nil pt "R0") error("Schematic port failed\n"))
        p1bLabel(cv pt list(xCoord(pt)+0.5 yCoord(pt)) port)
        idx=idx+1)
      dbClose(pm))
    schCheck(cv) dbSave(cv) dbClose(cv)
    fprintf(p1bCreateLog "CELL_CREATED %s\n" name) drain(p1bCreateLog)
    printf("P1B_CELL_CREATED %s\n" name)))

procedure(p1bCreateAll()
  let((f)
    p1bTypeSelfCheck()
    unless(ddGetObj("project1") error("project1 library missing\n"))
    ; Preflight every target before any mutation. Repeat load does not overwrite.
    foreach(record p1bDesign
      when(ddGetObj("project1" car(record)) error("Existing cell %s: stop, no overwrite.\n" car(record))))
    p1bSymbol(car(car(p1bDesign)) cadr(car(p1bDesign)))
    foreach(record p1bDesign p1bCell(record))
    f=outfile(strcat(p1bRoot "/created.txt"))
    fprintf(f "basic_1.0.4 native views created; NOT A SIMULATION PASS\n") close(f)
    printf("P1B_ALL_CREATED: next run python3 run.py run --group passives\n")
    t))
p1bCreateLog=outfile(strcat(p1bRoot "/create_status.txt") "a")
p1bCdfLog=outfile(strcat(p1bRoot "/cdf_values.tsv") "a")
fprintf(p1bCreateLog "BEGIN basic_1.0.4\n") drain(p1bCreateLog)
p1bResult=errset(p1bCreateAll() t)
fprintf(p1bCreateLog "RESULT %L (errors, if any, are printed in CIW)\n" p1bResult)
close(p1bCreateLog) close(p1bCdfLog)
unless(p1bResult error("Generation stopped. Keep create_status.txt and CIW error text; do not delete existing cells.\n"))
