#!/usr/bin/env python3
"""Qualify an explicitly separate TG candidate against the frozen standard TG.

DC on-conductance is measured with 10mV differential stimulus. Transient
qualification includes the full 2.5us acquisition + 7.5us hold interval.
The signal source changes to its opposite excursion during hold to expose
off-state feedthrough and leakage. This is not full switched-CDAC simulation.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
import os
from pathlib import Path
import shutil

import numpy as np

from run import HERE, ROOT, PDK, LSB, block, command, digest


def base(folder, corner, temp):
    return f"""* Independent low-threshold-NFET sampling switch experiment
.lib {PDK}/libs.tech/combined/sky130.lib.spice {corner}
.include {folder}/reference.spice
.include {folder}/candidate.spice
.temp {temp}
.options reltol=1e-5 abstol=1e-14 vntol=1e-8 method=gear klu
"""


def transient(folder, name, case, model, wn, wp):
    corner, vdd, temp, delta, source_r = case
    cm, vin = vdd / 2, vdd / 2 + delta
    return base(folder, corner, temp) + f"""
VDD vdd 0 {vdd}
VIN src 0 PWL(0 {cm} 20n {cm} 21n {vin:.12g} 2.7u {vin:.12g} 2.701u {cm-delta:.12g})
RS src inp {max(source_r, .001)}
VEN en 0 PWL(0 {vdd} 2.5u {vdd} 2.501u 0)
VENB enb 0 PWL(0 0 2.5u 0 2.501u {vdd})
XSW inp hold en enb vdd 0 {model} WN={wn} WP={wp}
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


def conductance(folder, name, case, wn, wp, candidate_model):
    corner, vdd, temp = case
    return base(folder, corner, temp) + f"""
VDD vdd 0 {vdd}
VEN en 0 {vdd}
VCM cm 0 0.4
BA a 0 v=v(cm)+0.005
BB b 0 v=v(cm)-0.005
BC c 0 v=v(cm)+0.005
BD d 0 v=v(cm)-0.005
XS a b en 0 vdd 0 adc_tgate WN=8 WP=16
XL c d en 0 vdd 0 {candidate_model} WN={wn} WP={wp}
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
dc VCM 0.4 {vdd-.4:.12g} .002
wrdata {folder}/{name}.tsv v(cm) i(BB) i(BD)
quit
.endc
.end
"""


def capcheck(folder, name):
    return base(folder, "tt", 27) + f"""
VCAP cap 0 DC 0.9 AC 1
XH cap 0 adc_mim_bank COUNT=4096
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
ac lin 1 1meg 1meg
let cmeasured=-imag(i(VCAP))/(2*3.141592653589793*frequency)
wrdata {folder}/{name}.tsv cmeasured
quit
.endc
.end
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--suite", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--wn", type=float, default=8)
    parser.add_argument("--wp", type=float, default=16)
    parser.add_argument("--model", choices=("adc_tgate_lvt", "adc_tgate_dual_lvt"), default="adc_tgate_lvt")
    parser.add_argument("--baseline", action="store_true", help="Also rerun frozen standard-Vt TG with the identical extended-hold bench")
    args = parser.parse_args()
    folder = HERE / "runs" / args.tag
    if folder.parent != HERE / "runs" or folder.exists():
        raise RuntimeError("Supply an unused simple tag; prior evidence is immutable")
    folder.mkdir(parents=True)
    # Use the frozen reference that produced the standard-TG layout results,
    # not a possibly concurrently edited ADC integration source.
    ref = HERE / "artifacts/reference.spice"
    candidate = HERE / "candidates" / f"{args.model}.spice"
    shutil.copy2(ref, folder / "reference.spice")
    shutil.copy2(candidate, folder / "candidate.spice")
    env = dict(os.environ, SPICE_USERINIT_DIR=str(PDK / "libs.tech/ngspice"))

    def simulate_deck(name, content):
        path = folder / f"{name}.spice"
        path.write_text(content)
        command(name, ["ngspice", "-b", str(path)], folder, env)
        return np.loadtxt(folder / f"{name}.tsv", skiprows=1, ndmin=2)

    cdata = simulate_deck("load_capacitance", capcheck(folder, "load_capacitance"))
    capacitance = float(cdata[0, 1])
    if not np.isclose(capacitance, 81.28512e-12, rtol=1e-7):
        raise RuntimeError(f"MIM load model differs from qualified value: {capacitance}")
    dc = []
    for i, case in enumerate((("tt", 1.8, 27), ("ss", 1.62, -20), ("ss", 1.62, 85), ("ff", 1.98, 85))):
        name = f"conductance_{i}"
        data = simulate_deck(name, conductance(folder, name, case, args.wn, args.wp, args.model))
        selected = (data[:, 1] >= case[1]/2-.2) & (data[:, 1] <= case[1]/2+.2)
        rstd, rlvt = .01/np.abs(data[:, 2]), .01/np.abs(data[:, 3])
        dc.append({"corner": case[0], "vdd_v": case[1], "temperature_c": case[2],
            "input_range_v": [case[1]/2-.2, case[1]/2+.2],
            "max_standard_ron_ohm": float(max(rstd[selected])),
            "max_candidate_ron_ohm": float(max(rlvt[selected])),
            "data": name + ".tsv"})
    if args.suite == "full":
        cases = list(itertools.product(("tt", "ff", "ss", "fs", "sf"),
            (1.62, 1.8, 1.98), (-20, 27, 85), (-.2, 0, .2), (350,)))
        cases += list(itertools.product(("tt",), (1.8,), (27,), (-.2, 0, .2), (0, 1000)))
    else:
        cases = [(corner, vdd, temp, delta, 350)
                 for corner, vdd, temp in (("tt", 1.8, 27), ("ss", 1.62, -20), ("ff", 1.98, 85))
                 for delta in (-.2, 0, .2)]
    models = ("adc_tgate", args.model) if args.baseline else (args.model,)

    def one(item):
        index, case, model = item
        name = f"sample_{index:03d}_{model}"
        wn, wp = (8, 16) if model == "adc_tgate" else (args.wn, args.wp)
        data = simulate_deck(name, transient(folder, name, case, model, wn, wp))
        pre, held, before_step, after_step, end = [float(np.interp(t, data[:, 0], data[:, 3]))
            for t in (2.49e-6, 2.6e-6, 2.699e-6, 2.8e-6, 10e-6)]
        target = case[1]/2+case[3]
        return {"index": index, "name": name, "model": model, "wn_um": wn, "wp_um": wp,
            "corner": case[0], "vdd_v": case[1], "temperature_c": case[2],
            "input_v": target, "source_ohm": case[4],
            "acquisition_error_v": pre-target, "hold_error_100ns_v": held-target,
            "end_hold_error_7p5us_v": end-target,
            "switch_open_step_v": held-pre, "off_input_feedthrough_v": after_step-before_step,
            "late_hold_droop_7p2us_v": end-after_step,
            "hold_drift_including_input_feedthrough_v": end-held,
            "acquisition_pass_quarter_lsb": abs(pre-target) <= LSB/4,
            "end_hold_pass_quarter_lsb": abs(end-target) <= LSB/4}
    work = [(i, case, model) for i, case in enumerate(cases) for model in models]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(one, work))
    candidate_rows = [row for row in rows if row["model"] == args.model]
    failures = [row for row in candidate_rows if not (row["acquisition_pass_quarter_lsb"] and row["end_hold_pass_quarter_lsb"])]
    report = {"status": "passed_tested_cases" if not failures else "failed_specification",
        "suite": args.suite, "run_tag": args.tag, "candidate_only": True,
        "schematic_only": True, "cadence_used": False, "whole_adc_validated": False,
        "sample_runs": len(rows), "candidate_failure_count": len(failures),
        "candidate_model": args.model,
        "candidate_wn_um": args.wn, "candidate_wp_um": args.wp,
        "lsb_v": LSB, "quarter_lsb_v": LSB/4, "measured_load_capacitance_f": capacitance,
        "hold_test": "2.5us acquisition + 7.5us hold; source changes to opposite excursion at 2.7us",
        "dc_conductance": dc, "results": rows,
        "limitations": ["No bootstrap; both clocks stay between 0 and VDD.",
            "Finite source resistance, but ideal zero-impedance clock and supply drivers.",
            "Per-leg sampled-voltage checks; not full differential switched-CDAC or noise qualification.",
            "Model corner/temperature sweep is not mismatch Monte Carlo or physical signoff."],
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (Path(__file__), candidate, ref)},
        "artifact_sha256": {p.name: digest(p) for p in sorted(folder.iterdir()) if p.is_file()}}
    (folder / "validation.json").write_text(json.dumps(report, indent=2)+"\n")
    shutil.copy2(folder / "validation.json", HERE / "results" / f"{args.tag}.json")
    print(json.dumps({k: v for k, v in report.items() if k not in ("results", "artifact_sha256")}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
