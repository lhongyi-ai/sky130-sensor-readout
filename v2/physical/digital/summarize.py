#!/usr/bin/env python3
"""Audit explicit physical checks and retain portable implementation evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "v2/physical/digital"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def only(folder: Path, pattern: str) -> Path:
    matches = list(folder.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {pattern}, got {len(matches)}")
    return matches[0]


def main() -> int:
    tag = sys.argv[1] if len(sys.argv) > 1 else "final"
    run = HERE / "runs" / tag
    if run.parent != HERE / "runs" or not run.is_dir():
        raise ValueError("Expected an existing direct child run tag")
    state_file = only(run, "*-misc-reportmanufacturability/state_out.json")
    state = json.loads(state_file.read_text())
    metrics = state["metrics"]
    required_zero = [
        "design__instance_unmapped__count", "synthesis__check_error__count",
        "route__drc_errors", "antenna__violating__nets", "antenna__violating__pins",
        "design__disconnected_pin__count", "design__critical_disconnected_pin__count",
        "design__xor_difference__count", "magic__drc_error__count",
        "klayout__drc_error__count", "magic__illegal_overlap__count",
        "design__lvs_error__count", "design__lvs_unmatched_pin__count",
        "design__max_slew_violation__count", "design__max_cap_violation__count",
        "timing__unannotated_net_filtered__count",
    ]
    checks = {key: {"value": metrics.get(key), "passed": metrics.get(key) == 0}
              for key in required_zero}
    corners = [f"{rc}_{lib}" for rc in ("min", "nom", "max")
               for lib in ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95")]
    timing = []
    for corner in corners:
        setup = metrics.get(f"timing__setup__ws__corner:{corner}")
        hold = metrics.get(f"timing__hold__ws__corner:{corner}")
        passed = setup is not None and hold is not None and setup >= 0 and hold >= 0
        timing.append({"corner": corner, "setup_slack_ns": setup,
                       "hold_slack_ns": hold, "passed": passed})
    lvs_file = only(run, "*-netgen-lvs/reports/lvs.netgen.rpt")
    checks["lvs_unique_match"] = {"passed": "Final result: Circuits match uniquely." in lvs_file.read_text()}
    gate_file = HERE / "results/routed_gate_validation.json"
    gate = json.loads(gate_file.read_text())
    checks["routed_exhaustive_functional_test"] = {
        "passed": gate.get("status") == "passed" and gate.get("run_tag") == tag,
        "run_tag": gate.get("run_tag"), "counters": gate.get("counters")}
    required_views = ("gds", "lef", "def", "nl", "pnl", "spef", "lib", "sdf", "spice", "render", "odb")
    artifact_root = HERE / "artifacts"
    for view in required_views:
        source_dir = run / "final" / view
        if not source_dir.is_dir() or not any(source_dir.rglob("*")):
            raise RuntimeError(f"Missing required physical view {view}")
        for source in source_dir.rglob("*"):
            if source.is_file():
                target = artifact_root / source.relative_to(run / "final")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    evidence = HERE / "evidence"
    evidence.mkdir(exist_ok=True)
    selected = [state_file, run / "resolved.json", lvs_file,
                only(run, "*-misc-reportmanufacturability/manufacturability.rpt"),
                only(run, "*-magic-drc/reports/drc.magic.rpt"),
                only(run, "*-klayout-drc/reports/drc.klayout.json"),
                only(run, "*-openroad-stapostpnr/summary.rpt")]
    sta_folder = only(run, "*-openroad-stapostpnr")
    for corner in corners:
        selected.extend((sta_folder / corner / name) for name in ("checks.rpt", "power.rpt", "ws.max.rpt", "ws.min.rpt"))
    for source in selected:
        target = evidence / source.relative_to(run)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    # A source snapshot makes final physical evidence independent of future edits.
    for source in (HERE / "config.json", ROOT / "v2/digital/constraints.sdc", ROOT / "v2/rtl/sar_controller.v"):
        shutil.copy2(source, evidence / source.name)
    passed = all(item["passed"] for item in checks.values()) and all(item["passed"] for item in timing)
    report = {
        "status": "passed" if passed else "failed", "run_tag": tag,
        "evidence_level": "standalone_digital_macro_routed_drc_lvs_rc_extraction_sta",
        "analog_frontend_validated": False, "full_chip_validated": False,
        "cadence_used": False, "silicon_measured": False,
        "clock_period_ns": 625, "output_load_pf": 0.05,
        "die_bbox_um": metrics["design__die__bbox"],
        "macro_rectangle_area_um2": metrics["design__die__area"],
        "standard_cell_area_including_clock_and_repair_um2": metrics["design__instance__area__stdcell"],
        "checks": checks, "timing_corners": timing,
        "limitations": [
            "Only standalone SAR digital controller; not PGA, CDAC, comparator or whole-chip layout.",
            "Nine characterized digital Liberty × RC corners are not the requested analog 45-point PVT matrix.",
            "Functional gate simulation is zero-delay; STA checks timing separately.",
            "Asynchronous reset release and analog phase nonoverlap need system-level verification.",
            "No same-edge synchronous hold check applies to the asynchronous comparator_evaluate output; its 10ns propagation bound remains checked.",
            "Power log uses an explicit exhaustive-test workload, not worst-case or full-chip transistor current.",
            "Open-source DRC/LVS decks establish this flow's checks, not foundry production signoff or tapeout readiness.",
        ],
        "source_sha256": {str(p.relative_to(ROOT)): digest(p) for p in (
            HERE / "config.json", HERE / "run.sh", HERE / "summarize.py", HERE / "verify_routed.py",
            HERE / "power.tcl", HERE / "activity_trace.sv", ROOT / "v2/digital/constraints.sdc",
            ROOT / "v2/rtl/sar_controller.v", ROOT / "v2/tests/rtl/tb_sar_controller.sv")},
        "artifact_sha256": {str(p.relative_to(ROOT)): digest(p) for folder in (artifact_root, evidence)
                            for p in sorted(folder.rglob("*")) if p.is_file()},
    }
    (HERE / "results/physical_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if not key.endswith("sha256")}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
