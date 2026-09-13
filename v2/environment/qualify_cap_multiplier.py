#!/usr/bin/env python3
"""Test nominal and local-mismatch scaling of parallel MIM banks.

200 independent capacitor instances per construction, same TT mismatch run.
This is a PDK parameter-semantics test, not ADC INL/Monte Carlo qualification.
"""
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
PDK = Path(os.environ.get("SKY130_PDK", "/foss/pdks/sky130A"))


def main():
    out = HERE / "results" / ("cap_multiplier_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True)
    latest = HERE / "results/cap_multiplier_qualification.json"
    latest.write_text(json.dumps({"status": "RUNNING", "run": str(out.relative_to(HERE))}))
    groups = {"unit": "", "m64_only": "m=64", "m64_mult64": "m=64 mult=64"}
    lines = ["Cap bank local mismatch multiplier semantics", f".lib {PDK}/libs.tech/combined/sky130.lib.spice tt_mm", ".temp 27"]
    for group, params in groups.items():
        for i in range(200):
            key = f"{group}_{i}"
            lines += [f"V{key} {key} 0 AC 1", f"X{key} {key} 0 sky130_fd_pr__cap_mim_m3_1 W=3 L=3 {params}"]
    lines += [".control", "set num_threads=1", "set numdgt=15", "setseed 1302026", "reset", "ac lin 1 1000 1000"]
    for group in groups:
        for i in range(200):
            key = f"{group}_{i}"
            lines += [f"let c_{key}=-imag(v{key}#branch)/(2*pi*1000)", f"print c_{key}"]
    lines += ["quit", ".endc", ".end", ""]
    source = out / "cap_multiplier.spice"
    source.write_text("\n".join(lines))
    env = dict(os.environ, SPICE_USERINIT_DIR=str(PDK / "libs.tech/ngspice"))
    proc = subprocess.run(["ngspice", "-b", str(source)], cwd=out, env=env, capture_output=True, text=True, timeout=180)
    log = proc.stdout + proc.stderr
    (out / "simulation.log").write_text(log)
    groups_result = {}
    nominal = 19.845e-15
    for group in groups:
        numbers = []
        for i in range(200):
            match = re.search(rf"^c_{group}_{i}\s*=\s*([-+\deE.]+)", log, re.MULTILINE)
            if match:
                numbers.append(float(match[1]))
        mean = statistics.mean(numbers) if numbers else None
        sigma = statistics.stdev(numbers) if len(numbers) > 1 else None
        groups_result[group] = {"sample_count": len(numbers), "mean_cap_f": mean, "sample_sigma_f": sigma,
            "relative_sigma": sigma/mean if mean else None, "nominal_unit_multiplier": mean/nominal if mean else None,
            "samples_f": numbers}
    checks = {"all_600_instances_measured": proc.returncode == 0 and all(x["sample_count"] == 200 for x in groups_result.values())}
    if checks["all_600_instances_measured"]:
        for group, expected in (("unit", 1), ("m64_only", 64), ("m64_mult64", 64)):
            checks[group + "_nominal_correct"] = math.isclose(groups_result[group]["nominal_unit_multiplier"], expected, rel_tol=0.01)
        ratio_m = groups_result["unit"]["relative_sigma"] / groups_result["m64_only"]["relative_sigma"]
        ratio_both = groups_result["unit"]["relative_sigma"] / groups_result["m64_mult64"]["relative_sigma"]
        # This expected failure is an intentionally tested negative control.
        checks["m_only_detected_as_incorrect_independent_unit_matching"] = 0.6 < ratio_m < 1.5
        checks["m_and_mult_independent_unit_sigma_scaling"] = 5 < ratio_both < 11
    else:
        ratio_m = ratio_both = None
    report = {"status": "CAP_MULTIPLIER_SEMANTICS_PASS" if all(checks.values()) else "FAIL",
        "evidence_level": "PDK_MISMATCH_PARAMETER_QUALIFICATION", "chip_qualified": False,
        "run": str(out.relative_to(HERE)), "checks": checks, "groups": groups_result,
        "sigma_ratio_unit_to_m64_only": ratio_m, "sigma_ratio_unit_to_m64_mult64": ratio_both,
        "qualified_aggregation": "Use both m=N (nominal parallel C) and mult=N (local model mismatch sigma). No nominal double multiplication observed." if all(checks.values()) else None,
        "limitations": ["Only independent local Gaussian mismatch represented by this PDK, not spatial gradients or routing parasitics.",
                         "200 capacitor devices per construction, not 200 complete ADC or chip instances.",
                         "Aggregation is appropriate only for identical units with independent local mismatch; physical unit array still requires layout."]}
    latest.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "checks": checks,
        "sigma_ratio_m_only": ratio_m, "sigma_ratio_m_and_mult": ratio_both}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
