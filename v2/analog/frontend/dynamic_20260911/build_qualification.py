#!/usr/bin/env python3
"""Build the conservative final status from frozen dynamic and loop evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CANDIDATE = HERE / "candidate_06.spice"
DYNAMIC_NAME = "07_20260911T085157880653Z_candidate_06"
LOOP_NAME = "08_20260911T085257873008Z_candidate_06_loops"
DYNAMIC = HERE / "diagnostics" / DYNAMIC_NAME
LOOPS = HERE / "diagnostics" / LOOP_NAME


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(folder: Path) -> bool:
    manifest = json.loads((folder / "evidence_manifest.json").read_text())
    if manifest.get("version") != 1:
        raise ValueError(f"Unsupported manifest: {folder}")
    for name, expected in manifest["files"].items():
        path = folder / name
        if not path.is_file() or path.stat().st_size != expected["size_bytes"] or digest(path) != expected["sha256"]:
            raise ValueError(f"Frozen evidence mismatch: {folder.name}/{name}")
    return True


def wrapped_phase(value: float) -> float:
    return (value + 180) % 360 - 180


def loop_audit(loop: dict) -> dict:
    down = [item for item in loop["unity_crossings"] if item["direction"] == "down"]
    up = [item for item in loop["unity_crossings"] if item["direction"] == "up"]
    low_phase = wrapped_phase(loop["low_frequency_phase_deg"])
    negative_feedback_sign = abs(low_phase) <= 45
    pass_gate = bool(
        negative_feedback_sign
        and down
        and not up
        and all(item["phase_margin_deg"] >= 60 for item in down)
    )
    return {
        **loop,
        "low_frequency_phase_wrapped_deg": low_phase,
        "low_frequency_negative_feedback_sign": negative_feedback_sign,
        "high_frequency_upcrossing_absent": not up,
        "audited_phase_margin_gate_pass": pass_gate,
    }


def main() -> None:
    dynamic_manifest = verify_manifest(DYNAMIC)
    loop_manifest = verify_manifest(LOOPS)
    dynamic = json.loads((DYNAMIC / "summary.json").read_text())
    raw_loop = json.loads((LOOPS / "summary.json").read_text())
    candidate_sha = digest(CANDIDATE)
    for source in (dynamic, raw_loop):
        if source["candidate_sha256"] != candidate_sha:
            raise ValueError("Selected evidence does not bind to candidate_06.spice")

    dynamic_gates = {
        "same_source_all_three_gains": len({dynamic["candidate_sha256"] for _ in dynamic["gains"]}) == 1,
        "all_gain_static_gate_pass": dynamic["all_gain_static_gate_pass"],
        "all_gain_real_sampling_gate_pass": dynamic["all_gain_real_sampling_gate_pass"],
        "all_gain_power_gate_pass": dynamic["all_gain_power_gate_pass"],
        "all_gain_device_region_gate_pass": dynamic["all_gain_device_region_gate_pass"],
        "external_vcm_reference_used": dynamic["external_vcm_reference_used"],
        "external_vcm_endpoint_tracking_gate_pass": dynamic["external_vcm_endpoint_tracking_gate_pass"],
    }
    nominal_dynamic_prerequisites_pass = all(dynamic_gates.values())

    audited_loops = {}
    for gain, modes in raw_loop["loops"].items():
        audited_loops[gain] = {mode: loop_audit(result) for mode, result in modes.items()}
    dm_primary_downcross_pm = {
        gain: min(
            item["phase_margin_deg"]
            for item in modes["dm"]["unity_crossings"] if item["direction"] == "down"
        )
        for gain, modes in audited_loops.items()
    }
    output_cm_primary_downcross_pm = {
        gain: min(
            item["phase_margin_deg"]
            for item in modes["output_cm"]["unity_crossings"] if item["direction"] == "down"
        )
        for gain, modes in audited_loops.items()
    }
    formal_loop_gate = all(
        result["audited_phase_margin_gate_pass"]
        for modes in audited_loops.values() for result in modes.values()
    )

    diagnostic_inventory = []
    for folder in sorted((HERE / "diagnostics").iterdir()):
        summary = json.loads((folder / "summary.json").read_text())
        diagnostic_inventory.append({
            "ordinal": summary["ordinal"],
            "folder": f"diagnostics/{folder.name}",
            "candidate": summary["candidate"],
            "candidate_sha256": summary["candidate_sha256"],
            "status_as_recorded": summary["status"],
            "elapsed_s": summary["elapsed_s"],
        })

    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "NOMINAL_DYNAMIC_PASS__FORMAL_MULTILOOP_STABILITY_NOT_CLOSED",
        "candidate_path": CANDIDATE.name,
        "candidate_sha256": candidate_sha,
        "selected_dynamic_evidence": f"diagnostics/{DYNAMIC_NAME}",
        "selected_loop_evidence": f"diagnostics/{LOOP_NAME}",
        "selected_manifests_verified": dynamic_manifest and loop_manifest,
        "bounded_real_ngspice_diagnostics_used": 8,
        "bounded_real_ngspice_diagnostics_limit": 8,
        "setup_failure_not_counted_as_real_ngspice_run": "setup_failures/01_20260911T084048784001Z_no_ngspice_on_path",
        "diagnostic_inventory": diagnostic_inventory,
        "nominal_dynamic_gates": dynamic_gates,
        "nominal_dynamic_prerequisites_pass": nominal_dynamic_prerequisites_pass,
        "gains": dynamic["gains"],
        "external_vcm_endpoint_tracking": dynamic["external_vcm_endpoint_tracking"],
        "physical_device_legality": {
            "miller_zero_resistor_model": "sky130_fd_pr__res_high_po_0p69",
            "miller_zero_resistance_ohm": 1200,
            "miller_zero_length_um": (1200 - 779.8) / 491.36,
            "isolation_resistor_model": "sky130_fd_pr__res_high_po_0p35",
            "qualified_assembly_isolation_resistance_ohm": 1500,
            "isolation_resistor_length_um": (1500 - 961) / 993,
            "minimum_pcell_length_um": 0.5,
            "known_subminimum_resistor_length_absent": True,
            "gate_pass": (1200 - 779.8) / 491.36 >= .5 and (1500 - 961) / 993 >= .5,
            "scope": "Schematic parameter audit only; no frontend layout, DRC, LVS, or PEX claim.",
        },
        "loop_audit": {
            "raw_run_status_superseded": raw_loop["status"],
            "why_superseded": "The frozen runner checked only down-crossing phase margin. It did not reject a wrong low-frequency feedback sign or a later high-frequency up-crossing.",
            "dm_primary_downcross_phase_margin_deg": dm_primary_downcross_pm,
            "output_cm_primary_downcross_phase_margin_deg": output_cm_primary_downcross_pm,
            "audited_loops": audited_loops,
            "formal_multiloop_stability_gate_pass": formal_loop_gate,
            "blocking_findings": [
                "Stage-1 common-mode scalar return ratio begins near -180 degrees at gains 1 and 4, so the assumed negative-feedback sign is not demonstrated for every gain.",
                "Every differential return-ratio trace crosses upward through 0 dB again between about 38.9 and 74.8 MHz; a first-downcrossing phase margin alone is insufficient.",
                "The scalar injections leave the other loops closed and do not provide a return-difference determinant or an open-loop RHP-pole count for this coupled multi-loop circuit.",
            ],
        },
        "formal_stability_gate_pass": formal_loop_gate,
        "pvt_45_screen_allowed": formal_loop_gate,
        "pvt_45_screen_run": False,
        "pvt_45_screen_skip_reason": "The formal multiloop stability prerequisite failed and the eight-diagnostic tuning budget is exhausted.",
        "noise_qualified": False,
        "full_frontend_qualified": False,
        "full_chip_qualified": False,
        "cadence_used": False,
        "layout_drc_lvs_pex_complete": False,
        "scope": "Pre-layout SKY130/ngspice evidence only. No native transient device noise, ADC SNDR, Cadence, PEX, full-chip, tapeout, or silicon claim.",
    }
    (HERE / "qualification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
