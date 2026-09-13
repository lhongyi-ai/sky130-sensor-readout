#!/usr/bin/env python3
"""Build/check/extract/test the dual-LVT TG without altering frozen ADC files."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import shutil

import numpy as np

from run import HERE, ROOT, PDK, LSB, command, digest


def transient(folder, name, case, extracted, wn, wp, model):
    corner, vdd, temp, delta, source_r, cm_shift = case
    cm, vin = vdd/2+cm_shift, vdd/2+cm_shift+delta
    dut = "adc_tgate_flat" if extracted else f"{model} WN={wn} WP={wp}"
    return f"""* Independent LVT switch schematic versus actual flattened layout RC
.lib {PDK}/libs.tech/combined/sky130.lib.spice {corner}
.include {folder}/reference.spice
.include {folder}/candidate.spice
.include {folder}/adc_tgate_flat.rc.spice
.temp {temp}
.options reltol=1e-5 abstol=1e-14 vntol=1e-8 method=gear klu
VDD vdd 0 {vdd}
VIN src 0 PWL(0 {cm} 20n {cm} 21n {vin:.12g} 2.7u {vin:.12g} 2.701u {cm-delta:.12g})
RS src inp {max(source_r,.001)}
VEN en 0 PWL(0 {vdd} 2.5u {vdd} 2.501u 0)
VENB enb 0 PWL(0 0 2.5u 0 2.501u {vdd})
XSW inp hold en enb vdd 0 {dut}
XH hold 0 adc_mim_bank COUNT=4096
RDC hold 0 1e15
.ic v(hold)={cm}
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
tran 5n 10u uic
wrdata {folder}/{name}.tsv v(src) v(inp) v(hold) i(vdd)
quit
.endc
.end
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--suite", choices=("physical_only", "smoke", "full", "expanded"), default="smoke")
    parser.add_argument("--model", choices=("adc_tgate_dual_lvt", "adc_tgate_dual_lvt_dummy"), default="adc_tgate_dual_lvt")
    parser.add_argument("--wn", type=float, default=4)
    parser.add_argument("--wp", type=float, default=5)
    args = parser.parse_args()
    folder = HERE / "runs" / args.tag
    if folder.parent != HERE / "runs" or folder.exists():
        raise RuntimeError("Use an unused direct-child run tag")
    folder.mkdir(parents=True)
    shutil.copy2(HERE / "artifacts/reference.spice", folder / "reference.spice")
    candidate = HERE / "candidates" / f"{args.model}.spice"
    source = re.sub(r"WN=[0-9.]+ WP=[0-9.]+", f"WN={args.wn} WP={args.wp}",candidate.read_text())
    (folder / "candidate.spice").write_text(source)
    env = dict(os.environ, TG_RUN_DIR=str(folder), TG_CAND_WN=str(args.wn), TG_CAND_WP=str(args.wp),
        SPICE_USERINIT_DIR=str(PDK / "libs.tech/ngspice"))
    magic = ["magic", "-dnull", "-noconsole", "-rcfile", str(PDK / "libs.tech/magic/sky130A.magicrc")]
    generator = HERE / ("generate_dummy_layout.tcl" if args.model.endswith("_dummy") else "generate_lvt_layout.tcl")
    geometry = command("layout", magic+[str(generator)], folder, env)
    if "TG_DRC_COUNT 0" not in geometry or "TG_DRC_DETAILS \n" not in geometry:
        raise RuntimeError("Candidate layout DRC did not pass")
    command("rc_extraction", magic+[str(HERE / "extract_rc.tcl")], folder, env)
    command("lvs", ["netgen", "-batch", "lvs", f"{folder}/adc_tgate_layout.lvs.spice adc_tgate_layout",
        f"{folder}/candidate.spice {args.model}", str(PDK / "libs.tech/netgen/sky130A_setup.tcl"),
        str(folder / "lvs.rpt"), "-json"], folder, env)
    if "Circuits match uniquely." not in (folder / "lvs.rpt").read_text():
        raise RuntimeError("Candidate LVS not a unique match")
    rc = (folder / "adc_tgate_flat.rc.spice").read_text()
    resistors = re.findall(r"(?m)^R\S+\s+\S+\s+\S+\s+([0-9.eE+-]+)$", rc)
    caps = re.findall(r"(?m)^C\S+\s+\S+\s+\S+\s+([0-9.eE+-]+)f$", rc)
    if not resistors or not caps or any(float(x) <= 0 for x in resistors+caps):
        raise RuntimeError("Expected a positive physical R/C network")
    if args.suite == "physical_only":
        cases = []
    elif args.suite == "smoke":
        cases = [(c,v,t,d,350,0) for c,v,t in (("tt",1.8,27),("ss",1.62,-20),("ff",1.98,85)) for d in (-.2,0,.2)]
    else:
        cm_shifts = (-.05,0,.05) if args.suite == "expanded" else (0,)
        cases = list(itertools.product(("tt","ff","ss","fs","sf"), (1.62,1.8,1.98),
            (-20,27,85), (-.2,0,.2), (350,), cm_shifts))
        cases += list(itertools.product(("tt",), (1.8,), (27,), (-.2,0,.2), (0,1000), cm_shifts))
    def simulate(item):
        index, case, extracted = item
        name = f"sample_{index:03d}_{'rc' if extracted else 'schematic'}"
        path = folder / f"{name}.spice"
        path.write_text(transient(folder,name,case,extracted,args.wn,args.wp,args.model))
        command(name,["ngspice","-b",str(path)],folder,env)
        data = np.loadtxt(folder/f"{name}.tsv",skiprows=1)
        pre, held, before_step, after_step, end = [float(np.interp(t,data[:,0],data[:,3]))
            for t in (2.49e-6,2.6e-6,2.699e-6,2.8e-6,10e-6)]
        target = case[1]/2+case[5]+case[3]
        return {"index":index,"name":name,"view":"layout_rc" if extracted else "schematic",
            "corner":case[0],"vdd_v":case[1],"temperature_c":case[2],"input_v":target,
            "commonmode_shift_v":case[5],"source_ohm":case[4],"acquisition_error_v":pre-target,
            "hold_error_100ns_v":held-target,"end_hold_error_7p5us_v":end-target,
            "off_input_feedthrough_v":after_step-before_step,"late_hold_droop_7p2us_v":end-after_step,
            "hold_drift_including_input_feedthrough_v":end-held,
            "acquisition_pass_quarter_lsb":abs(pre-target)<=LSB/4,
            "end_hold_pass_quarter_lsb":abs(end-target)<=LSB/4}
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows=list(pool.map(simulate, [(i,c,e) for i,c in enumerate(cases) for e in (False,True)]))
    failures=[r for r in rows if not (r["acquisition_pass_quarter_lsb"] and r["end_hold_pass_quarter_lsb"])]
    import klayout.db as db
    layout=db.Layout()
    layout.read(str(folder/"adc_tgate_layout.gds"))
    bbox=layout.top_cell().bbox()
    bbox_um=[v*layout.dbu for v in (bbox.left,bbox.bottom,bbox.right,bbox.top)]
    report={"status":("passed_physical_checks_only" if not rows else "passed_tested_cases") if not failures else "failed_specification",
        "run_tag":args.tag,"suite":args.suite,"evidence_level":"standalone_dual_lvt_switch_drc_lvs_flattened_rc",
        "cadence_used":False,"whole_adc_validated":False,
        "candidate_model":args.model,"dummy_ratio":.5 if args.model.endswith("_dummy") else None,
        "candidate_nfet":{"device":"sky130_fd_pr__nfet_01v8_lvt","w_um":args.wn,"l_um":.15},
        "candidate_pfet":{"device":"sky130_fd_pr__pfet_01v8_lvt","w_um":args.wp,"l_um":.35},
        "magic_drc_count":0,"netgen_lvs":"unique_match","extracted_resistors":len(resistors),
        "extracted_capacitors":len(caps),"bbox_um":bbox_um,"bbox_area_um2":bbox.area()*layout.dbu**2,
        "extraction_corner":"Magic nominal RC; transistor PVT is swept, not RC corners",
        "case_pairs":len(cases),"transient_runs":len(rows),"failed_view_cases":len(failures),
        "quarter_lsb_v":LSB/4,"load_f":81.28512e-12,
        "hold_test":"2.5us acquisition +7.5us hold; source flips to opposite excursion at2.7us" if rows else None,
        "limitations":["Standalone switch, not top-level extracted ADC or full sensor readout.",
            "No mismatch/noise/CDAC reference switching, and ideal clock/supply drive.",
            "Per-leg quarter-LSB checks are not a differential linearity or SNDR result.",
            "Open-source DRC/LVS is not a foundry production signoff."],
        "results":rows,"candidate_netlist_sha256":hashlib.sha256(source.encode()).hexdigest(),
        "source_sha256":{str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),candidate,
            generator,HERE/"extract_rc.tcl")},
        "artifact_sha256":{p.name:digest(p) for p in sorted(folder.iterdir()) if p.is_file()}}
    (folder/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    shutil.copy2(folder/"validation.json", HERE/"results"/f"{args.tag}.json")
    out=HERE/"artifacts"/args.tag
    out.mkdir(exist_ok=True)
    for name in ("adc_tgate_layout.gds","adc_tgate_layout.mag","tg_nfet_lvt.mag","tg_pfet_lvt.mag",
        "tg_nfet_dummy.mag","tg_pfet_dummy.mag",
        "adc_tgate_flat.mag","adc_tgate_layout.lvs.spice","adc_tgate_flat.rc.spice","candidate.spice",
        "reference.spice","lvs.rpt","lvs.json","layout.log","rc_extraction.log","validation.json"):
        if (folder/name).exists():
            shutil.copy2(folder/name,out/name)
    print(json.dumps({k:v for k,v in report.items() if k not in ("results","artifact_sha256")},indent=2))
    return 1 if failures else 0


if __name__=="__main__":
    raise SystemExit(main())
