#!/usr/bin/env python3
"""Build an auditable manifest for the non-Cadence Xschem review package."""

from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
CANDIDATE = (HERE / "../dynamic_20260911/candidate_06.spice").resolve()
SOURCE_QUALIFICATION = (HERE / "../dynamic_20260911/qualification.json").resolve()
SAMPLER = (HERE / "../dynamic_20260911/sampling_switch.spice").resolve()
LOCAL_QUALIFICATION = HERE / "qualification.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_dimensions(path: Path) -> list[int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path}")
    return list(struct.unpack(">II", data[16:24]))


def exact_subckt_ports(source: str, name: str) -> list[str]:
    prefix = f".subckt {name} "
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line[len(prefix) :].split()
    raise ValueError(f"Missing subcircuit: {name}")


def artifact(path: Path) -> dict[str, object]:
    relative = path.relative_to(HERE).as_posix()
    record: dict[str, object] = {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    if path.suffix == ".png":
        record["dimensions_px"] = png_dimensions(path)
    return record


def main() -> None:
    source = CANDIDATE.read_text(encoding="utf-8")
    source_qualification = json.loads(SOURCE_QUALIFICATION.read_text(encoding="utf-8"))
    local_qualification = json.loads(LOCAL_QUALIFICATION.read_text(encoding="utf-8"))
    candidate_hash = sha256(CANDIDATE)

    expected_ports = {
        "rd_fdota": ["INP", "INN", "OUTP", "OUTN", "VDD", "VSS", "VCM"],
        "sky130_v2_switchable_pga": [
            "VINP", "VINN", "OUTP", "OUTN", "VDD", "VSS", "VCM", "SEL0", "SEL1",
        ],
        "sky130_v2_switchable_sample_driver": [
            "VINP", "VINN", "OUTP", "OUTN", "VDD", "VSS", "VCM", "SEL0", "SEL1",
            "params:", "RISO=1800",
        ],
    }
    observed_ports = {name: exact_subckt_ports(source, name) for name in expected_ports}

    structural_tokens = [
        "XMIP N1 INP TAIL VSS sky130_fd_pr__nfet_01v8 L=1 W=80",
        "XMIN N2 INN TAIL VSS sky130_fd_pr__nfet_01v8 L=1 W=80",
        "XMTAIL TAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=40",
        "XMLP N1 NCM VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=64",
        "XMLN N2 NCM VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=64",
        "XRN1 N1 NCM VSS rd_hr R=100000",
        "XRN2 N2 NCM VSS rd_hr R=100000",
        "XCN1 N1 NCM rd_c1p",
        "XCN2 N2 NCM rd_c1p",
        "XMSP OUTP N1 VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=180",
        "XMSN OUTN N2 VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=180",
        "XMOP OUTP CMG VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=9",
        "XMON OUTN CMG VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=9",
        "XRZP N1 CZP VSS rd_lr R=1200",
        "XRZN N2 CZN VSS rd_lr R=1200",
        "XCCP CZP OUTP rd_c8p",
        "XCCN CZN OUTN rd_c8p",
        "XRCMP OUTP CMS VSS rd_hr R=100000",
        "XRCMN OUTN CMS VSS rd_hr R=100000",
        "XCMS DS CMS CS VSS sky130_fd_pr__nfet_01v8 L=1 W=20",
        "XCMR CMG VCM CR VSS sky130_fd_pr__nfet_01v8 L=1 W=20",
        "XRSCS CS CTAIL VSS rd_hr R=10000",
        "XRSCR CR CTAIL VSS rd_hr R=10000",
        "XCMT CTAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=8",
        "XRDS VDD DS VSS rd_hr R=105000",
        "XRCMG VDD CMG VSS rd_hr R=105000",
        "XRINP VINP SUMPOS VSS rd_hr R=10000",
        "XRINN VINN SUMNEG VSS rd_hr R=10000",
        "XFP1 OUTN SUMPOS E1 E1B VDD VSS rd_fbbranch RFB=10350",
        "XFN1 OUTP SUMNEG E1 E1B VDD VSS rd_fbbranch RFB=10350",
        "XFP4 OUTN SUMPOS E4 E4B VDD VSS rd_fbbranch RFB=41400",
        "XFN4 OUTP SUMNEG E4 E4B VDD VSS rd_fbbranch RFB=41400",
        "XFP16 OUTN SUMPOS E16 E16B VDD VSS rd_fbbranch RFB=165600",
        "XFN16 OUTP SUMNEG E16 E16B VDD VSS rd_fbbranch RFB=165600",
        "XRIP COREP OUTP VSS rd_hr R={RISO}",
        "XRIN COREN OUTN VSS rd_hr R={RISO}",
        "XCFP OUTP VSS rd_c4p",
        "XCFN OUTN VSS rd_c4p",
    ]
    structural_audit = {token: token in source for token in structural_tokens}

    page_files = [
        HERE / "frontend_top.sch", HERE / "sky130_v2_switchable_pga.sch", HERE / "rd_fdota.sch",
    ]
    symbol_files = sorted(HERE.glob("*.sym"))
    support_files = [
        HERE / "README.md", HERE / "qualification.json", HERE / "render_headless.sh",
        HERE / "build_manifest.py", HERE / "test_xschem_delivery.py",
    ]
    render_files = [
        HERE / "renders/frontend_top.png", HERE / "renders/frontend_top.svg",
        HERE / "renders/switchable_pga.png", HERE / "renders/switchable_pga.svg",
        HERE / "renders/rd_fdota.png", HERE / "renders/rd_fdota.svg",
    ]
    all_files = page_files + symbol_files + support_files + render_files

    gains = source_qualification["gains"]
    nominal = source_qualification["nominal_dynamic_gates"]
    physical = source_qualification["physical_device_legality"]
    loop_audit = source_qualification["loop_audit"]
    visual = local_qualification["visual_no_overlap_audit"]
    manifest = {
        "schema_version": 2,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "XSCHEM_REVIEW_VISUAL_PASS__SOURCE_FORMAL_STABILITY_OPEN",
        "scope": {
            "tool": "Xschem 3.4.8RC",
            "technology": "SKY130A device names and layout-capable primitives",
            "cadence_native": False,
            "signoff_schematic": False,
            "silicon_measured": False,
            "purpose": "Browsable non-Cadence review pages bound to the authoritative SPICE candidate",
        },
        "authoritative_sources": {
            "candidate_path_from_this_directory": "../dynamic_20260911/candidate_06.spice",
            "candidate_sha256": candidate_hash,
            "candidate_bytes": CANDIDATE.stat().st_size,
            "qualification_path_from_this_directory": "../dynamic_20260911/qualification.json",
            "qualification_sha256": sha256(SOURCE_QUALIFICATION),
            "local_visual_qualification_path": "qualification.json",
            "local_visual_qualification_sha256": sha256(LOCAL_QUALIFICATION),
            "sampler_path_from_this_directory": "../dynamic_20260911/sampling_switch.spice",
            "sampler_sha256": sha256(SAMPLER),
            "hash_matches_source_qualification": candidate_hash == source_qualification["candidate_sha256"],
            "hash_matches_local_qualification": candidate_hash == local_qualification["candidate_sha256"],
        },
        "port_audit": {
            name: {"expected": expected_ports[name], "observed": observed_ports[name], "pass": observed_ports[name] == expected_ports[name]}
            for name in expected_ports
        },
        "structural_token_audit": structural_audit,
        "hierarchy": [
            {"page": "frontend_top.sch", "shows": "sensor boundary, switchable PGA, tested 1.5-kohm RC isolation, 4x-MIM filter load and real SAR sampler boundary"},
            {"page": "sky130_v2_switchable_pga.sch", "shows": "10-kohm inputs, six cross-feedback branches, G=1/4/16 values, decoder truth table and rd_fdota boundary"},
            {"page": "rd_fdota.sch", "shows": "two-input/two-output signal path, two stages, startup bias, direct NCM sensing, VCM-referenced CMG loop and 8-MIM Miller paths"},
        ],
        "frozen_candidate_truth": {
            "qualification_status": source_qualification["status"],
            "same_source_all_three_gains": nominal["same_source_all_three_gains"],
            "static_max_holdout_error_lsb": {gain: gains[gain]["max_independent_holdout_error_lsb"] for gain in ("1", "4", "16")},
            "dynamic_max_acquisition_error_v": {gain: gains[gain]["max_acquisition_error_v"] for gain in ("1", "4", "16")},
            "mean_frontend_vdd_vcm_power_w": {gain: gains[gain]["mean_frontend_vdd_vcm_power_w"] for gain in ("1", "4", "16")},
            "all_three_static_pass": nominal["all_gain_static_gate_pass"],
            "all_three_dynamic_pass": nominal["all_gain_real_sampling_gate_pass"],
            "all_three_power_pass": nominal["all_gain_power_gate_pass"],
            "all_three_device_region_pass": nominal["all_gain_device_region_gate_pass"],
            "external_vcm_endpoint_tracking_pass": nominal["external_vcm_endpoint_tracking_gate_pass"],
            "formal_multiloop_stability_pass": loop_audit["formal_multiloop_stability_gate_pass"],
            "first_downcross_dm_phase_margin_deg": loop_audit["dm_primary_downcross_phase_margin_deg"],
            "first_downcross_output_cm_phase_margin_deg": loop_audit["output_cm_primary_downcross_phase_margin_deg"],
            "stability_blocking_findings": loop_audit["blocking_findings"],
            "pvt_45_run": source_qualification["pvt_45_screen_run"],
            "noise_qualified": source_qualification["noise_qualified"],
            "physical_parameter_audit_pass": physical["gate_pass"],
            "miller_zero_resistor": {"model": physical["miller_zero_resistor_model"], "resistance_ohm": physical["miller_zero_resistance_ohm"], "length_um": physical["miller_zero_length_um"]},
            "isolation_resistor": {"subcircuit_default_ohm": 1800, "qualified_assembly_ohm": physical["qualified_assembly_isolation_resistance_ohm"], "model": physical["isolation_resistor_model"], "qualified_assembly_length_um": physical["isolation_resistor_length_um"]},
            "layout_drc_lvs_pex_complete": source_qualification["layout_drc_lvs_pex_complete"],
        },
        "rendering": {
            "command": "./render_headless.sh (inside the configured SKY130 container login environment)",
            "rendered_pages": 3,
            "formats": ["PNG", "SVG"],
            "png_dimensions_px": [2400, 1600],
            "ascii_only_schematic_labels": True,
            "missing_symbol_marker_present": False,
            "live_xschem_process_after_final_render": False,
            "visual_no_overlap_audit": visual,
            "incident": {
                "occurred": True,
                "description": "An unconfigured direct-shell attempt made Xschem dump core while combining two exports in one process.",
                "cleanup": "The exact 13-MB temporary core file was deleted. The final script uses the configured login environment, one export per process, an explicit timeout and an EXIT trap for Xvfb.",
                "affects_final_artifacts": False,
            },
        },
        "limitations": [
            "These pages are non-Cadence review drawings, not a Cadence Virtuoso library or signoff schematic.",
            "The authoritative electrical implementation remains dynamic_20260911/candidate_06.spice; do not substitute an Xschem-generated netlist.",
            "Nominal static, real-sampler dynamic, power, device-region and endpoint VCM checks pass for all three gains.",
            "Formal coupled multiloop stability is not closed: every DM trace has a high-frequency up-crossing and the stage-1 CM return sign is anomalous at gains 1 and 4.",
            "The 45-PVT screen and noise qualification have not run.",
            "The resistor parameter audit passes, but no frontend layout, DRC, LVS, PEX or post-layout result exists.",
            "The no-overlap assessment is a recorded human visual review of the final PNGs, not an algorithmic geometry proof.",
        ],
        "artifacts": [artifact(path) for path in all_files],
    }

    manifest["integrity_pass"] = bool(
        manifest["authoritative_sources"]["hash_matches_source_qualification"]
        and manifest["authoritative_sources"]["hash_matches_local_qualification"]
        and all(item["pass"] for item in manifest["port_audit"].values())
        and all(structural_audit.values())
        and visual["all_pages_pass"]
        and all(path.is_file() and path.stat().st_size > 0 for path in all_files)
    )
    (HERE / "artifact_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": manifest["status"], "integrity_pass": manifest["integrity_pass"]}))


if __name__ == "__main__":
    main()
