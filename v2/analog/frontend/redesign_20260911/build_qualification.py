#!/usr/bin/env python3
"""Build the reproducible static-pass/dynamic-fail qualification summary."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import numpy as np


HERE = Path(__file__).resolve().parent
RUN_NAME = "06_20260911T082721717297Z_candidate_01"
RUN = HERE / "diagnostics" / RUN_NAME
CANDIDATE = HERE / "candidate_01.spice"
LSB = 0.8 / 4096
ACQ_WINDOW = 2.476847754e-6


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(folder: Path) -> None:
    manifest = json.loads((folder / "evidence_manifest.json").read_text())
    if manifest.get("version") != 1:
        raise ValueError("Unsupported evidence manifest")
    for name, expected in manifest["files"].items():
        path = folder / name
        if not path.is_file() or path.stat().st_size != expected["size_bytes"] or digest(path) != expected["sha256"]:
            raise ValueError(f"Frozen evidence mismatch: {name}")


def interval(t: np.ndarray, y: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    mask = (t >= lo) & (t <= hi)
    if np.sum(mask) < 3:
        raise ValueError("Missing partial-transient reference window")
    trap = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    return float(trap(y[mask], t[mask]) / (t[mask][-1] - t[mask][0])), float(np.ptp(y[mask]))


def main() -> None:
    verify_manifest(RUN)
    candidate_sha = digest(CANDIDATE)
    if candidate_sha != digest(RUN / "candidate_snapshot.spice"):
        raise ValueError("Current candidate differs from selected frozen run")

    columns = json.loads((RUN / "columns.json").read_text())
    dc = np.loadtxt(RUN / "dc.dat", skiprows=1, ndmin=2)
    tr = np.loadtxt(RUN / "transient.dat", skiprows=1, ndmin=2)
    if dc.shape != (81, len(columns["dc"])) or not np.isfinite(dc).all():
        raise ValueError("Selected DC evidence is incomplete")
    if tr.shape[1] != len(columns["transient"]) or not np.isfinite(tr).all():
        raise ValueError("Selected partial transient is invalid")
    cd = {name: i for i, name in enumerate(columns["dc"])}
    ct = {name: i for i, name in enumerate(columns["transient"])}
    target = dc[:, cd["v(sw)"]]
    if not np.allclose(target, np.linspace(-.4, .4, 81), atol=1e-10, rtol=0):
        raise ValueError("Wrong DC stimulus")

    gains = {}
    for gain in (1, 4, 16):
        p = f"xg{gain}"
        od = dc[:, cd[f"v({p}.filtp)"]] - dc[:, cd[f"v({p}.filtn)"]]
        cm = (dc[:, cd[f"v({p}.filtp)"]] + dc[:, cd[f"v({p}.filtn)"]]) / 2
        train = np.array([8, 40, 72])
        fit = np.polyfit(od[train], target[train], 1)
        hold = np.ones(81, dtype=bool)
        hold[train] = False
        residual = (np.polyval(fit, od) - target) / LSB
        power = -1.8 * dc[:, cd[f"i(v.{p}.vddc)"]] - .9 * dc[:, cd[f"i(v.{p}.vcmc)"]]

        t = tr[:, 0]
        filt = tr[:, ct[f"v({p}.filtp)"]] - tr[:, ct[f"v({p}.filtn)"]]
        held = tr[:, ct[f"v({p}.hp)"]] - tr[:, ct[f"v({p}.hn)"]]
        tcm = (tr[:, ct[f"v({p}.filtp)"]] + tr[:, ct[f"v({p}.filtn)"]]) / 2
        ref, ripple = interval(t, filt, 16e-6, 19e-6)
        aperture = 10e-6 + ACQ_WINDOW - 10e-9
        acq_error = float(np.interp(aperture, t, held) - ref)
        post_error = float(np.interp(aperture + 30e-9, t, held) - ref)

        devices = {}
        for dev, model in (
            ("xmip", "nfet_01v8"), ("xmin", "nfet_01v8"), ("xmtail", "nfet_01v8"),
            ("xmlp", "pfet_01v8"), ("xmln", "pfet_01v8"),
            ("xmsp", "pfet_01v8"), ("xmsn", "pfet_01v8"),
            ("xmop", "nfet_01v8"), ("xmon", "nfet_01v8"),
            ("xcms", "nfet_01v8"), ("xcmr", "nfet_01v8"), ("xcmt", "nfet_01v8"),
        ):
            base = f"@m.{p}.xdut.xota.{dev}.msky130_fd_pr__{model}"
            margin = np.abs(dc[:, cd[base + "[vds]"]]) - np.abs(dc[:, cd[base + "[vdsat]"]])
            worst = int(np.argmin(margin))
            devices[dev] = {
                "min_abs_vds_minus_abs_vdsat_v": float(margin[worst]),
                "worst_target_v": float(target[worst]),
            }

        static_error = float(np.max(np.abs(residual[hold])))
        static_cm = float(np.max(np.abs(cm - .9)))
        gains[str(gain)] = {
            "same_candidate_sha256": candidate_sha,
            "source_resistance_ohm_per_side": 350,
            "dc_points": 81,
            "calibration_training_targets_v": [-.32, 0, .32],
            "independent_holdout_points": 78,
            "calibration_coefficients": fit.tolist(),
            "max_independent_holdout_error_lsb": static_error,
            "static_accuracy_limit_lsb": 1.0,
            "max_output_common_mode_error_v": static_cm,
            "output_endpoints_v": [float(od[0]), float(od[-1])],
            "static_gate_pass": bool(static_error <= 1 and static_cm <= .05),
            "frontend_vdd_vcm_power_w": {"minimum_dc": float(power.min()), "maximum_dc": float(power.max())},
            "provisional_frontend_power_limit_w": 1.85e-3,
            "power_gate_pass": bool(power.max() <= 1.85e-3),
            "device_regions": devices,
            "all_reported_key_devices_saturated_by_20mv": bool(min(x["min_abs_vds_minus_abs_vdsat_v"] for x in devices.values()) >= .02),
            "partial_first_cycle_only": {
                "reference_window_s": [16e-6, 19e-6],
                "reference_mean_v": ref,
                "reference_peak_to_peak_v": ripple,
                "reference_stability_limit_v": LSB / 40,
                "acquisition_measurement_time_s": aperture,
                "acquisition_error_v": acq_error,
                "post_aperture_30ns_error_v": post_error,
                "settling_limit_v": LSB / 4,
                "max_output_cm_error_before_second_input_edge_v": float(np.max(np.abs(tcm[(t >= 9e-6) & (t < 20e-6)] - .9))),
                "dynamic_gate_pass": False,
                "why_false": "Reference ripple exceeds the frozen limit; G1 and G16 also exceed the acquisition-error limit.",
            },
        }

    log = (RUN / "simulator.log").read_text(errors="replace")
    match = re.search(r"Timestep too small; time = ([0-9.eE+-]+)", log)
    if not match:
        raise ValueError("Expected recorded transient stop was not found")
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "STATIC_THREE_GAIN_PASS__DYNAMIC_AND_STABILITY_FAIL",
        "candidate_path": "candidate_01.spice",
        "candidate_sha256": candidate_sha,
        "selected_frozen_evidence": f"diagnostics/{RUN_NAME}",
        "selected_evidence_manifest_verified": True,
        "same_source_all_three_gains": True,
        "gains": gains,
        "all_three_gain_static_gate_pass": all(g["static_gate_pass"] for g in gains.values()),
        "all_three_gain_power_gate_pass": all(g["power_gate_pass"] for g in gains.values()),
        "all_three_gain_reported_device_region_gate_pass": all(g["all_reported_key_devices_saturated_by_20mv"] for g in gains.values()),
        "all_three_gain_dynamic_gate_pass": False,
        "differential_loop_phase_margin_measured": False,
        "common_mode_loop_phase_margin_measured": False,
        "formal_stability_gate_pass": False,
        "real_sampler_used": True,
        "sampler_path": "sampling_switch.spice",
        "sample_capacitor_units_per_side": 4096,
        "acquisition_window_s": ACQ_WINDOW,
        "transient_completed": False,
        "recorded_transient_stop_s": float(match.group(1)),
        "transient_failure": "ngspice timestep-too-small at the third reset edge after two input cycles; first-cycle waveforms already fail the frozen quiet-reference gate.",
        "nominal_frontend_prerequisites_pass": False,
        "pvt_45_screen_allowed": False,
        "pvt_45_screen_run": False,
        "physical_layoutability_gate_pass": False,
        "physical_layoutability_issue": {
            "device": "two 1.2 kohm Miller nulling resistors",
            "model": "sky130_fd_pr__res_high_po_0p35",
            "netlist_length_um": (1200 - 961) / 993,
            "pdk_pcell_minimum_length_um": 0.5,
            "resolution": "This stopped candidate is not silently rounded. A future candidate must use a wider/lower-value PDK resistor option or at least the minimum legal geometry, then be re-simulated.",
        },
        "feedback_network_physical_estimate": {
            "resistor_width_um": 0.35,
            "rin_10k_length_um_each": (10000 - 961) / 993,
            "rf_10p35k_length_um_each": (10350 - 961) / 993,
            "rf_41p4k_length_um_each": (41400 - 961) / 993,
            "rf_165p6k_length_um_each": (165600 - 961) / 993,
            "maximum_single_feedback_resistor_active_body_area_um2": 0.35 * (165600 - 961) / 993,
            "g1_differential_sensor_load_ohm_approx": 2 * (10000 + 350),
            "g1_full_scale_current_per_input_leg_a_approx": 0.2 / (10000 + 350),
            "scope": "Active resistor body only; contacts, end effects, spacing, guard rings, routing and switches increase final layout area.",
        },
        "noise_reused_from_old_candidate": False,
        "noise_qualified": False,
        "full_frontend_qualified": False,
        "full_chip_qualified": False,
        "scope": "Pre-layout schematic-level SKY130 device evidence only. Not Cadence, not PEX, not full ADC, not silicon.",
    }
    (HERE / "qualification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
