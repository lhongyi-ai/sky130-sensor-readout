#!/usr/bin/env python3
"""Index small real-circuit evidence and measured runtime; never full-code PASS."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys

from static_campaign import HERE, LSB, sha, write_json


def main():
    continuous = HERE / "campaigns/continuous_three_point"
    batch_path = continuous / "batches/000000/attempt_001/summary.json"
    batch = json.loads(batch_path.read_text())
    if batch["status"] != "BATCH_COMPLETE_NOT_ADC_QUALIFIED":
        raise ValueError("continuous conversion evidence incomplete")
    # Invoke immutable analyser, including its raw-waveform integrity checks.
    proc = subprocess.run([sys.executable, str(continuous / "frozen/static_campaign.py"),
                           "collect", str(continuous)], capture_output=True, text=True)
    if proc.returncode:
        raise ValueError("frozen raw evidence audit failed: " + proc.stderr)
    coverage = json.loads(proc.stdout)
    profiles = sorted(continuous.glob("op_profile_*/summary.json"))
    profile_path = next(p for p in reversed(profiles) if json.loads(p.read_text())["status"] == "OP_RUNTIME_PROFILE_COMPLETE")
    profile = json.loads(profile_path.read_text())
    seconds_per_conversion = profile["batches"][0]["estimated_seconds_per_conversion_excluding_separate_op"]
    load_op = profile["model_load_and_op_process_wall_seconds"]
    budgets = []
    for stage, points in (("centres", 4096), ("ramp32", 131073)):
        batches = math.ceil(points / 8)
        conversions = 2 * points + batches - 1
        seconds = conversions * seconds_per_conversion + batches * load_op + profile["build_wall_seconds"]
        budgets.append({"stage": stage, "point_count": points, "batch_size": 8,
            "warmup_conversions_per_point": 1, "history_replay_conversions": batches - 1,
            "total_conversions": conversions, "estimated_wall_days_one_worker_one_pvt": seconds / 86400,
            "estimate_only_not_measured_coverage": True})
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(HERE), "-p", "test_*.py", "-v"],
                           capture_output=True, text=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = HERE / "results" / stamp
    output.mkdir(parents=True)
    (output / "software_tests.log").write_text(tests.stdout + tests.stderr)
    inputs = []
    for row in batch["rows"]:
        expected = min(4095, max(0, math.floor((row["input_v"] + .4) / LSB)))
        inputs.append({**row, "expected_ideal_code": expected, "raw_error_lsb": row["raw_code"] - expected})
    report = {
        "status": "SMALL_TRANSISTOR_SUBSET_COMPLETE_FULL_CODE_NOT_COMPLETE",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": "20260908T045601001817Z composite, no analog or core RTL changes",
        "retained_points": inputs, "all_conversion_codes_including_discarded_warmups": batch["raw_codes"],
        "continuous_conversion_count": len(batch["sequence"]),
        "same_process_input_changes": True, "build_once_per_campaign": True,
        "software_tests_returncode": tests.returncode, "coverage_status": coverage["status"],
        "complete_adc_qualified": False, "full_chip_qualified": False,
        "all_non_cadence_work_complete": False,
        "measured_build_seconds": profile["build_wall_seconds"],
        "measured_six_conversion_process_seconds": batch["wall_seconds"],
        "measured_separate_load_op_process_seconds": load_op,
        "estimated_transient_and_output_seconds": profile["batches"][0]["estimated_transient_and_output_wall_seconds"],
        "projected_cost": budgets,
        "evidence": {str(p.relative_to(HERE)): sha(p) for p in (batch_path, profile_path, continuous / "plan.json", continuous / "runtime.json")},
        "limitations": ["Only three retained input points and six sequential conversions at TT 1.8 V 27 C.",
            "Model-load/OP measured separately; transient portion inferred by subtraction, not internally instrumented.",
            "Full sweep wall estimates assume this tiny sample's throughput; not a guarantee and may change greatly with input/corner/numerical settings.",
            "No full-code INL/DNL, no device-noise SNDR, no mismatch, no ADC layout or PEX.",
            "The first OP profiling attempt failed to print unsaved vectors; that fixture error is retained and the next attempt corrects only the save list."],
    }
    write_json(output / "summary.json", report)
    print(json.dumps(report, indent=2))
    return tests.returncode


if __name__ == "__main__":
    raise SystemExit(main())
