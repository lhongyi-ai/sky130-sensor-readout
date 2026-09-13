#!/usr/bin/env python3
"""Generate synthesis and independent functional gate-test evidence.

Run inside the pinned project EDA image from the project root. PDK sources stay
outside this repository; their hashes, not their contents, enter the manifest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "v2/digital/results"
PDK = Path(os.environ.get("PDK_ROOT", "/foss/pdks")) / "sky130A"
LIB = PDK / "libs.ref/sky130_fd_sc_hd"


def run(name: str, command: list[str], env: dict | None = None) -> str:
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=600)
    (OUT / f"{name}.log").write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(f"{name}: exit {result.returncode}; see retained log")
    return result.stdout


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ["PDK_ROOT"] = str(PDK.parent)
    report = {"evidence_level": "mapped_standard_cell_functional_simulation",
              "analog_adc_validated": False, "post_layout_validated": False,
              "status": "running", "sta_scope": "library_cells_without_wire_parasitics"}
    try:
        report["yosys_version"] = run("yosys_version", ["yosys", "-V"]).strip()
        report["opensta_version"] = run("opensta_version", ["sta", "-version"]).strip()
        run("synthesis", ["yosys", "-c", "v2/digital/synthesize.tcl"])
        netlist = OUT / "sar_controller_mapped.v"
        run("gate_compile", ["iverilog", "-g2012", "-DFUNCTIONAL", "-s",
            "tb_sar_controller", "-o", str(OUT / "gate_test.vvp"),
            str(LIB / "verilog/primitives.v"), str(LIB / "verilog/sky130_fd_sc_hd.v"),
            str(netlist), "v2/tests/rtl/tb_sar_controller.sv"])
        result = run("gate_test", ["vvp", str(OUT / "gate_test.vvp")])
        marker = next((line for line in result.splitlines()
                       if line.startswith("PASS sar_controller:")), None)
        if marker is None or "FAIL" in result:
            raise RuntimeError("Gate simulation did not emit an unambiguous PASS")
        report["gate_test"] = {"status": "passed", "timing": "zero_delay_functional",
            "counters": {k: int(v) for k, v in re.findall(r"(\w+)=(\d+)", marker)}}
        report["sta_libraries"] = []
        timing_met = True
        for corner in ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95"):
            filename = f"sky130_fd_sc_hd__{corner}.lib"
            env = dict(os.environ, SAR_LIBERTY=filename)
            timing = run(f"sta_{corner}", ["sta", "-exit", "v2/digital/sta.tcl"], env)
            if re.search(r"(^|\n)Error:", timing):
                raise RuntimeError(f"STA reports an error at {corner}")
            slack = {kind: float(value) for kind, value in re.findall(
                r"worst slack (max|min)\s+([-+0-9.eE]+)", timing)}
            if set(slack) != {"max", "min"}:
                raise RuntimeError(f"Incomplete STA slack evidence at {corner}")
            timing_met = timing_met and all(value >= 0 for value in slack.values())
            report["sta_libraries"].append({"file": filename, "sha256": sha(LIB / "lib" / filename),
                "note": "library characterization corner; NOT the 45-point analog PVT matrix",
                "worst_slack_ns": slack,
                "setup_and_hold_met": all(value >= 0 for value in slack.values())})
        mapped = json.loads((OUT / "sar_controller_mapped.json").read_text())
        cells = mapped["modules"]["sar_controller"]["cells"]
        types = {}
        for cell in cells.values():
            name = cell["type"]
            if not name.startswith("sky130_fd_sc_hd__"):
                raise RuntimeError(f"Unmapped cell: {name}")
            types[name] = types.get(name, 0) + 1
        report["mapped_cells"] = len(cells)
        report["cell_type_counts"] = types
        report["pre_layout_timing_status"] = "passed" if timing_met else "failed"
        report["status"] = "passed" if timing_met else "functional_passed_timing_failed"
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        report["status"] = "failed"
        report["reason"] = str(exc)
    inputs = [ROOT / "v2/rtl/sar_controller.v", ROOT / "v2/tests/rtl/tb_sar_controller.sv",
              Path(__file__), ROOT / "v2/digital/synthesize.tcl",
              ROOT / "v2/digital/sta.tcl", ROOT / "v2/digital/constraints.sdc"]
    report["source_sha256"] = {str(p.relative_to(ROOT)): sha(p) for p in inputs}
    report["artifact_sha256"] = {str(p.relative_to(ROOT)): sha(p) for p in sorted(OUT.iterdir())
        if p.is_file() and p.name not in ("validation.json", "gate_test.vvp")}
    (OUT / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
