#!/usr/bin/env python3
"""Audit a completed timestep pair, including resampling-error diagnosis.

No extra SPICE experiment. Resampling decomposition is relative to the 2 ns
reference curve, not an exact physical solution and not permission to waive a
failed predeclared waveform tolerance.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np

from static_campaign import HERE, LSB, sha, write_json
from timestep_convergence import crossings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    root = args.experiment.resolve()
    comparison = json.loads((root / "comparison.json").read_text())
    base_summary = json.loads((root / "maxstep_2ns/summary.json").read_text())
    trial_summary = json.loads((root / "maxstep_10ns/summary.json").read_text())
    for directory, summary in ((root / "maxstep_2ns", base_summary), (root / "maxstep_10ns", trial_summary)):
        for name, expected in summary["artifact_sha256"].items():
            if sha(directory / name) != expected:
                raise ValueError("evidence changed: " + str(directory / name))
    a = np.loadtxt(root / "maxstep_2ns/waveform.dat", skiprows=1)
    b = np.loadtxt(root / "maxstep_10ns/waveform.dat", skiprows=1)
    old = np.loadtxt(HERE / "campaigns/continuous_three_point/batches/000000/attempt_001/waveform.dat", skiprows=1)
    grid = np.arange(62001, dtype=float) * 1e-9
    grid[-1] = min(a[-1, 0], b[-1, 0])
    original = a[:, 21] - a[:, 22]
    trial = b[:, 21] - b[:, 22]
    base_on_grid = np.interp(grid, a[:, 0], original)
    base_on_trial_times = np.interp(b[:, 0], a[:, 0], original)
    base_resampled_on_grid = np.interp(grid, b[:, 0], base_on_trial_times)
    trial_on_grid = np.interp(grid, b[:, 0], trial)
    resampling = base_resampled_on_grid - base_on_grid
    residual = trial_on_grid - base_resampled_on_grid
    total = trial_on_grid - base_on_grid
    worst = int(np.argmax(np.abs(total)))
    times = a[:, 0]
    mid = (times[:-1] + times[1:]) / 2
    edges = np.sort(np.r_[crossings(times, a[:, 17], .9), crossings(times, -a[:, 17], -.9)])
    index = np.searchsorted(edges, mid, side="right") - 1
    elapsed = mid - edges[np.maximum(index, 0)]
    near = (index >= 0) & (elapsed < 20e-9)
    summary = {
        "status": comparison["status"], "complete_adc_qualified": False,
        "new_maxstep_adopted": False, "original_default_maxstep_ns": 2,
        "observed_speedup": comparison["observed_speedup"],
        "instrumentation_did_not_change_old_saved_vectors": bool(np.array_equal(old, a[:, :16])),
        "baseline_step_statistics": base_summary["time_step_statistics"],
        "trial_step_statistics": trial_summary["time_step_statistics"],
        "baseline_steps_within_20ns_after_evaluate_edges": int(near.sum()),
        "baseline_duration_within_these_windows_us": float(np.diff(times)[near].sum() * 1e6),
        "step_count_not_cpu_profile": True,
        "interpolation_diagnosis_relative_to_2ns_reference": {
            "maximum_trial_accepted_point_error_v": float(np.max(np.abs(trial - base_on_trial_times))),
            "maximum_common_grid_error_v": float(np.max(np.abs(total))),
            "maximum_reference_resampling_component_v": float(np.max(np.abs(resampling))),
            "maximum_residual_after_same_grid_representation_v": float(np.max(np.abs(residual))),
            "worst_common_grid_time_s": float(grid[worst]),
            "at_worst_total_v": float(total[worst]),
            "at_worst_reference_resampling_component_v": float(resampling[worst]),
            "at_worst_residual_v": float(residual[worst]),
            "declared_threshold_v": .05 * LSB,
            "does_not_overrule_failed_predeclared_test": True,
        },
        "evidence_sha256": {name: sha(root / name) for name in (
            "comparison.json", "manifest.json", "maxstep_2ns/summary.json", "maxstep_10ns/summary.json")},
        "conclusions": [
            "The 10 ns limit reduces long steps but almost none of the sub-100 ps switching steps; measured speedup is only about 10 percent.",
            "All six codes and all 72 predecision CDAC samples agree within the predeclared small-signal tolerance, but the whole-trajectory interpolation test fails.",
            "Resampling decomposition diagnoses the failed peak; it is relative to the 2 ns numerical reference, not proof of exact physical error.",
            "No unmeasured attribution of solver CPU to d_cosim is made. Accepted-point density alone cannot distinguish event overhead, Newton iterations and timestep rejection.",
            "No 20 ns experiment and no full sweep were launched; default remains 2 ns. No whole-ADC precision or convergence claim is made.",
        ],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    write_json(root / ("diagnosis_" + stamp + ".json"), summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
