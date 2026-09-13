#!/usr/bin/env python3
"""Bounded event-trace experiments for the frozen transistor SAR ADC.

The generated PWL sources replace only the XSPICE testbench bridge.  The real
SKY130 CDAC, switches, phase generator, preamplifier and dynamic comparator are
left in the deck.  A predicted trace is evidence only when every real Q/QB
decision accepts the prediction; it is never treated as a measured all-code
result by itself.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import numpy as np


HERE = Path(__file__).resolve().parent
CLOSURE = HERE.parent / "closure_20260911"
REFERENCE = CLOSURE / "results/20260911T081221912898Z_bridge_fixed"
LSB = 0.8 / 4096
VDD = 1.8
EDGE_S = 1e-9
OUTPUTS = (
    ["ready", "busy", "valid"]
    + [f"data{i}" for i in range(11, -1, -1)]
    + ["dgain1", "dgain0", "gain1", "gain0", "sample"]
    + [f"trial{i}" for i in range(11, -1, -1)]
    + ["evaluate"]
)
# Six code centres not present in the old trace.  The first experiment used an
# extreme code (127) and the transistor solver stopped at the first hold edge;
# these still span both polarities but avoid treating overload recovery as an
# acceleration result.
PREDICTED_WORDS = [3000, 1601, 1907, 2203, 2557, 3311]
NGSPICE = shutil.which("ngspice") or "/foss/tools/bin/ngspice"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def save_vectors(deck: str) -> list[str]:
    rows = [line for line in deck.splitlines() if line.startswith(".save ")]
    if len(rows) != 1:
        raise ValueError("expected exactly one .save row")
    return rows[0].split()[1:]


def load_reference():
    deck_path = REFERENCE / "adc.spice"
    wave_path = REFERENCE / "waveform.dat"
    summary_path = REFERENCE / "summary.json"
    certificate_path = REFERENCE / "bridge_certificate.json"
    for path in (deck_path, wave_path, summary_path, certificate_path, REFERENCE / ".spiceinit"):
        if not path.exists():
            raise FileNotFoundError(path)
    summary = json.loads(summary_path.read_text())
    if summary.get("status") != "TRANSISTOR_WAVEFORM_COMPLETE_NOT_CERTIFIED":
        raise ValueError("fixed-shim reference is not a completed bounded waveform")
    for name, expected in summary["source_and_output_sha256"].items():
        if sha(REFERENCE / name) != expected:
            raise ValueError("fixed-shim reference changed: " + name)
    deck = deck_path.read_text()
    vectors = save_vectors(deck)
    values = np.loadtxt(wave_path, skiprows=1)
    if values.ndim != 2 or values.shape[1] != len(vectors) + 1:
        raise ValueError("fixed-shim waveform/vector mismatch")
    return deck, vectors, values, summary


def crossings(times: np.ndarray, values: np.ndarray, level: float) -> np.ndarray:
    rows = np.flatnonzero((values[:-1] - level) * (values[1:] - level) < 0)
    result = []
    for row in rows:
        result.append(
            times[row]
            + (times[row + 1] - times[row])
            * (level - values[row])
            / (values[row + 1] - values[row])
        )
    return np.asarray(result)


def trace_from_reference(times: np.ndarray, values: np.ndarray):
    """Recover exact one-nanosecond bridge ramps from their 0.9 V crossings."""
    initial = VDD if values[0] > VDD / 2 else 0.0
    rows = np.flatnonzero((values[:-1] - VDD / 2) * (values[1:] - VDD / 2) < 0)
    events = []
    for row in rows:
        middle = (
            times[row]
            + (times[row + 1] - times[row])
            * (VDD / 2 - values[row])
            / (values[row + 1] - values[row])
        )
        target = VDD if values[row + 1] > values[row] else 0.0
        events.append((float(middle - EDGE_S / 2), target))
    return initial, events


def trace_from_changes(initial_bit: int, changes: list[tuple[float, int]]):
    current = int(initial_bit)
    events = []
    for when, target in sorted(changes):
        target = int(target)
        if target not in (0, 1):
            raise ValueError("logic trace is not binary")
        if target != current:
            events.append((float(when), VDD * target))
            current = target
    return VDD * initial_bit, events


def pwl_source(name: str, initial: float, events: list[tuple[float, float]], stop_s: float) -> str:
    pairs = [(0.0, initial)]
    current = initial
    for start, target in events:
        if start < pairs[-1][0] or start + EDGE_S > stop_s + 1e-15:
            raise ValueError(f"invalid edge time for {name}")
        pairs.extend(((start, current), (start + EDGE_S, target)))
        current = target
    if pairs[-1][0] < stop_s:
        pairs.append((stop_s, current))
    body = " ".join(f"{t:.17g} {v:.17g}" for t, v in pairs)
    return f"VTRACE_{name} {name} 0 PWL({body})"


def known_traces(vectors: list[str], values: np.ndarray):
    result = {}
    for name in OUTPUTS:
        column = vectors.index(f"v({name})") + 1
        result[name] = trace_from_reference(values[:, 0], values[:, column])
    return result


def predicted_traces(base, words: list[int]):
    """Apply the frozen SAR recurrence to new predicted result words."""
    if len(words) != 6 or any(not 0 <= word <= 4095 for word in words):
        raise ValueError("bounded predicted fixture requires six 12-bit words")
    result = dict(base)
    # Reuse the measured bridge event lattice for simultaneous controller
    # outputs.  Writing mathematically equal decimal times next to recovered
    # floating-point times created an artificial ~2.5e-21 s breakpoint and
    # ngspice correctly refused to step through it in the first two attempts.
    control_events = []
    for name in ("sample", "evaluate", "valid"):
        control_events.extend(start for start, _ in base[name][1])

    def on_lattice(nominal: float) -> float:
        close = [event for event in control_events if abs(event - nominal) <= 2e-12]
        if not close:
            raise ValueError(f"no frozen bridge event near {nominal}")
        return min(close, key=lambda event: abs(event - nominal))

    # trial_code before bit b is the already-decided prefix plus a one in b.
    trial_changes = {bit: [] for bit in range(12)}
    data_changes = {bit: [] for bit in range(12)}
    for frame, word in enumerate(words):
        offset = frame * 10e-6
        for position in range(12):
            bit = 11 - position
            trial = (word & ~((1 << (bit + 1)) - 1)) | (1 << bit)
            when = on_lattice(3.503e-6 + offset + position * 625e-9)
            for wire in range(12):
                trial_changes[wire].append((when, (trial >> wire) & 1))
        end = on_lattice(11.003e-6 + offset)
        for wire in range(12):
            trial_changes[wire].append((end, 0))
            data_changes[wire].append((end, (word >> wire) & 1))
    for wire in range(12):
        result[f"trial{wire}"] = trace_from_changes(0, trial_changes[wire])
        result[f"data{wire}"] = trace_from_changes(0, data_changes[wire])
    return result


def input_pwl(words: list[int], sign: int) -> str:
    diffs = [-0.4 + (word + 0.5) * LSB for word in words]
    values = [0.9 + sign * diff / 2 for diff in diffs]
    pairs = [(0.0, values[0])]
    for frame, value in enumerate(values[1:], 1):
        change = 11.014e-6 + (frame - 1) * 10e-6
        pairs.extend(((change, values[frame - 1]), (change + EDGE_S, value)))
    return "PWL(" + " ".join(f"{t:.17g} {v:.17g}" for t, v in pairs) + ")"


def make_deck(mode: str):
    source, vectors, reference, summary = load_reference()
    traces = known_traces(vectors, reference)
    expected = summary["expected_codes"]
    if mode == "predicted":
        traces = predicted_traces(traces, PREDICTED_WORDS)
        expected = PREDICTED_WORDS
    stop_s = float(reference[-1, 0])
    sources = [pwl_source(name, *traces[name], stop_s) for name in OUTPUTS]
    removed = []
    lines = []
    for line in source.splitlines():
        if line.startswith((
            "Ainputs ",
            "Asar ",
            "Aoutputs ",
            ".model logic_in ",
            ".model logic_out ",
            ".model sar_model ",
        )):
            removed.append(line)
            continue
        if line.startswith(".options "):
            line += " trtol=1"
        if mode == "predicted" and line.startswith("VIP sp 0 "):
            line = "VIP sp 0 " + input_pwl(PREDICTED_WORDS, +1)
        if mode == "predicted" and line.startswith("VIN sn 0 "):
            line = "VIN sn 0 " + input_pwl(PREDICTED_WORDS, -1)
        if line == ".control":
            lines.extend(sources)
        lines.append(line)
    deck = "\n".join(lines) + "\n"
    if len(removed) != 6 or re.search(r"^A(inputs|sar|outputs) ", deck, re.M):
        raise ValueError("testbench bridge removal was incomplete")
    required = ("XPHASE sample", "XADC inp inn decision decision_b", "v(decision)", "v(decision_b)")
    if any(token not in deck for token in required):
        raise ValueError("a real analog block or comparator observation was removed")
    return deck, vectors, reference, expected, traces, removed


def reconstructed_source_error(vectors, reference, traces):
    rows = {}
    for name in OUTPUTS:
        column = vectors.index(f"v({name})") + 1
        initial, events = traces[name]
        tt = [0.0]
        vv = [initial]
        current = initial
        for start, target in events:
            tt.extend((start, start + EDGE_S))
            vv.extend((current, target))
            current = target
        tt.append(reference[-1, 0])
        vv.append(current)
        rebuilt = np.interp(reference[:, 0], tt, vv)
        rows[name] = float(np.max(np.abs(rebuilt - reference[:, column])))
    maximum = max(rows.values())
    return {
        "status": "PASS" if maximum <= 0.05 * LSB else "FAIL",
        "threshold_v": 0.05 * LSB,
        "maximum_v": maximum,
        "per_output_max_v": rows,
        "scope": "Every accepted time point in the fixed-shim reference, before analog rerun",
    }


def parse_rusage(log: str):
    wanted = (
        "Total elapsed time (seconds)",
        "Total iterations",
        "Transient timepoints",
        "Accepted timepoints",
        "Rejected timepoints",
        "Total analysis time (seconds)",
        "Matrix load time",
        "Matrix factor time",
        "Matrix solve time",
        "Transient trunc time",
    )
    result = {}
    for key in wanted:
        match = re.search(r"^" + re.escape(key) + r"\s*=\s*([-+0-9.eE]+)", log, re.M)
        if match:
            result[key] = float(match.group(1))
    return result


def comparator_certificate(values: np.ndarray, vectors: list[str], expected: list[int]):
    time = values[:, 0]
    q = values[:, vectors.index("v(decision)") + 1]
    qb = values[:, vectors.index("v(decision_b)") + 1]
    eval_v = values[:, vectors.index("v(evaluate)") + 1]
    valid_v = values[:, vectors.index("v(valid)") + 1]
    evaluate = crossings(time, eval_v, 0.18)
    valid = crossings(time, valid_v, 0.9)
    evaluate = np.asarray([t for t in evaluate if np.interp(t + 1e-12, time, eval_v) > np.interp(t - 1e-12, time, eval_v)])
    valid = np.asarray([t for t in valid if np.interp(t + 1e-12, time, valid_v) > np.interp(t - 1e-12, time, valid_v)])
    target_eval = np.asarray([3.8156e-6 + f * 10e-6 + p * 625e-9 for f in range(6) for p in range(12)])
    target_valid = np.asarray([11.0035e-6 + f * 10e-6 for f in range(6)])
    timing_ok = len(evaluate) == 72 and len(valid) == 6
    if timing_ok:
        timing_ok = max(np.max(np.abs(evaluate - target_eval)), np.max(np.abs(valid - target_valid))) <= 1e-9
    decisions = []
    for frame, word in enumerate(expected):
        result_edge = 11.0035e-6 + frame * 10e-6
        for position in range(12):
            bit = 11 - position
            # The comparator evaluates during the low clock half-cycle.  The
            # unchanged RTL samples it at the following rising edge; that read
            # window, rather than the evaluate rising edge, is certified.
            centre = result_edge - bit * 625e-9
            sample_times = np.linspace(centre - 10e-9, centre + 10e-9, 41)
            qv = np.interp(sample_times, time, q)
            qbv = np.interp(sample_times, time, qb)
            high = qv.min() >= 0.8 * VDD and qbv.max() <= 0.2 * VDD
            low = qv.max() <= 0.2 * VDD and qbv.min() >= 0.8 * VDD
            observed = 1 if high else 0 if low else None
            predicted = (word >> bit) & 1
            decisions.append({
                "frame": frame,
                "bit": bit,
                "predicted": predicted,
                "observed": observed,
                "accepted": observed == predicted,
                "q_min_v": float(qv.min()),
                "q_max_v": float(qv.max()),
                "qb_min_v": float(qbv.min()),
                "qb_max_v": float(qbv.max()),
            })
    accepted = sum(row["accepted"] for row in decisions)
    return {
        "status": "PASS" if timing_ok and accepted == 72 else "FAIL",
        "timing_ok": bool(timing_ok),
        "accepted_decisions": accepted,
        "required_decisions": 72,
        "decisions": decisions,
        "scope": "Real transistor Q/QB across +/-10 ns around all 72 evaluate windows",
    }


def analog_comparison(reference: np.ndarray, candidate: np.ndarray, vectors: list[str]):
    threshold = 0.05 * LSB
    # Compare on both solvers' accepted points.  This is stricter than the old
    # 1 ns reporting grid, while remaining a finite saved-waveform comparison.
    grid = np.unique(np.r_[reference[:, 0], candidate[:, 0]])
    channels = {
        "cdac_differential": ("v(xadc.tp)", "v(xadc.tn)"),
        "reference_positive": ("v(rp)",),
        "reference_negative": ("v(rn)",),
        "reference_common_mode": ("v(vcm)",),
    }
    reports = {}
    for name, labels in channels.items():
        def signal(values):
            first = np.interp(grid, values[:, 0], values[:, vectors.index(labels[0]) + 1])
            if len(labels) == 2:
                first -= np.interp(grid, values[:, 0], values[:, vectors.index(labels[1]) + 1])
            return first
        delta = signal(candidate) - signal(reference)
        reports[name] = {
            "max_error_v": float(np.max(np.abs(delta))),
            "worst_time_s": float(grid[np.argmax(np.abs(delta))]),
        }
    maximum = max(row["max_error_v"] for row in reports.values())
    return {
        "status": "PASS" if maximum <= threshold else "FAIL",
        "threshold_v": threshold,
        "maximum_v": maximum,
        "channels": reports,
        "grid": "union of every accepted time point from reference and candidate, linearly interpolated",
        "limitation": "Finite saved points are not a continuous-time mathematical bound.",
    }


def run(mode: str, timeout: float):
    deck, vectors, reference, expected, traces, removed = make_deck(mode)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    directory = HERE / "results" / f"{timestamp}_{mode}"
    directory.mkdir(parents=True)
    (directory / "adc.spice").write_text(deck)
    (directory / ".spiceinit").write_bytes((REFERENCE / ".spiceinit").read_bytes())
    source_gate = reconstructed_source_error(vectors, reference, traces) if mode == "known" else None
    provenance = {
        "mode": mode,
        "reference_directory": str(REFERENCE),
        "reference_sha256": {name: sha(REFERENCE / name) for name in ("adc.spice", "waveform.dat", "summary.json", "bridge_certificate.json", ".spiceinit")},
        "runner_sha256": sha(Path(__file__)),
        "removed_testbench_bridge_lines": removed,
        "preserved_real_blocks": ["sensor_phases", "sensor_adc_candidate", "CDAC", "sampling/reference switches", "preamp", "dynamic comparator"],
        "expected_codes": expected,
        "predicted_inputs_v": [-0.4 + (word + 0.5) * LSB for word in expected] if mode == "predicted" else None,
        "source_reconstruction_gate": source_gate,
        "complete_adc_qualified": False,
    }
    write_json(directory / "provenance.json", provenance)
    write_json(directory / "summary.json", {"status": "RUNNING", "mode": mode, "complete_adc_qualified": False})
    began = time.monotonic()
    try:
        process = subprocess.run(
            [NGSPICE, "-b", "-o", "native.log", "adc.spice"],
            cwd=directory,
            env=dict(os.environ, SPICE_USERINIT_DIR=str(directory)),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        returncode = process.returncode
        text = process.stdout + process.stderr
    except subprocess.TimeoutExpired as error:
        returncode = None
        text = "TIMEOUT\n" + (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
    wall = time.monotonic() - began
    if (directory / "native.log").exists():
        text += (directory / "native.log").read_text(errors="replace")
    (directory / "simulation.log").write_text(text)
    result = {
        "status": "INCOMPLETE",
        "mode": mode,
        "returncode": returncode,
        "wall_seconds": wall,
        "expected_codes": expected,
        "complete_adc_qualified": False,
        "rusage": parse_rusage(text),
    }
    waveform = directory / "waveform.dat"
    if returncode == 0 and waveform.exists():
        values = np.loadtxt(waveform, skiprows=1)
        if values.ndim == 2 and values.shape[1] == len(vectors) + 1 and values[-1, 0] >= 62e-6 - 1e-12:
            result["rows"] = len(values)
            result["decision_certificate"] = comparator_certificate(values, vectors, expected)
            if mode == "known":
                result["source_reconstruction_gate"] = source_gate
                result["analog_equivalence"] = analog_comparison(reference, values, vectors)
                gates = [source_gate["status"], result["analog_equivalence"]["status"], result["decision_certificate"]["status"]]
                result["status"] = "BOUNDED_EQUIVALENCE_PASS" if all(x == "PASS" for x in gates) else "NUMERICAL_GATE_FAIL"
            else:
                negative = comparator_certificate(values, vectors, [expected[0] ^ 1] + expected[1:])
                result["negative_test"] = {
                    "mutation": "flip predicted LSB of frame 0 without changing the saved transistor waveform",
                    "status": "PASS" if negative["status"] == "FAIL" and negative["accepted_decisions"] == 71 else "FAIL",
                    "accepted_decisions_after_mutation": negative["accepted_decisions"],
                }
                result["status"] = "PREDICTED_TRACE_ACCEPTED" if result["decision_certificate"]["status"] == "PASS" and result["negative_test"]["status"] == "PASS" else "PREDICTED_TRACE_REJECTED"
    result["artifact_sha256"] = {p.name: sha(p) for p in directory.iterdir() if p.is_file() and p.name != "summary.json"}
    write_json(directory / "summary.json", result)
    print(json.dumps({"directory": str(directory), "status": result["status"], "seconds": wall, "rows": result.get("rows"), "decisions": result.get("decision_certificate", {}).get("accepted_decisions"), "analog_max_v": result.get("analog_equivalence", {}).get("maximum_v")}, indent=2))
    return 0 if result["status"] in ("BOUNDED_EQUIVALENCE_PASS", "PREDICTED_TRACE_ACCEPTED") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("known", "predicted"))
    parser.add_argument("--timeout", type=float, default=360)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 360:
        parser.error("timeout must be 1..360 seconds")
    raise SystemExit(run(args.mode, args.timeout))


if __name__ == "__main__":
    main()
