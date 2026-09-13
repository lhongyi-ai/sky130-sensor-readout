#!/usr/bin/env python3
"""Validate final routed connectivity against original TB and estimate activity power."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "v2/physical/digital"
OUT = HERE / "results"


def run(name: str, args: list[str], env: dict | None = None) -> str:
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    text = result.stdout + result.stderr
    (OUT / f"{name}.log").write_text(text)
    if result.returncode:
        raise RuntimeError(f"{name} failed ({result.returncode})")
    return text


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "final"
    folder = HERE / "runs" / tag
    if folder.parent != HERE / "runs" or not folder.is_dir():
        raise ValueError("Expected an existing direct child run tag")
    OUT.mkdir(exist_ok=True)
    library = Path(os.environ.get("PDK_ROOT", "/foss/pdks")) / "sky130A/libs.ref/sky130_fd_sc_hd"
    netlist = folder / "final/nl/sar_controller.nl.v"
    report = {"status": "running", "run_tag": tag, "timing_simulation": False,
              "evidence_level": "routed_netlist_zero_delay_functional_verification"}
    try:
        run("routed_gate_compile", ["iverilog", "-g2012", "-DFUNCTIONAL", "-s",
            "tb_sar_controller", "-s", "activity_trace", "-o", str(OUT / "routed_test.vvp"),
            str(library / "verilog/primitives.v"), str(library / "verilog/sky130_fd_sc_hd.v"),
            str(netlist), "v2/tests/rtl/tb_sar_controller.sv",
            "v2/physical/digital/activity_trace.sv"])
        result = run("routed_gate_test", ["vvp", str(OUT / "routed_test.vvp")])
        marker = next((line for line in result.splitlines() if line.startswith("PASS sar_controller:")), None)
        if not marker or "FAIL" in result:
            raise RuntimeError("Routed functional test failed or omitted PASS")
        report["counters"] = {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", marker)}
        env = dict(os.environ, SAR_PHYSICAL_RUN_DIR=str(folder), PDK_ROOT=str(library.parents[2]))
        power = run("activity_power", ["sta", "-exit", "v2/physical/digital/power.tcl"], env)
        if re.search(r"(^|\n)Error:", power):
            raise RuntimeError("Activity power estimation reported an error")
        annotation = re.search(r"Annotated (\d+) pin activities", power)
        unannotated = re.search(r"unannotated\s+(\d+)", power)
        if not annotation or int(annotation.group(1)) <= 0 or not unannotated or int(unannotated.group(1)) != 0:
            raise RuntimeError("Power activity annotation is missing or incomplete")
        report["annotated_pin_activities"] = int(annotation.group(1))
        report["unannotated_pin_activities"] = int(unannotated.group(1))
        total = re.search(r"^Total\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)", power, re.MULTILINE)
        if not total:
            raise RuntimeError("Power total is missing")
        report["estimated_workload_power_W"] = dict(zip(
            ("internal", "switching", "leakage", "total"), map(float, total.groups())))
        report["power_report_scope"] = "TT25C1.8V Liberty + nominal SPEF + zero-delay exhaustive-test VCD; not full-chip power"
        report["status"] = "passed"
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        report.update(status="failed", reason=str(exc))
    report["netlist_sha256"] = hashlib.sha256(netlist.read_bytes()).hexdigest()
    report["vcd_sha256"] = hashlib.sha256((OUT / "routed_activity.vcd").read_bytes()).hexdigest() if (OUT / "routed_activity.vcd").exists() else None
    report["testbench_sha256"] = hashlib.sha256((ROOT / "v2/tests/rtl/tb_sar_controller.sv").read_bytes()).hexdigest()
    (OUT / "routed_gate_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
