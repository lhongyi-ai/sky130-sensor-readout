#!/usr/bin/env python3
"""Run inside the pinned open-tools container; never copies PDK content.

Qualifies the *open-source* device simulator and statistical activation, not
Cadence, a circuit block, or foundry signoff. Every attempted run keeps its deck
and log. Seeds are applied before reset so random PDK parameters are rebuilt.
"""
from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / ("devices_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
PDK = Path(os.environ.get("SKY130_PDK", "/foss/pdks/sky130A"))
DECK = PDK / "libs.tech/combined/sky130.lib.spice"


def run_case(name, corner="tt", vdd=1.8, temperature=27, seed=1302026):
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    source = f"""SKY130 device/statistical qualification, not circuit performance
.lib {DECK} {corner}
.temp {temperature}
.options reltol=1e-7 abstol=1e-15
VDD vdd 0 {vdd}
VGN gn 0 {vdd/2}
VGP gp 0 {vdd/2}
VNA dn_a 0 {vdd/2}
VNB dn_b 0 {vdd/2}
VPA dp_a 0 {vdd/2}
VPB dp_b 0 {vdd/2}
XNA dn_a gn 0 0 sky130_fd_pr__nfet_01v8 L=1 W=2 nf=1 mult=1
XNB dn_b gn 0 0 sky130_fd_pr__nfet_01v8 L=1 W=2 nf=1 mult=1
XPA dp_a gp vdd vdd sky130_fd_pr__pfet_01v8 L=1 W=4 nf=1 mult=1
XPB dp_b gp vdd vdd sky130_fd_pr__pfet_01v8 L=1 W=4 nf=1 mult=1
VCA ca 0 DC 0 AC 1
VCB cb 0 DC 0 AC 1
VCM cm 0 DC 0 AC 1
XCA ca 0 sky130_fd_pr__cap_mim_m3_1 W=3 L=3
XCB cb 0 sky130_fd_pr__cap_mim_m3_1 W=3 L=3
XCM cm 0 sky130_fd_pr__cap_mim_m3_1 W=3 L=3 m=64
.control
set num_threads=1
set numdgt=15
setseed {seed}
reset
op
let id_na=-vna#branch
let id_nb=-vnb#branch
let id_pa=vpa#branch
let id_pb=vpb#branch
print id_na id_nb id_pa id_pb
ac lin 1 1000 1000
let cap_a=-imag(vca#branch)/(2*pi*1000)
let cap_b=-imag(vcb#branch)/(2*pi*1000)
let cap_64=-imag(vcm#branch)/(2*pi*1000)
print cap_a cap_b cap_64
quit
.endc
.end
"""
    deck = folder / "device.spice"
    deck.write_text(source)
    env = dict(os.environ, SPICE_USERINIT_DIR=str(PDK / "libs.tech/ngspice"))
    proc = subprocess.run(["ngspice", "-b", str(deck)], env=env, cwd=folder,
                          capture_output=True, text=True, timeout=45)
    log = proc.stdout + proc.stderr
    (folder / "simulation.log").write_text(log)
    values = {}
    for key in ("id_na", "id_nb", "id_pa", "id_pb", "cap_a", "cap_b", "cap_64"):
        match = re.search(rf"^{key}\s*=\s*([-+\deE.]+)", log, re.MULTILINE)
        values[key] = float(match[1]) if match else None
    good = proc.returncode == 0 and all(x is not None and math.isfinite(x) and x > 0 for x in values.values())
    return {"name": name, "corner": corner, "vdd_v": vdd, "temperature_c": temperature,
            "seed": seed, "returncode": proc.returncode, "status": "PASS" if good else "FAIL", **values}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report_path = OUT / "qualification.json"
    (OUT / "qualify.py.snapshot").write_bytes(Path(__file__).read_bytes())
    report_path.write_text(json.dumps({"status": "RUNNING", "cadence_qualified": False}))
    files = [DECK, PDK / "libs.tech/combined/README", PDK / "libs.tech/combined/continuous/models_fet.spice",
             PDK / "libs.tech/combined/continuous/models_capacitors.spice",
             PDK / "libs.tech/combined/continuous/models_global.spice",
             PDK / "libs.tech/combined/continuous/parameters_cap_nom.spice",
             PDK / "libs.tech/magic/sky130A.tech", PDK / "libs.tech/netgen/sky130A_setup.tcl"]
    manifest = {str(p.relative_to(PDK)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    jobs = [(f"pvt/{c}_{v:.2f}_{t}", c, v, t, 1302026)
            for c in ("tt", "ff", "ss", "fs", "sf") for v in (1.62, 1.8, 1.98) for t in (-20, 27, 85)]
    jobs += [(f"mismatch/sample_{i:03d}", "tt_mm", 1.8, 27, 1302026 + i) for i in range(200)]
    jobs += [("controls/replay", "tt_mm", 1.8, 27, 1302026),
             ("controls/off_different_seed", "tt", 1.8, 27, 99999)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda args: run_case(*args), jobs))
    pvt, mm, replay, off = rows[:45], rows[45:245], rows[-2], rows[-1]
    keys = ("id_na", "id_nb", "id_pa", "id_pb", "cap_a", "cap_b", "cap_64")
    all_valid = all(r["status"] == "PASS" for r in rows)
    checks = {"all_247_simulations_valid": all_valid}
    summary = {}
    if all_valid:
        nominal = next(r for r in pvt if r["corner"] == "tt" and r["vdd_v"] == 1.8 and r["temperature_c"] == 27)
        checks.update({
            "nominal_identical_devices_equal": all(nominal[a] == nominal[b] for a, b in
                (("id_na", "id_nb"), ("id_pa", "id_pb"), ("cap_a", "cap_b"))),
            "mismatch_off_seed_invariant": all(nominal[k] == off[k] for k in keys),
            "mismatch_on_seed_reproducible": all(mm[0][k] == replay[k] for k in keys),
            "mismatch_on_varies_between_samples": all(len({r[k] for r in mm}) > 190 for k in keys),
            "mim_nominal_3um_value": math.isclose(nominal["cap_a"], 19.845e-15, rel_tol=1e-6),
            "mim_m64_scales_nominal_capacitance": math.isclose(nominal["cap_64"] / nominal["cap_a"], 64, rel_tol=1e-6),
        })
        for name, field in (("nfet_current", "id_na"), ("pfet_current", "id_pa"), ("mim_unit_cap", "cap_a"), ("mim_m64_cap", "cap_64")):
            numbers = [r[field] for r in mm]
            mean = statistics.mean(numbers)
            summary[name] = {"mean": mean, "sample_stdev": statistics.stdev(numbers),
                             "relative_stdev": statistics.stdev(numbers) / mean,
                             "min": min(numbers), "max": max(numbers)}
        ratio = summary["mim_unit_cap"]["relative_stdev"] / summary["mim_m64_cap"]["relative_stdev"]
        summary["mim_unit_to_m64_relative_sigma_ratio"] = ratio
        # A/B qualification established that m-only is intentionally a NEGATIVE
        # control. It scales C but NOT independent-unit mismatch. Correct m=N,
        # mult=N is verified separately in qualify_cap_multiplier.py. Keep the
        # original failed discovery run; do not reinterpret it as a valid bank.
        checks["negative_control_m_only_rejected_for_independent_unit_matching"] = 0.6 < ratio < 1.5
    report = {"status": "OPEN_DEVICE_ENVIRONMENT_PASS" if all(checks.values()) else "FAIL",
              "evidence_level": "PDK_DEVICE_AND_STATISTICAL_ACTIVATION_TEST",
              "cadence_qualified": False, "chip_qualified": False,
              "pdk_resolved_path": str(PDK.resolve()), "pdk_file_sha256": manifest,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "run": str(OUT.relative_to(HERE)),
              "checks": checks, "mismatch_sample_count": 200, "statistics": summary,
              "limitations": ["200 samples are isolated devices, not 200 sensor-core samples.",
                              "Activation and seed reproducibility do not establish silicon accuracy or production yield.",
                              "Only tt_mm mismatch is qualified; process mc is not qualified.",
                              "No Cadence or complete design physical qualification is implied."],
              "runs": rows}
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (HERE / "results/device_qualification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "checks": checks, "statistics": summary}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
