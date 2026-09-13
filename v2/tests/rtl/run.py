#!/usr/bin/env python3
"""Run isolated digital SAR verification; emit machine-readable evidence to stdout."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    design = root / "v2/rtl/sar_controller.v"
    testbench = root / "v2/tests/rtl/tb_sar_controller.sv"
    report = {
        "status": "not_run",
        "evidence_level": "digital_rtl_with_ideal_held_code_comparator",
        "analog_adc_validated": False,
        "physical_timing_validated": False,
        "stages": [],
    }
    compiler = shutil.which("iverilog")
    runtime = shutil.which("vvp")
    if not compiler or not runtime:
        report.update(status="blocked", reason="iverilog and vvp must both be installed")
        print(json.dumps(report, indent=2))
        return 2
    version = subprocess.run([compiler, "-V"], capture_output=True, text=True)
    report["simulator"] = version.stdout.splitlines()[0] if version.stdout else compiler

    with tempfile.TemporaryDirectory(prefix="sky130-sar-rtl-") as temporary:
        temp = Path(temporary)
        commands = [
            ("verilog_2005_design_compile", [compiler, "-g2005", "-Wall", "-s",
              "sar_controller", "-o", str(temp / "design.vvp"), str(design)]),
            ("testbench_compile", [compiler, "-g2012", "-Wall", "-s",
              "tb_sar_controller", "-o", str(temp / "test.vvp"),
              str(design), str(testbench)]),
            ("self_checking_simulation", [runtime, str(temp / "test.vvp")]),
        ]
        output = ""
        for name, command in commands:
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                report.update(status="failed", reason=f"{name} timed out after 60 seconds")
                print(json.dumps(report, indent=2))
                return 1
            output = result.stdout + result.stderr
            report["stages"].append({
                "name": name, "returncode": result.returncode, "output": output.strip(),
            })
            if result.returncode != 0:
                report.update(status="failed", reason=f"{name} returned a nonzero status")
                print(json.dumps(report, indent=2))
                return 1
        pass_line = next((line for line in output.splitlines()
                          if line.startswith("PASS sar_controller:")), None)
        if pass_line is None or "FAIL" in output:
            report.update(status="failed", reason="missing PASS marker or present FAIL marker")
            print(json.dumps(report, indent=2))
            return 1
        report.update(status="passed", counters={
            key: int(value) for key, value in re.findall(r"(\w+)=(\d+)", pass_line)
        })
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
