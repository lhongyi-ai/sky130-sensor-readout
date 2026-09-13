#!/usr/bin/env python3
"""Validate every actual comparator decision; forced data is never evidence.

For this frozen bridge/timing contract, controller output changes are 3 ns after
the external ideal clock's edge starts. A +/-10 ns window around each scheduled
result update covers the read plus bridge delay and exceeds the original setup
and hold constraints. Q and QB must remain complementary valid rails throughout
all recorded points in that window. No simulated source may drive Q or QB.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from trace_replay import BASELINE, OLD, sc, tc, save_vectors


def comparator_certificate(values, expected_codes, vdd=1.8):
    if len(expected_codes) != 6 or any(not 0 <= code <= 4095 for code in expected_codes):
        raise ValueError("this bounded protocol requires six valid predicted codes")
    valid = tc.crossings(values[:, 0], values[:, 1], vdd / 2)
    evaluate = tc.crossings(values[:, 0], values[:, 17], .1 * vdd)
    expected_valid = (11.0035 + np.arange(6) * 10) * 1e-6
    expected_evaluate = np.array([3.8156 + frame * 10 + bit * .625 for frame in range(6) for bit in range(12)]) * 1e-6
    if len(valid) != 6 or len(evaluate) != 72 or np.max(np.abs(valid - expected_valid)) > 1e-9 or np.max(np.abs(evaluate - expected_evaluate)) > 1e-9:
        return {"status": "INVALID_TIMING", "decisions": [], "complete_adc_qualified": False}
    result = []
    for frame, (end, word) in enumerate(zip(valid, expected_codes)):
        for position in range(12):
            bit = 11 - position
            centre = end - bit * 625e-9
            left, right = centre - 10e-9, centre + 10e-9
            use = (values[:, 0] >= left) & (values[:, 0] <= right)
            if not np.any(use) or left < values[0, 0] or right > values[-1, 0]:
                raise ValueError("decision window outside completed waveform")
            times = np.r_[left, values[use, 0], right]
            q = np.interp(times, values[:, 0], values[:, 28])
            qb = np.interp(times, values[:, 0], values[:, 29])
            high = bool(q.min() >= .8 * vdd and qb.max() <= .2 * vdd)
            low = bool(q.max() <= .2 * vdd and qb.min() >= .8 * vdd)
            observed = 1 if high else 0 if low else None
            expected = (word >> bit) & 1
            result.append({"frame": frame, "bit": bit, "expected": expected,
                "observed": observed, "accepted": observed == expected,
                "window_s": [float(left), float(right)], "saved_points": int(use.sum()),
                "q_range_v": [float(q.min()), float(q.max())], "qb_range_v": [float(qb.min()), float(qb.max())]})
    all_accepted = all(row["accepted"] for row in result)
    derived_codes = []
    for frame in range(6):
        rowset = [row for row in result if row["frame"] == frame]
        derived_codes.append(sum(row["observed"] << row["bit"] for row in rowset) if all(row["observed"] is not None for row in rowset) else None)
    return {"status": "ALL_72_ACTUAL_DECISIONS_ACCEPT_PREDICTED_TRACE" if all_accepted else "REJECTED_TRACE",
            "decisions": result, "observed_replay_decision_words": derived_codes,
            "certified_codes": derived_codes if all_accepted else None,
            "matched_decisions": sum(row["accepted"] for row in result), "required_decisions": 72,
            "complete_adc_qualified": False,
            "scope": "Actual Q/QB transistor outputs, not the forced output data or predicted comparator source",
            "limitations": ["Deterministic static six-conversion protocol only; no random-noise or PVT certificate.",
                "Saved accepted points plus interval endpoints are checked; no exact continuous solution is claimed.",
                "Acceptance is conditional on separately verified unchanged RTL and calibrated bridge timing."]}


def analog_comparison(reference, candidate):
    pre = tc.crossings(reference[:, 0], reference[:, 17], .18) - 1e-9
    if len(pre) != 72:
        raise ValueError("reference must contain all 72 evaluations")
    grid = np.arange(62001, dtype=float) * 1e-9
    grid[-1] = min(reference[-1, 0], candidate[-1, 0])
    threshold = .05 * sc.LSB
    channels = {}
    for name, columns in {"cdac_differential": (21, 22), "rp": (23,), "rn": (24,), "vcm": (25,)}.items():
        def signal(values, times):
            result = np.interp(times, values[:, 0], values[:, columns[0]])
            return result - np.interp(times, values[:, 0], values[:, columns[1]]) if len(columns) == 2 else result
        diff = signal(candidate, grid) - signal(reference, grid)
        before = signal(candidate, pre) - signal(reference, pre)
        channels[name] = {"common_grid_max_error_v": float(np.max(np.abs(diff))),
            "predecision_max_error_v": float(np.max(np.abs(before))),
            "worst_common_grid_time_s": float(grid[np.argmax(np.abs(diff))])}
    timing = {}
    for name, column, level in (("valid", 1, .9), ("evaluate", 17, .18)):
        a, b = tc.crossings(reference[:, 0], reference[:, column], level), tc.crossings(candidate[:, 0], candidate[:, column], level)
        timing[name] = float(np.max(np.abs(a - b))) if len(a) == len(b) and len(a) else None
    checks = {"all_analog_common_grid_errors_le_0_05lsb": all(row["common_grid_max_error_v"] <= threshold for row in channels.values()),
              "all_predecision_errors_le_0_05lsb": all(row["predecision_max_error_v"] <= threshold for row in channels.values()),
              "valid_and_evaluate_times_within_1ns": all(value is not None and value <= 1e-9 for value in timing.values())}
    return {"status": "FINITE_TRACE_ANALOG_EQUIVALENCE_PASS" if all(checks.values()) else "FINITE_TRACE_ANALOG_EQUIVALENCE_FAIL",
        "checks": checks, "threshold_v": threshold, "common_grid_ns": 1, "channels": channels,
        "timing_max_error_s": timing, "complete_adc_qualified": False,
        "limitations": ["Same six conversions only; no extrapolation to 4096 codes or 131073 input grid.",
            "The common 1 ns interpolation grid may not capture sub-ns glitch maxima."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    summary = json.loads((candidate / "summary.json").read_text())
    if summary["status"] != "TRANSISTOR_WAVEFORM_COMPLETE_NOT_CERTIFIED":
        raise ValueError("candidate simulation did not complete")
    for name, value in summary["source_and_output_sha256"].items():
        if sc.sha(candidate / name) != value:
            raise ValueError("candidate evidence changed")
    values = np.loadtxt(candidate / "waveform.dat", skiprows=1)
    result = {"decision_certificate": comparator_certificate(values, summary["expected_codes"]),
        "summary_sha256": sc.sha(candidate / "summary.json"), "complete_adc_qualified": False,
        "analyzer_sha256": sc.sha(Path(__file__)),
        "live_rtl_inside_analog_run": summary["live_rtl_inside_analog_run"]}
    if args.reference:
        reference = args.reference.resolve()
        baseline = np.loadtxt(reference / "waveform.dat", skiprows=1)
        result["analog_comparison"] = analog_comparison(baseline, values)
        result["reference_summary_sha256"] = sc.sha(reference / "summary.json")
        result["observed_speedup"] = json.loads((reference / "summary.json").read_text())["wall_seconds"] / summary["wall_seconds"]
    report_path = candidate / ("certificate_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    sc.write_json(report_path, result)
    print(json.dumps({"decision_status": result["decision_certificate"]["status"],
        "report": str(report_path), "matched_decisions": result["decision_certificate"].get("matched_decisions", 0),
        "analog_comparison": result.get("analog_comparison"), "speedup": result.get("observed_speedup")}, indent=2))
    decisions_ok = result["decision_certificate"]["status"] == "ALL_72_ACTUAL_DECISIONS_ACCEPT_PREDICTED_TRACE"
    analog_ok = "analog_comparison" not in result or result["analog_comparison"]["status"] == "FINITE_TRACE_ANALOG_EQUIVALENCE_PASS"
    return 0 if decisions_ok and analog_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
