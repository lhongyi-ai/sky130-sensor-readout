#!/usr/bin/env python3
"""Batch independent TG replicas per PVT: identical tests, less PDK parsing.

All replicas share ideal clock/supply voltage sources, so no coupling through
those zero-impedance nodes is implied. Every sensor source/load is independent.
Use one PVT process per batch; ngspice retains the real transistor nonlinearities.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np

from run import HERE, ROOT, PDK, LSB, command, digest


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tag",required=True)
    ap.add_argument("--model",choices=("adc_tgate_dual_lvt","adc_tgate_dual_lvt_dummy"),default="adc_tgate_dual_lvt")
    ap.add_argument("--wn",type=float,default=4)
    ap.add_argument("--wp",type=float,default=5)
    ap.add_argument("--dummy",type=float,default=.5)
    ap.add_argument("--acquisition-ns",type=float,default=2476.847754)
    ap.add_argument("--suite",choices=("extremes","full","one"),default="extremes")
    ap.add_argument("--physical-run",help="Add actual RC view from this existing checked layout run")
    args=ap.parse_args()
    folder=HERE/"runs"/args.tag
    if folder.parent != HERE/"runs" or folder.exists():
        raise ValueError("Use an unused simple tag")
    folder.mkdir(parents=True)
    source=HERE/"candidates"/f"{args.model}.spice"
    shutil.copy2(source,folder/"candidate.spice")
    shutil.copy2(HERE/"artifacts/reference.spice",folder/"reference.spice")
    shutil.copy2(Path(__file__),folder/"batch_qualification.py")
    if args.physical_run:
        physical=HERE/"runs"/args.physical_run
        meta=json.loads((physical/"validation.json").read_text())
        if meta["magic_drc_count"] != 0 or meta["netgen_lvs"] != "unique_match":
            raise ValueError("Physical view must have checked DRC/LVS")
        if meta["candidate_nfet"]["w_um"] != args.wn or meta["candidate_pfet"]["w_um"] != args.wp:
            raise ValueError("Physical and schematic sizes must match")
        if meta.get("candidate_model") != args.model or meta.get("dummy_ratio") != (args.dummy if args.model.endswith("_dummy") else None):
            raise ValueError("Physical topology and dummy ratio must match the schematic")
        shutil.copy2(physical/"adc_tgate_flat.rc.spice",folder/"adc_tgate_flat.rc.spice")
        views=("schematic","layout_rc")
    else:
        views=("schematic",)
    if args.suite=="full":
        pvts=list(itertools.product(("tt","ff","ss","fs","sf"),(1.62,1.8,1.98),(-20,27,85)))
    elif args.suite=="one":
        pvts=[("ss",1.62,-20)]
    else:
        pvts=[("tt",1.8,27),("ss",1.62,-20),("fs",1.98,85),("sf",1.62,-20)]
    localcases=list(itertools.product((-.2,0,.2),(0,350,1000),(-.05,0,.05),views))
    aq=args.acquisition_ns*1e-9
    env=dict(os.environ,SPICE_USERINIT_DIR=str(PDK/"libs.tech/ngspice"))
    def simulate(item):
        ix,(corner,vdd,temp)=item
        name=f"batch_{ix:02d}_{corner}_{vdd}_{temp}"
        lines=[f"* Independent switch qualification replicas: {name}",
            f".lib {PDK}/libs.tech/combined/sky130.lib.spice {corner}",
            f".include {folder}/candidate.spice",f".include {folder}/reference.spice",
            f".temp {temp}",".options reltol=1e-5 abstol=1e-14 vntol=1e-8 method=gear klu",
            f"VDD vdd 0 {vdd}",f"VEN en 0 PWL(0 {vdd} {aq:.14g} {vdd} {aq+1e-9:.14g} 0)",
            f"VENB enb 0 PWL(0 0 {aq:.14g} 0 {aq+1e-9:.14g} {vdd})"]
        if args.physical_run:
            lines.append(f".include {folder}/adc_tgate_flat.rc.spice")
        for j,(delta,rs,cshift,view) in enumerate(localcases):
            cm=vdd/2+cshift; target=cm+delta
            dut="adc_tgate_flat" if view=="layout_rc" else f"{args.model} WN={args.wn} WP={args.wp}"
            if view=="schematic" and args.model.endswith("_dummy"):
                dut+=f" DUMMY={args.dummy}"
            lines += [f"VIN{j} src{j} 0 PWL(0 {cm:.12g} 20n {cm:.12g} 21n {target:.12g} {aq+200e-9:.14g} {target:.12g} {aq+201e-9:.14g} {cm-delta:.12g})",
                f"RS{j} src{j} inp{j} {max(rs,.001)}",f"XSW{j} inp{j} hold{j} en enb vdd 0 {dut}",
                f"XH{j} hold{j} 0 adc_mim_bank COUNT=4096",f"RDC{j} hold{j} 0 1e15",f".ic v(hold{j})={cm:.12g}"]
        lines += [".control","set num_threads=1","set wr_singlescale","set wr_vecnames","set numdgt=12",
            "tran 5n 10u uic",f"wrdata {folder}/{name}.tsv "+" ".join(f"v(hold{j})" for j in range(len(localcases))),
            "quit",".endc",".end"]
        path=folder/f"{name}.spice";path.write_text("\n".join(lines)+"\n")
        started=time.monotonic()
        command(name,["ngspice","-b",str(path)],folder,env,timeout=600)
        values=np.loadtxt(folder/f"{name}.tsv",skiprows=1)
        rows=[]
        for j,(delta,rs,cshift,view) in enumerate(localcases):
            target=vdd/2+cshift+delta
            pre,held,before_step,after_step,end=[float(np.interp(t,values[:,0],values[:,j+1]))
                for t in (aq-1e-9,aq+100e-9,aq+199e-9,aq+300e-9,10e-6)]
            rows.append({"batch":ix,"column":j+1,"view":view,"corner":corner,"vdd_v":vdd,
                "temperature_c":temp,"source_ohm":rs,"commonmode_shift_v":cshift,"input_v":target,
                "acquisition_error_v":pre-target,"hold_error_100ns_v":held-target,"end_hold_error_v":end-target,
                "off_input_feedthrough_v":after_step-before_step,"late_hold_droop_v":end-after_step,
                "acquisition_pass_quarter_lsb":abs(pre-target)<=LSB/4,
                "end_hold_pass_quarter_lsb":abs(end-target)<=LSB/4})
        return {"name":name,"runtime_s":time.monotonic()-started,"results":rows}
    # Bound memory use when other analog qualifications share this container.
    with ThreadPoolExecutor(max_workers=1) as pool:
        batches=list(pool.map(simulate,enumerate(pvts)))
    rows=[r for b in batches for r in b["results"]]
    failures=[r for r in rows if not(r["acquisition_pass_quarter_lsb"] and r["end_hold_pass_quarter_lsb"])]
    corefailures=[r for r in failures if r["source_ohm"]==350]
    report={"status":"passed_tested_cases" if not failures else "failed_specification",
        "run_tag":args.tag,"suite":args.suite,"candidate_model":args.model,"wn_um":args.wn,"wp_um":args.wp,
        "dummy_ratio":args.dummy if args.model.endswith("_dummy") else None,
        "cadence_used":False,"whole_adc_validated":False,"acquisition_ns":args.acquisition_ns,
        "acquisition_measurement_ns":args.acquisition_ns-1,"end_measurement_ns":10000,
        "hold_interval_ns":10000-args.acquisition_ns,"quarter_lsb_v":LSB/4,"load_f":81.28512e-12,
        "pvt_batches":len(pvts),"replica_cases":len(rows),"failed_cases":len(failures),
        "simulation_workers":1,
        "core_350ohm_failed_cases":len(corefailures),"views":list(views),"physical_run":args.physical_run,
        "sampling_clock_source":"Minimum acquisition window from real 45-PVT phase-generator characterization; ideal rail clocks use this conservative duration.",
        "limitations":["Standalone voltage sampling, not reference-switching full CDAC or ADC SNDR.",
            "No mismatch/noise; ideal clock and supply drive; RC view uses Magic nominal extraction only.",
            "0ohm and1kohm are sensitivity tests; 350ohm is the frozen core source assumption.",
            "The held-voltage quarter-LSB check is an extra engineering guardband, not a substitute for external static calibration tests."],
        "batch_runtime_s":{b["name"]:b["runtime_s"] for b in batches},"results":rows,
        "source_sha256":{str(p.relative_to(ROOT)):digest(p) for p in (Path(__file__),source)},
        "artifact_sha256":{p.name:digest(p) for p in sorted(folder.iterdir()) if p.is_file()}}
    (folder/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    shutil.copy2(folder/"validation.json",HERE/"results"/f"{args.tag}.json")
    print(json.dumps({k:v for k,v in report.items() if k not in("results","artifact_sha256")},indent=2))
    return 1 if failures else 0


if __name__=="__main__":
    raise SystemExit(main())
