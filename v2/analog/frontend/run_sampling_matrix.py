#!/usr/bin/env python3
"""Real PDK sampling matrix: shared parsing, nine DUTs per corner/temperature.

This matrix qualifies frontend acquisition only, NOT all system metrics.
Each DUT has independent voltage sources and ideal testbench reset timing.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
from run_frontend import HERE, LIB, run_deck
from measurements import checked_data,interval_stats

p=argparse.ArgumentParser()
p.add_argument("--corners",nargs="+",default=["tt","ss","ff","sf","fs"])
p.add_argument("--temps",nargs="+",type=float,default=[-20,27,85])
p.add_argument("--gains",nargs="+",type=int,default=[1,4,16])
p.add_argument("--vdds",nargs="+",type=float,default=[1.62,1.8,1.98])
p.add_argument("--parallel",type=int,default=1)
p.add_argument("--out",default="results/sampling_matrix")
a=p.parse_args()
folder=HERE/a.out
folder.mkdir(parents=True,exist_ok=True)
core=folder/"frontend_pdk_snapshot.spice"
if core.exists():
    raise FileExistsError("Use a new output folder; existing matrix evidence is immutable")
core.write_bytes((HERE/"frontend_pdk.spice").read_bytes())
adc=folder/"adc_blocks_snapshot.spice"
adc.write_bytes((HERE.parent/"adc/adc_blocks.spice").read_bytes())
test_cell="""
.subckt frontend_case params: SUP=1.8 G=4 S0=1.8 S1=0
VDD VDD 0 {SUP}
VCM VCM 0 {SUP/2}
VIP SP 0 PULSE({SUP/2-0.18/G} {SUP/2+0.18/G} 10u 10n 10n 10u 20u)
VIN SN 0 PULSE({SUP/2+0.18/G} {SUP/2-0.18/G} 10u 10n 10n 10u 20u)
RSP SP IP 350
RSN SN IN 350
VSEL0 SEL0 0 {S0}
VSEL1 SEL1 0 {S1}
XPGA IP IN OP ON VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga
VACQ ACQ 0 PULSE(0 {SUP} 10u 1n 1n 2.476847754u 10u)
VACQB ACQB 0 PULSE({SUP} 0 10u 1n 1n 2.476847754u 10u)
VRST RST 0 PULSE(0 {SUP} 8u 1n 1n 1u 10u)
VRSTB RSTB 0 PULSE({SUP} 0 8u 1n 1n 1u 10u)
XRIP OP FILTP 0 frontend_r R=1800
XRIN ON FILTN 0 frontend_r R=1800
XCFP FILTP 0 frontend_c4p
XCFN FILTN 0 frontend_c4p
XTGP FILTP HP ACQ ACQB VDD 0 adc_tgate
XTGN FILTN HN ACQ ACQB VDD 0 adc_tgate
XCP HP VCM adc_mim_bank COUNT=4096
XCN HN VCM adc_mim_bank COUNT=4096
XRSTP VCM HP RST RSTB VDD 0 adc_tgate
XRSTN VCM HN RST RSTB VDD 0 adc_tgate
RLEAKP HP VCM 1g
RLEAKN HN VCM 1g
.ends frontend_case
"""

def one(corner,temp):
    out=folder/f"{corner}_{temp:g}"
    out.mkdir(exist_ok=True)
    cases=list(itertools.product(a.vdds,a.gains))
    text=f"* Real frontend acquisition PVT, not full ADC signoff\n.lib {LIB} {corner}\n.include {core}\n.include {adc}\n.temp {temp}\n.options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18 method=gear maxord=2\n"+test_cell
    for i,(v,g) in enumerate(cases):
        text+=f"XCASE{i} frontend_case SUP={v} G={g} S0={v if g==4 else 0} S1={v if g==16 else 0}\n"
    text+=".control\nset noaskquit\nset wr_singlescale\nset wr_vecnames\ntran 5n 40u\n"
    for i,(v,g) in enumerate(cases):
        text+=f"let d{i}=v(xcase{i}.op)-v(xcase{i}.on)\nlet h{i}=v(xcase{i}.hp)-v(xcase{i}.hn)\nlet c{i}=(v(xcase{i}.op)+v(xcase{i}.on))/2\nlet p{i}=-v(xcase{i}.vdd)*i(v.xcase{i}.vdd)\nwrdata case{i}.dat d{i} h{i} c{i} p{i}\n"
    text+="quit\n.endc\n.end\n"
    print(f"Running {corner} {temp:g}C: {len(cases)} independent gain/voltage DUTs",flush=True)
    run_deck("matrix",text,out)
    rows=[]
    for i,(v,g) in enumerate(cases):
        tr=checked_data(out/f"case{i}.dat",stop=40e-6)
        acquired=[];held=[];refs=[];ripples=[]
        for end in [(start+2.476847754)*1e-6-10e-9 for start in [10,20,30]]:
            ref,ripple=interval_stats(tr[:,0],tr[:,1],end+3e-6,end+4e-6)
            acquired.append(float(np.interp(end,tr[:,0],tr[:,2])-ref))
            held.append(float(np.interp(end+30e-9,tr[:,0],tr[:,2])-ref))
            refs.append(ref)
            ripples.append(ripple)
        late=tr[:,0]>=10e-6
        row={"corner":corner,"temp_c":temp,"vdd_v":v,"gain":g,
            "max_acquisition_error_v":max(abs(x) for x in acquired),
            "max_post_aperture_error_v":max(abs(x) for x in held),
            "max_common_mode_error_v":float(np.max(abs(tr[:,3]-v/2))),
            "mean_frontend_power_w":interval_stats(tr[:,0],tr[:,4],10e-6,40e-6)[0],
            "reference_peak_to_peak_v":ripples,
            "own_settled_references_v":refs,
            "raw_path":str((out/f"case{i}.dat").relative_to(HERE))}
        row["acquisition_pass"]=row["max_acquisition_error_v"]<=0.8/4096/4
        row["post_aperture_pass"]=row["max_post_aperture_error_v"]<=0.8/4096/4
        row["common_mode_pass"]=row["max_common_mode_error_v"]<=0.05
        row["gain_not_collapsed"]=all(0.25<abs(x)<0.45 for x in refs)
        row['references_stable']=max(ripples)<=.8/4096/40
        row["sampling_subset_pass"]=all(row[k] for k in ["acquisition_pass","post_aperture_pass","common_mode_pass","gain_not_collapsed","references_stable"])
        rows.append(row)
    (out/"summary.json").write_text(json.dumps(rows,indent=2)+"\n")
    return rows

rows=[]
with ThreadPoolExecutor(max_workers=a.parallel) as pool:
    for got in pool.map(lambda ct:one(*ct),itertools.product(a.corners,a.temps)):
        rows.extend(got)
result={"frontend_sha256":hashlib.sha256(core.read_bytes()).hexdigest(),
    "adc_sampler_sha256":hashlib.sha256(adc.read_bytes()).hexdigest(),
    "acquisition_window_s":2.476847754e-6,"power_interval_s":[10e-6,40e-6],
    "cases_run":len(rows),"sampling_subset_passes":sum(r["sampling_subset_pass"] for r in rows),
    "all_system_specs_qualified":False,
    "caution":"Own-endpoint dynamic acquisition/hold tests, not fixed-calibration accuracy/noise/SNDR/system PVT signoff.",
    "cases":rows}
(folder/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
