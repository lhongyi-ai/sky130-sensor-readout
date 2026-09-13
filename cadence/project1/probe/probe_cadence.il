; project1 environment metadata probe. No dbCreate/dbSave/CDF writes/callbacks.
; Run using the load command printed by: bash run.sh probe

procedure(p1ProbeCell(fp lib cell)
  let((obj cdf cv ans spec n)
    obj=ddGetObj(lib cell)
    fprintf(fp "CELL\t%L\n" list(lib cell obj~>views~>name))
    ans=errset(cdfGetCellCDF(obj) nil)
    if(ans then
      cdf=car(ans)
      when(cdf
        n=0
        foreach(p cdf->parameters
          when(n<160
            fprintf(fp "CDF_PARAMETER\t%L\n"
              list(lib cell p->name p->type p->defValue p->units
                   p->parseAsNumber p->parseAsCEL p->choices))
            n=n+1
          )
        )
        foreach(p cdf->parameters
          fprintf(fp "CDF_DECLARED_BOUNDS\t%L\n"
            list(lib cell p->name p->minVal p->maxVal))
        )
        fprintf(fp "CDF_LIMITS\t%L\n"
          list(lib cell "Bounds and multiplier semantics require PCell/model qualification; callbacks not executed."))
        ans=errset(cdf->simInfo->spectre nil)
        when(ans
          spec=car(ans)
          when(spec
            fprintf(fp "SPECTRE_CDF\t%L\n"
              list(lib cell spec->componentName spec->termOrder
                   spec->instParameters spec->otherParameters spec->namePrefix
                   spec->netlistProcedure spec->propMapping spec->termMapping))
          )
        )
      )
    else fprintf(fp "CELL_ERROR\t%L\n" list(lib cell "CDF_READ_FAILED")))
    ; Read an existing symbol only. Never evaluate a layout PCell.
    when(ddGetObj(lib cell "symbol")
      ans=errset(dbOpenCellViewByType(lib cell "symbol" "" "r") nil)
      when(ans
        cv=car(ans)
        when(cv
          foreach(term cv~>terminals
            fprintf(fp "SYMBOL_TERMINAL\t%L\n" list(lib cell term~>name term~>direction))
            foreach(pin term~>pins
              fprintf(fp "SYMBOL_PIN\t%L\n" list(lib cell term~>name pin~>fig~>bBox))
            )
          )
          dbClose(cv)
        )
      )
    )
  )
)

procedure(p1Probe(outdir runid)
  let((fp pathfp fpname ans libs project tf count match libname cellname coreok)
    fpname=strcat(outdir "/cadence_report.txt")
    when(isFile(fpname) error("Report already exists. Start a new probe run; no overwrite.\n"))
    fp=outfile(fpname)
    unless(fp error("Cannot open report directory: %s\n" outdir))
    coreok=t
    fprintf(fp "RUN_ID\t%L\n" runid)
    fprintf(fp "EVIDENCE_LEVEL\t%L\n" "READ_ONLY_METADATA_NOT_SIMULATION")
    ans=errset(getVersion(t) nil)
    fprintf(fp "VIRTUOSO_VERSION\t%L\n" if(ans car(ans) "UNAVAILABLE"))
    fprintf(fp "WORKING_DIRECTORY\t%L\n" getWorkingDir())
    ; A narrowly scoped PATH sidecar enables shell/Virtuoso comparison.
    pathfp=outfile(strcat(outdir "/cadence_paths.txt"))
    when(pathfp
      foreach(key '("PATH" "CDSHOME" "MMSIMHOME" "SPECTREHOME")
        ans=errset(getShellEnvVar(key) nil)
        when(ans when(stringp(car(ans)) fprintf(pathfp "%s\t%s\n" key car(ans))))
      )
      close(pathfp)
    )
    project=ddGetObj("project1")
    if(project then
      fprintf(fp "PROJECT_LIBRARY\t%L\n" list("project1" project~>readPath))
      count=0
      foreach(cell project~>cells
        when(count<2000 fprintf(fp "EXISTING_CELL\t%L\n" list(cell~>name cell~>views~>name)))
        count=count+1
      )
      fprintf(fp "PROJECT_CELL_COUNT\t%L\n" count)
      ans=errset(techGetTechFile(project) nil)
      if(ans then
        tf=car(ans)
        if(tf then
          ans=errset(techGetTechLibName(tf) nil)
          fprintf(fp "PROJECT_TECH_LIBRARY\t%L\n" if(ans car(ans) "UNAVAILABLE"))
          unless(and(ans car(ans)) coreok=nil)
        else coreok=nil fprintf(fp "REQUIRED_ERROR\t%L\n" "PROJECT_TECH_MISSING"))
      else coreok=nil fprintf(fp "REQUIRED_ERROR\t%L\n" "TECH_QUERY_FAILED"))
    else coreok=nil fprintf(fp "REQUIRED_ERROR\t%L\n" "PROJECT1_LIBRARY_NOT_FOUND"))
    libs=ddGetLibList()
    foreach(lib libs
      libname=lib~>name
      when(or(rexMatchp("sky130" libname) member(libname '("analogLib" "basic")))
        fprintf(fp "LIBRARY\t%L\n" list(libname lib~>readPath))
        count=0
        foreach(cell lib~>cells
          cellname=cell~>name
          match=or(rexMatchp("nfet.*01v8" cellname) rexMatchp("pfet.*01v8" cellname)
            rexMatchp("cap_mim" cellname) rexMatchp("^res_" cellname)
            member(cellname '("vdc" "idc" "res" "cap" "gnd" "iprobe" "diffstbprobe" "ipin" "opin" "iopin")))
          when(and(match count<100)
            ans=errset(p1ProbeCell(fp libname cellname) nil)
            unless(ans fprintf(fp "CELL_ERROR\t%L\n" list(libname cellname "METADATA_READ_FAILED")))
            count=count+1
          )
        )
        fprintf(fp "DEVICE_INSPECTION_COUNT\t%L\n" list(libname count "maximum 100 per library"))
      )
    )
    foreach(libname '("sky130_fd_sc_hd" "sky130_scl_9T" "sky130_scl_9t")
      fprintf(fp "DIGITAL_LIBRARY_PRESENT\t%L\n" list(libname if(ddGetObj(libname) t nil)))
    )
    fprintf(fp "QUALIFICATION\t%L\n" "LICENSE_MODELS_NOISE_MISMATCH_DRC_LVS_PEX_NOT_RUN")
    fprintf(fp "CORE_METADATA_OK\t%L\n" coreok)
    fprintf(fp "PROBE_COMPLETE\t%L\n" runid)
    close(fp)
    printf("PROJECT1_PROBE_COMPLETE: %s\nReturn to terminal: bash run.sh collect\n" fpname)
    t
  )
)
