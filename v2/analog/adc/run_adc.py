#!/usr/bin/env python3
"""Render and execute deterministic SKY130 transistor/MIM ADC block benches.

Run inside the pinned IIC container, repository mounted at /repo:
  SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice python3 v2/analog/adc/run_adc.py
No randomized perturbation in this script is represented as PDK Monte Carlo.
"""
from __future__ import annotations

import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np

HERE = Path(__file__).resolve().parent
GENERATED = HERE / "generated"
RESULTS = HERE / "results"
PDK = Path("/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice")
LSB = 0.8 / 4096


def deck(title, body, control, corner="tt", temp=27):
    return f"""* {title}
.lib {PDK} {corner}
.include {HERE / 'adc_blocks.spice'}
.temp {temp}
.options reltol=1e-5 abstol=1e-14 vntol=1e-8 method=gear klu
{body}
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
{control}
quit
.endc
.end
"""


def run_case(name, content, reuse_completed=False):
    path = GENERATED / f"{name}.spice"
    source_paths=set()
    def includes(text):
        for match in re.finditer(r'(?im)^\s*\.include\s+["\']?([^\s"\']+)',text):
            p=Path(match.group(1)).resolve()
            if p.is_file() and HERE in p.parents and p not in source_paths:
                source_paths.add(p);includes(p.read_text())
    includes(content)
    source_hashes={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source_paths)}
    provenance_path=RESULTS/(name+'.provenance.json')
    previous_provenance=json.loads(provenance_path.read_text()) if provenance_path.exists() else None
    source_match=bool(previous_provenance and all(previous_provenance.get('source_hashes',{}).get(k)==v for k,v in source_hashes.items()))
    if reuse_completed and previous_provenance and previous_provenance.get('status')=='SIMULATED' and source_match and path.exists() and path.read_text()==content:
        return name
    if path.exists():
        previous = RESULTS / "history" / (hashlib.sha256(path.read_bytes()).hexdigest()[:12]+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        previous.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, previous / path.name)
        for suffix in (".log", ".tsv", ".provenance.json"):
            artifact = RESULTS / (name+suffix)
            if artifact.exists():
                shutil.copy2(artifact, previous / artifact.name)
        for artifact in RESULTS.glob(name+'_*.tsv'):
            shutil.copy2(artifact,previous/artifact.name)
    path.write_text(content)
    for p in sorted(source_paths):
        snapshot=RESULTS/'source_snapshots'/source_hashes[str(p.relative_to(HERE))]/p.name
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        if not snapshot.exists():shutil.copy2(p,snapshot)
    provenance=dict(name=name,started_utc=datetime.now(timezone.utc).isoformat(),
                    deck_sha256=hashlib.sha256(content.encode()).hexdigest(),source_hashes=source_hashes,
                    pdk_deck_sha256=hashlib.sha256(PDK.read_bytes()).hexdigest(),status='RUNNING')
    provenance_path.write_text(json.dumps(provenance,indent=2)+'\n')
    try:
        with (RESULTS / f"{name}.log").open("w") as log_handle:
            result = subprocess.run(["ngspice", "-b", str(path)], stdout=log_handle, stderr=subprocess.STDOUT,
                                    text=True, timeout=600 if name.startswith(("sar_","cmp_refine_","preamp_")) else 150)
    except subprocess.TimeoutExpired:
        provenance.update(status='TIMEOUT',finished_utc=datetime.now(timezone.utc).isoformat())
        provenance_path.write_text(json.dumps(provenance,indent=2)+'\n')
        raise
    log = (RESULTS / f"{name}.log").read_text()
    failed=bool(result.returncode or re.search(r"(?im)^\s*(fatal error|error:|timestep too small|doanalyses:)", log))
    provenance.update(status='SIMULATION_ERROR' if failed else 'SIMULATED',returncode=result.returncode,
                      finished_utc=datetime.now(timezone.utc).isoformat())
    provenance_path.write_text(json.dumps(provenance,indent=2)+'\n')
    if failed:
        raise RuntimeError(f"{name}: ngspice failed, inspect retained log")
    return name


def table(name):
    return np.loadtxt(RESULTS / f"{name}.tsv", skiprows=1, ndmin=2)


def interp(data, time, col):
    if time < data[0,0]-1e-15 or time > data[-1,0]+1e-15:
        raise ValueError(f'Requested measurement {time:g}s outside recorded range [{data[0,0]:g}, {data[-1,0]:g}]; incomplete transient cannot pass.')
    return float(np.interp(time, data[:, 0], data[:, col]))


def prepare():
    GENERATED.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)


def capacitor_case():
    return deck("MIM multiplier qualification: AC current independently checks count", """
VONE one 0 DC 0 AC 1
VBANK bank 0 DC 0 AC 1
XONE one 0 adc_mim_bank COUNT=1
XBANK bank 0 adc_mim_bank COUNT=4096
""", f"ac lin 1 1k 1k\nwrdata {RESULTS / 'mim_scaling.tsv'} imag(i(vone)) imag(i(vbank))")


def comparator_case(name, diff=LSB/4, vdd=1.8, cm=.9, corner="tt", temp=27, dsize=0, source_r=350):
    body = f"""
VDD vdd 0 {vdd}
VIP sp 0 {cm+diff/2:.12g}
VIN sn 0 {cm-diff/2:.12g}
RP sp ip {source_r}
RN sn inn {source_r}
XCP ip 0 adc_mim_bank COUNT=4096
XCN inn 0 adc_mim_bank COUNT=4096
VCLK clk 0 PULSE(0 {vdd} 200n 1n 1n 250n 625n)
XCMP ip inn op on clk vdd 0 adc_strongarm ADC_PAIR_WIDTH_SKEW={dsize}
CLOADP op 0 5f
CLOADN on 0 5f
"""
    control = f"tran 200p 800n\nwrdata {RESULTS / (name+'.tsv')} v(ip) v(inn) v(op) v(on) v(clk) i(vdd)"
    return deck(name, body, control, corner, temp)


def sample_case(name, vin, source_r=350, vdd=1.8, corner="tt", temp=27):
    body = f"""
VDD vdd 0 {vdd}
VIN src 0 PWL(0 .9 20n .9 21n {vin:.12g})
RS src inp {max(source_r, 1e-3)}
VEN en 0 PWL(0 {vdd} 2.5u {vdd} 2.501u 0)
VENB enb 0 PWL(0 0 2.5u 0 2.501u {vdd})
XSW inp hold en enb vdd 0 adc_tgate
XH hold 0 adc_mim_bank COUNT=4096
RDC hold 0 1e15
.ic v(hold)=.9
"""
    return deck(name, body, f"tran 1n 3u uic\nwrdata {RESULTS / (name+'.tsv')} v(src) v(inp) v(hold) i(vdd)", corner, temp)


def cdac_case(name, code):
    # Two differential arrays; all bottom plates at VCM during sampling.
    # Conversion drives P array complementary and N array direct. One-unit
    # dummy is P->VREFP,N->VREFN, giving exact offset-binary zero at code 2048.
    body = ["VDD vdd 0 1.8", "VCM cm 0 .9", "VIP ip 0 .9", "VIN inn 0 .9",
            "VEN en 0 PWL(0 1.8 2.5u 1.8 2.501u 0)",
            "VENB enb 0 PWL(0 0 2.5u 0 2.501u 1.8)",
            "XSP ip tp en enb vdd 0 adc_tgate", "XSN inn tn en enb vdd 0 adc_tgate",
            "RP tp 0 1e15", "RN tn 0 1e15"]
    for b in range(12):
        p, n = ((.7, 1.1) if (code >> b)&1 else (1.1, .7))
        body += [f"VBP{b} bp{b} 0 PWL(0 .9 2.52u .9 2.521u {p})",
                 f"VBN{b} bn{b} 0 PWL(0 .9 2.52u .9 2.521u {n})"]
    body += ["VDP dp 0 PWL(0 .9 2.52u .9 2.521u 1.1)", "VDN dn 0 PWL(0 .9 2.52u .9 2.521u .7)",
             "XCP tp " + " ".join(f"bp{b}" for b in reversed(range(12))) + " dp adc_cdac12",
             "XCN tn " + " ".join(f"bn{b}" for b in reversed(range(12))) + " dn adc_cdac12"]
    return deck(name, "\n".join(body), f"tran 1n 3u\nwrdata {RESULTS / (name+'.tsv')} v(tp) v(tn)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--suite", choices=["smoke", "full"], default="full")
    ap.add_argument("--only", choices=["all", "cdac", "comparator", "analyze"], default="all")
    args = ap.parse_args()
    prepare()
    cases = {"mim_scaling": capacitor_case()}
    comparator_specs = []
    for diff in ([-LSB/4, LSB/4] if args.suite == "smoke" else [-.01, -.001, -LSB/2, -LSB/4, -1e-6, 1e-6, LSB/4, LSB/2, .001, .01]):
        name = f"cmp_tt_{'p' if diff>0 else 'n'}{abs(diff)*1e6:.4f}uv"
        cases[name] = comparator_case(name, diff)
        comparator_specs.append(dict(name=name, diff_v=diff, vdd=1.8, corner="tt", temperature_c=27, dsize=0))
    if args.suite == "full":
        for corner in ["tt", "ff", "ss", "fs", "sf"]:
            for vdd in [1.62, 1.8, 1.98]:
                for temp in [-20, 27, 85]:
                    for sign in [-1, 1]:
                        name = f"cmp_{corner}_{vdd}_{temp}_{sign}"
                        cases[name] = comparator_case(name, sign*LSB/4, vdd, vdd/2, corner, temp)
                        comparator_specs.append(dict(name=name, diff_v=sign*LSB/4, vdd=vdd, corner=corner, temperature_c=temp, dsize=0))
        for ds in [-.01, .01]:
            for diff in [-.003, -.001, -.0001, .0001, .001, .003]:
                name = f"cmp_geometry_{ds}_{diff}"
                cases[name] = comparator_case(name, diff=diff, dsize=ds)
                comparator_specs.append(dict(name=name, diff_v=diff, vdd=1.8, corner="tt", temperature_c=27, dsize=ds))
    sample_specs = []
    for source_r in ([350] if args.suite == "smoke" else [0, 350, 1000]):
        for vin in ([.7, .9, 1.1] if args.suite == "smoke" else np.linspace(.7,1.1,17)):
            name = f"sample_{source_r}_{vin:.5f}"
            cases[name] = sample_case(name, vin, source_r)
            sample_specs.append(dict(name=name, input_v=float(vin), source_ohm=source_r))
    cdac_codes = [0, 2048, 4095] if args.suite == "smoke" else sorted(set([0,1,2047,2048,2049,4094,4095]+[1<<b for b in range(12)]))
    for code in cdac_codes:
        name = f"cdac_{code}"
        cases[name] = cdac_case(name, code)
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        selected = cases.items() if args.only == "all" else ((k,v) for k,v in cases.items() if
                    (args.only=="cdac" and k.startswith("cdac_")) or (args.only=="comparator" and k.startswith("cmp_")))
        for name in pool.map(lambda item: run_case(*item), selected):
            print(f"simulated {name}", flush=True)
    cap = table("mim_scaling")
    unit_f = abs(cap[0,1]) / (2*math.pi*1000)
    array_f = abs(cap[0,2]) / (2*math.pi*1000)
    scale_error = abs(array_f/unit_f/4096-1)
    if scale_error > 1e-4:
        raise RuntimeError(f"MIM multiplier was not verified: ratio={array_f/unit_f}")
    cmp_rows = []
    for spec in comparator_specs:
        d = table(spec["name"])
        decision_diff = interp(d,400e-9,3)-interp(d,400e-9,4)
        valid = abs(decision_diff) > .8*spec["vdd"]
        expected = spec["diff_v"] > 0
        good = bool(valid and ((decision_diff>0)==expected))
        evaluate = (d[:,0] >= 201e-9) & (d[:,0] <= 449e-9)
        resolved = evaluate & (np.abs(d[:,3]-d[:,4]) >= .8*spec["vdd"])
        delay = (float(d[resolved,0][0])-200e-9) if np.any(resolved) else None
        input_diff = d[:,1]-d[:,2]
        input_cm = (d[:,1]+d[:,2])/2
        kick_diff = float(np.max(np.abs(input_diff[evaluate]-spec["diff_v"])))
        kick_cm = float(np.max(np.abs(input_cm[evaluate]-spec["vdd"]/2)))
        avg_power = float(np.trapezoid(-spec["vdd"]*d[:,6],d[:,0])/(d[-1,0]-d[0,0]))
        cmp_rows.append({**spec,"correct_decision":good,"resolved":bool(valid),"decision_diff_v":decision_diff,
                         "resolution_delay_s":delay,"kickback_diff_v":kick_diff,"kickback_common_mode_v":kick_cm,
                         "average_supply_power_w":avg_power})
    sample_rows = []
    for spec in sample_specs:
        d = table(spec["name"])
        pre = interp(d,2.49e-6,3)
        post = interp(d,2.6e-6,3)
        end = interp(d,3e-6,3)
        sample_rows.append({**spec,"acquire_error_v":pre-spec["input_v"],"hold_error_v":post-spec["input_v"],
                           "switch_open_step_v":post-pre,"hold_droop_400ns_v":end-post,
                           "acquire_pass_quarter_lsb":bool(abs(pre-spec["input_v"]) <= LSB/4),
                           "hold_pass_quarter_lsb":bool(abs(post-spec["input_v"]) <= LSB/4)})
    cdac_rows = []
    for code in cdac_codes:
        d = table(f"cdac_{code}")
        measured = interp(d,2.9e-6,1)-interp(d,2.9e-6,2)
        expected = .4-code*LSB
        cdac_rows.append(dict(code=code,expected_diff_v=expected,measured_diff_v=measured,error_lsb=(measured-expected)/LSB))
    summary = dict(evidence_level="deterministic schematic-level SKY130 ngspice; NOT ADC qualification",
                   suite=args.suite,simulations=len(cases),lsb_v=LSB,
                   mim=dict(unit_w_um=3,unit_l_um=3,unit_capacitance_f=unit_f,array_capacitance_per_side_f=array_f,
                            count_per_side=4096,parallel_scaling_relative_error=scale_error,
                            active_mim_plate_area_total_um2=8192*9,excludes_routing_spacing_dummy_area=True,
                            differential_ktc_rms_v=math.sqrt(2*1.380649e-23*300.15/array_f)),
                   comparator=cmp_rows,sampling=sample_rows,cdac=cdac_rows,
                   limitations=["No extracted parasitics or layout", "No stochastic comparator noise", "No statistical MOS or MIM mismatch",
                                "CDAC bench bottom plates driven by ideal voltage sources; not switched-reference qualification",
                                "No closed-loop SAR conversion, full-code INL/DNL, SNDR/ENOB or calibration qualification",
                                "Geometry sensitivity is deliberately deterministic, not foundry Monte Carlo"])
    (RESULTS / "adc_block_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    manifest = {"files":{str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(GENERATED.glob("*.spice"))},
                "block_sha256":hashlib.sha256((HERE/"adc_blocks.spice").read_bytes()).hexdigest(),
                "pdk_library_sha256":hashlib.sha256(PDK.read_bytes()).hexdigest(),
                "ngspice_version":subprocess.run(["ngspice","--version"],capture_output=True,text=True).stdout}
    (RESULTS / "adc_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"cases":len(cases),"mim_unit_ff":unit_f*1e15,"array_pf":array_f*1e12,
                      "comparator_correct":sum(x["correct_decision"] for x in cmp_rows),"comparator_cases":len(cmp_rows),
                      "acquisition_pass":sum(x["acquire_pass_quarter_lsb"] for x in sample_rows),
                      "hold_pass":sum(x["hold_pass_quarter_lsb"] for x in sample_rows),"sampling_cases":len(sample_rows),
                      "cdac_max_error_lsb":max(abs(x["error_lsb"]) for x in cdac_rows)},indent=2))


if __name__ == "__main__":
    main()
