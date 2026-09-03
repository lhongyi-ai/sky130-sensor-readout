#!/usr/bin/env python3
"""Analyze the nominal Day 3 two-stage OTA and preserve optimization evidence."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "day3"
GENERATED = ROOT / "results" / "generated" / "day3"
PLOTS = ROOT / "results" / "plots"


def numeric_rows(path: Path, expected_columns: int) -> np.ndarray:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        tokens = line.split()
        if len(tokens) != expected_columns:
            continue
        try:
            rows.append([float(token) for token in tokens])
        except ValueError:
            continue
    if not rows:
        raise ValueError(f"No numeric rows with {expected_columns} columns in {path}")
    return np.asarray(rows, dtype=float)


def interpolate_log_crossing(frequency: np.ndarray, value: np.ndarray, level: float) -> float:
    indices = np.flatnonzero((value[:-1] - level) * (value[1:] - level) <= 0)
    if not indices.size:
        return math.nan
    index = int(indices[0])
    f0, f1 = float(frequency[index]), float(frequency[index + 1])
    y0, y1 = float(value[index]), float(value[index + 1])
    if y1 == y0:
        return f0
    fraction = (level - y0) / (y1 - y0)
    return float(10 ** (np.log10(f0) + fraction * (np.log10(f1) - np.log10(f0))))


def load_loop(tag: str) -> pd.DataFrame:
    frame = pd.DataFrame(
        numeric_rows(RAW / f"{tag}_loop.tsv", 3),
        columns=("frequency_hz", "gain_db", "phase_raw_deg"),
    )
    phase = np.rad2deg(np.unwrap(np.deg2rad(frame["phase_raw_deg"].to_numpy())))
    phase -= round(float(phase[0]) / 360.0) * 360.0
    frame["phase_unwrapped_deg"] = phase
    return frame


def loop_metrics(frame: pd.DataFrame) -> dict[str, float]:
    frequency = frame["frequency_hz"].to_numpy()
    gain = frame["gain_db"].to_numpy()
    phase = frame["phase_unwrapped_deg"].to_numpy()
    unity_hz = interpolate_log_crossing(frequency, gain, 0.0)
    if not math.isfinite(unity_hz):
        raise ValueError("Loop gain has no 0-dB crossing")
    unity_phase = float(np.interp(np.log10(unity_hz), np.log10(frequency), phase))
    return {
        "a0_db": float(gain[0]),
        "low_frequency_phase_deg": float(phase[0]),
        "ugb_hz": unity_hz,
        "phase_at_ugb_deg": unity_phase,
        "phase_margin_deg": 180.0 + unity_phase,
        "gain_3db_bandwidth_hz": interpolate_log_crossing(frequency, gain, float(gain[0]) - 3.0),
    }


def analyze_compensation(parameters: dict[str, object]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    records: list[dict[str, object]] = []
    curves: dict[str, pd.DataFrame] = {}
    selected_tag = str(parameters["selected_tag"])
    for variant in parameters["variants"]:
        tag = str(variant["tag"])
        curve = load_loop(tag)
        curves[tag] = curve
        metrics = loop_metrics(curve)
        hard_pass = metrics["a0_db"] >= 50.0 and metrics["ugb_hz"] >= 5e6 and metrics["phase_margin_deg"] >= 55.0
        records.append(
            {
                "tag": tag,
                "cc_pf": float(variant["cc_f"]) * 1e12,
                "rz_ohm": float(variant["rz_ohm"]),
                **metrics,
                "low_frequency_phase_near_zero": abs(metrics["low_frequency_phase_deg"]) <= 5.0,
                "hard_ac_specs_pass": hard_pass,
                "selection_role": (
                    "SELECTED" if tag == selected_tag else "CC_ONLY_BASELINE" if tag == "cc3p_rz0" else "EXPLORED"
                ),
            }
        )
    frame = pd.DataFrame(records)
    frame.to_csv(ROOT / "results" / "day3_compensation_comparison.csv", index=False, float_format="%.9g")
    selected = frame.loc[frame["tag"] == selected_tag]
    if len(selected) != 1:
        raise ValueError(f"Selected compensation tag {selected_tag!r} is missing or duplicated")
    if not bool(selected.iloc[0]["low_frequency_phase_near_zero"]):
        raise ValueError("The return-ratio low-frequency phase is not near 0 degrees; loop sign is suspect")
    if not bool(selected.iloc[0]["hard_ac_specs_pass"]):
        raise ValueError(f"Selected compensation {selected_tag} does not pass the hard AC specifications")

    before_after = frame.loc[frame["tag"].isin(("cc3p_rz0", selected_tag))].copy()
    baseline_pm = float(frame.loc[frame["tag"] == "cc3p_rz0", "phase_margin_deg"].iloc[0])
    before_after.insert(0, "state", before_after["tag"].map({"cc3p_rz0": "BEFORE_CC_ONLY", selected_tag: "AFTER_RZ_SELECTED"}))
    before_after["phase_margin_improvement_vs_cc_only_deg"] = before_after["phase_margin_deg"] - baseline_pm
    before_after.to_csv(ROOT / "results" / "day3_compensation_before_after.csv", index=False, float_format="%.9g")
    return frame, curves


def verify_compact_sizing(parameters: dict[str, object]) -> Path:
    """Cross-check public sizing metadata against both generated production decks."""
    loop_deck = (GENERATED / f"{parameters['selected_tag']}.spice").read_text(encoding="utf-8")
    transient_deck = (GENERATED / "nominal_transient.spice").read_text(encoding="utf-8")
    required_lines = (
        ".param W12=16.83798 L12=0.5",
        ".param W34UNIT=25 L34=0.5",
        ".param W5=25.8754 L5=0.8",
        ".param W10=8.08605 L10=0.8",
    )
    for deck_name, deck in (("selected loop-gain", loop_deck), ("nominal transient", transient_deck)):
        missing = [line for line in required_lines if line not in deck]
        if missing:
            raise ValueError(f"{deck_name} deck does not contain final compact Day 2 sizing: {missing}")
        if deck.count("L={L34} W={W34UNIT}") != 4:
            raise ValueError(f"{deck_name} deck does not contain exactly two M3 and two M4 25-um units")

    records: list[dict[str, object]] = []
    for device, values in parameters["device_sizes_um"].items():
        records.append({"device": device, **values, "verified_in_both_production_decks": True})
    output = ROOT / "results" / "day3_design_parameters.csv"
    pd.DataFrame(records).to_csv(output, index=False, float_format="%.9g")
    return output


def load_operating_point(tag: str) -> pd.Series:
    columns = [
        "scale",
        "vout_v",
        "vx_v",
        "vbn_v",
        "vbp_v",
        "tail_v",
        "nmir_v",
        "vinp_v",
        "vinn_v",
        "idd_a",
    ]
    for number in range(1, 11):
        columns.extend((f"m{number}_id_a", f"m{number}_gm_s", f"m{number}_gds_s", f"m{number}_vdsat_v"))
    data = numeric_rows(RAW / f"{tag}_op.tsv", len(columns))
    return pd.DataFrame(data, columns=columns).iloc[-1]


def write_device_operating_point(op: pd.Series) -> tuple[Path, bool, float]:
    roles = {
        1: "input pair, VINN side",
        2: "input pair, VINP side",
        3: "PMOS mirror diode load (two units)",
        4: "PMOS mirror output load (two units)",
        5: "NMOS tail current sink",
        6: "NMOS second-stage common source",
        7: "PMOS second-stage current source",
        8: "PMOS diode IREF reference",
        9: "PMOS VBN-bias branch",
        10: "NMOS diode VBN reference",
    }
    widths = {1: 16.83798, 2: 16.83798, 3: 50.0, 4: 50.0, 5: 25.8754, 6: math.nan,
              7: 72.2005, 8: 7.22005, 9: 7.22005, 10: 8.08605}
    lengths = {1: 0.5, 2: 0.5, 3: 0.5, 4: 0.5, 5: 0.8, 6: 0.5,
               7: 0.8, 8: 0.8, 9: 0.8, 10: 0.8}
    parameters = json.loads((GENERATED / "selected_parameters.json").read_text(encoding="utf-8"))
    widths[6] = float(parameters["w6_um"])
    margins = {
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
    records: list[dict[str, object]] = []
    for number in range(1, 11):
        current = float(op[f"m{number}_id_a"])
        gm = float(op[f"m{number}_gm_s"])
        gds = float(op[f"m{number}_gds_s"])
        records.append(
            {
                "device": f"M{number}",
                "role": roles[number],
                "w_um": widths[number],
                "l_um": lengths[number],
                "drain_current_ua": current * 1e6,
                "gm_us": gm * 1e6,
                "gds_us": gds * 1e6,
                "gm_over_id_vinv": gm / current,
                "intrinsic_gain_vv": gm / gds,
                "vdsat_abs_v": float(op[f"m{number}_vdsat_v"]),
                "saturation_margin_v": margins[number],
                "model_saturation_check": "PASS" if margins[number] >= 0.0 else "FAIL",
            }
        )
    output = ROOT / "results" / "day3_nominal_operating_point.csv"
    pd.DataFrame(records).to_csv(output, index=False, float_format="%.9g")
    return output, all(value >= 0.0 for value in margins.values()), min(margins.values())


def settling_time(
    time_s: np.ndarray, output_v: np.ndarray, target_v: float, reference_s: float, window_end_s: float
) -> float:
    mask = (time_s >= reference_s) & (time_s < window_end_s)
    indices = np.flatnonzero(mask)
    if not indices.size:
        return math.nan
    within = np.abs(output_v[indices] - target_v) <= 0.01 * abs(target_v - (0.8 if target_v == 1.2 else 1.2))
    stays_within = np.logical_and.accumulate(within[::-1])[::-1]
    candidates = indices[np.flatnonzero(stays_within)]
    if not candidates.size:
        return math.nan
    return float(time_s[candidates[0]] - reference_s)


def crossing_time(
    time_s: np.ndarray,
    signal_v: np.ndarray,
    *,
    level_v: float,
    start_s: float,
    stop_s: float,
    rising: bool,
) -> float:
    """Linearly interpolate the first directed threshold crossing."""
    candidates = np.flatnonzero((time_s[:-1] >= start_s) & (time_s[1:] <= stop_s))
    for index in candidates:
        y0, y1 = float(signal_v[index]), float(signal_v[index + 1])
        directed = y0 <= level_v < y1 if rising else y0 >= level_v > y1
        if not directed:
            continue
        if y1 == y0:
            return float(time_s[index])
        fraction = (level_v - y0) / (y1 - y0)
        return float(time_s[index] + fraction * (time_s[index + 1] - time_s[index]))
    raise ValueError("Input did not cross its 50% level in the expected direction")


def fitted_slew_rate(
    time_s: np.ndarray,
    output_v: np.ndarray,
    *,
    start_s: float,
    stop_s: float,
    rising: bool,
) -> tuple[float, int]:
    """Fit the monotonic 20%-80% segment required by the frozen spec."""
    first_level, second_level = ((0.88, 1.12) if rising else (1.12, 0.88))
    window = np.flatnonzero((time_s >= start_s) & (time_s < stop_s))
    if not window.size:
        raise ValueError("Slew-rate search window contains no samples")

    if rising:
        first_candidates = window[output_v[window] >= first_level]
    else:
        first_candidates = window[output_v[window] <= first_level]
    if not first_candidates.size:
        raise ValueError("Output did not cross the first 20%-80% slew threshold")
    first = int(first_candidates[0])

    remaining = window[window >= first]
    if rising:
        second_candidates = remaining[output_v[remaining] >= second_level]
    else:
        second_candidates = remaining[output_v[remaining] <= second_level]
    if not second_candidates.size:
        raise ValueError("Output did not cross the second 20%-80% slew threshold")
    second = int(second_candidates[0])

    indices = np.arange(first, second + 1)
    if indices.size < 5:
        raise ValueError("Fewer than five samples span the 20%-80% slew interval")
    differences = np.diff(output_v[indices])
    tolerance_v = 1e-6
    if rising and np.any(differences < -tolerance_v):
        raise ValueError("Rising 20%-80% slew interval is not monotonic")
    if not rising and np.any(differences > tolerance_v):
        raise ValueError("Falling 80%-20% slew interval is not monotonic")

    slope_v_per_s = float(np.polyfit(time_s[indices], output_v[indices], 1)[0])
    return abs(slope_v_per_s) / 1e6, int(indices.size)


def analyze_transient() -> tuple[pd.DataFrame, dict[str, float]]:
    frame = pd.DataFrame(numeric_rows(RAW / "nominal_transient.tsv", 3), columns=("time_s", "vinp_v", "vout_v"))
    time_s = frame["time_s"].to_numpy()
    input_v = frame["vinp_v"].to_numpy()
    output_v = frame["vout_v"].to_numpy()
    sr_positive, rising_fit_points = fitted_slew_rate(
        time_s, output_v, start_s=1e-6, stop_s=2.2e-6, rising=True
    )
    sr_negative, falling_fit_points = fitted_slew_rate(
        time_s, output_v, start_s=3e-6, stop_s=4.2e-6, rising=False
    )
    rising_input_midpoint = crossing_time(
        time_s, input_v, level_v=1.0, start_s=1e-6, stop_s=1.02e-6, rising=True
    )
    falling_input_midpoint = crossing_time(
        time_s, input_v, level_v=1.0, start_s=3.02e-6, stop_s=3.04e-6, rising=False
    )
    rising_settle = settling_time(time_s, output_v, 1.2, rising_input_midpoint, 3.02e-6)
    falling_settle = settling_time(time_s, output_v, 0.8, falling_input_midpoint, 5.00e-6)
    high_window = (time_s >= 1.02e-6) & (time_s < 3.00e-6)
    low_window = (time_s >= 3.04e-6) & (time_s < 4.98e-6)
    metrics = {
        "slew_rate_positive_v_per_us": sr_positive,
        "slew_rate_negative_v_per_us": sr_negative,
        "slew_rate_positive_fit_points": rising_fit_points,
        "slew_rate_negative_fit_points": falling_fit_points,
        "rising_1pct_settling_us": rising_settle * 1e6,
        "falling_1pct_settling_us": falling_settle * 1e6,
        "worst_1pct_settling_us": max(rising_settle, falling_settle) * 1e6,
        "rising_input_50pct_crossing_us": rising_input_midpoint * 1e6,
        "falling_input_50pct_crossing_us": falling_input_midpoint * 1e6,
        "rising_overshoot_mv": max(0.0, float(np.max(output_v[high_window]) - 1.2)) * 1e3,
        "falling_undershoot_mv": max(0.0, float(0.8 - np.min(output_v[low_window]))) * 1e3,
        "initial_output_v": float(output_v[0]),
        "final_output_v": float(output_v[-1]),
    }
    return frame, metrics


def write_summary(
    parameters: dict[str, object], selected: pd.Series, op: pd.Series, transient: dict[str, float],
    all_saturated: bool, minimum_margin: float
) -> Path:
    power_uw = 1.8 * float(op["idd_a"]) * 1e6
    rows = [
        ("stage_status", "DAY3_NOMINAL_COMPLETE_PVT_NOT_RUN", "", "informational", "INFO"),
        ("corner", "tt", "", "nominal", "INFO"),
        ("temperature_c", 27, "degC", "nominal", "INFO"),
        ("vdd_v", 1.8, "V", "nominal", "INFO"),
        ("vcm_v", 0.9, "V", "nominal", "INFO"),
        ("rload_to_vss_ohm", 100000, "ohm", "fixed load", "INFO"),
        ("cload_pf", 5.0, "pF", "fixed load", "INFO"),
        ("w6_um", float(parameters["w6_um"]), "um", "M6 balance-selected", "INFO"),
        ("cc_pf", float(parameters["cc_f"]) * 1e12, "pF", "selected compensation", "INFO"),
        ("rz_ohm", float(parameters["rz_ohm"]), "ohm", "selected compensation", "INFO"),
        ("dc_output_v", float(op["vout_v"]), "V", "unity-follower DC at VINP=0.9 V", "PASS" if abs(float(op["vout_v"])-0.9) <= 0.01 else "FAIL"),
        ("supply_current_ua", float(op["idd_a"]) * 1e6, "uA", "reported", "INFO"),
        ("quiescent_power_uw", power_uw, "uW", "<=600 hard; <=400 stretch", "PASS" if power_uw <= 600 else "FAIL"),
        ("open_loop_gain_db", float(selected["a0_db"]), "dB", ">=50 hard; >=60 stretch", "PASS" if float(selected["a0_db"]) >= 50 else "FAIL"),
        ("unity_gain_bandwidth_mhz", float(selected["ugb_hz"]) / 1e6, "MHz", ">=5 hard; >=10 stretch", "PASS" if float(selected["ugb_hz"]) >= 5e6 else "FAIL"),
        ("phase_margin_deg", float(selected["phase_margin_deg"]), "deg", ">=55 hard; >=65 stretch", "PASS" if float(selected["phase_margin_deg"]) >= 55 else "FAIL"),
        ("loop_phase_at_1hz_deg", float(selected["low_frequency_phase_deg"]), "deg", "near 0 confirms T sign", "PASS" if abs(float(selected["low_frequency_phase_deg"])) <= 5 else "FAIL"),
        ("slew_rate_positive_v_per_us", transient["slew_rate_positive_v_per_us"], "V/us", ">=2 hard; >=4 stretch", "PASS" if transient["slew_rate_positive_v_per_us"] >= 2 else "FAIL"),
        ("slew_rate_negative_v_per_us", transient["slew_rate_negative_v_per_us"], "V/us", ">=2 hard; >=4 stretch", "PASS" if transient["slew_rate_negative_v_per_us"] >= 2 else "FAIL"),
        ("slew_rate_positive_fit_points", transient["slew_rate_positive_fit_points"], "samples", "20%-80% least-squares fit; >=5", "PASS" if transient["slew_rate_positive_fit_points"] >= 5 else "FAIL"),
        ("slew_rate_negative_fit_points", transient["slew_rate_negative_fit_points"], "samples", "80%-20% least-squares fit; >=5", "PASS" if transient["slew_rate_negative_fit_points"] >= 5 else "FAIL"),
        ("rising_input_50pct_crossing_us", transient["rising_input_50pct_crossing_us"], "us", "settling-time reference", "INFO"),
        ("falling_input_50pct_crossing_us", transient["falling_input_50pct_crossing_us"], "us", "settling-time reference", "INFO"),
        ("rising_1pct_settling_us", transient["rising_1pct_settling_us"], "us", "reported", "INFO"),
        ("falling_1pct_settling_us", transient["falling_1pct_settling_us"], "us", "reported", "INFO"),
        ("worst_1pct_settling_us", transient["worst_1pct_settling_us"], "us", "<=1.5 hard; <=1 stretch", "PASS" if transient["worst_1pct_settling_us"] <= 1.5 else "FAIL"),
        ("rising_overshoot_mv", transient["rising_overshoot_mv"], "mV", "reported large-signal behavior", "INFO"),
        ("falling_undershoot_mv", transient["falling_undershoot_mv"], "mV", "reported large-signal behavior", "INFO"),
        ("all_m1_to_m10_saturated", all_saturated, "", "all model margins >=0", "PASS" if all_saturated else "FAIL"),
        ("minimum_device_saturation_margin_v", minimum_margin, "V", ">=0", "PASS" if minimum_margin >= 0 else "FAIL"),
        ("analysis_scope", "schematic-level simulation", "", "no fabricated/measured claim", "INFO"),
    ]
    output = ROOT / "results" / "day3_nominal_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("metric", "value", "unit", "requirement_or_context", "status"))
        writer.writerows(rows)
    return output


def plot_balance(parameters: dict[str, object]) -> Path:
    frame = pd.read_csv(ROOT / "results" / "day3_m6_balance.csv")
    selected = float(parameters["w6_um"])
    fig, axes = plt.subplots(2, 1, figsize=(8.7, 7.2), sharex=True, constrained_layout=True)
    axes[0].plot(frame["w6_um"], frame["m6_current_ua"], label="M6 sink", linewidth=2.0)
    axes[0].plot(frame["w6_um"], frame["m7_current_ua"] - frame["rl_current_ua"], label="M7 source - 9 uA load", linewidth=2.0)
    axes[0].axvline(selected, color="#D1495B", linestyle="--", label=f"selected {selected:.3f} um")
    axes[0].set(ylabel="Current (uA)", title="M6 balance at fixed VOUT=0.9 V and VX=0.79207 V")
    axes[0].legend()
    axes[1].plot(frame["w6_um"], frame["residual_ua"], color="#176B87", linewidth=2.0)
    axes[1].axhline(0, color="#555555", linestyle="--")
    axes[1].axvline(selected, color="#D1495B", linestyle="--")
    axes[1].set(xlabel="M6 width (um), L=0.5 um", ylabel="M7 - M6 - load (uA)")
    for axis in axes:
        axis.grid(True, alpha=0.3)
    output = PLOTS / "day3_m6_balance.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_compensation(comparison: pd.DataFrame, curves: dict[str, pd.DataFrame], selected_tag: str) -> Path:
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 7.8), sharex=True, constrained_layout=True)
    for tag, curve in curves.items():
        selected = tag == selected_tag
        baseline = tag == "cc3p_rz0"
        if not (selected or baseline):
            axes[0].semilogx(curve["frequency_hz"], curve["gain_db"], color="#B8B8B8", linewidth=0.8, alpha=0.45)
            axes[1].semilogx(curve["frequency_hz"], curve["phase_unwrapped_deg"], color="#B8B8B8", linewidth=0.8, alpha=0.45)
            continue
        color = "#D1495B" if selected else "#176B87"
        label = "selected 3 pF + 2 kohm" if selected else "baseline 3 pF, RZ~0"
        axes[0].semilogx(curve["frequency_hz"], curve["gain_db"], color=color, linewidth=2.3, label=label)
        axes[1].semilogx(curve["frequency_hz"], curve["phase_unwrapped_deg"], color=color, linewidth=2.3, label=label)
    axes[0].axhline(0, color="#555555", linestyle="--", linewidth=1)
    axes[1].axhline(-180, color="#555555", linestyle="--", linewidth=1)
    axes[0].set(ylabel="Return-ratio magnitude (dB)", title="Day 3 Miller compensation exploration - TT, 1.8 V, 27 C")
    axes[1].set(xlabel="Frequency (Hz)", ylabel="Unwrapped phase (deg)")
    axes[0].legend()
    axes[1].legend()
    for axis in axes:
        axis.grid(True, which="both", alpha=0.28)
    selected = comparison.loc[comparison["tag"] == selected_tag].iloc[0]
    axes[0].text(0.02, 0.06, f"selected: A0={selected['a0_db']:.2f} dB, UGB={selected['ugb_hz']/1e6:.2f} MHz",
                 transform=axes[0].transAxes, bbox={"facecolor": "white", "alpha": 0.86, "edgecolor": "#AAAAAA"})
    axes[1].text(0.02, 0.08, f"selected PM={selected['phase_margin_deg']:.2f} deg",
                 transform=axes[1].transAxes, bbox={"facecolor": "white", "alpha": 0.86, "edgecolor": "#AAAAAA"})
    output = PLOTS / "day3_loop_gain_compensation.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_transient(frame: pd.DataFrame, metrics: dict[str, float]) -> Path:
    time_us = frame["time_s"] * 1e6
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 7.5), sharex=True, constrained_layout=True)
    axes[0].plot(time_us, frame["vinp_v"], color="#777777", linestyle="--", linewidth=1.7, label="VINP")
    axes[0].plot(time_us, frame["vout_v"], color="#176B87", linewidth=2.1, label="VOUT")
    axes[0].set(ylabel="Voltage (V)", title="Day 3 unity-follower 0.8 / 1.2-V transient - 5 pF || 100 kohm to VSS")
    axes[0].legend()
    axes[1].plot(time_us, (frame["vout_v"] - frame["vinp_v"]) * 1e3, color="#D1495B", linewidth=1.6)
    axes[1].axhline(4, color="#777777", linestyle=":")
    axes[1].axhline(-4, color="#777777", linestyle=":")
    axes[1].set(xlabel="Time (us)", ylabel="VOUT - VINP (mV)")
    axes[0].text(
        0.54,
        0.08,
        f"20%-80% fit: SR+={metrics['slew_rate_positive_v_per_us']:.2f} V/us\n"
        f"SR-={metrics['slew_rate_negative_v_per_us']:.2f} V/us\n"
        f"worst 1% settle={metrics['worst_1pct_settling_us']:.3f} us",
        transform=axes[0].transAxes,
        bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": "#AAAAAA"},
    )
    for axis in axes:
        axis.grid(True, alpha=0.3)
    output = PLOTS / "day3_unity_follower_transient.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def audit_logs() -> Path:
    records: list[dict[str, object]] = []
    fatal_needles = ("error:", "fatal", "timestep too small", "singular matrix", "convergence failed")
    any_fatal = False
    for path in sorted(RAW.glob("*.log")):
        text = path.read_text(encoding="utf-8", errors="replace")
        lower = text.lower()
        hits = [needle for needle in fatal_needles if needle in lower]
        any_fatal |= bool(hits)
        records.append(
            {
                "log": path.name,
                "ngspice_done": "ngspice-47 done" in lower,
                "fatal_tokens": ";".join(hits),
                "known_multiplier_warning_count": lower.count("m=xx on .subckt line"),
                "dynamic_gmin_used": "dynamic gmin stepping completed" in lower,
            }
        )
    output = ROOT / "results" / "day3_log_audit.csv"
    pd.DataFrame(records).to_csv(output, index=False)
    if any_fatal:
        raise RuntimeError(f"Fatal/error text found in Day 3 logs; inspect {output}")
    return output


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    parameters = json.loads((GENERATED / "selected_parameters.json").read_text(encoding="utf-8"))
    verify_compact_sizing(parameters)
    comparison, curves = analyze_compensation(parameters)
    selected = comparison.loc[comparison["tag"] == parameters["selected_tag"]].iloc[0]
    op = load_operating_point(str(parameters["selected_tag"]))
    _, all_saturated, minimum_margin = write_device_operating_point(op)
    transient_frame, transient_metrics = analyze_transient()
    write_summary(parameters, selected, op, transient_metrics, all_saturated, minimum_margin)
    plot_balance(parameters)
    plot_compensation(comparison, curves, str(parameters["selected_tag"]))
    plot_transient(transient_frame, transient_metrics)
    audit_logs()
    print(json.dumps({
        "selected_tag": parameters["selected_tag"],
        "w6_um": parameters["w6_um"],
        "a0_db": selected["a0_db"],
        "ugb_mhz": selected["ugb_hz"] / 1e6,
        "phase_margin_deg": selected["phase_margin_deg"],
        "power_uw": 1.8 * float(op["idd_a"]) * 1e6,
        **transient_metrics,
        "all_m1_to_m10_saturated": all_saturated,
        "minimum_saturation_margin_v": minimum_margin,
    }, indent=2))


if __name__ == "__main__":
    main()
