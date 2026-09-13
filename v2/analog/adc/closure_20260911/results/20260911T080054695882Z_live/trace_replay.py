#!/usr/bin/env python3
"""Bounded trace-certified transistor experiment, not a full-ADC signoff.

Only ideal testbench digital bridges/controllers may be replaced by speculative
voltage traces. The real comparator must independently validate every decision.
An incorrect prediction is a rejected trace, never valid conversion evidence.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "verification_20260910"
sys.path.insert(0, str(OLD))
import static_campaign as sc
import timestep_convergence as tc

BASELINE = OLD / "timestep_results/20260910T063430835346Z/maxstep_2ns"
CAMPAIGN = OLD / "campaigns/continuous_three_point"
ROOT = HERE.parents[2]
OUTPUTS = ["ready", "busy", "valid"] + [f"data{i}" for i in range(11, -1, -1)] + ["dgain1", "dgain0", "gain1", "gain0", "sample"] + [f"trial{i}" for i in range(11, -1, -1)] + ["evaluate"]


def read_original():
    plan = sc.read_plan(CAMPAIGN)
    record = json.loads((BASELINE / "summary.json").read_text())
    source = BASELINE / "adc.spice"
    if sc.sha(source) != record["artifact_sha256"]["adc.spice"]:
        raise ValueError("baseline deck changed")
    return source.read_text(), plan, record


def save_vectors(source):
    lines = [line for line in source.splitlines() if line.startswith(".save ")]
    if len(lines) != 1:
        raise ValueError("expected one save directive")
    return lines[0].split()[1:]


def instrument(source):
    saved = save_vectors(source)
    extras = [f"v({name})" for name in OUTPUTS if f"v({name})" not in saved]
    lines = []
    for line in source.splitlines():
        if line.startswith(".save ") or line.startswith("wrdata waveform.dat "):
            line += " " + " ".join(extras)
        if line == "quit":
            lines.append("rusage all")
        lines.append(line)
    return "\n".join(lines) + "\n"


def compress_trace(times, values, tolerance=1e-10):
    """RDP vertical-error bound at every recorded point; no edge rounding."""
    if len(times) != len(values) or len(times) < 2 or np.any(np.diff(times) <= 0):
        raise ValueError("strictly increasing time required")
    selected = {0, len(times) - 1}
    stack = [(0, len(times) - 1)]
    while stack:
        left, right = stack.pop()
        if right - left <= 1:
            continue
        intermediate = slice(left + 1, right)
        line = values[left] + (values[right] - values[left]) * (times[intermediate] - times[left]) / (times[right] - times[left])
        error = np.abs(values[intermediate] - line)
        offset = int(np.argmax(error))
        if error[offset] > tolerance:
            split = left + 1 + offset
            selected.add(split)
            stack.extend(((left, split), (split, right)))
    indices = np.asarray(sorted(selected))
    reconstructed = np.interp(times, times[indices], values[indices])
    maximum = float(np.max(np.abs(reconstructed - values)))
    if maximum > tolerance * 1.01:
        raise ValueError("trace compression exceeds declared error")
    return times[indices], values[indices], maximum


def pwl_voltage(name, times, values):
    chunks = [f"VTRACE_{name} {name} 0 PWL("]
    for start in range(0, len(times), 4):
        chunks.append("+ " + " ".join(f"{t:.17g} {v:.17g}" for t, v in zip(times[start:start + 4], values[start:start + 4])))
    chunks.append("+ )")
    return "\n".join(chunks)


def replay_deck(source, waveform):
    saved = save_vectors(source)
    values = np.loadtxt(waveform, skiprows=1)
    if values.shape[1] != len(saved) + 1:
        raise ValueError("source / waveform vector order mismatch")
    sources, compression = [], {}
    for name in OUTPUTS:
        column = saved.index(f"v({name})") + 1
        t, v, error = compress_trace(values[:, 0], values[:, column])
        sources.append(pwl_voltage(name, t, v))
        compression[name] = {"kept_points": len(t), "max_error_v": error}
    lines, removed = [], []
    for line in source.splitlines():
        if line.startswith(("Ainputs ", "Asar ", "Aoutputs ", ".model logic_in ", ".model logic_out ", ".model sar_model ")):
            removed.append(line)
            continue
        if line.startswith(".options "):
            # XSPICE reduced trtol to 1 in the reference; preserve it explicitly
            # when there are no XSPICE devices left. Other tolerances untouched.
            line += " trtol=1"
        if line == ".control":
            lines.extend(sources)
        lines.append(line)
    if len(removed) != 6:
        raise ValueError("unexpected bridge removal set")
    result = "\n".join(lines) + "\n"
    if any(line.startswith("A") for line in lines):
        raise ValueError("unexpected XSPICE devices remain")
    if "XADC inp inn decision decision_b" not in result or "XPHASE sample top_sample" not in result:
        raise ValueError("real ADC or phase generator was removed")
    if any(name in OUTPUTS for name in ("decision", "decision_b", "top_sample", "acq", "conv", "rp", "rn", "vcm")):
        raise ValueError("analog node is not an allowed speculative driver")
    return result, compression, removed


def start_directory(label):
    directory = HERE / "results" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + label)
    directory.mkdir(parents=True)
    return directory


def execute(directory, deck, label, expected_codes, timeout=360):
    if directory.exists() and (directory / "summary.json").exists():
        raise ValueError("immutable experiment already exists")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "adc.spice").write_text(deck)
    (directory / ".spiceinit").write_bytes((BASELINE / ".spiceinit").read_bytes())
    (directory / "trace_replay.py").write_bytes(Path(__file__).read_bytes())
    sc.write_json(directory / "summary.json", {"status": "RUNNING", "scope": label, "complete_adc_qualified": False})
    start = time.monotonic()
    try:
        proc = subprocess.run(["ngspice", "-b", "-o", "native.log", "adc.spice"], cwd=directory,
            env=dict(os.environ, SPICE_USERINIT_DIR=str(directory)), capture_output=True, text=True, timeout=timeout)
        rc, log = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as error:
        rc, log = None, "TIMEOUT\n" + (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
    elapsed = time.monotonic() - start
    if (directory / "native.log").exists():
        log += (directory / "native.log").read_text(errors="replace")
    (directory / "simulation.log").write_text(log)
    result = {"status": "INCOMPLETE", "scope": label, "wall_seconds": elapsed, "returncode": rc,
              "complete_adc_qualified": False, "live_rtl_inside_analog_run": label == "live_record",
              "expected_codes_are_predictions_not_measurements": label != "live_record"}
    waveform = directory / "waveform.dat"
    if rc == 0 and waveform.exists():
        values = np.loadtxt(waveform, skiprows=1)
        if values.ndim == 2 and values.shape[1] == len(save_vectors(deck)) + 1 and values[-1, 0] >= 62e-6 - 1e-12:
            result["status"] = "TRANSISTOR_WAVEFORM_COMPLETE_NOT_CERTIFIED"
            result["time_step_statistics"] = tc.time_step_statistics(values)
            result["rows"] = len(values)
            result["expected_codes"] = expected_codes
    result["source_and_output_sha256"] = {p.name: sc.sha(p) for p in directory.iterdir() if p.is_file() and p.name != "summary.json"}
    sc.write_json(directory / "summary.json", result)
    print(json.dumps({"directory": str(directory), "status": result["status"], "seconds": elapsed,
                      "rows": result.get("rows")}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("live", "replay"))
    parser.add_argument("--live-directory", type=Path)
    args = parser.parse_args()
    source, plan, record = read_original()
    if sc.runtime_identity() != json.loads((CAMPAIGN / "runtime.json").read_text()):
        raise ValueError("PDK or tool identity changed")
    if args.stage == "live":
        directory = start_directory("live")
        sc.write_json(directory / "provenance.json", {"original_deck_sha256": sc.sha(BASELINE / "adc.spice"),
            "plan_sha256": plan["plan_sha256"], "runtime_sha256": sc.sha(CAMPAIGN / "runtime.json"),
            "binary_sha256": sc.sha(CAMPAIGN / "build/cosim_controller.so"), "allowed_core_changes": []})
        execute(directory, instrument(source), "live_record", record["raw_codes"])
    else:
        if args.live_directory is None:
            parser.error("--live-directory required")
        live = args.live_directory.resolve()
        previous = json.loads((live / "summary.json").read_text())
        if previous["status"] != "TRANSISTOR_WAVEFORM_COMPLETE_NOT_CERTIFIED":
            raise ValueError("live trace did not complete")
        for name, expected in previous["source_and_output_sha256"].items():
            if sc.sha(live / name) != expected:
                raise ValueError("live evidence changed")
        deck, compression, removed = replay_deck((live / "adc.spice").read_text(), live / "waveform.dat")
        directory = start_directory("replay")
        sc.write_json(directory / "provenance.json", {"live_directory": str(live), "live_summary_sha256": sc.sha(live / "summary.json"),
            "compressed_driver_errors": compression, "removed_testbench_lines": removed,
            "real_comparator_phase_cdac_and_switches_preserved": True, "predictive_capability_tested": False})
        execute(directory, deck, "known_live_trace_replay", previous["expected_codes"])


if __name__ == "__main__":
    main()
