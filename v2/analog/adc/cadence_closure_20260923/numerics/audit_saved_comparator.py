#!/usr/bin/env python3
"""Audit retained comparator outputs; descriptive evidence, never a waiver.

The existing full absolute-time union-grid comparison remains authoritative.
PCHIP is only an interpolation-sensitivity probe, not a replacement gate.
"""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SOURCE = REPO / "v2/physical/cdac_repair_20260923/adc_native_mapping_1"
LIMIT = .05 * .8 / 4096


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def absolute_compare(t, y, u, z):
    """Keep every accepted point, every switching edge, and physical time."""
    if not (np.all(np.diff(t) > 0) and np.all(np.diff(u) > 0)):
        raise ValueError("Accepted times must increase strictly")
    if t[0] != u[0] or t[-1] != u[-1]:
        raise ValueError("Do not extrapolate or silently truncate run duration")
    if not all(np.isfinite(x).all() for x in [t, y, u, z]):
        raise ValueError("Nonfinite waveform")
    grid = np.union1d(t, u)
    delta = np.interp(grid, u, z) - np.interp(grid, t, y)
    i = int(np.argmax(np.abs(delta)))
    return grid, delta, i


def bracket(t, y, at):
    i = int(np.searchsorted(t, at))
    lo, hi = max(0, i - 2), min(len(t), i + 2)
    return {"time_s": t[lo:hi].tolist(), "voltage_v": y[lo:hi].tolist()}


def describe_channel(t, y, u, z):
    grid, delta, i = absolute_compare(t, y, u, z)
    # Quantify sensitivity to the offline reconstruction only. Never assert
    # that a smaller reconstructed difference is the true continuous error.
    pchip_delta = PchipInterpolator(u, z)(grid) - PchipInterpolator(t, y)(grid)
    p = int(np.argmax(np.abs(pchip_delta)))
    return {
        "linear_union_max_abs_v": float(abs(delta[i])),
        "linear_union_signed_delta_v": float(delta[i]),
        "linear_union_worst_time_s": float(grid[i]),
        "linear_union_gate_0_05lsb": bool(abs(delta[i]) <= LIMIT),
        "union_points": len(grid),
        "union_points_over_diagnostic_limit": int(np.count_nonzero(abs(delta) > LIMIT)),
        "baseline_bracket_at_linear_worst": bracket(t, y, grid[i]),
        "strict_bracket_at_linear_worst": bracket(u, z, grid[i]),
        "pchip_diagnostic_only": {
            "max_abs_v": float(abs(pchip_delta[p])),
            "worst_time_s": float(grid[p]),
            "difference_from_linear_at_linear_worst_v": float(pchip_delta[i] - delta[i]),
            "not_a_gate": True,
            "not_an_error_bound": True,
        },
    }


def warning_summary(path):
    s = path.read_text()
    notices = []
    for m in re.finditer(r"Warning from spectre at time = ([0-9.e+-]+) (\w+) during[^\n]*\n\s+WARNING \(([^)]+)\): ([^\n]+)", s):
        notices.append({"time_text": m[1] + " " + m[2], "code": m[3], "text": m[4]})
    return {
        "log_sha256": sha(path),
        "printed_warning_records": notices,
        "warning_suppression_present": "Further occurrences of this warning will be suppressed" in s,
        "LTE_printed_count_is_lower_bound": "Further occurrences of this warning will be suppressed" in s,
        "newton_disaster_recovery_present": "Disaster recovery algorithm is enabled" in s,
    }


def main():
    old = SOURCE / "reset1/compare_numerics.py"
    spec = importlib.util.spec_from_file_location("frozen_compare", old)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = SOURCE / "private_runtime/reset1_comparator_002"
    strict = SOURCE / "private_runtime/reset1_comparator_strict_001"
    bf, sf = base / "reset_decide.tran.tran", strict / "reset_decide.tran.tran"
    bh, bn, b = module.parse(bf)
    sh, sn, s = module.parse(sf)
    assert set(bn) == set(sn)
    s = s[:, [0] + [sn.index(n) + 1 for n in bn]]
    idx = {n: i + 1 for i, n in enumerate(bn)}
    selected = {
        "preamp_differential": ["XCMP.XADC_PREP", "XCMP.XADC_PREN"],
        "R_BAR": ["XCMP.XADC_XCMP_R_BAR"],
        "Q": ["Q"],
        "SET_MID": ["XCMP.XADC_XCMP_XSET_MID"],
    }
    channels = {}
    for name, columns in selected.items():
        y = sum((1 if j == 0 else -1) * b[:, idx[c]] for j, c in enumerate(columns))
        z = sum((1 if j == 0 else -1) * s[:, idx[c]] for j, c in enumerate(columns))
        channels[name] = describe_channel(b[:, 0], y, s[:, 0], z)
        channels[name]["nodes"] = columns
    result = {
        "status": "DIAGNOSTIC_ONLY_EXISTING_FAILURE_UNCHANGED",
        "physical_ADC_gate": "NOT_RUN_IN_THIS_FIXTURE",
        "absolute_diagnostic_limit_v": LIMIT,
        "source_hashes": {str(p.relative_to(REPO)): sha(p) for p in [old, bf, sf, base / "input.scs", strict / "input.scs"]},
        "solver_profiles": {"baseline": bh, "strict": sh},
        "channels": channels,
        "logs": {"baseline": warning_summary(base / "spectre.out"), "strict": warning_summary(strict / "spectre.out")},
        "limitations": [
            "No waveform shifts, excluded edges, threshold changes, or changed original verdicts.",
            "PCHIP reconstruction is an interpolation-sensitivity diagnostic, not ground truth or an error bound.",
            "Five printed warnings do not prove five events when the simulator suppresses repeats.",
            "Internal body nodes are not saved in the retained allpub data, so their mechanism cannot be proven from this data alone.",
        ],
    }
    target = HERE / "saved_comparator_audit.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(target), "channels": channels}, indent=2))


if __name__ == "__main__":
    main()
