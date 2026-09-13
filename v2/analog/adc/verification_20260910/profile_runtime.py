#!/usr/bin/env python3
"""Measure compile and separate model-load/OP wall time; retain all outputs.

The OP-only process is a workload estimate, not exact instrumentation of the
transient process. Report the subtraction as an estimate, never measured solver
CPU time. The ADC netlist, biases, source, RTL binary and PDK remain unchanged.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time

from static_campaign import read_plan, sha, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=180)
    args = parser.parse_args()
    campaign = args.campaign.resolve()
    plan = read_plan(campaign)
    completed = []
    for path in sorted((campaign / "batches").glob("*/attempt_*/summary.json")):
        result = json.loads(path.read_text())
        if result.get("status") == "BATCH_COMPLETE_NOT_ADC_QUALIFIED":
            completed.append((path, result))
    if not completed:
        raise ValueError("a completed real transistor batch is required first")
    source_report, result = completed[0]
    source = source_report.parent / "adc.spice"
    if sha(source) != result["deck_sha256"]:
        raise ValueError("source deck changed")
    out = campaign / ("op_profile_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir()
    original = source.read_text()
    deck = re.sub(r"^tran .*$", "op", original, flags=re.M)
    deck = re.sub(r"^\.save .*$", ".save v(vdd) v(inp) v(inn) v(xadc.tp) v(xadc.tn)", deck, flags=re.M)
    deck = re.sub(r"^wrdata .*$", "print v(vdd) v(inp) v(inn) v(xadc.tp) v(xadc.tn)", deck, flags=re.M)
    if deck == original:
        raise ValueError("transient directive not found")
    (out / "op.spice").write_text(deck)
    (out / ".spiceinit").write_bytes((source_report.parent / ".spiceinit").read_bytes())
    start = time.monotonic()
    try:
        proc = subprocess.run(["ngspice", "-b", "-o", "native.log", "op.spice"], cwd=out,
            env=dict(os.environ, SPICE_USERINIT_DIR=str(out)), capture_output=True, text=True, timeout=args.timeout_seconds)
        rc, log = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as error:
        rc, log = None, "TIMEOUT\n" + (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
    elapsed = time.monotonic() - start
    if (out / "native.log").exists():
        log += (out / "native.log").read_text(errors="replace")
    (out / "simulation.log").write_text(log)
    ok = rc == 0 and "v(xadc.tp)" in log and "v(xadc.tn)" in log
    build = json.loads((campaign / "build/binary.json").read_text())
    summary = {
        "status": "OP_RUNTIME_PROFILE_COMPLETE" if ok else "OP_PROFILE_FAILED",
        "plan_sha256": plan["plan_sha256"], "source_deck_sha256": sha(source),
        "op_deck_sha256": sha(out / "op.spice"), "returncode": rc,
        "build_wall_seconds": build.get("build_wall_seconds"),
        "model_load_and_op_process_wall_seconds": elapsed,
        "complete_adc_qualified": False,
        "batches": [],
        "limitations": ["OP/model-load timing measured in separate process, not inside the transient process.",
            "Subtracting this workload is an estimate; operating-system caching, contention and numerical startup differ.",
            "Runtime extrapolation is not evidence of completed code coverage or performance."],
    }
    for path, batch in completed:
        conversions = len(batch["sequence"])
        net = max(0, batch["wall_seconds"] - elapsed) if ok else None
        summary["batches"].append({"report": str(path.relative_to(campaign)), "conversion_count": conversions,
            "retained_points": len(batch["rows"]), "total_process_wall_seconds": batch["wall_seconds"],
            "estimated_transient_and_output_wall_seconds": net,
            "observed_seconds_per_conversion_including_load_op": batch["wall_seconds"] / conversions,
            "estimated_seconds_per_conversion_excluding_separate_op": net / conversions if ok else None})
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
