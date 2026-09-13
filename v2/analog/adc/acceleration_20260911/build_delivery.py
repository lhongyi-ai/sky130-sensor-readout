#!/usr/bin/env python3
"""Build the machine-readable audit and hash manifest for this bounded study."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acc = load_module("acceleration_builder", HERE / "accelerate.py")
gate_module = load_module("acceleration_gate_builder", HERE / "gate.py")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def common_grid_report(reference, candidate, vectors):
    grid = np.arange(62001, dtype=float) * 1e-9
    grid[-1] = min(reference[-1, 0], candidate[-1, 0])
    pre = np.asarray([3.8146e-6 + frame * 10e-6 + bit * 625e-9 for frame in range(6) for bit in range(12)])
    channels = {
        "cdac_differential": ("v(xadc.tp)", "v(xadc.tn)"),
        "rp": ("v(rp)",),
        "rn": ("v(rn)",),
        "vcm": ("v(vcm)",),
    }
    result = {}
    for name, labels in channels.items():
        def signal(values, times):
            value = np.interp(times, values[:, 0], values[:, vectors.index(labels[0]) + 1])
            if len(labels) == 2:
                value -= np.interp(times, values[:, 0], values[:, vectors.index(labels[1]) + 1])
            return value
        delta = signal(candidate, grid) - signal(reference, grid)
        pre_delta = signal(candidate, pre) - signal(reference, pre)
        result[name] = {
            "one_ns_grid_max_error_v": float(np.max(np.abs(delta))),
            "predecision_max_error_v": float(np.max(np.abs(pre_delta))),
            "worst_one_ns_grid_time_s": float(grid[np.argmax(np.abs(delta))]),
        }
    threshold = 0.05 * acc.LSB
    return {
        "status": "PASS" if max(row["one_ns_grid_max_error_v"] for row in result.values()) <= threshold else "FAIL",
        "threshold_v": threshold,
        "channels": result,
        "scope": "Legacy 1 ns common grid plus all 72 predecision points; union-grid result remains authoritative in the run summary.",
    }


def main():
    reference_summary = read(acc.REFERENCE / "summary.json")
    known_dir = HERE / "results/20260911T082551662858Z_known"
    predicted_dir = HERE / "results/20260911T083114860787Z_predicted"
    known = read(known_dir / "summary.json")
    predicted = read(predicted_dir / "summary.json")
    aborted = []
    for name in ("20260911T082931655937Z_predicted", "20260911T083032868118Z_predicted"):
        directory = HERE / "results" / name
        summary = read(directory / "summary.json")
        log = (directory / "simulation.log").read_text(errors="replace")
        marker = "Timestep too small; time = 3.503e-06, timestep = 2.5e-21"
        if marker not in log:
            raise ValueError("expected preserved timestep diagnosis absent: " + name)
        aborted.append({
            "directory": str(directory),
            "status": summary["status"],
            "wall_seconds": summary["wall_seconds"],
            "failure": marker,
            "waveform_sha256": sha(directory / "waveform.dat"),
        })
    if known["status"] != "NUMERICAL_GATE_FAIL":
        raise ValueError("known event replay status changed")
    if predicted["status"] != "PREDICTED_TRACE_ACCEPTED":
        raise ValueError("independent prediction status changed")

    reference_deck, vectors, reference_values, _ = acc.load_reference()
    known_values = np.loadtxt(known_dir / "waveform.dat", skiprows=1)
    traces = acc.known_traces(vectors, reference_values)
    events = sum(len(value[1]) for value in traces.values())
    event_points = sum(2 + 2 * len(value[1]) for value in traces.values())
    old_replay_provenance = read(acc.CLOSURE / "results/20260911T080430354263Z_replay/provenance.json")
    old_points = sum(row["kept_points"] for row in old_replay_provenance["compressed_driver_errors"].values())

    old_wall = reference_summary["wall_seconds"]
    new_wall = known["wall_seconds"]
    analysis = known["rusage"]["Total analysis time (seconds)"]
    matrix = sum(known["rusage"][key] for key in ("Matrix load time", "Matrix factor time", "Matrix solve time"))
    required_inputs = 4096 * 32 + 1
    required_decisions = required_inputs * 12
    report = {
        "scope": "Four actual ngspice processes maximum: one known event replay, two preserved predicted-fixture aborts, and one completed independent predicted trace. A PATH launch failure started no simulator and is listed separately.",
        "complete_adc_qualified": False,
        "full_code_problem_resolved": False,
        "long_all_code_gate": gate_module.evaluate_gate(),
        "event_compression": {
            "outputs": 33,
            "logic_edges": events,
            "pwl_points": event_points,
            "old_rdp_pwl_points": old_points,
            "point_count_reduction": old_points / event_points,
            "source_reconstruction_max_error_v": known["source_reconstruction_gate"]["maximum_v"],
            "source_threshold_v": 0.05 * acc.LSB,
            "source_gate": known["source_reconstruction_gate"]["status"],
        },
        "known_trace_real_spice": {
            "directory": str(known_dir),
            "status": known["status"],
            "wall_seconds": new_wall,
            "fixed_shim_reference_wall_seconds": old_wall,
            "observed_speedup": old_wall / new_wall,
            "accepted_real_comparator_decisions": known["decision_certificate"]["accepted_decisions"],
            "required_real_comparator_decisions": 72,
            "union_accepted_point_numeric_gate": known["analog_equivalence"],
            "legacy_one_ns_and_predecision_view": common_grid_report(reference_values, known_values, vectors),
        },
        "independent_prediction": {
            "directory": str(predicted_dir),
            "status": predicted["status"],
            "input_differential_v": [-0.4 + (word + 0.5) * acc.LSB for word in predicted["expected_codes"]],
            "predicted_codes": predicted["expected_codes"],
            "accepted_real_comparator_decisions": predicted["decision_certificate"]["accepted_decisions"],
            "required_real_comparator_decisions": 72,
            "negative_test": predicted["negative_test"],
            "wall_seconds": predicted["wall_seconds"],
            "claim_limit": "Finite six-input conditional trace certificate, not all-code or live-RTL-in-loop signoff.",
        },
        "preserved_failures": {
            "no_process_launch": str(HERE / "results/20260911T082521485574Z_known"),
            "actual_spice_aborts": aborted,
        },
        "profile": {
            "deck_lines": 117632,
            "circuit_equations": 3703,
            "accepted_timepoints": known["rusage"]["Accepted timepoints"],
            "total_iterations": known["rusage"]["Total iterations"],
            "analysis_seconds": analysis,
            "wall_seconds": new_wall,
            "matrix_load_factor_solve_seconds": matrix,
            "matrix_fraction_of_analysis": matrix / analysis,
            "nonanalysis_wall_seconds": new_wall - analysis,
            "optimistic_speedup_if_all_nonanalysis_and_output_cost_vanished": new_wall / analysis,
            "interpretation": "Saving fewer nodes can reduce about 95 MB/6 conversions of raw output, but cannot remove the dominant nonlinear matrix work.",
        },
        "full_grid_lower_bound": {
            "required_inputs": required_inputs,
            "required_real_comparator_decisions": required_decisions,
            "single_worker_days_from_observed_known_run": required_inputs * (new_wall / 6) / 86400,
            "single_worker_days_even_if_nonanalysis_cost_vanished": required_inputs * (analysis / 6) / 86400,
            "naive_raw_waveform_storage_tb_decimal": (known_dir / "waveform.dat").stat().st_size / 6 * required_inputs / 1e12,
            "limitations": [
                "This is an optimistic continuous-run linear extrapolation, not a promised runtime.",
                "The resumable batch runner's history replay/warmup estimate remains about 96.86 days for batch size 8.",
                "Tighter numerical controls required to pass 0.05 LSB may increase runtime.",
            ],
        },
        "source_binding": {
            "fixed_shim_reference": str(acc.REFERENCE),
            "fixed_shim_reference_hashes": {name: sha(acc.REFERENCE / name) for name in ("adc.spice", "waveform.dat", "summary.json", "bridge_certificate.json", ".spiceinit")},
            "current_runner_sha256": sha(HERE / "accelerate.py"),
            "exact_executed_decks_are_preserved_per_result": True,
            "pdk_or_restricted_files_copied": False,
        },
    }
    report_path = HERE / "results/delivery_report.json"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")

    entries = {}
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name == "manifest.json" or "__pycache__" in path.parts:
            continue
        relative = str(path.relative_to(HERE))
        entries[relative] = {"bytes": path.stat().st_size, "sha256": sha(path)}
    manifest = {
        "schema": 1,
        "scope": "Every file in acceleration_20260911 except this self-referential manifest and Python bytecode caches.",
        "files": entries,
        "file_count": len(entries),
        "total_bytes": sum(row["bytes"] for row in entries.values()),
        "complete_adc_qualified": False,
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"report": str(report_path), "manifest": str(HERE / "manifest.json"), "files": len(entries), "bytes": manifest["total_bytes"]}, indent=2))


if __name__ == "__main__":
    main()
