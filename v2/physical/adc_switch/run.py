#!/usr/bin/env python3
"""Build, DRC/LVS, RC-extract and simulate one real SKY130 sampling switch.

The stimulus and load deliberately match the ADC block owner's sampler bench.
No result here qualifies the comparator, complete ADC, PGA or entire chip.
"""
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
import subprocess

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PDK = Path("/foss/pdks/sky130A")
LSB = 0.8 / 4096


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(name, args, folder, env=None, timeout=180):
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    text = result.stdout + result.stderr
    (folder / f"{name}.log").write_text(text)
    if result.returncode or re.search(r"(?im)^\s*(fatal error|error:|timestep too small|doanalyses:)", text):
        raise RuntimeError(f"{name} failed; retained output in {folder}")
    return text


def block(source, name):
    match = re.search(rf"(?ims)^\.subckt {name}\b.*?^\.ends[^\n]*", source)
    if not match:
        raise RuntimeError(f"Missing frozen block {name}")
    return match.group(0)


def deck(folder, name, case, extracted):
    corner, vdd, temp, delta, source_r = case
    cm = vdd / 2
    vin = cm + delta
    output = folder / f"{name}.tsv"
    dut = "adc_tgate_flat" if extracted else "adc_tgate"
    return f"""* Matched schematic versus extracted-RC sampling switch: {name}
.lib {PDK}/libs.tech/combined/sky130.lib.spice {corner}
.include {folder}/reference.spice
.include {folder}/adc_tgate_flat.rc.spice
.temp {temp}
.options reltol=1e-5 abstol=1e-14 vntol=1e-8 method=gear klu
VDD vdd 0 {vdd}
VIN src 0 PWL(0 {cm} 20n {cm} 21n {vin:.12g})
RS src inp {max(source_r, .001)}
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
tran 2n 3u uic
wrdata {output} v(src) v(inp) v(hold) i(vdd)
quit
.endc
.end
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="final")
    parser.add_argument("--suite", choices=("smoke", "full"), default="full")
    args = parser.parse_args()
    folder = HERE / "runs" / args.tag
    if folder.parent != HERE / "runs" or folder.exists():
        raise RuntimeError("Use a new simple run tag; previous evidence is never overwritten")
    folder.mkdir(parents=True)
    source_path = ROOT / "v2/analog/adc/adc_blocks.spice"
    source = source_path.read_text()
    tg = block(source, "adc_tgate")
    if not re.search(r"WN=8\s+WP=16\s+LSW=0\.15", tg):
        raise RuntimeError("TG dimensions changed; layout must be reviewed before regeneration")
    reference = tg + "\n\n" + block(source, "adc_mim_bank") + "\n"
    (folder / "reference.spice").write_text(reference)
    env = dict(os.environ, TG_RUN_DIR=str(folder), PDK_ROOT=str(PDK.parent),
               SPICE_USERINIT_DIR=str(PDK / "libs.tech/ngspice"))
    magic = ["magic", "-dnull", "-noconsole", "-rcfile", str(PDK / "libs.tech/magic/sky130A.magicrc")]
    geometry = command("layout", magic + [str(HERE / "generate_layout.tcl")], folder, env)
    if "TG_DRC_COUNT 0" not in geometry or "TG_DRC_DETAILS \n" not in geometry:
        raise RuntimeError("Physical DRC did not pass")
    command("rc_extraction", magic + [str(HERE / "extract_rc.tcl")], folder, env)
    lvs = command("lvs", ["netgen", "-batch", "lvs",
        f"{folder}/adc_tgate_layout.lvs.spice adc_tgate_layout",
        f"{folder}/reference.spice adc_tgate", str(PDK / "libs.tech/netgen/sky130A_setup.tcl"),
        str(folder / "lvs.rpt"), "-json"], folder, env)
    if "Circuits match uniquely." not in (folder / "lvs.rpt").read_text():
        raise RuntimeError("LVS is not a unique match")
    rc = (folder / "adc_tgate_flat.rc.spice").read_text()
    resistors = re.findall(r"(?m)^R\S+\s+\S+\s+\S+\s+([0-9.eE+-]+)$", rc)
    caps = re.findall(r"(?m)^C\S+\s+\S+\s+\S+\s+([0-9.eE+-]+)f$", rc)
    if not resistors or not caps or any(float(x) <= 0 for x in resistors + caps):
        raise RuntimeError("Expected a positive physical R/C network, not placeholder extraction")
    if args.suite == "full":
        cases = list(itertools.product(("tt", "ff", "ss", "fs", "sf"),
            (1.62, 1.8, 1.98), (-20, 27, 85), (-.2, 0, .2), (350,)))
        cases += list(itertools.product(("tt",), (1.8,), (27,), (-.2, 0, .2), (0, 1000)))
    else:
        cases = list(itertools.product(("tt",), (1.8,), (27,), (-.2, 0, .2), (350,)))
    def simulate(item):
        index, case, extracted = item
        name = f"sample_{index:03d}_{'rc' if extracted else 'schematic'}"
        path = folder / f"{name}.spice"
        path.write_text(deck(folder, name, case, extracted))
        command(name, ["ngspice", "-b", str(path)], folder, env)
        values = np.loadtxt(folder / f"{name}.tsv", skiprows=1)
        pre, held, end = [float(np.interp(t, values[:, 0], values[:, 3])) for t in (2.49e-6, 2.6e-6, 3e-6)]
        target = case[1] / 2 + case[3]
        return {"index": index, "name": name, "view": "layout_rc" if extracted else "schematic",
                "corner": case[0], "vdd_v": case[1], "temperature_c": case[2],
                "input_v": target, "source_ohm": case[4],
                "acquisition_error_v": pre - target, "hold_error_v": held - target,
                "switch_open_step_v": held - pre, "hold_droop_400ns_v": end - held,
                "acquisition_pass_quarter_lsb": abs(pre - target) <= LSB / 4,
                "hold_pass_quarter_lsb": abs(held - target) <= LSB / 4}
    work = [(i, case, extracted) for i, case in enumerate(cases) for extracted in (False, True)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(simulate, work))
    passed = all(row["acquisition_pass_quarter_lsb"] and row["hold_pass_quarter_lsb"] for row in rows)
    deltas = [{"index": i,
        "acquisition_rc_minus_schematic_v": rows[2*i+1]["acquisition_error_v"] - rows[2*i]["acquisition_error_v"],
        "hold_rc_minus_schematic_v": rows[2*i+1]["hold_error_v"] - rows[2*i]["hold_error_v"]}
        for i in range(len(cases))]
    report = {"status": "passed" if passed else "failed_specification", "suite": args.suite,
        "evidence_level": "standalone_sampling_tg_drc_lvs_flattened_rc_transient",
        "cadence_used": False, "whole_adc_validated": False, "run_tag": args.tag,
        "magic_drc_count": 0, "netgen_lvs": "unique_match",
        "extracted_resistors": len(resistors), "extracted_capacitors": len(caps),
        "extraction_corner": "Magic nominal RC; process/voltage/temperature sweeps apply to transistor models, not RC corners",
        "lsb_v": LSB, "quarter_lsb_v": LSB / 4,
        "load": "SKY130 MIM bank: 4096 units W=L=3um; nominal qualified ADC load ~81.28512pF",
        "case_pairs": len(cases), "transient_runs": len(rows), "results": rows,
        "view_differences": deltas,
        "limitations": ["No switched-capacitor full-ADC integration, layout mismatch, clock skew or noise qualification.",
            "Common-mode follows VDD/2, tested at per-leg offsets -0.2,0,+0.2V only.",
            "Quarter-LSB test is per leg; differential ADC error requires joint two-leg validation.",
            "Open-source Magic DRC and Netgen LVS are not foundry production signoff."],
        "frozen_tgate_sha256": hashlib.sha256(tg.encode()).hexdigest(),
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (Path(__file__), HERE / "generate_layout.tcl", HERE / "extract_rc.tcl")},
        "artifact_sha256": {str(p.relative_to(folder)): digest(p) for p in sorted(folder.iterdir()) if p.is_file()}}
    (folder / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    destination = HERE / "results"
    destination.mkdir(exist_ok=True)
    shutil.copy2(folder / "validation.json", destination / "switch_validation.json")
    for name in ("adc_tgate_layout.gds", "adc_tgate_layout.mag", "tg_nfet8.mag", "tg_pfet16.mag",
                 "adc_tgate_flat.mag", "adc_tgate_layout.lvs.spice", "adc_tgate_flat.cap.spice",
                 "adc_tgate_flat.rc.spice", "reference.spice", "lvs.rpt", "lvs.json", "layout.log", "rc_extraction.log"):
        candidate = folder / name
        if candidate.exists():
            target = HERE / "artifacts" / name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(candidate, target)
    print(json.dumps({k: v for k, v in report.items() if k not in ("artifact_sha256", "results", "view_differences")}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
