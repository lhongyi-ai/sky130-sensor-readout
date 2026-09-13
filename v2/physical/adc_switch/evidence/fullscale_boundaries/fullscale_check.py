#!/usr/bin/env python3
"""Additional opposite-full-scale transitions at four representative PVTs.

The full 45-PVT qualification starts the holding capacitor at common mode.
This boundary test instead starts it at the opposite signal endpoint. It is
reported separately, without pretending four PVTs are another full 45 sweep.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

import numpy as np

from run import HERE, PDK, LSB, command, digest


def main():
    report=json.loads((HERE/"results/dummy_w4w8_rc_full.json").read_text())
    original=HERE/"runs"/report["run_tag"]
    folder=HERE/"runs/dummy_fullscale_boundaries"
    if folder.exists():
        raise ValueError("Boundary output exists; preserve prior evidence")
    folder.mkdir(parents=True)
    for name in ("candidate.spice","reference.spice","adc_tgate_flat.rc.spice"):
        shutil.copy2(original/name,folder/name)
    shutil.copy2(Path(__file__),folder/"fullscale_check.py")
    selected={("tt",1.8,27),("ss",1.62,-20),("fs",1.98,85),("sf",1.62,-20)}
    indices=sorted({r["batch"] for r in report["results"] if (r["corner"],r["vdd_v"],r["temperature_c"]) in selected})
    rows=[]
    env=dict(os.environ,SPICE_USERINIT_DIR=str(PDK/"libs.tech/ngspice"))
    aq=report["acquisition_ns"]*1e-9
    for index in indices:
        paths=list(original.glob(f"batch_{index:02d}_*.spice"))
        if len(paths)!=1:
            raise ValueError("Expected one frozen batch input")
        path=paths[0]
        text=path.read_text().replace(str(original),str(folder))
        for line in text.splitlines():
            if not line.startswith("VIN"):
                continue
            match=re.search(r"^VIN(\d+) .*PWL\(0 (\S+) 20n (\S+) 21n (\S+) .* (\S+)\)$",line)
            if match is None:
                raise ValueError("Unexpected frozen input stimulus format")
            j,cm1,cm2,target,opposite=match.groups()
            replacement=line.replace(f"PWL(0 {cm1} 20n {cm2}",f"PWL(0 {opposite} 20n {opposite}")
            text=text.replace(line,replacement)
            text=re.sub(rf"(?m)^\.ic v\(hold{j}\)=\S+$",f".ic v(hold{j})={opposite}",text)
        target_path=folder/path.name
        target_path.write_text(text)
        command(path.stem,["ngspice","-b",str(target_path)],folder,env,timeout=600)
        values=np.loadtxt(folder/f"{path.stem}.tsv",skiprows=1)
        for source in (r for r in report["results"] if r["batch"]==index):
            row=dict(source)
            target=row["input_v"]
            col=row["column"]
            pre,held,before,after,end=[float(np.interp(t,values[:,0],values[:,col]))
                for t in (aq-1e-9,aq+100e-9,aq+199e-9,aq+300e-9,10e-6)]
            row.update(acquisition_error_v=pre-target,hold_error_100ns_v=held-target,end_hold_error_v=end-target,
                acquisition_pass_quarter_lsb=abs(pre-target)<=LSB/4,end_hold_pass_quarter_lsb=abs(end-target)<=LSB/4,
                off_input_feedthrough_v=after-before,late_hold_droop_v=end-after,
                initial_held_v=row["vdd_v"]+2*row["commonmode_shift_v"]-target)
            rows.append(row)
    failed=[r for r in rows if not(r["acquisition_pass_quarter_lsb"] and r["end_hold_pass_quarter_lsb"])]
    output={"status":"passed_tested_boundaries" if not failed else "failed_specification",
        "full_45_pvt_sweep":False,"pvt_cases":[list(p) for p in sorted(selected)],"view_cases":len(rows),
        "failed_cases":len(failed),"acquisition_ns":report["acquisition_ns"],
        "stimulus":"Held node and source begin at opposite full-scale endpoint, then step to the target after20ns. Hold source reversal remains enabled.",
        "results":rows,"source_qualification_sha256":digest(HERE/"results/dummy_w4w8_rc_full.json"),
        "script_sha256":digest(Path(__file__)),"artifact_sha256":{p.name:digest(p) for p in sorted(folder.iterdir()) if p.is_file()}}
    (folder/"validation.json").write_text(json.dumps(output,indent=2)+"\n")
    shutil.copy2(folder/"validation.json",HERE/"results/dummy_fullscale_boundaries.json")
    print(json.dumps({k:v for k,v in output.items() if k not in("results","artifact_sha256")},indent=2))
    return 1 if failed else 0


if __name__=="__main__":
    raise SystemExit(main())
