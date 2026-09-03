#!/usr/bin/env python3
"""Analyze Day 1 device and current-mirror sweeps and create review artifacts."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw" / "day1"
PLOTS = ROOT / "results" / "plots"
CHAR_COLUMNS = ("gate_v", "id_a", "gm_s", "gds_s", "vth_v", "vdsat_v", "gm_id_vinv", "gm_gds")
MIRROR_COLUMNS = (
    "vout_v",
    "iref_forced_a",
    "iref_mos_a",
    "iout_a",
    "error_vs_forced_pct",
    "error_vs_reference_mos_pct",
    "vdsat_v",
    "sat_margin_v",
)
EXPECTED_SWEEP_POINTS = 181
SWEEP_ATOL_V = 1e-8


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


def validate_sweep(
    frame: pd.DataFrame,
    path: Path,
    *,
    start_v: float,
    stop_v: float,
) -> None:
    """Reject incomplete, non-finite, duplicated, or off-grid Day 1 sweeps."""

    if len(frame) != EXPECTED_SWEEP_POINTS:
        raise ValueError(
            f"Expected {EXPECTED_SWEEP_POINTS} numeric rows in {path}, found {len(frame)}"
        )
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        row, column = np.argwhere(~np.isfinite(values))[0]
        raise ValueError(
            f"Non-finite value in {path} at numeric row {row + 1}, "
            f"column {frame.columns[column]}"
        )
    expected_grid = np.linspace(start_v, stop_v, EXPECTED_SWEEP_POINTS)
    measured_grid = frame.iloc[:, 0].to_numpy(dtype=float)
    if not np.allclose(measured_grid, expected_grid, rtol=0.0, atol=SWEEP_ATOL_V):
        mismatch = int(
            np.flatnonzero(
                ~np.isclose(measured_grid, expected_grid, rtol=0.0, atol=SWEEP_ATOL_V)
            )[0]
        )
        raise ValueError(
            f"Unexpected sweep grid in {path} at numeric row {mismatch + 1}: "
            f"got {measured_grid[mismatch]:.12g} V, "
            f"expected {expected_grid[mismatch]:.12g} V"
        )


def contiguous_true_interval(
    mask: pd.Series,
    *,
    label: str,
    require_through_final_point: bool = False,
) -> tuple[int, int]:
    indices = np.flatnonzero(mask.to_numpy(dtype=bool))
    if indices.size == 0:
        raise ValueError(f"No points satisfy {label}")
    if not np.array_equal(indices, np.arange(indices[0], indices[-1] + 1)):
        raise ValueError(f"{label} is not one continuous sweep interval")
    if require_through_final_point and indices[-1] != len(mask) - 1:
        raise ValueError(f"{label} does not remain valid through the final sweep point")
    return int(indices[0]), int(indices[-1])


def load_characterization(device: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    pattern = re.compile(rf"{device}_characterization_l(?P<tag>[0-9p]+)\.tsv$")
    for path in sorted(RAW.glob(f"{device}_characterization_l*.tsv")):
        match = pattern.search(path.name)
        if not match:
            continue
        length_um = float(match.group("tag").replace("p", "."))
        frame = pd.DataFrame(numeric_rows(path, len(CHAR_COLUMNS)), columns=CHAR_COLUMNS)
        if device == "pfet":
            validate_sweep(frame, path, start_v=1.8, stop_v=0.0)
        else:
            validate_sweep(frame, path, start_v=0.0, stop_v=1.8)
        frame["device"] = device
        frame["length_um"] = length_um
        frame["id_per_w_ua_per_um"] = frame["id_a"] * 1e6 / 5.0
        if device == "pfet":
            frame["gate_overdrive_axis_v"] = 1.8 - frame["gate_v"]
        else:
            frame["gate_overdrive_axis_v"] = frame["gate_v"]
        frames.append(frame)
    if not frames:
        raise FileNotFoundError(f"No {device} characterization files found under {RAW}")
    return pd.concat(frames, ignore_index=True)


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    mask = (
        np.isfinite(frame["gm_id_vinv"])
        & np.isfinite(frame["gm_gds"])
        & (frame["id_per_w_ua_per_um"] > 1e-4)
        & frame["gm_id_vinv"].between(2.0, 40.0)
        & (frame["gm_gds"] > 0)
    )
    return frame.loc[mask].copy()


def nearest_point(frame: pd.DataFrame, device: str, length_um: float, gm_id_target: float) -> pd.Series:
    subset = clean(frame[(frame["device"] == device) & np.isclose(frame["length_um"], length_um)])
    if subset.empty:
        raise ValueError(f"No usable {device} data at L={length_um} um")
    index = (subset["gm_id_vinv"] - gm_id_target).abs().idxmin()
    return subset.loc[index]


def write_design_candidates(nfet: pd.DataFrame, pfet: pd.DataFrame) -> Path:
    combined = pd.concat([nfet, pfet], ignore_index=True)
    requests = [
        ("M1/M2", "nfet", "input pair (each)", 0.50, 15.0, 20.0),
        ("M5", "nfet", "tail current source", 0.80, 12.0, 40.0),
        ("M3/M4", "pfet", "first-stage mirror load", 0.80, 12.0, 20.0),
        ("M6", "nfet", "second-stage common source", 0.50, 10.0, 100.0),
        ("M7", "pfet", "second-stage current source", 0.80, 10.0, 100.0),
    ]
    rows: list[dict[str, object]] = []
    for group, device, role, length_um, gm_id_target, current_ua in requests:
        point = nearest_point(combined, device, length_um, gm_id_target)
        density = float(point["id_per_w_ua_per_um"])
        rows.append(
            {
                "device_group": group,
                "device": device,
                "role": role,
                "target_current_ua": current_ua,
                "length_um": length_um,
                "target_gm_id_vinv": gm_id_target,
                "sampled_gm_id_vinv": float(point["gm_id_vinv"]),
                "gate_bias_v": float(point["gate_v"]),
                "vgs_or_vsg_v": float(point["gate_overdrive_axis_v"]),
                "id_per_w_ua_per_um": density,
                "initial_width_um": current_ua / density,
                "gm_gds": float(point["gm_gds"]),
                "vdsat_v": float(point["vdsat_v"]),
                "status": "INITIAL_CANDIDATE_NOT_FINAL",
            }
        )
    output = ROOT / "results" / "device_sizing_candidates.csv"
    pd.DataFrame(rows).to_csv(output, index=False, float_format="%.6g")
    return output


def analyze_mirror() -> tuple[pd.DataFrame, dict[str, object]]:
    frame = pd.DataFrame(numeric_rows(RAW / "nmos_current_mirror.tsv", len(MIRROR_COLUMNS)), columns=MIRROR_COLUMNS)
    validate_sweep(frame, RAW / "nmos_current_mirror.tsv", start_v=0.0, stop_v=1.8)
    if (frame[["iref_forced_a", "iref_mos_a"]] <= 0.0).any().any():
        raise ValueError("Reference currents must remain positive throughout the mirror sweep")
    expected_forced_error = (
        100.0
        * (frame["iout_a"] - frame["iref_forced_a"]).abs()
        / frame["iref_forced_a"]
    )
    expected_reference_error = (
        100.0
        * (frame["iout_a"] - frame["iref_mos_a"]).abs()
        / frame["iref_mos_a"]
    )
    # ngspice wrdata emits eight significant digits, so derived columns can
    # differ slightly when recomputed from their independently rounded inputs.
    if not np.allclose(
        frame["error_vs_forced_pct"], expected_forced_error, rtol=5e-6, atol=1e-6
    ):
        raise ValueError("Mirror error versus forced IREF is inconsistent with raw currents")
    if not np.allclose(
        frame["error_vs_reference_mos_pct"],
        expected_reference_error,
        rtol=5e-6,
        atol=1e-6,
    ):
        raise ValueError("Mirror error versus reference MOS is inconsistent with raw currents")

    saturated = frame["sat_margin_v"] >= 0.0
    saturation_first, saturation_last = contiguous_true_interval(
        saturated,
        label="model-VDSAT saturation compliance",
        require_through_final_point=True,
    )
    compliance = float(frame.iloc[saturation_first]["vout_v"])
    compliance_max = float(frame.iloc[saturation_last]["vout_v"])
    five_percent = saturated & (frame["error_vs_forced_pct"] <= 5.0)
    five_percent_first, five_percent_last = contiguous_true_interval(
        five_percent,
        label="saturated, <=5% error-versus-forced-IREF compliance",
    )
    five_percent_min = float(frame.iloc[five_percent_first]["vout_v"])
    five_percent_max = float(frame.iloc[five_percent_last]["vout_v"])
    nominal_index = (frame["vout_v"] - 0.9).abs().idxmin()
    nominal = frame.loc[nominal_index]
    summary = {
        "corner": "tt",
        "temperature_c": 27,
        "vdd_v": 1.8,
        "reference_current_forced_ua": float(nominal["iref_forced_a"] * 1e6),
        "reference_device_current_at_0p9v_ua": float(nominal["iref_mos_a"] * 1e6),
        "output_current_at_0p9v_ua": float(nominal["iout_a"] * 1e6),
        "error_vs_forced_at_0p9v_pct": float(nominal["error_vs_forced_pct"]),
        "error_vs_reference_device_at_0p9v_pct": float(
            nominal["error_vs_reference_mos_pct"]
        ),
        "saturation_compliance_min_v": compliance,
        "saturation_compliance_max_v": compliance_max,
        "five_percent_error_vout_min_v": five_percent_min,
        "five_percent_error_vout_max_v": five_percent_max,
        "sweep_step_v": 0.01,
        "definition": (
            "grid-quantized compliance uses VDS>=model VDSAT; 5% interval uses "
            "absolute error versus forced IREF and is validated continuous"
        ),
    }
    output = ROOT / "results" / "current_mirror_summary.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary.keys())
        writer.writeheader()
        writer.writerow(summary)
    return frame, summary


def plot_characterization(nfet: pd.DataFrame, pfet: pd.DataFrame) -> Path:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5), constrained_layout=True)
    colors = plt.cm.viridis(np.linspace(0.05, 0.9, len(sorted(nfet["length_um"].unique()))))
    for device_frame, label, linestyle in ((nfet, "NFET", "-"), (pfet, "PFET", "--")):
        typical = device_frame[np.isclose(device_frame["length_um"], 0.5)]
        axes[0, 0].semilogy(
            typical["gate_overdrive_axis_v"],
            np.maximum(typical["id_per_w_ua_per_um"], 1e-6),
            linestyle,
            linewidth=2,
            label=f"{label}, L=0.50 um",
        )
    axes[0, 0].set(xlabel="VGS or VSG (V)", ylabel="ID/W (uA/um)", title="Current density at |VDS| = 0.9 V")
    axes[0, 0].legend()

    for color, length in zip(colors, sorted(nfet["length_um"].unique())):
        for frame, device, linestyle in ((nfet, "N", "-"), (pfet, "P", "--")):
            subset = clean(frame[np.isclose(frame["length_um"], length)]).sort_values("id_per_w_ua_per_um")
            axes[0, 1].semilogx(subset["id_per_w_ua_per_um"], subset["gm_id_vinv"], linestyle, color=color, alpha=0.9, label=f"{device} L={length:g}" if device == "N" else None)
            axes[1, 0].plot(subset["gm_id_vinv"], subset["gm_gds"], linestyle, color=color, alpha=0.9)
            axes[1, 1].plot(subset["gm_id_vinv"], subset["vdsat_v"], linestyle, color=color, alpha=0.9)
    axes[0, 1].set(xlabel="ID/W (uA/um)", ylabel="gm/ID (1/V)", title="Inversion level lookup")
    axes[0, 1].legend(ncol=2, fontsize=8, title="Solid N / dashed P")
    axes[1, 0].set(xlabel="gm/ID (1/V)", ylabel="gm/gds (V/V)", title="Intrinsic gain tradeoff")
    axes[1, 1].set(xlabel="gm/ID (1/V)", ylabel="|VDSAT| (V)", title="Saturation headroom")
    fig.suptitle("SKY130A standard-VT 1.8-V MOS characterization - TT, 27 C", fontsize=15)
    output = PLOTS / "day1_device_characterization.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def plot_mirror(frame: pd.DataFrame, summary: dict[str, object]) -> Path:
    fig, current_axis = plt.subplots(figsize=(9, 5.5), constrained_layout=True)
    error_axis = current_axis.twinx()
    current_axis.plot(frame["vout_v"], frame["iout_a"] * 1e6, linewidth=2.2, color="#176B87", label="IOUT")
    current_axis.plot(frame["vout_v"], frame["iref_forced_a"] * 1e6, linewidth=1.6, color="#333333", linestyle="--", label="Forced IREF")
    current_axis.plot(frame["vout_v"], frame["iref_mos_a"] * 1e6, linewidth=1.2, color="#777777", linestyle="-.", label="Reference MOS ID")
    error_axis.plot(frame["vout_v"], frame["error_vs_forced_pct"], linewidth=1.8, color="#D1495B", label="Error vs forced IREF")
    compliance = float(summary["saturation_compliance_min_v"])
    if np.isfinite(compliance):
        current_axis.axvline(compliance, color="#2A9D8F", linestyle=":", linewidth=2, label=f"Saturation grid limit = {compliance:.2f} V")
    five_percent_min = float(summary["five_percent_error_vout_min_v"])
    five_percent_max = float(summary["five_percent_error_vout_max_v"])
    current_axis.axvspan(
        five_percent_min,
        five_percent_max,
        color="#2A9D8F",
        alpha=0.08,
        label=f"<=5% interval = {five_percent_min:.2f}-{five_percent_max:.2f} V",
    )
    error_axis.axhline(5.0, color="#D1495B", linestyle=":", alpha=0.8, label="5% error limit")
    current_axis.set(xlabel="Output voltage (V)", ylabel="Current (uA)", title="SKY130A 1:1 NMOS current-mirror compliance - TT, 27 C")
    error_axis.set_ylabel("Current error (%)", color="#D1495B")
    current_axis.set_xlim(0, 1.8)
    error_axis.set_ylim(bottom=0)
    current_handles, current_labels = current_axis.get_legend_handles_labels()
    error_handles, error_labels = error_axis.get_legend_handles_labels()
    current_axis.legend(
        current_handles + error_handles,
        current_labels + error_labels,
        loc="center right",
        fontsize=8.5,
        framealpha=0.95,
    )
    output = PLOTS / "day1_current_mirror_compliance.png"
    fig.savefig(output, dpi=220)
    plt.close(fig)
    return output


def main() -> None:
    PLOTS.mkdir(parents=True, exist_ok=True)
    nfet = load_characterization("nfet")
    pfet = load_characterization("pfet")
    mirror, mirror_summary = analyze_mirror()
    candidates = write_design_candidates(nfet, pfet)
    device_plot = plot_characterization(nfet, pfet)
    mirror_plot = plot_mirror(mirror, mirror_summary)
    print(f"Wrote {candidates}")
    print(f"Wrote {device_plot}")
    print(f"Wrote {mirror_plot}")


if __name__ == "__main__":
    main()
