#!/usr/bin/env python3
"""Analyze Day 2 M1-M5 first-stage simulations and create review artifacts."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "day2"
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


def interpolate_crossing(x: np.ndarray, y: np.ndarray, level: float) -> float:
    candidates = np.flatnonzero((y[:-1] - level) * (y[1:] - level) <= 0)
    if candidates.size == 0:
        return math.nan
    index = int(candidates[0])
    x0, x1 = float(x[index]), float(x[index + 1])
    y0, y1 = float(y[index]), float(y[index + 1])
    if y1 == y0:
        return x0
    if x0 > 0 and x1 > 0:
        fraction = (level - y0) / (y1 - y0)
        return float(10 ** (np.log10(x0) + fraction * (np.log10(x1) - np.log10(x0))))
    return float(x0 + (level - y0) * (x1 - x0) / (y1 - y0))


def contiguous_interval_containing(x: np.ndarray, mask: np.ndarray, point: float) -> tuple[float, float]:
    if not mask.any():
        return math.nan, math.nan
    anchor = int(np.argmin(np.abs(x - point)))
    if not mask[anchor]:
        return math.nan, math.nan
    lo = anchor
    hi = anchor
    while lo > 0 and mask[lo - 1]:
        lo -= 1
    while hi + 1 < len(mask) and mask[hi + 1]:
        hi += 1
    return float(x[lo]), float(x[hi])


def load_results() -> tuple[pd.Series, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    op_columns = (
        "scale",
        "vbn_v",
        "tail_v",
        "nmir_v",
        "vx_v",
        "m1_id_a",
        "m2_id_a",
        "m3_id_a",
        "m4_id_a",
        "m5_id_a",
        "m1_gm_s",
        "m1_gds_s",
        "m2_gm_s",
        "m2_gds_s",
        "m3_gm_s",
        "m3_gds_s",
        "m4_gm_s",
        "m4_gds_s",
        "m5_gm_s",
        "m5_gds_s",
        "m1_vdsat_v",
        "m2_vdsat_v",
        "m3_vdsat_v",
        "m4_vdsat_v",
        "m5_vdsat_v",
        "idd_a",
    )
    ac_columns = ("frequency_hz", "gain_db", "phase_deg")
    diff_columns = ("vid_v", "vx_v", "nmir_v", "tail_v", "m1_id_a", "m2_id_a", "m5_id_a")
    icmr_columns = (
        "vcm_v",
        "vbn_v",
        "tail_v",
        "nmir_v",
        "vx_v",
        "m1_id_a",
        "m2_id_a",
        "m3_id_a",
        "m4_id_a",
        "m5_id_a",
        "m1_sat_margin_v",
        "m2_sat_margin_v",
        "m3_sat_margin_v",
        "m4_sat_margin_v",
        "m5_sat_margin_v",
    )
    # ngspice wrdata emits the constant-vector scale as an extra column here.
    icmr_gain_columns = ("frequency_hz", "vcm_v", "constant_scale", "gain_db")
    op_frame = pd.DataFrame(numeric_rows(RAW / "first_stage_op.tsv", len(op_columns)), columns=op_columns)
    ac = pd.DataFrame(numeric_rows(RAW / "first_stage_ac.tsv", len(ac_columns)), columns=ac_columns)
    diff = pd.DataFrame(numeric_rows(RAW / "first_stage_diff_dc.tsv", len(diff_columns)), columns=diff_columns)
    icmr = pd.DataFrame(numeric_rows(RAW / "first_stage_icmr.tsv", len(icmr_columns)), columns=icmr_columns)
    icmr_gain = pd.DataFrame(
        numeric_rows(RAW / "first_stage_icmr_gain.tsv", len(icmr_gain_columns)), columns=icmr_gain_columns
    )
    return op_frame.iloc[-1], ac, diff, icmr, icmr_gain


def analyze(
    op: pd.Series,
    ac: pd.DataFrame,
    diff: pd.DataFrame,
    icmr: pd.DataFrame,
    icmr_gain: pd.DataFrame,
) -> dict[str, object]:
    low_frequency_gain_db = float(ac.iloc[0]["gain_db"])
    bandwidth_3db_hz = interpolate_crossing(
        ac["frequency_hz"].to_numpy(), ac["gain_db"].to_numpy(), low_frequency_gain_db - 3.0
    )
    unity_gain_hz = interpolate_crossing(ac["frequency_hz"].to_numpy(), ac["gain_db"].to_numpy(), 0.0)

    central = diff[np.abs(diff["vid_v"]) <= 5e-4]
    if len(central) < 3:
        raise ValueError("Differential sweep does not contain enough points around zero")
    dc_slope, dc_intercept = np.polyfit(central["vid_v"], central["vx_v"], 1)
    dc_gain_vv = abs(float(dc_slope))
    dc_gain_db = float(20 * np.log10(dc_gain_vv))

    nominal_half_tail = float(op["m5_id_a"]) / 2.0
    current_ok = (
        icmr["m5_id_a"].between(0.90 * float(op["m5_id_a"]), 1.10 * float(op["m5_id_a"]))
        & icmr["m1_id_a"].between(0.85 * nominal_half_tail, 1.15 * nominal_half_tail)
        & icmr["m2_id_a"].between(0.85 * nominal_half_tail, 1.15 * nominal_half_tail)
    )
    saturation_columns = [column for column in icmr.columns if column.endswith("sat_margin_v")]
    saturation_ok = (icmr[saturation_columns] >= 0.0).all(axis=1)
    voltage_ok = icmr["vx_v"].between(0.05, 1.75)
    icmr["dc_region_valid"] = current_ok & saturation_ok & voltage_ok
    dc_region_min, dc_region_max = contiguous_interval_containing(
        icmr["vcm_v"].to_numpy(), icmr["dc_region_valid"].to_numpy(dtype=bool), 0.9
    )

    nominal_gain_db = float(np.interp(0.9, icmr_gain["vcm_v"], icmr_gain["gain_db"]))
    for column in saturation_columns:
        icmr_gain[column] = np.interp(icmr_gain["vcm_v"], icmr["vcm_v"], icmr[column])
    icmr_gain["min_sat_margin_v"] = icmr_gain[saturation_columns].min(axis=1)
    icmr_gain["vx_v"] = np.interp(icmr_gain["vcm_v"], icmr["vcm_v"], icmr["vx_v"])
    icmr_gain["gain_delta_db"] = icmr_gain["gain_db"] - nominal_gain_db
    icmr_gain["valid"] = (
        (icmr_gain["gain_delta_db"] >= -3.0)
        & (icmr_gain["min_sat_margin_v"] >= 0.0)
        & icmr_gain["vx_v"].between(0.05, 1.75)
    )
    icmr_min, icmr_max = contiguous_interval_containing(
        icmr_gain["vcm_v"].to_numpy(), icmr_gain["valid"].to_numpy(dtype=bool), 0.9
    )
    covers_required_range = bool(
        np.isfinite(icmr_min) and np.isfinite(icmr_max) and icmr_min <= 0.8 and icmr_max >= 1.3
    )

    def at_vcm(column: str, value: float) -> float:
        return float(np.interp(value, icmr_gain["vcm_v"], icmr_gain[column]))

    m1_sat = float(op["nmir_v"] - op["tail_v"] - op["m1_vdsat_v"])
    m2_sat = float(op["vx_v"] - op["tail_v"] - op["m2_vdsat_v"])
    m3_sat = float(1.8 - op["nmir_v"] - op["m3_vdsat_v"])
    m4_sat = float(1.8 - op["vx_v"] - op["m4_vdsat_v"])
    m5_sat = float(op["tail_v"] - op["m5_vdsat_v"])

    return {
        "corner": "tt",
        "temperature_c": 27.0,
        "vdd_v": 1.8,
        "vcm_v": 0.9,
        "reference_current_ua": 10.0,
        "supply_current_ua": float(op["idd_a"] * 1e6),
        "first_stage_power_uw": float(1.8 * op["idd_a"] * 1e6),
        "tail_current_ua": float(op["m5_id_a"] * 1e6),
        "m1_current_ua": float(op["m1_id_a"] * 1e6),
        "m2_current_ua": float(op["m2_id_a"] * 1e6),
        "bias_voltage_v": float(op["vbn_v"]),
        "tail_voltage_v": float(op["tail_v"]),
        "mirror_voltage_v": float(op["nmir_v"]),
        "first_stage_output_v": float(op["vx_v"]),
        "m1_gm_id_vinv": float(op["m1_gm_s"] / op["m1_id_a"]),
        "m1_gm_gds_vv": float(op["m1_gm_s"] / op["m1_gds_s"]),
        "m1_sat_margin_v": m1_sat,
        "m2_sat_margin_v": m2_sat,
        "m3_sat_margin_v": m3_sat,
        "m4_sat_margin_v": m4_sat,
        "m5_sat_margin_v": m5_sat,
        "ac_gain_1hz_db": low_frequency_gain_db,
        "dc_gain_near_zero_vv": dc_gain_vv,
        "dc_gain_near_zero_db": dc_gain_db,
        "first_stage_3db_bandwidth_hz": bandwidth_3db_hz,
        "first_stage_unity_gain_hz": unity_gain_hz,
        "dc_operating_region_min_v": dc_region_min,
        "dc_operating_region_max_v": dc_region_max,
        "icmr_gain_reference_at_0p9v_db": nominal_gain_db,
        "icmr_gain_delta_at_0p8v_db": at_vcm("gain_delta_db", 0.8),
        "icmr_gain_delta_at_1p3v_db": at_vcm("gain_delta_db", 1.3),
        "icmr_min_sat_margin_at_0p8v_v": at_vcm("min_sat_margin_v", 0.8),
        "icmr_min_sat_margin_at_1p3v_v": at_vcm("min_sat_margin_v", 1.3),
        "icmr_criterion_min_v": icmr_min,
        "icmr_criterion_max_v": icmr_max,
        "icmr_covers_0p8_to_1p3": covers_required_range,
        "icmr_criterion": "1-Hz differential gain no more than 3 dB below its VCM=0.9 V value; all M1-M5 model saturation margins >=0; 0.05<VX<1.75",
        "dc_operating_region_criterion": "preliminary diagnostic only: tail within 10%, each branch within 15% of nominal, saturation margins >=0, 0.05<VX<1.75",
        "stage_status": "DAY2_FIRST_STAGE_CHARACTERIZED_NOT_FINAL_OTA",
    }


def write_summary(metrics: dict[str, object]) -> Path:
    units = {
        "temperature_c": "degC",
        "vdd_v": "V",
        "vcm_v": "V",
        "reference_current_ua": "uA",
        "supply_current_ua": "uA",
        "first_stage_power_uw": "uW",
        "tail_current_ua": "uA",
        "m1_current_ua": "uA",
        "m2_current_ua": "uA",
        "bias_voltage_v": "V",
        "tail_voltage_v": "V",
        "mirror_voltage_v": "V",
        "first_stage_output_v": "V",
        "m1_gm_id_vinv": "1/V",
        "m1_gm_gds_vv": "V/V",
        "m1_sat_margin_v": "V",
        "m2_sat_margin_v": "V",
        "m3_sat_margin_v": "V",
        "m4_sat_margin_v": "V",
        "m5_sat_margin_v": "V",
        "ac_gain_1hz_db": "dB",
        "dc_gain_near_zero_vv": "V/V",
        "dc_gain_near_zero_db": "dB",
        "first_stage_3db_bandwidth_hz": "Hz",
        "first_stage_unity_gain_hz": "Hz",
        "dc_operating_region_min_v": "V",
        "dc_operating_region_max_v": "V",
        "icmr_gain_reference_at_0p9v_db": "dB",
        "icmr_gain_delta_at_0p8v_db": "dB",
        "icmr_gain_delta_at_1p3v_db": "dB",
        "icmr_min_sat_margin_at_0p8v_v": "V",
        "icmr_min_sat_margin_at_1p3v_v": "V",
        "icmr_criterion_min_v": "V",
        "icmr_criterion_max_v": "V",
    }
    output = ROOT / "results" / "day2_first_stage_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("metric", "value", "unit"))
        writer.writeheader()
        for key, value in metrics.items():
            writer.writerow({"metric": key, "value": value, "unit": units.get(key, "")})
    return output


def write_operating_point(op: pd.Series) -> Path:
    output = ROOT / "results" / "day2_first_stage_operating_point.csv"
    op.drop(labels=["scale"]).rename_axis("quantity").reset_index(name="value").to_csv(
        output, index=False, float_format="%.9g"
    )
    return output


def write_selected_sizing() -> Path:
    rows = [
        {
            "device_group": "M1/M2",
            "role": "NMOS differential input pair (each)",
            "day1_width_um": 6.73519,
            "day1_length_um": 0.5,
            "selected_total_width_um": 16.83798,
            "selected_unit_count": 1,
            "selected_unit_width_um": 16.83798,
            "selected_length_um": 0.5,
            "reason": "2.5x width lowers required VGS/VDSAT and recovers low-VCM headroom",
        },
        {
            "device_group": "M3/M4",
            "role": "PMOS active-load mirror bank (each side)",
            "day1_width_um": 22.4281,
            "day1_length_um": 0.8,
            "selected_total_width_um": 50.0,
            "selected_unit_count": 2,
            "selected_unit_width_um": 25.0,
            "selected_length_um": 0.5,
            "reason": "sets VX near 0.8 V while shorter L limits area/parasitics and flattens gain versus VCM",
        },
        {
            "device_group": "M5",
            "role": "NMOS tail current source",
            "day1_width_um": 10.7814,
            "day1_length_um": 0.8,
            "selected_total_width_um": 25.8754,
            "selected_unit_count": 1,
            "selected_unit_width_um": 25.8754,
            "selected_length_um": 0.8,
            "reason": "2.4x width lowers tail-source VDSAT",
        },
        {
            "device_group": "MB",
            "role": "10-uA diode-connected NMOS bias reference",
            "day1_width_um": 2.69535,
            "day1_length_um": 0.8,
            "selected_total_width_um": 8.08605,
            "selected_unit_count": 1,
            "selected_unit_width_um": 8.08605,
            "selected_length_um": 0.8,
            "reason": "sets the actual-circuit M5 current near 40 uA with the widened tail device",
        },
    ]
    output = ROOT / "results" / "day2_first_stage_sizing.csv"
    pd.DataFrame(rows).to_csv(output, index=False, float_format="%.8g")
    return output


def write_icmr_evidence(icmr_gain: pd.DataFrame) -> Path:
    output = ROOT / "results" / "day2_icmr_gain_sweep.csv"
    columns = ("vcm_v", "gain_db", "gain_delta_db", "vx_v", "min_sat_margin_v", "valid")
    icmr_gain.loc[:, columns].to_csv(output, index=False, float_format="%.9g")
    return output


def plot_ac(ac: pd.DataFrame, metrics: dict[str, object]) -> Path:
    fig, (gain_axis, phase_axis) = plt.subplots(2, 1, figsize=(9, 7), sharex=True, constrained_layout=True)
    gain_axis.semilogx(ac["frequency_hz"], ac["gain_db"], color="#176B87", linewidth=2.1)
    gain_axis.axhline(0.0, color="#555555", linewidth=1, linestyle="--")
    gain_axis.set(ylabel="|VX / VID| (dB)", title="Day 2 first-stage differential AC response - TT, 1.8 V, 27 C")
    gain_axis.text(
        0.02,
        0.08,
        f"A1(1 Hz) = {float(metrics['ac_gain_1hz_db']):.2f} dB",
        transform=gain_axis.transAxes,
        bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "#AAAAAA"},
    )
    phase_axis.semilogx(ac["frequency_hz"], ac["phase_deg"], color="#D1495B", linewidth=2.0)
    phase_axis.set(xlabel="Frequency (Hz)", ylabel="Phase (deg)")
    gain_axis.grid(True, which="both", alpha=0.3)
    phase_axis.grid(True, which="both", alpha=0.3)
    output = PLOTS / "day2_first_stage_ac.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_dc_icmr(
    diff: pd.DataFrame,
    icmr: pd.DataFrame,
    icmr_gain: pd.DataFrame,
    metrics: dict[str, object],
) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.2), constrained_layout=True)
    axes[0, 0].plot(diff["vid_v"] * 1e3, diff["vx_v"], color="#176B87", linewidth=2.1, label="VX")
    axes[0, 0].plot(diff["vid_v"] * 1e3, diff["nmir_v"], color="#777777", linestyle="--", label="mirror node")
    axes[0, 0].set(xlabel="Differential input VID (mV)", ylabel="Voltage (V)", title="Open-loop differential transfer")
    axes[0, 0].legend()

    axes[0, 1].plot(diff["vid_v"] * 1e3, diff["m1_id_a"] * 1e6, label="M1", linewidth=2)
    axes[0, 1].plot(diff["vid_v"] * 1e3, diff["m2_id_a"] * 1e6, label="M2", linewidth=2)
    axes[0, 1].plot(diff["vid_v"] * 1e3, diff["m5_id_a"] * 1e6, label="M5 tail", linewidth=1.6, linestyle="--")
    axes[0, 1].set(xlabel="Differential input VID (mV)", ylabel="Drain current (uA)", title="Differential-pair current steering")
    axes[0, 1].legend()

    axes[1, 0].plot(icmr["vcm_v"], icmr["tail_v"], label="tail", linewidth=2)
    axes[1, 0].plot(icmr["vcm_v"], icmr["nmir_v"], label="mirror node", linewidth=2)
    axes[1, 0].plot(icmr["vcm_v"], icmr["vx_v"], label="VX", linewidth=2)
    axes[1, 0].plot(icmr["vcm_v"], icmr["vbn_v"], label="VBN", linestyle="--", linewidth=1.5)
    axes[1, 0].set(xlabel="Input common-mode voltage (V)", ylabel="Node voltage (V)", title="Common-mode operating-point sweep")
    axes[1, 0].legend(ncol=2)

    axes[1, 1].plot(icmr_gain["vcm_v"], icmr_gain["gain_delta_db"], color="#176B87", linewidth=2.1, label="gain vs. 0.9 V")
    axes[1, 1].axhline(-3.0, color="#176B87", linestyle="--", linewidth=1, label="-3 dB limit")
    margin_axis = axes[1, 1].twinx()
    margin_axis.plot(icmr_gain["vcm_v"], icmr_gain["min_sat_margin_v"], color="#D1495B", linewidth=1.7, label="minimum saturation margin")
    margin_axis.axhline(0, color="#D1495B", linestyle=":", linewidth=1)
    lo = float(metrics["icmr_criterion_min_v"])
    hi = float(metrics["icmr_criterion_max_v"])
    if np.isfinite(lo) and np.isfinite(hi):
        axes[1, 1].axvspan(lo, hi, color="#2A9D8F", alpha=0.12, label=f"ICMR: {lo:.2f}-{hi:.2f} V")
    axes[1, 1].set(xlabel="Input common-mode voltage (V)", ylabel="Gain change (dB)", title="Gain-based ICMR and saturation check")
    margin_axis.set_ylabel("Minimum saturation margin (V)", color="#D1495B")
    lines = axes[1, 1].get_lines() + margin_axis.get_lines()
    labels = [line.get_label() for line in lines if not line.get_label().startswith("_")]
    lines = [line for line in lines if not line.get_label().startswith("_")]
    axes[1, 1].legend(lines, labels, loc="lower center", fontsize=8)

    for axis in axes.flat:
        axis.grid(True, alpha=0.3)
    fig.suptitle("SKY130A M1-M5 first-stage checks - TT, 1.8 V, 27 C", fontsize=15)
    output = PLOTS / "day2_first_stage_dc_icmr.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    op, ac, diff, icmr, icmr_gain = load_results()
    metrics = analyze(op, ac, diff, icmr, icmr_gain)
    summary = write_summary(metrics)
    operating_point = write_operating_point(op)
    sizing = write_selected_sizing()
    icmr_evidence = write_icmr_evidence(icmr_gain)
    ac_plot = plot_ac(ac, metrics)
    dc_plot = plot_dc_icmr(diff, icmr, icmr_gain, metrics)
    print(f"Wrote {summary}")
    print(f"Wrote {operating_point}")
    print(f"Wrote {sizing}")
    print(f"Wrote {icmr_evidence}")
    print(f"Wrote {ac_plot}")
    print(f"Wrote {dc_plot}")


if __name__ == "__main__":
    main()
