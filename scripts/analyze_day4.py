#!/usr/bin/env python3
"""Audit and aggregate the complete Day 4 OTA characterization campaign."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "day4"
GENERATED = ROOT / "results" / "generated" / "day4"
PLOTS = ROOT / "results" / "plots"
RESULTS = ROOT / "results"

PVT_POINTS = (
    ("P01", "TT", 1.80, 27, "Nominal"),
    ("P02", "FF", 1.80, 27, "Process sweep"),
    ("P03", "SS", 1.80, 27, "Process sweep"),
    ("P04", "FS", 1.80, 27, "Process sweep"),
    ("P05", "SF", 1.80, 27, "Process sweep"),
    ("P06", "TT", 1.62, -20, "Voltage-temperature sweep"),
    ("P07", "TT", 1.62, 27, "Voltage-temperature sweep"),
    ("P08", "TT", 1.62, 85, "Voltage-temperature sweep"),
    ("P09", "TT", 1.80, -20, "Voltage-temperature sweep"),
    ("P10", "TT", 1.80, 85, "Voltage-temperature sweep"),
    ("P11", "TT", 1.98, -20, "Voltage-temperature sweep"),
    ("P12", "TT", 1.98, 27, "Voltage-temperature sweep"),
    ("P13", "TT", 1.98, 85, "Voltage-temperature sweep"),
)

DEVICE_ROLES = {
    1: "NMOS input, VINN side",
    2: "NMOS input, VINP side",
    3: "PMOS diode mirror load, two units",
    4: "PMOS mirror output load, two units",
    5: "NMOS tail current source",
    6: "NMOS second-stage gain device",
    7: "PMOS second-stage current source",
    8: "PMOS diode IREF reference",
    9: "PMOS VBN-bias current source",
    10: "NMOS diode VBN reference",
}


def load_manifest() -> tuple[dict[str, Any], str]:
    manifest = json.loads((GENERATED / "day4_manifest.json").read_text(encoding="utf-8"))
    claimed = str(manifest["manifest_sha256"])
    payload = {key: value for key, value in manifest.items() if key not in ("manifest_sha256", "hash_definition")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    calculated = hashlib.sha256(canonical).hexdigest()
    if calculated != claimed:
        raise ValueError(f"Day 4 manifest hash mismatch: {claimed} versus {calculated}")
    source_path = ROOT / str(manifest["source_of_design_truth"])
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if source_hash != manifest["source_sha256"]:
        raise ValueError("Day 3 selected-parameter source changed after Day 4 decks were rendered")
    decks = sorted(GENERATED.rglob("*.spice"))
    if len(decks) != 172:
        raise ValueError(f"Expected 172 generated SPICE files including the shared subcircuit, found {len(decks)}")
    for deck in decks:
        if f"DAY4_MANIFEST_SHA256={claimed}" not in deck.read_text(encoding="utf-8"):
            raise ValueError(f"Generated deck lacks the selected manifest hash: {deck}")
    return manifest, claimed


MANIFEST, MANIFEST_HASH = load_manifest()


def numeric_rows(path: Path, expected_columns: int) -> np.ndarray:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        tokens = line.split()
        if tokens and tokens[-1] == MANIFEST_HASH:
            tokens = tokens[:-1]
        if len(tokens) != expected_columns:
            continue
        try:
            values = [float(token) for token in tokens]
        except ValueError:
            continue
        if not np.all(np.isfinite(values)):
            raise ValueError(f"Non-finite numeric row in {path}")
        rows.append(values)
    if not rows:
        raise ValueError(f"No {expected_columns}-column numeric rows in {path}")
    return np.asarray(rows, dtype=float)


def write_result(frame: pd.DataFrame, filename: str) -> Path:
    frame = frame.copy()
    if "manifest_sha256" in frame.columns:
        frame["manifest_sha256"] = MANIFEST_HASH
    else:
        frame["manifest_sha256"] = MANIFEST_HASH
    path = RESULTS / filename
    frame.to_csv(path, index=False, float_format="%.10g")
    return path


def complex_curve(path: Path, vector_name: str) -> pd.DataFrame:
    data = numeric_rows(path, 7)
    vector = data[:, 1] + 1j * data[:, 2]
    stimulus = data[:, 3] + 1j * data[:, 4]
    output = data[:, 5] + 1j * data[:, 6]
    return pd.DataFrame(
        {
            "frequency_hz": data[:, 0],
            f"{vector_name}_real": vector.real,
            f"{vector_name}_imag": vector.imag,
            f"{vector_name}_magnitude": np.abs(vector),
            f"{vector_name}_db": 20.0 * np.log10(np.maximum(np.abs(vector), np.finfo(float).tiny)),
            "stimulus_real": stimulus.real,
            "stimulus_imag": stimulus.imag,
            "output_real": output.real,
            "output_imag": output.imag,
        }
    )


def interpolate_log_x(x: np.ndarray, y: np.ndarray, x_value: float) -> float:
    return float(np.interp(math.log10(x_value), np.log10(x), y))


def loop_metrics(path: Path) -> tuple[dict[str, float], pd.DataFrame]:
    data = numeric_rows(path, 7)
    frequency = data[:, 0]
    loop = data[:, 1] + 1j * data[:, 2]
    gain_db = 20.0 * np.log10(np.maximum(np.abs(loop), np.finfo(float).tiny))
    phase = np.rad2deg(np.unwrap(np.angle(loop)))
    phase -= round(float(phase[0]) / 360.0) * 360.0
    downward = np.flatnonzero((gain_db[:-1] >= 0.0) & (gain_db[1:] < 0.0))
    all_crossings = np.flatnonzero((gain_db[:-1] * gain_db[1:] <= 0.0) & (gain_db[:-1] != gain_db[1:]))
    metrics: dict[str, float] = {
        "loop_a0_db": float(gain_db[0]),
        "loop_phase_1hz_deg": float(phase[0]),
        "zero_db_downward_crossings": float(len(downward)),
        "zero_db_all_crossings": float(len(all_crossings)),
        "first_downward_crossing_index": math.nan,
        "ugb_crossing_at_boundary": math.nan,
        "ugb_hz": math.nan,
        "phase_at_ugb_deg": math.nan,
        "pm_deg": math.nan,
    }
    if len(downward):
        index = int(downward[0])
        fraction = (0.0 - gain_db[index]) / (gain_db[index + 1] - gain_db[index])
        log_ugb = math.log10(frequency[index]) + fraction * (
            math.log10(frequency[index + 1]) - math.log10(frequency[index])
        )
        ugb = 10.0**log_ugb
        phase_at = float(phase[index] + fraction * (phase[index + 1] - phase[index]))
        metrics.update(
            {
                "ugb_hz": ugb,
                "phase_at_ugb_deg": phase_at,
                "pm_deg": 180.0 + phase_at,
                "first_downward_crossing_index": float(index),
                "ugb_crossing_at_boundary": float(index == 0 or index == len(frequency) - 2),
            }
        )
    curve = pd.DataFrame(
        {
            "frequency_hz": frequency,
            "loop_real": loop.real,
            "loop_imag": loop.imag,
            "gain_db": gain_db,
            "phase_unwrapped_deg": phase,
        }
    )
    return metrics, curve


def crossing_time(
    time_s: np.ndarray, signal_v: np.ndarray, *, level_v: float, start_s: float, stop_s: float, rising: bool
) -> float:
    candidates = np.flatnonzero((time_s[:-1] >= start_s) & (time_s[1:] <= stop_s))
    for index in candidates:
        y0, y1 = float(signal_v[index]), float(signal_v[index + 1])
        directed = y0 <= level_v < y1 if rising else y0 >= level_v > y1
        if directed:
            fraction = 0.0 if y1 == y0 else (level_v - y0) / (y1 - y0)
            return float(time_s[index] + fraction * (time_s[index + 1] - time_s[index]))
    raise ValueError(f"No {'rising' if rising else 'falling'} {level_v}-V crossing")


def fitted_slew(
    time_s: np.ndarray, output_v: np.ndarray, *, start_s: float, stop_s: float, rising: bool
) -> tuple[float, int]:
    first_level, second_level = ((0.88, 1.12) if rising else (1.12, 0.88))
    window = np.flatnonzero((time_s >= start_s) & (time_s < stop_s))
    first_candidates = window[output_v[window] >= first_level] if rising else window[output_v[window] <= first_level]
    if not len(first_candidates):
        raise ValueError("Output did not reach the first slew threshold")
    first = int(first_candidates[0])
    remaining = window[window >= first]
    second_candidates = remaining[output_v[remaining] >= second_level] if rising else remaining[output_v[remaining] <= second_level]
    if not len(second_candidates):
        raise ValueError("Output did not reach the second slew threshold")
    second = int(second_candidates[0])
    indices = np.arange(first, second + 1)
    if len(indices) < 5:
        raise ValueError("Fewer than five points in 20%-80% slew fit")
    differences = np.diff(output_v[indices])
    if rising and np.any(differences < -1e-6):
        raise ValueError("Rising slew interval is not monotonic")
    if not rising and np.any(differences > 1e-6):
        raise ValueError("Falling slew interval is not monotonic")
    slope = float(np.polyfit(time_s[indices], output_v[indices], 1)[0])
    return abs(slope) / 1e6, int(len(indices))


def settling_time(time_s: np.ndarray, output_v: np.ndarray, target_v: float, reference_s: float, stop_s: float) -> float:
    indices = np.flatnonzero((time_s >= reference_s) & (time_s < stop_s))
    if not len(indices):
        return math.nan
    within = np.abs(output_v[indices] - target_v) <= 0.004
    stays = np.logical_and.accumulate(within[::-1])[::-1]
    candidates = indices[np.flatnonzero(stays)]
    return float(time_s[candidates[0]] - reference_s) if len(candidates) else math.nan


def transient_metrics(path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    data = numeric_rows(path, 3)
    time_s, input_v, output_v = data.T
    rise_mid = crossing_time(time_s, input_v, level_v=1.0, start_s=1e-6, stop_s=1.02e-6, rising=True)
    fall_mid = crossing_time(time_s, input_v, level_v=1.0, start_s=3.02e-6, stop_s=3.04e-6, rising=False)
    sr_pos, pos_points = fitted_slew(time_s, output_v, start_s=1e-6, stop_s=2.2e-6, rising=True)
    sr_neg, neg_points = fitted_slew(time_s, output_v, start_s=3e-6, stop_s=4.2e-6, rising=False)
    rise_settle = settling_time(time_s, output_v, 1.2, rise_mid, 3.02e-6)
    fall_settle = settling_time(time_s, output_v, 0.8, fall_mid, 5.0e-6)
    high = output_v[(time_s >= 1.02e-6) & (time_s < 3.02e-6)]
    low = output_v[(time_s >= 3.04e-6) & (time_s <= 5e-6)]
    tail_high = output_v[(time_s >= 2.7e-6) & (time_s < 3.0e-6)]
    tail_low = output_v[(time_s >= 4.7e-6) & (time_s <= 5.0e-6)]
    metrics = {
        "sr_pos_V_per_us": sr_pos,
        "sr_neg_V_per_us": sr_neg,
        "sr_pos_fit_points": float(pos_points),
        "sr_neg_fit_points": float(neg_points),
        "rise_input_50_us": rise_mid * 1e6,
        "fall_input_50_us": fall_mid * 1e6,
        "rise_settling_us": rise_settle * 1e6,
        "fall_settling_us": fall_settle * 1e6,
        "worst_settling_us": max(rise_settle, fall_settle) * 1e6,
        "rise_settling_status": "PASS" if math.isfinite(rise_settle) else "SETTLING_NOT_REACHED",
        "fall_settling_status": "PASS" if math.isfinite(fall_settle) else "SETTLING_NOT_REACHED",
        "settling_status": (
            "SETTLING_NOT_REACHED"
            if not (math.isfinite(rise_settle) and math.isfinite(fall_settle))
            else ("PASS" if max(rise_settle, fall_settle) <= 1.5e-6 else "SETTLING_FAIL")
        ),
        "overshoot_mv": max(0.0, float(np.max(high) - 1.2)) * 1e3,
        "undershoot_mv": max(0.0, float(0.8 - np.min(low))) * 1e3,
        "tail_high_pp_mv": float(np.ptp(tail_high)) * 1e3,
        "tail_low_pp_mv": float(np.ptp(tail_low)) * 1e3,
    }
    return metrics, pd.DataFrame({"time_s": time_s, "vinp_v": input_v, "vout_v": output_v})


def op_columns() -> list[str]:
    columns = [
        "scale", "vout_v", "vx_v", "vbn_v", "vbp_v", "tail_v", "nmir_v", "vinp_v", "vinn_v",
        "ivdd_signed_a", "idd_abs_a",
    ]
    for device in range(1, 11):
        columns += [f"m{device}_id_a", f"m{device}_gm_s", f"m{device}_gds_s", f"m{device}_vdsat_v"]
    return columns


def parse_op(path: Path) -> pd.Series:
    columns = op_columns()
    return pd.DataFrame(numeric_rows(path, len(columns)), columns=columns).iloc[-1]


def saturation_margins(op: pd.Series, vdd: float) -> dict[int, float]:
    return {
        1: float(op["nmir_v"] - op["tail_v"] - op["m1_vdsat_v"]),
        2: float(op["vx_v"] - op["tail_v"] - op["m2_vdsat_v"]),
        3: float(vdd - op["nmir_v"] - op["m3_vdsat_v"]),
        4: float(vdd - op["vx_v"] - op["m4_vdsat_v"]),
        5: float(op["tail_v"] - op["m5_vdsat_v"]),
        6: float(op["vout_v"] - op["m6_vdsat_v"]),
        7: float(vdd - op["vout_v"] - op["m7_vdsat_v"]),
        8: float(vdd - op["vbp_v"] - op["m8_vdsat_v"]),
        9: float(vdd - op["vbn_v"] - op["m9_vdsat_v"]),
        10: float(op["vbn_v"] - op["m10_vdsat_v"]),
    }


def audit_logs() -> tuple[pd.DataFrame, dict[str, bool]]:
    records: list[dict[str, Any]] = []
    status_map: dict[str, bool] = {}
    for deck in sorted(GENERATED.rglob("*.spice")):
        if deck.name == "ota_subckt.spice":
            continue
        relative = deck.relative_to(GENERATED).as_posix()
        stem = relative.removesuffix(".spice")
        log_path = RAW / "logs" / f"{stem}.log"
        exit_path = RAW / "logs" / f"{stem}.exit_code"
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
        try:
            exit_code = int(exit_path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            exit_code = -1
        ngspice_done = "ngspice-47 done" in text
        convergence_failure = bool(
            re.search(r"timestep too small|doanalyses:.*error|failed to converge|singular matrix", text, re.IGNORECASE)
        )
        fatal_error = bool(re.search(r"(^|\n)Error:|fatal error|no such vector", text, re.IGNORECASE))
        dynamic_gmin_count = text.count("Starting dynamic gmin stepping")
        known_multiplier_warning = text.count("m=xx on .subckt line will override multiplier")
        warning_count = len(re.findall(r"^Warning:", text, re.MULTILINE))
        noise_conductance_warning_count = len(re.findall(r"conductance reset to", text, re.IGNORECASE))
        ok = exit_code == 0 and ngspice_done and not convergence_failure and not fatal_error
        status_map[relative] = ok
        if ok and dynamic_gmin_count:
            status = "PASS_WITH_DYNAMIC_GMIN"
        elif ok:
            status = "PASS"
        elif convergence_failure:
            status = "NO_CONVERGENCE"
        elif fatal_error:
            status = "SIMULATION_ERROR"
        elif exit_code == -1:
            status = "MISSING_RUN_RECORD"
        else:
            status = "INCOMPLETE_RUN"
        records.append(
            {
                "deck": f"results/generated/day4/{relative}",
                "log": f"results/raw/day4/logs/{stem}.log",
                "exit_code": exit_code,
                "ngspice_done": ngspice_done,
                "convergence_failure": convergence_failure,
                "fatal_error": fatal_error,
                "dynamic_gmin_start_count": dynamic_gmin_count,
                "known_multiplier_warning_count": known_multiplier_warning,
                "warning_count": warning_count,
                "noise_conductance_reset_warning_count": noise_conductance_warning_count,
                "status": status,
            }
        )
    frame = pd.DataFrame(records)
    write_result(frame, "day4_log_audit.csv")
    return frame, status_map


def first_frequency_gain(path: Path) -> tuple[float, float, pd.DataFrame]:
    curve = complex_curve(path, "ad")
    a0 = float(curve["ad_db"].iloc[0])
    diff_mag = float(np.hypot(curve["stimulus_real"].iloc[0], curve["stimulus_imag"].iloc[0]))
    gain_10hz = interpolate_log_x(curve["frequency_hz"].to_numpy(), curve["ad_db"].to_numpy(), 10.0)
    return a0, diff_mag, curve.assign(gain_flatness_1_to_10hz_db=gain_10hz - a0)


def analyze_pvt(sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    pvt_records: list[dict[str, Any]] = []
    operating_records: list[dict[str, Any]] = []
    loop_curves: dict[str, pd.DataFrame] = {}
    transient_curves: dict[str, pd.DataFrame] = {}
    for point_id, process, vdd, temp, note in PVT_POINTS:
        record: dict[str, Any] = {
            "point_id": point_id,
            "process": process,
            "VDD_V": vdd,
            "temp_C": temp,
            "CL_pF": 5.0,
            "RL_kOhm": 100.0,
            "gain_dB": math.nan,
            "actual_diff_input_at_1Hz_V": math.nan,
            "gain_flatness_1_to_10Hz_dB": math.nan,
            "ugb_MHz": math.nan,
            "pm_deg": math.nan,
            "loop_phase_1Hz_deg": math.nan,
            "zero_dB_downward_crossings": math.nan,
            "zero_dB_all_crossings": math.nan,
            "ivdd_signed_uA": math.nan,
            "power_uW": math.nan,
            "sr_pos_V_per_us": math.nan,
            "sr_neg_V_per_us": math.nan,
            "sr_pos_fit_points": math.nan,
            "sr_neg_fit_points": math.nan,
            "rise_settling_us": math.nan,
            "fall_settling_us": math.nan,
            "worst_settling_us": math.nan,
            "rise_settling_status": "NUMERICAL_INVALID",
            "fall_settling_status": "NUMERICAL_INVALID",
            "settling_status": "NUMERICAL_INVALID",
            "min_saturation_margin_V": math.nan,
            "all_devices_saturated": False,
        }
        exceptions: list[str] = []
        bench_names = {
            "diff": f"pvt/{point_id}_diff_ac.spice",
            "loop": f"pvt/{point_id}_loop.spice",
            "transient": f"pvt/{point_id}_transient.spice",
        }
        for label, deck in bench_names.items():
            if not sim_ok.get(deck, False):
                exceptions.append(f"{label}:NO_CONVERGENCE_OR_SIMULATION_ERROR")
        try:
            a0, diff_mag, diff_curve = first_frequency_gain(RAW / "pvt" / f"{point_id}_diff_ac.tsv")
            record["gain_dB"] = a0
            record["actual_diff_input_at_1Hz_V"] = diff_mag
            record["gain_flatness_1_to_10Hz_dB"] = float(diff_curve["gain_flatness_1_to_10hz_db"].iloc[0])
        except Exception as exc:  # preserve a matrix row even for malformed evidence
            exceptions.append(f"diff:NUMERICAL_INVALID:{exc}")
        try:
            loop, loop_curve = loop_metrics(RAW / "pvt" / f"{point_id}_loop.tsv")
            loop_curves[point_id] = loop_curve
            record.update(
                {
                    "ugb_MHz": loop["ugb_hz"] / 1e6,
                    "pm_deg": loop["pm_deg"],
                    "loop_phase_1Hz_deg": loop["loop_phase_1hz_deg"],
                    "zero_dB_downward_crossings": loop["zero_db_downward_crossings"],
                    "zero_dB_all_crossings": loop["zero_db_all_crossings"],
                    "first_downward_crossing_index": loop["first_downward_crossing_index"],
                    "ugb_crossing_at_boundary": loop["ugb_crossing_at_boundary"],
                }
            )
            if not math.isfinite(loop["ugb_hz"]):
                exceptions.append("loop:NO_0DB_DOWNWARD_CROSSING")
        except Exception as exc:
            exceptions.append(f"loop:NUMERICAL_INVALID:{exc}")
        try:
            op = parse_op(RAW / "pvt" / f"{point_id}_op.tsv")
            margins = saturation_margins(op, vdd)
            record["ivdd_signed_uA"] = float(op["ivdd_signed_a"]) * 1e6
            record["power_uW"] = vdd * float(op["idd_abs_a"]) * 1e6
            record["min_saturation_margin_V"] = min(margins.values())
            record["all_devices_saturated"] = all(value >= 0.0 for value in margins.values())
            for device in range(1, 11):
                current = float(op[f"m{device}_id_a"])
                gm = float(op[f"m{device}_gm_s"])
                gds = float(op[f"m{device}_gds_s"])
                operating_records.append(
                    {
                        "point_id": point_id,
                        "process": process,
                        "VDD_V": vdd,
                        "temp_C": temp,
                        "device": f"M{device}",
                        "role": DEVICE_ROLES[device],
                        "drain_current_uA": current * 1e6,
                        "gm_uS": gm * 1e6,
                        "gds_uS": gds * 1e6,
                        "vdsat_abs_V": float(op[f"m{device}_vdsat_v"]),
                        "saturation_margin_V": margins[device],
                        "saturation_status": "PASS" if margins[device] >= 0.0 else "SATURATION",
                        "vout_V": float(op["vout_v"]),
                        "vx_V": float(op["vx_v"]),
                        "tail_V": float(op["tail_v"]),
                        "nmir_V": float(op["nmir_v"]),
                        "vbn_V": float(op["vbn_v"]),
                        "vbp_V": float(op["vbp_v"]),
                        "ivdd_signed_uA": float(op["ivdd_signed_a"]) * 1e6,
                    }
                )
        except Exception as exc:
            exceptions.append(f"op:NUMERICAL_INVALID:{exc}")
        try:
            transient, curve = transient_metrics(RAW / "pvt" / f"{point_id}_transient.tsv")
            transient_curves[point_id] = curve
            record.update(transient)
        except Exception as exc:
            exceptions.append(f"transient:NUMERICAL_INVALID:{exc}")

        failures: list[str] = []
        tests = (
            ("GAIN_FAIL", record["gain_dB"], lambda x: x >= 50.0),
            ("UGB_FAIL", record["ugb_MHz"], lambda x: x >= 5.0),
            ("PM_FAIL", record["pm_deg"], lambda x: x >= 55.0),
            ("POWER_FAIL", record["power_uW"], lambda x: x <= 600.0),
            ("SR_POS_FAIL", record["sr_pos_V_per_us"], lambda x: x >= 2.0),
            ("SR_NEG_FAIL", record["sr_neg_V_per_us"], lambda x: x >= 2.0),
        )
        for label, value, predicate in tests:
            if not isinstance(value, (int, float, np.floating)) or not math.isfinite(float(value)) or not predicate(float(value)):
                failures.append(label)
        if math.isfinite(float(record["actual_diff_input_at_1Hz_V"])) and not math.isclose(
            float(record["actual_diff_input_at_1Hz_V"]), 1.0, rel_tol=1e-6, abs_tol=1e-6
        ):
            failures.append("DIFFERENTIAL_STIMULUS_FAIL")
        if math.isfinite(float(record["gain_flatness_1_to_10Hz_dB"])) and abs(float(record["gain_flatness_1_to_10Hz_dB"])) > 0.1:
            failures.append("GAIN_PLATEAU_FAIL")
        if not bool(record["all_devices_saturated"]):
            failures.append("SATURATION")
        if math.isfinite(float(record["zero_dB_downward_crossings"])) and float(record["zero_dB_downward_crossings"]) == 0:
            failures.append("NO_0DB_DOWNWARD_CROSSING")
        if math.isfinite(float(record["loop_phase_1Hz_deg"])) and abs(float(record["loop_phase_1Hz_deg"])) > 5.0:
            failures.append("LOOP_SIGN_FAIL")
        if math.isfinite(float(record["zero_dB_downward_crossings"])) and float(record["zero_dB_downward_crossings"]) > 1:
            failures.append("MULTIPLE_0DB_DOWNWARD_CROSSINGS")
        if float(record.get("ugb_crossing_at_boundary", 0.0)) == 1.0:
            failures.append("UGB_CROSSING_AT_BOUNDARY")
        if exceptions:
            if any("NO_CONVERGENCE" in item for item in exceptions):
                run_status = "NO_CONVERGENCE"
            elif any("NO_0DB_DOWNWARD_CROSSING" in item for item in exceptions):
                run_status = "NO_0DB_DOWNWARD_CROSSING"
            else:
                run_status = "NUMERICAL_INVALID"
        elif not bool(record["all_devices_saturated"]):
            run_status = "SATURATION"
        else:
            run_status = "COMPLETE"
        record.update(
            {
                "run_status": run_status,
                "pass_fail": "PASS" if not failures and not exceptions else ";".join(dict.fromkeys(failures + ([run_status] if exceptions else []))),
                "raw_evidence_path": ";".join(
                    [
                        f"results/raw/day4/pvt/{point_id}_diff_ac.tsv",
                        f"results/raw/day4/pvt/{point_id}_loop.tsv",
                        f"results/raw/day4/pvt/{point_id}_op.tsv",
                        f"results/raw/day4/pvt/{point_id}_transient.tsv",
                    ]
                ),
                "notes": (
                    note
                    + ("; " + " | ".join(exceptions) if exceptions else "")
                    + (
                        f"; settling={record['settling_status']}"
                        if record["settling_status"] != "PASS"
                        else ""
                    )
                    + "; external ideal 10-uA IREF"
                ),
            }
        )
        pvt_records.append(record)
    pvt = pd.DataFrame(pvt_records)
    operating = pd.DataFrame(operating_records)
    write_result(pvt, "pvt_summary.csv")
    write_result(operating, "day4_pvt_operating_points.csv")
    return pvt, operating, loop_curves, transient_curves


def response_curve(path: Path, name: str) -> pd.DataFrame:
    data = numeric_rows(path, 7)
    response = data[:, 1] + 1j * data[:, 2]
    stimulus = data[:, 3] + 1j * data[:, 4]
    return pd.DataFrame(
        {
            "frequency_hz": data[:, 0],
            f"{name}_real": response.real,
            f"{name}_imag": response.imag,
            f"{name}_magnitude": np.abs(response),
            "stimulus_magnitude": np.abs(stimulus),
        }
    )


def analyze_rejection() -> tuple[pd.DataFrame, dict[str, float | str]]:
    diff = complex_curve(RAW / "pvt" / "P01_diff_ac.tsv", "ad")
    common = response_curve(RAW / "nominal" / "common_mode.tsv", "acm")
    plus = response_curve(RAW / "nominal" / "psrr_plus.tsv", "aps_plus")
    minus = response_curve(RAW / "nominal" / "psrr_minus.tsv", "aps_minus")
    frequency = diff["frequency_hz"].to_numpy()
    if not (
        np.allclose(frequency, common["frequency_hz"])
        and np.allclose(frequency, plus["frequency_hz"])
        and np.allclose(frequency, minus["frequency_hz"])
    ):
        raise ValueError("Nominal rejection curves do not share an identical frequency grid")
    ad = diff["ad_magnitude"].to_numpy()
    acm = common["acm_magnitude"].to_numpy()
    aps_plus = plus["aps_plus_magnitude"].to_numpy()
    aps_minus = minus["aps_minus_magnitude"].to_numpy()
    cmrr = 20.0 * np.log10(ad / np.maximum(acm, np.finfo(float).tiny))
    psrr_plus = 20.0 * np.log10(ad / np.maximum(aps_plus, np.finfo(float).tiny))
    psrr_minus = 20.0 * np.log10(ad / np.maximum(aps_minus, np.finfo(float).tiny))
    curve = pd.DataFrame(
        {
            "frequency_hz": frequency,
            "ad_magnitude_V_per_V": ad,
            "acm_magnitude_V_per_V": acm,
            "aps_plus_magnitude_V_per_V": aps_plus,
            "aps_minus_magnitude_V_per_V": aps_minus,
            "cmrr_dB": cmrr,
            "psrr_plus_dB": psrr_plus,
            "psrr_minus_dB": psrr_minus,
            "common_mode_stimulus_magnitude_V": common["stimulus_magnitude"].to_numpy(),
            "psrr_plus_stimulus_magnitude_V": plus["stimulus_magnitude"].to_numpy(),
            "psrr_minus_stimulus_magnitude_V": minus["stimulus_magnitude"].to_numpy(),
        }
    )
    write_result(curve, "day4_cmrr_psrr_curves.csv")
    values: dict[str, float | str] = {
        "cmrr_1k_dB": interpolate_log_x(frequency, cmrr, 1e3),
        "psrr_plus_1k_dB": interpolate_log_x(frequency, psrr_plus, 1e3),
        "psrr_minus_1k_dB": interpolate_log_x(frequency, psrr_minus, 1e3),
        "cmrr_status": "PASS" if interpolate_log_x(frequency, cmrr, 1e3) >= 55.0 else "CMRR_FAIL",
        "psrr_plus_status": "PASS" if interpolate_log_x(frequency, psrr_plus, 1e3) >= 45.0 else "PSRR_PLUS_FAIL",
        "psrr_minus_status": "PASS" if interpolate_log_x(frequency, psrr_minus, 1e3) >= 45.0 else "PSRR_MINUS_FAIL",
    }
    return curve, values


def parse_icmr_op(path: Path) -> pd.Series:
    columns = ["scale", "vout_v", "vx_v", "vbn_v", "vbp_v", "tail_v", "nmir_v"]
    for device in range(1, 11):
        columns += [f"m{device}_id_a", f"m{device}_vdsat_v"]
    return pd.DataFrame(numeric_rows(path, len(columns)), columns=columns).iloc[-1]


def icmr_margins(op: pd.Series) -> dict[int, float]:
    return {
        1: float(op["nmir_v"] - op["tail_v"] - op["m1_vdsat_v"]),
        2: float(op["vx_v"] - op["tail_v"] - op["m2_vdsat_v"]),
        3: float(1.8 - op["nmir_v"] - op["m3_vdsat_v"]),
        4: float(1.8 - op["vx_v"] - op["m4_vdsat_v"]),
        5: float(op["tail_v"] - op["m5_vdsat_v"]),
        6: float(op["vout_v"] - op["m6_vdsat_v"]),
        7: float(1.8 - op["vout_v"] - op["m7_vdsat_v"]),
        8: float(1.8 - op["vbp_v"] - op["m8_vdsat_v"]),
        9: float(1.8 - op["vbn_v"] - op["m9_vdsat_v"]),
        10: float(op["vbn_v"] - op["m10_vdsat_v"]),
    }


def interval_containing_anchor(values: np.ndarray, valid: np.ndarray, anchor: float) -> tuple[float, float] | None:
    anchor_indices = np.flatnonzero(np.isclose(values, anchor, atol=1e-9))
    if not len(anchor_indices) or not valid[int(anchor_indices[0])]:
        return None
    left = right = int(anchor_indices[0])
    while left > 0 and valid[left - 1] and math.isclose(values[left] - values[left - 1], 0.01, abs_tol=1e-8):
        left -= 1
    while right + 1 < len(values) and valid[right + 1] and math.isclose(values[right + 1] - values[right], 0.01, abs_tol=1e-8):
        right += 1
    return float(values[left]), float(values[right])


def analyze_icmr(sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(121):
        vcm = round(0.40 + 0.01 * index, 2)
        tag = f"vcm_{vcm:.2f}".replace(".", "p")
        deck = f"icmr/{tag}.spice"
        record: dict[str, Any] = {"vcm_V": vcm, "gain_dB": math.nan, "vout_V": math.nan}
        reasons: list[str] = []
        try:
            ac = numeric_rows(RAW / "icmr" / f"{tag}_ac.tsv", 5)
            ad = ac[:, 1] + 1j * ac[:, 2]
            vdiff = ac[:, 3] + 1j * ac[:, 4]
            record["gain_dB"] = float(20 * np.log10(abs(ad[0])))
            record["actual_diff_input_at_1Hz_V"] = float(abs(vdiff[0]))
            op = parse_icmr_op(RAW / "icmr" / f"{tag}_op.tsv")
            margins = icmr_margins(op)
            record.update(
                {
                    "vout_V": float(op["vout_v"]),
                    "vx_V": float(op["vx_v"]),
                    "vbn_V": float(op["vbn_v"]),
                    "vbp_V": float(op["vbp_v"]),
                    "tail_V": float(op["tail_v"]),
                    "nmir_V": float(op["nmir_v"]),
                    "tracking_error_mV": abs(float(op["vout_v"]) - vcm) * 1e3,
                    "minimum_saturation_margin_V": min(margins.values()),
                }
            )
            for device in range(1, 11):
                record[f"m{device}_id_uA"] = float(op[f"m{device}_id_a"]) * 1e6
                record[f"m{device}_vdsat_V"] = float(op[f"m{device}_vdsat_v"])
                record[f"m{device}_saturation_margin_V"] = margins[device]
        except Exception as exc:
            reasons.append(f"NUMERICAL_INVALID:{exc}")
        if not sim_ok.get(deck, False):
            reasons.append("NO_CONVERGENCE_OR_SIMULATION_ERROR")
        record["point_status"] = "PENDING_GAIN_REFERENCE" if not reasons else ";".join(reasons)
        records.append(record)
    frame = pd.DataFrame(records)
    nominal_rows = frame[np.isclose(frame["vcm_V"], 0.9)]
    nominal_gain = float(nominal_rows["gain_dB"].iloc[0]) if len(nominal_rows) else math.nan
    valid_flags: list[bool] = []
    final_status: list[str] = []
    for record in records:
        reasons: list[str] = []
        if str(record["point_status"]) != "PENDING_GAIN_REFERENCE":
            reasons.append(str(record["point_status"]))
        gain = float(record.get("gain_dB", math.nan))
        record["gain_delta_vs_0p9_dB"] = gain - nominal_gain
        if not math.isfinite(gain) or gain < nominal_gain - 3.0:
            reasons.append("GAIN_FAIL")
        if not math.isclose(float(record.get("actual_diff_input_at_1Hz_V", math.nan)), 1.0, rel_tol=1e-6, abs_tol=1e-6):
            reasons.append("DIFFERENTIAL_STIMULUS_FAIL")
        if float(record.get("minimum_saturation_margin_V", -math.inf)) < 0.0:
            reasons.append("SATURATION")
        vout = float(record.get("vout_V", math.nan))
        if not math.isfinite(vout) or vout <= 0.05 or vout >= 1.75 or abs(vout - float(record["vcm_V"])) > 0.01:
            reasons.append("OUTPUT_CLIPPED_OR_PINNED")
        valid = not reasons
        record["valid"] = valid
        record["point_status"] = "VALID" if valid else ";".join(dict.fromkeys(reasons))
        valid_flags.append(valid)
        final_status.append(record["point_status"])
    frame = pd.DataFrame(records)
    interval = interval_containing_anchor(frame["vcm_V"].to_numpy(), np.asarray(valid_flags, dtype=bool), 0.9)
    low, high = interval if interval else (math.nan, math.nan)
    contains_hard = bool(interval and low <= 0.8 + 1e-9 and high >= 1.3 - 1e-9)
    summary = {
        "nominal_gain_dB": nominal_gain,
        "low_endpoint_V": low,
        "high_endpoint_V": high,
        "contains_0p8_to_1p3": contains_hard,
        "low_endpoint_status": "PASS" if math.isfinite(low) and low <= 0.8 + 1e-9 else "ICMR_LOW_FAIL",
        "high_endpoint_status": "PASS" if math.isfinite(high) and high >= 1.3 - 1e-9 else "ICMR_HIGH_FAIL",
        "status": "PASS" if contains_hard else "ICMR_FAIL" if interval else "NO_VALID_NOMINAL_ANCHOR",
        "grid_start_V": 0.4,
        "grid_stop_V": 1.6,
        "grid_step_V": 0.01,
        "point_count": len(frame),
    }
    write_result(frame, "day4_icmr_sweep.csv")
    return frame, summary


def largest_valid_interval(values: np.ndarray, valid: np.ndarray) -> tuple[float, float] | None:
    best: tuple[int, int] | None = None
    start: int | None = None
    for index, is_valid in enumerate(valid):
        contiguous = index == 0 or math.isclose(values[index] - values[index - 1], 0.01, abs_tol=1e-8)
        if is_valid and (start is None or contiguous):
            if start is None:
                start = index
        elif is_valid:
            start = index
        elif start is not None:
            candidate = (start, index - 1)
            if best is None or candidate[1] - candidate[0] > best[1] - best[0]:
                best = candidate
            start = None
    if start is not None:
        candidate = (start, len(values) - 1)
        if best is None or candidate[1] - candidate[0] > best[1] - best[0]:
            best = candidate
    return (float(values[best[0]]), float(values[best[1]])) if best else None


def parse_swing(path: Path, direction: str) -> pd.DataFrame:
    columns = [
        "scale", "command_V", "drive_V", "vout_V", "vinn_V", "vx_V",
        "m6_id_A", "m6_vdsat_V", "m7_id_A", "m7_vdsat_V",
    ]
    frame = pd.DataFrame(numeric_rows(path, len(columns)), columns=columns)
    frame["direction"] = direction
    return frame


def analyze_swing(sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, dict[str, Any]]:
    forward = parse_swing(RAW / "nominal" / "output_swing_forward.tsv", "COMMAND_ASCENDING")
    reverse = parse_swing(RAW / "nominal" / "output_swing_reverse.tsv", "COMMAND_DESCENDING")
    forward = forward.sort_values("command_V").reset_index(drop=True)
    reverse = reverse.sort_values("command_V").reset_index(drop=True)
    if len(forward) != 181 or len(reverse) != 181:
        raise ValueError(f"Output-swing sweeps must each contain 181 points, got {len(forward)} and {len(reverse)}")
    if not np.allclose(forward["command_V"], np.arange(181) * 0.01, atol=1e-8):
        raise ValueError("Forward command mapping is not the declared 0-to-1.8-V, 10-mV grid")
    if not np.allclose(reverse["command_V"], forward["command_V"], atol=1e-8):
        raise ValueError("Reverse command grid does not match the forward grid")
    for frame in (forward, reverse):
        frame["mapping_error_V"] = frame["command_V"] - (1.8 - frame["drive_V"])
        frame["tracking_error_mV"] = np.abs(frame["vout_V"] - frame["command_V"]) * 1e3
        frame["m6_saturation_margin_V"] = frame["vout_V"] - frame["m6_vdsat_V"]
        frame["m7_saturation_margin_V"] = 1.8 - frame["vout_V"] - frame["m7_vdsat_V"]
        frame["not_clipped"] = (frame["vout_V"] > 0.01) & (frame["vout_V"] < 1.79)
        frame["valid"] = (
            (frame["tracking_error_mV"] <= 10.0 + 1e-8)
            & (frame["m6_saturation_margin_V"] >= 0.0)
            & (frame["m7_saturation_margin_V"] >= 0.0)
            & frame["not_clipped"]
        )
        statuses: list[str] = []
        for row in frame.itertuples():
            reasons = []
            if row.tracking_error_mV > 10.0 + 1e-8:
                reasons.append("TRACKING_FAIL")
            if row.m6_saturation_margin_V < 0.0 or row.m7_saturation_margin_V < 0.0:
                reasons.append("SATURATION")
            if not row.not_clipped:
                reasons.append("CLIPPING")
            statuses.append("VALID" if not reasons else ";".join(reasons))
        frame["point_status"] = statuses
    vector_spans = {
        name: max(float(np.ptp(forward[name])), float(np.ptp(reverse[name])))
        for name in ("m6_id_A", "m6_vdsat_V", "m7_id_A", "m7_vdsat_V")
    }
    if vector_spans["m6_id_A"] <= 1e-9 or vector_spans["m7_id_A"] <= 1e-9:
        raise ValueError(f"Output-swing device-current vectors do not vary pointwise: {vector_spans}")
    if vector_spans["m6_vdsat_V"] <= 1e-5 or vector_spans["m7_vdsat_V"] <= 1e-5:
        raise ValueError(f"Output-swing VDSAT vectors do not vary pointwise: {vector_spans}")
    pointwise_deltas = {
        name: float(np.max(np.abs(forward[name] - reverse[name])))
        for name in ("m6_id_A", "m6_vdsat_V", "m7_id_A", "m7_vdsat_V")
    }
    if pointwise_deltas["m6_id_A"] > 1e-8 or pointwise_deltas["m7_id_A"] > 1e-8:
        raise ValueError(f"Forward/reverse device currents disagree at equal commands: {pointwise_deltas}")
    if pointwise_deltas["m6_vdsat_V"] > 1e-3 or pointwise_deltas["m7_vdsat_V"] > 1e-3:
        raise ValueError(f"Forward/reverse VDSAT values disagree at equal commands: {pointwise_deltas}")
    forward["reverse_vout_V"] = reverse["vout_V"]
    forward["forward_reverse_delta_uV"] = np.abs(forward["vout_V"] - reverse["vout_V"]) * 1e6
    forward["reverse_valid"] = reverse["valid"].to_numpy()
    forward["counterpart_point_status"] = reverse["point_status"].to_numpy()
    reverse["reverse_vout_V"] = forward["vout_V"]
    reverse["forward_reverse_delta_uV"] = forward["forward_reverse_delta_uV"]
    reverse["reverse_valid"] = forward["valid"].to_numpy()
    reverse["counterpart_point_status"] = forward["point_status"].to_numpy()
    both_valid = forward["valid"].to_numpy() & forward["reverse_valid"].to_numpy()
    interval = largest_valid_interval(forward["command_V"].to_numpy(), both_valid)
    low, high = interval if interval else (math.nan, math.nan)
    mapping_max = max(float(np.max(np.abs(forward["mapping_error_V"]))), float(np.max(np.abs(reverse["mapping_error_V"]))))
    hysteresis_max = float(np.max(forward["forward_reverse_delta_uV"]))
    run_ok = sim_ok.get("nominal/output_swing.spice", False)
    passed = bool(run_ok and interval and low <= 0.3 + 1e-9 and high >= 1.5 - 1e-9)
    summary = {
        "low_endpoint_V": low,
        "high_endpoint_V": high,
        "includes_0p3_to_1p5": passed,
        "low_endpoint_status": "PASS" if math.isfinite(low) and low <= 0.3 + 1e-9 else "OUTPUT_SWING_LOW_FAIL",
        "high_endpoint_status": "PASS" if math.isfinite(high) and high >= 1.5 - 1e-9 else "OUTPUT_SWING_HIGH_FAIL",
        "status": "PASS" if passed else "OUTPUT_SWING_FAIL" if run_ok else "NO_CONVERGENCE",
        "forward_points": len(forward),
        "reverse_points": len(reverse),
        "grid_step_V": 0.01,
        "RIN_ohm": 10e6,
        "RFB_ohm": 10e6,
        "command_mapping": "VOUT_command=1.8-VDRIVE",
        "maximum_command_mapping_error_V": mapping_max,
        "maximum_forward_reverse_delta_uV": hysteresis_max,
        "m6_id_vector_span_uA": vector_spans["m6_id_A"] * 1e6,
        "m7_id_vector_span_uA": vector_spans["m7_id_A"] * 1e6,
        "m6_vdsat_vector_span_V": vector_spans["m6_vdsat_V"],
        "m7_vdsat_vector_span_V": vector_spans["m7_vdsat_V"],
        "maximum_forward_reverse_m6_id_delta_uA": pointwise_deltas["m6_id_A"] * 1e6,
        "maximum_forward_reverse_m7_id_delta_uA": pointwise_deltas["m7_id_A"] * 1e6,
        "maximum_forward_reverse_m6_vdsat_delta_V": pointwise_deltas["m6_vdsat_V"],
        "maximum_forward_reverse_m7_vdsat_delta_V": pointwise_deltas["m7_vdsat_V"],
        "directional_device_vector_verification": "PASS",
    }
    write_result(pd.concat([forward, reverse], ignore_index=True), "day4_output_swing_sweep.csv")
    return forward, summary


def analyze_noise(diff_curve: pd.DataFrame, sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, dict[str, Any]]:
    data = numeric_rows(RAW / "nominal" / "noise.tsv", 3)
    frequency = data[:, 0]
    onoise = data[:, 1]
    inoise = data[:, 2]
    if len(frequency) != 501 or not math.isclose(float(frequency[0]), 10.0, rel_tol=1e-8) or not math.isclose(
        float(frequency[-1]), 1e6, rel_tol=1e-8
    ):
        raise ValueError("Noise result is not the declared 10-Hz-to-1-MHz, 100-points/decade grid")
    integrated = math.sqrt(float(np.trapezoid(np.square(inoise), frequency)))
    density_1k = interpolate_log_x(frequency, inoise, 1e3)
    ad_interp_db = np.interp(
        np.log10(frequency), np.log10(diff_curve["frequency_hz"]), diff_curve["ad_db"]
    )
    ad_interp = 10.0 ** (ad_interp_db / 20.0)
    referred_check = onoise / ad_interp
    relative_error = np.abs(referred_check - inoise) / np.maximum(inoise, np.finfo(float).tiny)
    curve = pd.DataFrame(
        {
            "frequency_hz": frequency,
            "output_noise_density_V_per_sqrtHz": onoise,
            "input_noise_density_V_per_sqrtHz": inoise,
            "independent_output_over_Ad_V_per_sqrtHz": referred_check,
            "input_refer_verification_relative_error": relative_error,
        }
    )
    write_result(curve, "day4_noise_curve.csv")
    verified = bool(float(np.nanmax(relative_error)) <= 0.02)
    summary = {
        "density_1k_nV_per_sqrtHz": density_1k * 1e9,
        "integrated_10Hz_1MHz_uV_rms": integrated * 1e6,
        "input_refer_max_relative_error": float(np.nanmax(relative_error)),
        "input_refer_verification": "PASS" if verified else "NOISE_REFERENCE_CHECK_FAIL",
        "status": "REPORTED" if sim_ok.get("nominal/noise.spice", False) and verified else "NOISE_ANALYSIS_FAIL",
        "conductance_reset_warning_count": (RAW / "logs" / "nominal" / "noise.log").read_text(encoding="utf-8", errors="replace").lower().count("conductance reset to"),
        "point_count": len(curve),
        "frequency_start_Hz": float(frequency[0]),
        "frequency_stop_Hz": float(frequency[-1]),
    }
    return curve, summary


def analyze_load_stability(sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, dict[int, pd.DataFrame], dict[int, pd.DataFrame]]:
    records: list[dict[str, Any]] = []
    loops: dict[int, pd.DataFrame] = {}
    transients: dict[int, pd.DataFrame] = {}
    for cl_pf in (1, 2, 5):
        loop, loop_curve = loop_metrics(RAW / "load" / f"cl{cl_pf}p_loop.tsv")
        transient, transient_curve = transient_metrics(RAW / "load" / f"cl{cl_pf}p_transient.tsv")
        loops[cl_pf] = loop_curve
        transients[cl_pf] = transient_curve
        no_oscillation = bool(
            math.isfinite(transient["rise_settling_us"])
            and math.isfinite(transient["fall_settling_us"])
            and transient["tail_high_pp_mv"] <= 8.0
            and transient["tail_low_pp_mv"] <= 8.0
        )
        run_ok = sim_ok.get(f"load/cl{cl_pf}p_loop.spice", False) and sim_ok.get(
            f"load/cl{cl_pf}p_transient.spice", False
        )
        reasons = []
        if not run_ok:
            reasons.append("NO_CONVERGENCE")
        if not math.isfinite(loop["ugb_hz"]):
            reasons.append("NO_0DB_DOWNWARD_CROSSING")
        elif loop["pm_deg"] < 55.0:
            reasons.append("PM_FAIL")
        if abs(loop["loop_phase_1hz_deg"]) > 5.0:
            reasons.append("LOOP_SIGN_FAIL")
        if loop["zero_db_downward_crossings"] > 1:
            reasons.append("MULTIPLE_0DB_DOWNWARD_CROSSINGS")
        if loop["ugb_crossing_at_boundary"] == 1.0:
            reasons.append("UGB_CROSSING_AT_BOUNDARY")
        if not no_oscillation:
            reasons.append("TRANSIENT_STABILITY_FAIL")
        records.append(
            {
                "CL_pF": cl_pf,
                "RL_kOhm": 100,
                "ugb_MHz": loop["ugb_hz"] / 1e6,
                "pm_deg": loop["pm_deg"],
                "loop_phase_1Hz_deg": loop["loop_phase_1hz_deg"],
                "zero_dB_downward_crossings": loop["zero_db_downward_crossings"],
                "zero_dB_all_crossings": loop["zero_db_all_crossings"],
                "first_downward_crossing_index": loop["first_downward_crossing_index"],
                "ugb_crossing_at_boundary": loop["ugb_crossing_at_boundary"],
                **transient,
                "no_sustained_or_growing_oscillation": no_oscillation,
                "status": "PASS" if not reasons else ";".join(reasons),
                "raw_loop_path": f"results/raw/day4/load/cl{cl_pf}p_loop.tsv",
                "raw_transient_path": f"results/raw/day4/load/cl{cl_pf}p_transient.tsv",
            }
        )
    frame = pd.DataFrame(records)
    write_result(frame, "day4_load_stability.csv")
    return frame, loops, transients


def day3_summary() -> dict[str, str]:
    with (RESULTS / "day3_nominal_summary.csv").open(newline="", encoding="utf-8") as handle:
        return {row["metric"]: row["value"] for row in csv.DictReader(handle)}


def analyze_correlation(pvt: pd.DataFrame) -> pd.DataFrame:
    prior = day3_summary()
    nominal = pvt.loc[pvt["point_id"] == "P01"].iloc[0]
    comparisons = (
        ("open_loop_gain", float(prior["open_loop_gain_db"]), float(nominal["gain_dB"]), "dB", 0.02),
        ("unity_gain_bandwidth", float(prior["unity_gain_bandwidth_mhz"]), float(nominal["ugb_MHz"]), "MHz", 0.02),
        ("phase_margin", float(prior["phase_margin_deg"]), float(nominal["pm_deg"]), "deg", 0.02),
        ("quiescent_power", float(prior["quiescent_power_uw"]), float(nominal["power_uW"]), "uW", 0.02),
        ("slew_rate_positive_formal", float(prior["slew_rate_positive_v_per_us"]), float(nominal["sr_pos_V_per_us"]), "V/us", 0.02),
        ("slew_rate_negative_formal", float(prior["slew_rate_negative_v_per_us"]), float(nominal["sr_neg_V_per_us"]), "V/us", 0.02),
        ("worst_1pct_settling_formal", float(prior["worst_1pct_settling_us"]), float(nominal["worst_settling_us"]), "us", 0.002),
    )
    records = []
    for metric, reference, observed, unit, tolerance in comparisons:
        difference = abs(observed - reference)
        records.append(
            {
                "metric": metric,
                "day3_reference": reference,
                "day4_observed": observed,
                "absolute_difference": difference,
                "tolerance": tolerance,
                "unit": unit,
                "status": "PASS" if math.isfinite(difference) and difference <= tolerance else "CORRELATION_FAIL",
            }
        )
    frame = pd.DataFrame(records)
    write_result(frame, "day4_nominal_correlation.csv")
    return frame


def safe_rejection() -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        return analyze_rejection()
    except Exception as exc:
        frame = pd.DataFrame(
            columns=[
                "frequency_hz", "ad_magnitude_V_per_V", "acm_magnitude_V_per_V",
                "aps_plus_magnitude_V_per_V", "aps_minus_magnitude_V_per_V", "cmrr_dB",
                "psrr_plus_dB", "psrr_minus_dB",
            ]
        )
        write_result(frame, "day4_cmrr_psrr_curves.csv")
        return frame, {
            "cmrr_1k_dB": math.nan,
            "psrr_plus_1k_dB": math.nan,
            "psrr_minus_1k_dB": math.nan,
            "cmrr_status": "NUMERICAL_INVALID",
            "psrr_plus_status": "NUMERICAL_INVALID",
            "psrr_minus_status": "NUMERICAL_INVALID",
            "error": str(exc),
        }


def safe_swing(sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        return analyze_swing(sim_ok)
    except Exception as exc:
        frame = pd.DataFrame(columns=["command_V", "vout_V", "valid", "point_status"])
        write_result(frame, "day4_output_swing_sweep.csv")
        return frame, {
            "low_endpoint_V": math.nan,
            "high_endpoint_V": math.nan,
            "low_endpoint_status": "NUMERICAL_INVALID",
            "high_endpoint_status": "NUMERICAL_INVALID",
            "status": "NUMERICAL_INVALID",
            "error": str(exc),
        }


def safe_noise(diff_curve: pd.DataFrame, sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        return analyze_noise(diff_curve, sim_ok)
    except Exception as exc:
        frame = pd.DataFrame(columns=["frequency_hz", "input_noise_density_V_per_sqrtHz"])
        write_result(frame, "day4_noise_curve.csv")
        return frame, {
            "density_1k_nV_per_sqrtHz": math.nan,
            "integrated_10Hz_1MHz_uV_rms": math.nan,
            "input_refer_verification": "NUMERICAL_INVALID",
            "status": "NUMERICAL_INVALID",
            "conductance_reset_warning_count": math.nan,
            "error": str(exc),
        }


def safe_load(sim_ok: dict[str, bool]) -> tuple[pd.DataFrame, dict[int, pd.DataFrame], dict[int, pd.DataFrame]]:
    try:
        return analyze_load_stability(sim_ok)
    except Exception as exc:
        frame = pd.DataFrame(
            [
                {"CL_pF": cl, "RL_kOhm": 100, "ugb_MHz": math.nan, "pm_deg": math.nan, "status": f"NUMERICAL_INVALID:{exc}"}
                for cl in (1, 2, 5)
            ]
        )
        write_result(frame, "day4_load_stability.csv")
        return frame, {}, {}


def nominal_summary_rows(
    pvt: pd.DataFrame,
    rejection: dict[str, Any],
    icmr: dict[str, Any],
    swing: dict[str, Any],
    noise: dict[str, Any],
    load: pd.DataFrame,
    log_audit: pd.DataFrame,
) -> pd.DataFrame:
    nominal = pvt.loc[pvt["point_id"] == "P01"].iloc[0]
    rows: list[dict[str, Any]] = []

    def add(metric: str, value: Any, unit: str, requirement: str, status: str, evidence: str, notes: str = "") -> None:
        rows.append(
            {
                "metric": metric,
                "value": value,
                "unit": unit,
                "requirement_or_context": requirement,
                "status": status,
                "evidence_path": evidence,
                "notes": notes,
            }
        )

    add("stage_status", "DAY4_CHARACTERIZATION_COMPLETE", "", "13-point PVT plus nominal characterization", "INFO", "results/pvt_summary.csv")
    add("nominal_open_loop_gain", nominal["gain_dB"], "dB", ">=50 hard; >=60 stretch", "PASS" if nominal["gain_dB"] >= 50 else "GAIN_FAIL", "results/raw/day4/pvt/P01_diff_ac.tsv")
    add("nominal_unity_gain_bandwidth", nominal["ugb_MHz"], "MHz", ">=5 hard; >=10 stretch", "PASS" if nominal["ugb_MHz"] >= 5 else "UGB_FAIL", "results/raw/day4/pvt/P01_loop.tsv")
    add("nominal_phase_margin", nominal["pm_deg"], "deg", ">=55 hard; >=65 stretch", "PASS" if nominal["pm_deg"] >= 55 else "PM_FAIL", "results/raw/day4/pvt/P01_loop.tsv")
    add("nominal_quiescent_power", nominal["power_uW"], "uW", "<=600 hard; <=400 stretch", "PASS" if nominal["power_uW"] <= 600 else "POWER_FAIL", "results/raw/day4/pvt/P01_op.tsv", "Signed source current retained in pvt_summary.csv")
    add("nominal_slew_rate_positive", nominal["sr_pos_V_per_us"], "V/us", ">=2 hard; >=4 stretch", "PASS" if nominal["sr_pos_V_per_us"] >= 2 else "SR_POS_FAIL", "results/raw/day4/pvt/P01_transient.tsv", "Least-squares fit over directed monotonic 20%-80% interval")
    add("nominal_slew_rate_negative", nominal["sr_neg_V_per_us"], "V/us", ">=2 hard; >=4 stretch", "PASS" if nominal["sr_neg_V_per_us"] >= 2 else "SR_NEG_FAIL", "results/raw/day4/pvt/P01_transient.tsv", "Least-squares fit over directed monotonic 80%-20% interval")
    add("nominal_worst_1pct_settling", nominal["worst_settling_us"], "us", "<=1.5 hard; <=1.0 stretch", "PASS" if nominal["worst_settling_us"] <= 1.5 else "SETTLING_FAIL", "results/raw/day4/pvt/P01_transient.tsv", "Time zero is interpolated input 50% crossing")
    add("CMRR_at_1kHz", rejection["cmrr_1k_dB"], "dB", ">=55 hard; >=65 stretch", str(rejection["cmrr_status"]), "results/day4_cmrr_psrr_curves.csv")
    add("PSRR_plus_at_1kHz", rejection["psrr_plus_1k_dB"], "dB", ">=45 hard; >=55 stretch", str(rejection["psrr_plus_status"]), "results/day4_cmrr_psrr_curves.csv")
    add("PSRR_minus_at_1kHz", rejection["psrr_minus_1k_dB"], "dB", ">=45 hard; >=55 stretch", str(rejection["psrr_minus_status"]), "results/day4_cmrr_psrr_curves.csv", "VSS is an explicit AC source; VDD and inputs remain absolute AC ground")
    add("ICMR_low_endpoint", icmr["low_endpoint_V"], "V", "<=0.8", str(icmr["low_endpoint_status"]), "results/day4_icmr_sweep.csv", "Largest continuous valid 10-mV-grid interval containing 0.9 V; 50-mV rail guard")
    add("ICMR_high_endpoint", icmr["high_endpoint_V"], "V", ">=1.3", str(icmr["high_endpoint_status"]), "results/day4_icmr_sweep.csv", "Gain within -3 dB of nominal and every M1-M10 saturation margin nonnegative")
    add("ICMR_combined_interval", f"{icmr['low_endpoint_V']}-{icmr['high_endpoint_V']}", "V", "contains 0.8-1.3 V", str(icmr["status"]), "results/day4_icmr_sweep.csv")
    add("output_swing_low_endpoint", swing["low_endpoint_V"], "V", "<=0.3", str(swing["low_endpoint_status"]), "results/day4_output_swing_sweep.csv", "Equal 10-Megohm RIN/RFB; forward/reverse sweeps")
    add("output_swing_high_endpoint", swing["high_endpoint_V"], "V", ">=1.5", str(swing["high_endpoint_status"]), "results/day4_output_swing_sweep.csv", "Tracking error <=10 mV and M6/M7 saturated")
    add("output_swing_combined_interval", f"{swing['low_endpoint_V']}-{swing['high_endpoint_V']}", "V", "contains 0.3-1.5 V", str(swing["status"]), "results/day4_output_swing_sweep.csv")
    noise_note = f"SPICE conductance-reset warnings retained: {noise['conductance_reset_warning_count']} (see log audit)"
    add("input_noise_density_at_1kHz", noise["density_1k_nV_per_sqrtHz"], "nV/sqrtHz", "REPORT", str(noise["status"]), "results/day4_noise_curve.csv", noise_note)
    add("integrated_input_noise_10Hz_1MHz", noise["integrated_10Hz_1MHz_uV_rms"], "uV_rms", "REPORT", str(noise["status"]), "results/day4_noise_curve.csv", noise_note)
    for cl in (1, 2, 5):
        row = load.loc[load["CL_pF"] == cl].iloc[0]
        add(f"phase_margin_CL_{cl}pF", row["pm_deg"], "deg", ">=55 and no sustained/growing oscillation", str(row["status"]), "results/day4_load_stability.csv")
    add("external_IREF_model", "IDEAL_10_UA", "", "scope limitation", "LIMITATION", "results/generated/day4/day4_manifest.json", "Reference-generator PVT variation is not represented")
    add("mismatch_and_Monte_Carlo", "NOT_PERFORMED_SCOPE_LIMITATION", "", "not in five-day schematic scope", "N/A_SCOPE_LIMITATION", "results/generated/day4/day4_manifest.json")
    add("schematic_level_only", True, "", "no measured/fabricated claim", "LIMITATION", "results/generated/day4/day4_manifest.json", "No extracted parasitics or layout")
    add("completed_ngspice_decks", int((log_audit["status"].isin(["PASS", "PASS_WITH_DYNAMIC_GMIN"])).sum()), "decks", f"{len(log_audit)} required", "PASS" if bool(log_audit["status"].isin(["PASS", "PASS_WITH_DYNAMIC_GMIN"]).all()) else "SIMULATION_ERROR", "results/day4_log_audit.csv")
    frame = pd.DataFrame(rows)
    write_result(frame, "day4_nominal_summary.csv")
    return frame


def overall_summary(
    pvt: pd.DataFrame,
    rejection: dict[str, Any],
    icmr: dict[str, Any],
    swing: dict[str, Any],
    noise: dict[str, Any],
    load: pd.DataFrame,
) -> pd.DataFrame:
    nominal = pvt.loc[pvt["point_id"] == "P01"].iloc[0]

    def core_row(
        metric: str, column: str, reducer: str, hard: str, stretch: str, unit: str, predicate: Any
    ) -> dict[str, Any]:
        series = pd.to_numeric(pvt[column], errors="coerce")
        finite = series.notna() & np.isfinite(series)
        if not finite.all():
            return {
                "metric": metric, "scope": "13-point PVT", "hard_target": hard, "stretch_target": stretch,
                "nominal_result": nominal[column], "worst_pvt_result": math.nan, "worst_condition": "NUMERICAL_INVALID",
                "unit": unit, "status": "NUMERICAL_INVALID", "evidence_path": "results/pvt_summary.csv", "notes": "One or more required values are blank/non-finite",
            }
        index = series.idxmin() if reducer == "min" else series.idxmax()
        operating_points_valid = bool((pvt["run_status"] == "COMPLETE").all())
        values_pass = bool(predicate(series).all()) and operating_points_valid
        return {
            "metric": metric,
            "scope": "13-point PVT",
            "hard_target": hard,
            "stretch_target": stretch,
            "nominal_result": nominal[column],
            "worst_pvt_result": float(series.loc[index]),
            "worst_condition": str(pvt.loc[index, "point_id"]),
            "unit": unit,
            "status": "PASS" if values_pass else ("PVT_OPERATING_POINT_FAIL" if not operating_points_valid else f"{metric.upper().replace(' ', '_').replace('-', '_')}_FAIL"),
            "evidence_path": "results/pvt_summary.csv",
            "notes": "External ideal 10-uA IREF; schematic-level PVT",
        }

    rows = [
        core_row("Open-loop DC gain", "gain_dB", "min", ">=50", ">=60", "dB", lambda x: x >= 50),
        core_row("Unity-gain bandwidth", "ugb_MHz", "min", ">=5", ">=10", "MHz", lambda x: x >= 5),
        core_row("Phase margin", "pm_deg", "min", ">=55", ">=65", "deg", lambda x: x >= 55),
        core_row("Quiescent power", "power_uW", "max", "<=600", "<=400", "uW", lambda x: x <= 600),
        core_row("Positive slew rate", "sr_pos_V_per_us", "min", ">=2", ">=4", "V/us", lambda x: x >= 2),
        core_row("Negative slew rate", "sr_neg_V_per_us", "min", ">=2", ">=4", "V/us", lambda x: x >= 2),
    ]

    def nominal_row(metric: str, hard: str, stretch: str, value: Any, unit: str, status: str, evidence: str, notes: str = "") -> dict[str, Any]:
        return {
            "metric": metric,
            "scope": "Nominal",
            "hard_target": hard,
            "stretch_target": stretch,
            "nominal_result": value,
            "worst_pvt_result": "N/A_NOT_SWEPT",
            "worst_condition": "N/A_NOT_SWEPT",
            "unit": unit,
            "status": status,
            "evidence_path": evidence,
            "notes": notes,
        }

    rows += [
        nominal_row("1% settling time", "<=1.5", "<=1.0", nominal["worst_settling_us"], "us", "PASS" if nominal["worst_settling_us"] <= 1.5 else "SETTLING_FAIL", "results/pvt_summary.csv", "Worst of rising/falling; input 50% time reference"),
        nominal_row("CMRR at 1 kHz", ">=55", ">=65", rejection["cmrr_1k_dB"], "dB", str(rejection["cmrr_status"]), "results/day4_cmrr_psrr_curves.csv"),
        nominal_row("PSRR+ at 1 kHz", ">=45", ">=55", rejection["psrr_plus_1k_dB"], "dB", str(rejection["psrr_plus_status"]), "results/day4_cmrr_psrr_curves.csv"),
        nominal_row("PSRR- at 1 kHz", ">=45", ">=55", rejection["psrr_minus_1k_dB"], "dB", str(rejection["psrr_minus_status"]), "results/day4_cmrr_psrr_curves.csv", "Explicit VSS perturbation"),
        nominal_row("ICMR low endpoint", "<=0.8", "lower is better", icmr["low_endpoint_V"], "V", str(icmr["low_endpoint_status"]), "results/day4_icmr_sweep.csv", f"Combined interval status: {icmr['status']}"),
        nominal_row("ICMR high endpoint", ">=1.3", "higher is better", icmr["high_endpoint_V"], "V", str(icmr["high_endpoint_status"]), "results/day4_icmr_sweep.csv", f"Combined interval status: {icmr['status']}"),
        nominal_row("Output-swing low endpoint", "<=0.3", "lower is better", swing["low_endpoint_V"], "V", str(swing["low_endpoint_status"]), "results/day4_output_swing_sweep.csv", f"Combined interval status: {swing['status']}; forward/reverse sweep"),
        nominal_row("Output-swing high endpoint", ">=1.5", "higher is better", swing["high_endpoint_V"], "V", str(swing["high_endpoint_status"]), "results/day4_output_swing_sweep.csv", f"Combined interval status: {swing['status']}; forward/reverse sweep"),
        nominal_row("Input-referred noise density at 1 kHz", "REPORT", "lower is better", noise["density_1k_nV_per_sqrtHz"], "nV/sqrtHz", str(noise["status"]), "results/day4_noise_curve.csv", f"No pass threshold; {noise['conductance_reset_warning_count']} model conductance-reset warnings retained"),
        nominal_row("Integrated input-referred noise 10 Hz-1 MHz", "REPORT", "lower is better", noise["integrated_10Hz_1MHz_uV_rms"], "uV_rms", str(noise["status"]), "results/day4_noise_curve.csv", f"Numerical integration; {noise['conductance_reset_warning_count']} model conductance-reset warnings retained"),
    ]
    for cl in (1, 2, 5):
        load_row = load.loc[load["CL_pF"] == cl].iloc[0]
        row = nominal_row(
            f"PM at CL={cl} pF", ">=55", ">=65", load_row["pm_deg"], "deg", str(load_row["status"]),
            "results/day4_load_stability.csv", "RL=100 kOhm; transient must show no sustained/growing oscillation",
        )
        row["scope"] = "Nominal load sweep"
        rows.append(row)
    frame = pd.DataFrame(rows)
    write_result(frame, "summary.csv")
    return frame


def write_measurement_definitions() -> pd.DataFrame:
    rows = [
        ("A0", "20log10(abs(VOUT/(VINP-VINN))) at 1 Hz", "Actual differential stimulus retained; DC follower closed through 1-GH LBREAK and opened for AC"),
        ("UGB", "first downward 0-dB crossing of signed T=-VOUT/VINN", "Every crossing counted; boundary or multiple downward crossing is a failure"),
        ("PM", "180 deg plus unwrapped complex phase(T) at UGB", "Low-frequency loop phase must be within 5 deg of zero"),
        ("Power", "(VDD-VSS)*abs(I(VDD))", "Signed I(VDD) is retained separately"),
        ("SR+/-", "least-squares slope over directed monotonic 20%-80% / 80%-20% output interval", "0.8-V to 1.2-V command; 20-ns input edges"),
        ("Settling", "earliest time after interpolated input 50% crossing that remains within 4 mV", "Rise/fall kept separately; worse direction reported"),
        ("ICMR", "largest continuous valid 10-mV interval containing 0.9 V", "Gain >= nominal-3 dB, M1-M10 margins >=0, output uses 50-mV rail guard"),
        ("Output swing", "largest continuous valid interval common to forward and reverse sweeps", "Equal 10-Meg RIN/RFB; <=10-mV tracking; M6/M7 saturated"),
        ("CMRR", "20log10(abs(Ad/Acm))", "Ad and Acm measured at same frequency/bias"),
        ("PSRR+/-", "20log10(abs(Ad/Aps))", "1-V AC supply perturbation; explicit VSS bench for PSRR-"),
        ("Noise", "SPICE input-referred density; RMS=sqrt(integral density^2 df)", "10 Hz-1 MHz; report only; cross-checked against output noise/Ad"),
        ("Load stability", "PM plus unity-follower transient", "CL=1/2/5 pF, RL=100 kOhm; no sustained/growing oscillation"),
    ]
    frame = pd.DataFrame(rows, columns=["metric", "definition", "audit_note"])
    write_result(frame, "day4_measurement_definitions.csv")
    return frame


def plot_pvt(pvt: pd.DataFrame) -> None:
    specs = [
        ("gain_dB", "A0 (dB)", 50, "min"),
        ("ugb_MHz", "UGB (MHz)", 5, "min"),
        ("pm_deg", "PM (deg)", 55, "min"),
        ("power_uW", "Power (uW)", 600, "max"),
        ("sr_pos_V_per_us", "SR+ (V/us)", 2, "min"),
        ("sr_neg_V_per_us", "SR- (V/us)", 2, "min"),
    ]
    fig, axes = plt.subplots(3, 2, figsize=(12, 10), constrained_layout=True)
    x = np.arange(len(pvt))
    colors = ["#2B7A78" if status == "PASS" else "#C44E52" for status in pvt["pass_fail"]]
    for axis, (column, ylabel, limit, direction) in zip(axes.flat, specs):
        values = pd.to_numeric(pvt[column], errors="coerce")
        axis.bar(x, values, color=colors, alpha=0.88)
        axis.axhline(limit, color="#1F1F1F", linestyle="--", linewidth=1.2, label=f"hard {direction}: {limit:g}")
        axis.set_xticks(x, pvt["point_id"], rotation=45)
        axis.set_ylabel(ylabel)
        axis.grid(True, axis="y", alpha=0.25)
        axis.legend(fontsize=8)
    fig.suptitle("Day 4 core metrics across the frozen 13-point PVT matrix", fontsize=14)
    fig.savefig(PLOTS / "day4_pvt_summary.png", dpi=220)
    plt.close(fig)


def plot_rejection(curve: pd.DataFrame) -> None:
    if curve.empty:
        return
    fig, axis = plt.subplots(figsize=(9.5, 5.8), constrained_layout=True)
    axis.semilogx(curve["frequency_hz"], curve["cmrr_dB"], label="CMRR", linewidth=2.0)
    axis.semilogx(curve["frequency_hz"], curve["psrr_plus_dB"], label="PSRR+", linewidth=2.0)
    axis.semilogx(curve["frequency_hz"], curve["psrr_minus_dB"], label="PSRR-", linewidth=2.0)
    axis.axvline(1e3, color="#555555", linestyle="--", linewidth=1, label="1 kHz evaluation")
    axis.axhline(55, color="#7A5195", linestyle=":", linewidth=1.2, label="CMRR hard limit: 55 dB")
    axis.axhline(45, color="#EF5675", linestyle="-.", linewidth=1.2, label="PSRR hard limit: 45 dB")
    axis.set(xlabel="Frequency (Hz)", ylabel="Rejection ratio (dB)", title="Nominal CMRR and supply rejection")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    fig.savefig(PLOTS / "day4_cmrr_psrr.png", dpi=220)
    plt.close(fig)


def plot_icmr(frame: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 7.5), sharex=True, constrained_layout=True)
    valid = frame["valid"].fillna(False).to_numpy(dtype=bool)
    axes[0].plot(frame["vcm_V"], frame["gain_dB"], color="#176B87", linewidth=2)
    if math.isfinite(float(summary["nominal_gain_dB"])):
        axes[0].axhline(float(summary["nominal_gain_dB"]) - 3, color="#C44E52", linestyle="--", label="nominal - 3 dB")
    axes[0].scatter(frame.loc[~valid, "vcm_V"], frame.loc[~valid, "gain_dB"], color="#C44E52", s=16, label="invalid")
    axes[0].set(ylabel="Differential gain at 1 Hz (dB)", title="Full-OTA input common-mode range")
    axes[0].legend()
    axes[1].plot(frame["vcm_V"], frame["minimum_saturation_margin_V"], color="#2B7A78", linewidth=2, label="minimum M1-M10 margin")
    axes[1].axhline(0, color="#555555", linestyle="--")
    axes[1].fill_between(frame["vcm_V"], 0, 1, where=valid, transform=axes[1].get_xaxis_transform(), color="#55A868", alpha=0.12, label="valid interval")
    axes[1].set(xlabel="Input common-mode voltage (V)", ylabel="Minimum saturation margin (V)")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend()
    axes[0].grid(True, alpha=0.25)
    fig.savefig(PLOTS / "day4_icmr.png", dpi=220)
    plt.close(fig)


def plot_swing(frame: pd.DataFrame, metrics: dict[str, Any]) -> None:
    if frame.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 7.4), sharex=True, constrained_layout=True)
    valid_low = float(metrics["low_endpoint_V"])
    valid_high = float(metrics["high_endpoint_V"])
    valid_label = (
        f"common valid interval {valid_low:.2f}-{valid_high:.2f} V "
        "(covers required 0.30-1.50 V)"
    )
    for axis in axes:
        axis.axvspan(valid_low, valid_high, color="#55A868", alpha=0.12, label=valid_label if axis is axes[0] else None)
        axis.axvline(0.30, color="#555555", linestyle=":", linewidth=1.2)
        axis.axvline(1.50, color="#555555", linestyle=":", linewidth=1.2)
    axes[0].plot(frame["command_V"], frame["command_V"], color="#555555", linestyle="--", label="ideal")
    axes[0].plot(frame["command_V"], frame["vout_V"], color="#176B87", linewidth=2, label="forward measured")
    axes[0].plot(frame["command_V"], frame["reverse_vout_V"], color="#E17C05", linewidth=1.4, label="reverse measured")
    invalid = ~frame["valid"].fillna(False)
    axes[0].scatter(frame.loc[invalid, "command_V"], frame.loc[invalid, "vout_V"], color="#C44E52", s=13, label="invalid")
    axes[0].set(ylabel="Output voltage (V)", title="Offset-inverting output-swing verification")
    axes[0].legend()
    axes[1].plot(frame["command_V"], frame["tracking_error_mV"], color="#2B7A78", linewidth=2, label="tracking error")
    axes[1].axhline(10, color="#C44E52", linestyle="--", label="10 mV limit")
    axes[1].plot(frame["command_V"], 1e3 * frame["m6_saturation_margin_V"], label="M6 margin (mV)", alpha=0.8)
    axes[1].plot(frame["command_V"], 1e3 * frame["m7_saturation_margin_V"], label="M7 margin (mV)", alpha=0.8)
    axes[1].axhline(0, color="#555555", linestyle=":")
    axes[1].set(xlabel="Commanded output (V)", ylabel="Error / margin (mV)")
    axes[1].legend(ncol=2)
    for axis in axes:
        axis.grid(True, alpha=0.25)
    fig.savefig(PLOTS / "day4_output_swing.png", dpi=220)
    plt.close(fig)


def plot_noise(curve: pd.DataFrame) -> None:
    if curve.empty:
        return
    fig, axis = plt.subplots(figsize=(9.2, 5.6), constrained_layout=True)
    axis.loglog(curve["frequency_hz"], curve["input_noise_density_V_per_sqrtHz"] * 1e9, linewidth=2, color="#176B87", label="SPICE input-referred")
    axis.loglog(curve["frequency_hz"], curve["independent_output_over_Ad_V_per_sqrtHz"] * 1e9, linestyle="--", linewidth=1.2, color="#E17C05", label="output noise / Ad check")
    axis.axvline(1e3, color="#555555", linestyle=":")
    axis.set(xlabel="Frequency (Hz)", ylabel="Input-referred density (nV/sqrtHz)", title="Nominal input-referred noise")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    fig.savefig(PLOTS / "day4_noise.png", dpi=220)
    plt.close(fig)


def plot_load(loops: dict[int, pd.DataFrame], transients: dict[int, pd.DataFrame]) -> None:
    if not loops or not transients:
        return
    colors = {1: "#176B87", 2: "#E17C05", 5: "#C44E52"}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for cl, curve in loops.items():
        axes[0, 0].semilogx(curve["frequency_hz"], curve["gain_db"], color=colors[cl], label=f"{cl} pF")
        axes[1, 0].semilogx(curve["frequency_hz"], curve["phase_unwrapped_deg"], color=colors[cl], label=f"{cl} pF")
    axes[0, 0].axhline(0, color="#555555", linestyle="--")
    axes[1, 0].axhline(-180, color="#555555", linestyle="--")
    axes[0, 0].set(ylabel="Loop magnitude (dB)", title="Load-dependent return ratio")
    axes[1, 0].set(xlabel="Frequency (Hz)", ylabel="Unwrapped phase (deg)")
    for cl, curve in transients.items():
        time_us = curve["time_s"] * 1e6
        axes[0, 1].plot(time_us, curve["vout_v"], color=colors[cl], label=f"{cl} pF")
        mask = (time_us >= 0.95) & (time_us <= 1.5)
        axes[1, 1].plot(time_us[mask], curve.loc[mask, "vout_v"], color=colors[cl], label=f"{cl} pF")
    axes[0, 1].set(ylabel="VOUT (V)", title="Unity-follower transient")
    axes[1, 1].set(xlabel="Time (us)", ylabel="VOUT (V)", title="Rising-edge detail")
    for axis in axes.flat:
        axis.grid(True, which="both", alpha=0.25)
        axis.legend()
    fig.savefig(PLOTS / "day4_load_stability.png", dpi=220)
    plt.close(fig)


def stamp_raw_tsv() -> None:
    for path in sorted(RAW.rglob("*.tsv")):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            continue
        stamped: list[str] = []
        numeric_count = 0
        for index, line in enumerate(lines):
            tokens = line.split()
            if index == 0:
                if tokens and tokens[-1] in (MANIFEST_HASH, "manifest_sha256"):
                    line = line.rsplit(None, 1)[0]
                stamped.append(line.rstrip() + "\tmanifest_sha256")
                continue
            if tokens and tokens[-1] == MANIFEST_HASH:
                stamped.append(line)
                numeric_count += 1
                continue
            is_numeric = False
            if tokens:
                try:
                    [float(token) for token in tokens]
                    is_numeric = True
                except ValueError:
                    is_numeric = False
            if is_numeric:
                stamped.append(line.rstrip() + "\t" + MANIFEST_HASH)
                if is_numeric:
                    numeric_count += 1
            else:
                stamped.append(line)
        if numeric_count == 0:
            raise ValueError(f"Raw TSV has no numeric rows to stamp: {path}")
        path.write_text("\n".join(stamped) + "\n", encoding="utf-8")


def verify_result_hashes(paths: list[Path]) -> None:
    for path in paths:
        frame = pd.read_csv(path, dtype=str)
        if "manifest_sha256" not in frame.columns:
            raise ValueError(f"Result lacks manifest_sha256 column: {path}")
        if len(frame) and set(frame["manifest_sha256"].dropna()) != {MANIFEST_HASH}:
            raise ValueError(f"Result contains a wrong or mixed manifest hash: {path}")


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    log_audit, sim_ok = audit_logs()
    pvt, _, pvt_loops, pvt_transients = analyze_pvt(sim_ok)
    correlation = analyze_correlation(pvt)
    rejection_curve, rejection = safe_rejection()
    icmr_frame, icmr = analyze_icmr(sim_ok)
    swing_frame, swing = safe_swing(sim_ok)
    diff_curve = complex_curve(RAW / "pvt" / "P01_diff_ac.tsv", "ad")
    noise_curve, noise = safe_noise(diff_curve, sim_ok)
    load, load_loops, load_transients = safe_load(sim_ok)
    nominal = nominal_summary_rows(pvt, rejection, icmr, swing, noise, load, log_audit)
    summary = overall_summary(pvt, rejection, icmr, swing, noise, load)
    definitions = write_measurement_definitions()

    plot_pvt(pvt)
    plot_rejection(rejection_curve)
    plot_icmr(icmr_frame, icmr)
    plot_swing(swing_frame, swing)
    plot_noise(noise_curve)
    plot_load(load_loops, load_transients)

    stamp_raw_tsv()
    result_paths = [
        RESULTS / "pvt_summary.csv",
        RESULTS / "summary.csv",
        RESULTS / "day4_log_audit.csv",
        RESULTS / "day4_pvt_operating_points.csv",
        RESULTS / "day4_nominal_correlation.csv",
        RESULTS / "day4_cmrr_psrr_curves.csv",
        RESULTS / "day4_icmr_sweep.csv",
        RESULTS / "day4_output_swing_sweep.csv",
        RESULTS / "day4_noise_curve.csv",
        RESULTS / "day4_load_stability.csv",
        RESULTS / "day4_nominal_summary.csv",
        RESULTS / "day4_measurement_definitions.csv",
    ]
    verify_result_hashes(result_paths)
    integrity_failures: list[str] = []
    required_pvt_columns = (
        "gain_dB",
        "actual_diff_input_at_1Hz_V",
        "gain_flatness_1_to_10Hz_dB",
        "ugb_MHz",
        "pm_deg",
        "loop_phase_1Hz_deg",
        "zero_dB_downward_crossings",
        "zero_dB_all_crossings",
        "ivdd_signed_uA",
        "power_uW",
        "sr_pos_V_per_us",
        "sr_neg_V_per_us",
        "min_saturation_margin_V",
    )
    if len(pvt) != len(PVT_POINTS):
        integrity_failures.append(f"PVT:ROW_COUNT_{len(pvt)}")
    for column in required_pvt_columns:
        values = pd.to_numeric(pvt[column], errors="coerce")
        if not np.isfinite(values).all():
            integrity_failures.append(f"PVT:{column}:NON_FINITE")
    if pvt["run_status"].isin(["NUMERICAL_INVALID", "NO_CONVERGENCE", "NO_0DB_DOWNWARD_CROSSING"]).any():
        integrity_failures.append("PVT:PARSER_OR_SIMULATION_FAILURE")
    nominal_pvt = pvt.loc[pvt["point_id"] == "P01"]
    for column in ("rise_settling_us", "fall_settling_us", "worst_settling_us"):
        values = pd.to_numeric(nominal_pvt[column], errors="coerce")
        if len(values) != 1 or not np.isfinite(values).all():
            integrity_failures.append(f"nominal settling:{column}:NON_FINITE")
    for label, status in (
        ("CMRR", rejection["cmrr_status"]),
        ("PSRR+", rejection["psrr_plus_status"]),
        ("PSRR-", rejection["psrr_minus_status"]),
        ("ICMR", icmr["status"]),
        ("output swing", swing["status"]),
        ("noise", noise["status"]),
    ):
        if "NUMERICAL_INVALID" in str(status) or "NO_CONVERGENCE" in str(status) or "ANALYSIS_FAIL" in str(status):
            integrity_failures.append(f"{label}:{status}")
    for label, value in (
        ("ICMR low endpoint", icmr["low_endpoint_V"]),
        ("ICMR high endpoint", icmr["high_endpoint_V"]),
        ("output-swing low endpoint", swing["low_endpoint_V"]),
        ("output-swing high endpoint", swing["high_endpoint_V"]),
        ("noise density", noise["density_1k_nV_per_sqrtHz"]),
        ("integrated noise", noise["integrated_10Hz_1MHz_uV_rms"]),
    ):
        if not isinstance(value, (int, float, np.floating)) or not math.isfinite(float(value)):
            integrity_failures.append(f"{label}:NON_FINITE")
    required_load_columns = (
        "ugb_MHz",
        "pm_deg",
        "loop_phase_1Hz_deg",
        "zero_dB_downward_crossings",
        "zero_dB_all_crossings",
        "sr_pos_V_per_us",
        "sr_neg_V_per_us",
        "rise_settling_us",
        "fall_settling_us",
        "worst_settling_us",
        "overshoot_mv",
        "undershoot_mv",
        "tail_high_pp_mv",
        "tail_low_pp_mv",
    )
    if len(load) != 3 or set(pd.to_numeric(load["CL_pF"], errors="coerce")) != {1.0, 2.0, 5.0}:
        integrity_failures.append("load stability:MISSING_OR_DUPLICATE_LOAD")
    for column in required_load_columns:
        values = pd.to_numeric(load[column], errors="coerce")
        if len(values) != 3 or not np.isfinite(values).all():
            integrity_failures.append(f"load stability:{column}:NON_FINITE_OR_MISSING")
    if any("NUMERICAL_INVALID" in str(status) or "NO_CONVERGENCE" in str(status) for status in load["status"]):
        integrity_failures.append("load stability:PARSER_OR_SIMULATION_FAILURE")
    if integrity_failures:
        raise ValueError(f"Day 4 analysis integrity gate failed: {integrity_failures}")
    log_pass = log_audit["status"].isin(["PASS", "PASS_WITH_DYNAMIC_GMIN"])
    if not bool(log_pass.all()):
        failed = log_audit.loc[~log_pass, ["deck", "status"]].to_dict("records")
        raise ValueError(f"One or more required Day 4 simulations failed log audit: {failed}")
    if not bool((correlation["status"] == "PASS").all()):
        raise ValueError("Nominal Day 3/Day 4 correlation gate failed; production summaries are rejected")
    if "NOT_RUN" in (RESULTS / "pvt_summary.csv").read_text(encoding="utf-8") or "NOT_RUN" in (
        RESULTS / "summary.csv"
    ).read_text(encoding="utf-8"):
        raise ValueError("A required Day 4 aggregate still contains NOT_RUN")
    print(
        "DAY4_ANALYSIS_OK "
        f"manifest={MANIFEST_HASH} pvt_rows={len(pvt)} icmr_rows={len(icmr_frame)} "
        f"logs={len(log_audit)} log_pass={int(log_audit['status'].isin(['PASS', 'PASS_WITH_DYNAMIC_GMIN']).sum())}"
    )


if __name__ == "__main__":
    main()
