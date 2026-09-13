#!/usr/bin/env python3
"""Two bounded same-circuit timestep experiments; no full-ADC qualification.

The old 2 ns output omitted CDAC/reference nodes, so a newly instrumented 2 ns
baseline is necessary. Only saved vectors and maxstep change, not devices,
models, tolerances, 1 ns edges, input sequence, core RTL or duration.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time

import numpy as np

from static_campaign import HERE, LSB, read_plan, runtime_identity, sha, write_json


EXTRA_SIGNALS = ["v(clk)", "v(evaluate)", "v(top_sample)", "v(acq)", "v(conv)",
                 "v(xadc.tp)", "v(xadc.tn)", "v(rp)", "v(rn)", "v(vcm)",
                 "v(xadc.prep)", "v(xadc.pren)", "v(decision)", "v(decision_b)"]
COLUMNS = {"time": 0, "valid": 1, "inp": 2, "inn": 3, "clk": 16, "evaluate": 17,
           "top_sample": 18, "acq": 19, "conv": 20, "tp": 21, "tn": 22,
           "rp": 23, "rn": 24, "vcm": 25, "prep": 26, "pren": 27, "decision": 28, "decision_b": 29}


def instrument(source, maxstep_ns):
    if maxstep_ns not in (2, 10):
        raise ValueError("only the two approved maximum timesteps are supported")
    original = source.splitlines()
    result = []
    counts = {"save": 0, "wrdata": 0, "tran": 0}
    for line in original:
        if line.startswith(".save "):
            counts["save"] += 1
            line += " " + " ".join(EXTRA_SIGNALS)
        elif line.startswith("wrdata waveform.dat "):
            counts["wrdata"] += 1
            line += " " + " ".join(EXTRA_SIGNALS)
        elif line.startswith("tran "):
            counts["tran"] += 1
            if line != "tran 2n 62u 0 2n":
                raise ValueError("expected unchanged 62 us, 2 ns baseline")
            # Preserve the first output interval argument; change only maxstep.
            line = f"tran 2n 62u 0 {maxstep_ns}n"
        result.append(line)
    if counts != {"save": 1, "wrdata": 1, "tran": 1}:
        raise ValueError("unexpected source structure")
    return "\n".join(result) + "\n"


def crossings(times, values, threshold):
    ids = np.flatnonzero((values[:-1] < threshold) & (values[1:] >= threshold))
    return times[ids] + (times[ids + 1] - times[ids]) * (threshold - values[ids]) / (values[ids + 1] - values[ids])


def time_step_statistics(values, vdd=1.8):
    dt = np.diff(values[:, 0])
    if np.any(dt <= 0):
        raise ValueError("nonpositive time step")
    result = {
        "rows": len(values), "stop_us": float(values[-1, 0] * 1e6),
        "dt_ns_percentiles": dict(zip(("min", "p1", "p10", "p50", "p90", "p99", "max"),
             (np.quantile(dt, [0, .01, .1, .5, .9, .99, 1]) * 1e9).tolist())),
        "steps_below_1ps": int(np.sum(dt < 1e-12)),
        "steps_below_100ps": int(np.sum(dt < 1e-10)),
        "step_count_is_not_cpu_profile": True,
    }
    if values.shape[1] >= 30:
        before = values[:-1, 0] < 1.001e-6
        acquisition = ~before & ((values[:-1, 18] > vdd / 2) | (values[:-1, 19] > vdd / 2))
        evaluating = ~before & ~acquisition & (values[:-1, 17] > vdd / 2)
        reset_settle = ~before & ~acquisition & ~evaluating
        result["phase_step_counts"] = {"startup": int(before.sum()), "acquisition": int(acquisition.sum()),
             "evaluate": int(evaluating.sum()), "hold_reset_cdac_settle": int(reset_settle.sum())}
    return result


def parse_result(directory, returncode, expected_codes):
    log = (directory / "simulation.log").read_text(errors="replace")
    codes = [int(x) for x in re.findall(r"COSIM_RESULT time_ns=[\d.]+ code=(\d+) gain_code=0", log)]
    result = {"status": "INCOMPLETE", "returncode": returncode, "raw_codes": codes,
              "complete_adc_qualified": False}
    if returncode != 0 or not (directory / "waveform.dat").exists():
        result["reason"] = "simulator timeout/failure or missing completed waveform"
        return result
    values = np.loadtxt(directory / "waveform.dat", skiprows=1)
    if values.ndim != 2 or values.shape[1] != 30 or not np.isfinite(values).all() or values[-1, 0] < 62e-6 - 1e-12:
        result["reason"] = "invalid or incomplete waveform"
        return result
    valid = crossings(values[:, 0], values[:, 1], .9)
    evaluate = crossings(values[:, 0], values[:, 17], .18)
    if len(valid) != 6 or len(codes) != 6 or len(evaluate) != 72:
        result["reason"] = "not all six conversions and 72 evaluate phases completed"
        return result
    buses = []
    for time_s in valid:
        volts = [np.interp(time_s + 10e-9, values[:, 0], values[:, col]) for col in range(4, 16)]
        if any(.18 < voltage < 1.62 for voltage in volts):
            result["reason"] = "unsettled output logic bus"
            return result
        buses.append(sum(int(voltage > .9) << (11 - bit) for bit, voltage in enumerate(volts)))
    result.update({"status": "CONVERSIONS_COMPLETE_ANALOG_COMPARISON_PENDING", "bus_codes": buses,
        "bus_matches_log": buses == codes, "codes_match_prior_frozen_result": codes == expected_codes,
        "valid_times_s": valid.tolist(), "evaluate_rise_10percent_times_s": evaluate.tolist(),
        "time_step_statistics": time_step_statistics(values)})
    if buses != codes:
        result["status"] = "OUTPUT_BUS_LOG_MISMATCH"
    return result


def sample(values, times, column):
    return np.interp(times, values[:, 0], values[:, column])


def compare(reference_directory, trial_directory):
    baseline = json.loads((reference_directory / "summary.json").read_text())
    trial = json.loads((trial_directory / "summary.json").read_text())
    result = {"status": "INCOMPLETE_PAIR", "complete_adc_qualified": False,
              "threshold_v": .05 * LSB, "threshold_lsb": .05, "valid_time_tolerance_ns": 1.0}
    status = "CONVERSIONS_COMPLETE_ANALOG_COMPARISON_PENDING"
    if baseline["status"] != status or trial["status"] != status:
        return result
    a = np.loadtxt(reference_directory / "waveform.dat", skiprows=1)
    b = np.loadtxt(trial_directory / "waveform.dat", skiprows=1)
    # Common absolute times from the reference waveform, before the evaluate
    # input reaches 10% VDD. All 72 decisions are included; no cherry-picking.
    pre = np.asarray(baseline["evaluate_rise_10percent_times_s"]) - 1e-9
    grid = np.arange(0, 62000 + 1, dtype=float) * 1e-9
    grid[-1] = min(a[-1, 0], b[-1, 0])
    channels = {}
    for name, columns in {"cdac_differential": (21, 22), "rp": (23,), "rn": (24,), "vcm": (25,),
                          "preamp_differential_diagnostic": (26, 27)}.items():
        def signal(values, times):
            output = sample(values, times, columns[0])
            return output - sample(values, times, columns[1]) if len(columns) == 2 else output
        pre_error = signal(b, pre) - signal(a, pre)
        error = signal(b, grid) - signal(a, grid)
        channels[name] = {"maximum_predecision_error_v": float(np.max(np.abs(pre_error))),
            "maximum_predecision_error_lsb": float(np.max(np.abs(pre_error)) / LSB),
            "common_1ns_grid_maximum_error_v": float(np.max(np.abs(error))),
            "common_1ns_grid_maximum_error_lsb": float(np.max(np.abs(error)) / LSB),
            "predecision_errors_v": pre_error.tolist(),
            "worst_grid_time_s": float(grid[np.argmax(np.abs(error))])}
        if name in ("rp", "rn", "vcm"):
            ideal = {"rp": 1.1, "rn": .7, "vcm": .9}[name]
            channels[name]["baseline_peak_reference_disturbance_v"] = float(np.max(np.abs(signal(a, grid) - ideal)))
            channels[name]["trial_peak_reference_disturbance_v"] = float(np.max(np.abs(signal(b, grid) - ideal)))
    valid_error_ns = np.abs(np.asarray(trial["valid_times_s"]) - np.asarray(baseline["valid_times_s"])) * 1e9
    evaluate_error_ns = np.abs(np.asarray(trial["evaluate_rise_10percent_times_s"]) - np.asarray(baseline["evaluate_rise_10percent_times_s"])) * 1e9
    checks = {
        "all_six_codes_match": trial["raw_codes"] == baseline["raw_codes"],
        "both_output_buses_match_logs": baseline["bus_matches_log"] and trial["bus_matches_log"],
        "baseline_codes_match_old_uninstrumented_2ns": baseline["codes_match_prior_frozen_result"],
        "valid_time_error_le_1ns": bool(np.max(valid_error_ns) <= 1),
        "evaluate_time_error_le_1ns": bool(np.max(evaluate_error_ns) <= 1),
        "all_72_predecision_cdac_errors_le_0_05lsb": channels["cdac_differential"]["maximum_predecision_error_v"] <= .05 * LSB,
        "all_reference_predecision_errors_le_0_05lsb": all(channels[n]["maximum_predecision_error_v"] <= .05 * LSB for n in ("rp", "rn", "vcm")),
        "all_reference_common_grid_errors_le_0_05lsb": all(channels[n]["common_1ns_grid_maximum_error_v"] <= .05 * LSB for n in ("rp", "rn", "vcm")),
        "cdac_common_grid_error_le_0_05lsb": channels["cdac_differential"]["common_1ns_grid_maximum_error_v"] <= .05 * LSB,
    }
    result.update({"status": "SMALL_SUBSET_TIMESTEP_COMPARISON_PASS" if all(checks.values()) else "TIMESTEP_COMPARISON_FAIL",
        "checks": checks, "channels": channels, "predecision_times_s": pre.tolist(),
        "valid_time_max_error_ns": float(np.max(valid_error_ns)), "evaluate_time_max_error_ns": float(np.max(evaluate_error_ns)),
        "baseline_wall_seconds": baseline["wall_seconds"], "trial_wall_seconds": trial["wall_seconds"],
        "observed_speedup": baseline["wall_seconds"] / trial["wall_seconds"],
        "limitations": ["Three inputs, six conversions, TT 1.8 V 27 C only; no whole-code or PVT numerical qualification.",
            "No device-noise SNDR or mismatch data. Same raw codes alone are insufficient for a numerical pass.",
            "Peak interpolation differences evaluated on shared 1 ns grid; sub-ns glitch maxima may be missed.",
            "Predecision CDAC residual checked at all 72 evaluate windows on common absolute times, 1 ns before reference evaluate crosses 10% VDD.",
            "Phase step counts are a timestep-density proxy, not measured CPU attribution; no proof that d_cosim alone is the bottleneck."]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=float, default=900)
    args = parser.parse_args()
    campaign = HERE / "campaigns/continuous_three_point"
    plan = read_plan(campaign)
    prior_path = campaign / "batches/000000/attempt_001/summary.json"
    prior = json.loads(prior_path.read_text())
    source = prior_path.parent / "adc.spice"
    if sha(source) != prior["deck_sha256"] or sha(campaign / "runtime.json") != prior["runtime_sha256"]:
        raise ValueError("prior evidence identity changed")
    if runtime_identity() != json.loads((campaign / "runtime.json").read_text()):
        raise ValueError("tool or PDK identity changed")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = HERE / "timestep_results" / stamp
    out.mkdir(parents=True)
    (out / "timestep_convergence.py").write_bytes(Path(__file__).read_bytes())
    write_json(out / "manifest.json", {"status": "RUNNING", "original_plan_sha256": plan["plan_sha256"],
        "original_deck_sha256": sha(source), "original_summary_sha256": sha(prior_path),
        "runtime_sha256": sha(campaign / "runtime.json"), "binary_sha256": sha(campaign / "build/cosim_controller.so"),
        "columns": COLUMNS, "approved_timesteps_ns": [2, 10], "complete_adc_qualified": False})
    for maxstep in (2, 10):
        read_plan(campaign)
        directory = out / f"maxstep_{maxstep}ns"
        directory.mkdir()
        (directory / "adc.spice").write_text(instrument(source.read_text(), maxstep))
        (directory / ".spiceinit").write_bytes((prior_path.parent / ".spiceinit").read_bytes())
        start = time.monotonic()
        try:
            proc = subprocess.run(["ngspice", "-b", "-o", "native.log", "adc.spice"], cwd=directory,
                env=dict(os.environ, SPICE_USERINIT_DIR=str(directory)), capture_output=True, text=True, timeout=args.timeout_seconds)
            rc, log = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as error:
            rc, log = None, "TIMEOUT\n" + (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
        elapsed = time.monotonic() - start
        if (directory / "native.log").exists():
            log += (directory / "native.log").read_text(errors="replace")
        (directory / "simulation.log").write_text(log)
        result = parse_result(directory, rc, prior["raw_codes"])
        result.update({"wall_seconds": elapsed, "maxstep_ns": maxstep,
                       "artifact_sha256": {p.name: sha(p) for p in directory.iterdir() if p.is_file()}})
        write_json(directory / "summary.json", result)
        print(json.dumps({"maxstep_ns": maxstep, "status": result["status"], "codes": result["raw_codes"], "wall_seconds": elapsed}), flush=True)
    result = compare(out / "maxstep_2ns", out / "maxstep_10ns")
    result["manifest_sha256"] = sha(out / "manifest.json")
    write_json(out / "comparison.json", result)
    print(json.dumps({"report": str(out / "comparison.json"), "status": result["status"], "checks": result.get("checks"),
                      "observed_speedup": result.get("observed_speedup")}, indent=2))
    return 0 if result["status"] == "SMALL_SUBSET_TIMESTEP_COMPARISON_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
