#!/usr/bin/env python3
"""Audit the existing routed-CDAC evidence and emit qualification.json.

This script intentionally does not rerun the physical tools.  The expensive,
bounded tool invocations are preserved as their own scripts and raw logs; this
auditor cross-checks those outputs against the original assignment CSVs so an
LVS pass produced by detached labels or a shared generator bug is not enough.
"""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ARTIFACTS = HERE / "artifacts"
PROBE = HERE / "probe_artifacts"
ASSIGNMENTS = HERE.parent / "cdac"
PLACEMENT_QUAL = HERE.parent / "cdac_layout_20260911" / "qualification.json"
EXPECTED_NETS = ["TOP", *[f"B{i}" for i in reversed(range(12))], "DUMMY", "EDGE_BIAS"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def subckt_pins(path: Path, cell: str) -> list[str]:
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f".subckt {cell} "):
            statement = line
            cursor = index + 1
            while cursor < len(lines) and lines[cursor].startswith("+"):
                statement += " " + lines[cursor][1:]
                cursor += 1
            tokens = statement.split()
            return tokens[2:]
    raise ValueError(f"{path}: no .subckt {cell}")


def raw_mim_topology(path: Path) -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = []
    pattern = re.compile(r"^X\S+\s+(\S+)\s+(\S+)\s+sky130_fd_pr__cap_mim_m3_1(?:\s|$)")
    for line in path.read_text().splitlines():
        match = pattern.match(line)
        if match:
            devices.append(match.groups())
    return devices


def raw_mim_dimensions(path: Path) -> list[tuple[float, float]]:
    dimensions: list[tuple[float, float]] = []
    pattern = re.compile(
        r"^X\S+\s+\S+\s+\S+\s+sky130_fd_pr__cap_mim_m3_1\s+(.*)$"
    )
    for line in path.read_text().splitlines():
        match = pattern.match(line)
        if not match:
            continue
        properties = dict(
            (name, float(value))
            for name, value in re.findall(r"\b([lw])=([0-9.eE+-]+)\b", match.group(1))
        )
        dimensions.append((properties.get("l", float("nan")), properties.get("w", float("nan"))))
    return dimensions


def expected_counts(polarity: str) -> tuple[Counter[str], int]:
    active: Counter[str] = Counter()
    edge = 0
    path = ASSIGNMENTS / f"cdac_{polarity.lower()}_assignment.csv"
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["electrical"] == "1":
                active[row["net"]] += 1
            else:
                edge += 1
    return active, edge


def side_topology(path: Path, polarity: str) -> dict[str, object]:
    devices = raw_mim_topology(path)
    dimensions = raw_mim_dimensions(path)
    active_expected, edge_expected = expected_counts(polarity)
    active_actual: Counter[str] = Counter()
    edge_actual = 0
    unexpected: list[list[str]] = []
    for c1, c2 in devices:
        if c1 == c2 == "EDGE_BIAS":
            edge_actual += 1
        elif c2 == "TOP" and c1 in active_expected:
            active_actual[c1] += 1
        else:
            unexpected.append([c1, c2])
    return {
        "mim_devices": len(devices),
        "active_counts_expected": dict(sorted(active_expected.items())),
        "active_counts_extracted": dict(sorted(active_actual.items())),
        "edge_dummies_expected": edge_expected,
        "edge_dummies_extracted": edge_actual,
        "unexpected_terminal_pairs": unexpected[:20],
        "all_extracted_mims_are_3um_by_3um": (
            len(dimensions) == len(devices)
            and all(length == 3.0 and width == 3.0 for length, width in dimensions)
        ),
        "matches_original_assignment": (
            len(devices) == 4356
            and len(dimensions) == len(devices)
            and all(length == 3.0 and width == 3.0 for length, width in dimensions)
            and active_actual == active_expected
            and edge_actual == edge_expected == 260
            and not unexpected
        ),
    }


def rc_summary(path: Path, cell: str, expected_pins: list[str], expected_mims: int) -> dict[str, object]:
    text = path.read_text()
    resistances = [
        float(value)
        for value in re.findall(r"(?m)^R\S+\s+\S+\s+\S+\s+([0-9.eE+-]+)$", text)
    ]
    capacitances = [
        float(value)
        for value in re.findall(r"(?m)^C\S+\s+\S+\s+\S+\s+([0-9.eE+-]+)f$", text)
    ]
    mims = len(re.findall(r"(?m)^X\S+\s+\S+\s+\S+\s+sky130_fd_pr__cap_mim_m3_1(?:\s|$)", text))
    pins = subckt_pins(path, cell)
    return {
        "file": str(path.relative_to(HERE)),
        "bytes": path.stat().st_size,
        "pins": pins,
        "pin_count": len(pins),
        "mim_devices": mims,
        "resistor_segments": len(resistances),
        "parasitic_capacitors": len(capacitances),
        "resistance_sum_ohm_non_path_metric": sum(resistances),
        "largest_resistor_segment_ohm": max(resistances) if resistances else None,
        "parasitic_capacitance_sum_ff_non_node_metric": sum(capacitances),
        "positive_rc_network": (
            pins == expected_pins
            and mims == expected_mims
            and bool(resistances)
            and bool(capacitances)
            and all(value > 0 for value in resistances)
            and all(value > 0 for value in capacitances)
        ),
    }


def png_dimensions(path: Path) -> list[int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path}: not PNG")
    return list(struct.unpack(">II", data[16:24]))


def lvs_unique(path: Path) -> bool:
    text = path.read_text()
    return "Final result: Circuits match uniquely." in text and "Netlists do not match" not in text


def main() -> int:
    generation = json.loads((HERE / "generation_manifest.json").read_text())
    readback = json.loads((ARTIFACTS / "klayout_readback.json").read_text())
    placement = json.loads(PLACEMENT_QUAL.read_text())

    full_magic = (ARTIFACTS / "magic_full.log").read_text()
    drc_counts = {
        "p_side": int(re.search(r"SIDE_DRC_COUNT P (\d+)", full_magic).group(1)),
        "n_side": int(re.search(r"SIDE_DRC_COUNT N (\d+)", full_magic).group(1)),
        "top": int(re.search(r"TOP_DRC_COUNT (\d+)", full_magic).group(1)),
    }

    side_topologies = {
        polarity: side_topology(
            ARTIFACTS / f"cdac_side_{polarity.lower()}_routed_flat.lvs.spice", polarity
        )
        for polarity in ("P", "N")
    }
    side_rc = {
        polarity: rc_summary(
            ARTIFACTS / f"cdac_side_{polarity.lower()}_routed_flat.rc.spice",
            f"cdac_side_{polarity.lower()}_routed_flat",
            EXPECTED_NETS,
            4356,
        )
        for polarity in ("P", "N")
    }
    top_pins = [*[f"P_{name}" for name in EXPECTED_NETS], *[f"N_{name}" for name in EXPECTED_NETS]]
    top_rc = rc_summary(
        ARTIFACTS / "cdac_diff_routed_flat_rc.spice",
        "cdac_diff_routed_flat_rc",
        top_pins,
        8712,
    )
    probe_rc = rc_summary(
        PROBE / "cdac_route_probe_flat.rc.spice",
        "cdac_route_probe_flat",
        ["TOP", "B0", "B1"],
        4,
    )

    res_ext = {
        "probe": PROBE / "cdac_route_probe_flat.res.ext",
        "p_side": ARTIFACTS / "cdac_side_p_routed_flat.res.ext",
        "n_side": ARTIFACTS / "cdac_side_n_routed_flat.res.ext",
        "top": ARTIFACTS / "cdac_diff_routed_flat_rc.res.ext",
    }
    res_ext_bytes = {name: path.stat().st_size if path.exists() else 0 for name, path in res_ext.items()}

    checks = {
        "original_binary_assignment_was_qualified": placement["status"] == "SKY130_CDAC_PLACEMENT_FLOORPLAN_PASS",
        "assignment_coordinates_and_common_centroid_preserved": generation["assignment_preserved"] is True,
        "representative_tile_magic_drc_zero": "PROBE_DRC_COUNT 0" in (PROBE / "magic.log").read_text(),
        "representative_tile_independent_lvs_unique": lvs_unique(PROBE / "lvs.rpt"),
        "representative_tile_has_real_rc_pex": probe_rc["positive_rc_network"],
        "p_side_magic_drc_zero": drc_counts["p_side"] == 0,
        "n_side_magic_drc_zero": drc_counts["n_side"] == 0,
        "differential_top_magic_drc_zero": drc_counts["top"] == 0,
        "p_side_independent_lvs_unique": lvs_unique(ARTIFACTS / "side_p_lvs.rpt"),
        "n_side_independent_lvs_unique": lvs_unique(ARTIFACTS / "side_n_lvs.rpt"),
        "differential_top_independent_lvs_unique": lvs_unique(ARTIFACTS / "top_lvs.rpt"),
        "p_side_extracted_topology_matches_original_csv": side_topologies["P"]["matches_original_assignment"],
        "n_side_extracted_topology_matches_original_csv": side_topologies["N"]["matches_original_assignment"],
        "side_rc_extraction_is_nonempty_and_positive": all(item["positive_rc_network"] for item in side_rc.values()),
        "top_rc_extraction_is_nonempty_and_positive": top_rc["positive_rc_network"],
        "all_res_ext_outputs_are_nonempty": all(value > 0 for value in res_ext_bytes.values()),
        "top_pex_has_exact_30_ports": top_rc["pins"] == top_pins,
        "klayout_reads_two_4356_mim_sides": (
            readback["top_direct_instances"] == 2
            and readback["p_side_direct_mim_instances"] == 4356
            and readback["n_side_direct_mim_instances"] == 4356
        ),
        "klayout_reads_all_30_physical_port_labels": readback["top_port_labels"] == readback["expected_port_labels"],
        "full_and_detail_png_are_nonempty": (
            png_dimensions(ARTIFACTS / "cdac_diff_routed.png") == [2800, 1400]
            and png_dimensions(ARTIFACTS / "cdac_routing_detail.png") == [2400, 1500]
        ),
        "presentation_pngs_hide_text_without_changing_gds": (
            readback["display_render"]["source_gds_unchanged"] is True
            and readback["display_render"]["text_shapes_removed_in_memory"] > 0
            and png_dimensions(ARTIFACTS / "cdac_diff_routed_display_no_labels.png")
            == [2800, 1400]
            and png_dimensions(ARTIFACTS / "cdac_routing_detail_display_no_labels.png")
            == [2400, 1500]
        ),
    }

    top_bbox = readback["top_bbox_um"]
    top_width = top_bbox[2] - top_bbox[0]
    top_height = top_bbox[3] - top_bbox[1]
    report: dict[str, object] = {
        "status": "SKY130_CDAC_ROUTED_OPEN_PDK_PASS" if all(checks.values()) else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "Standalone passive differential CDAC macro: real SKY130 MIM placement and M3/M4/via4/M5 routing, Magic DRC, independent Netgen LVS, full flattened RC extraction, and KLayout GDS readback",
        "cadence_used": False,
        "foundry_signoff": False,
        "final_complete_adc_layout": False,
        "completion": {
            "binary_assignment": True,
            "all_8192_active_units_placed": True,
            "all_active_top_and_12bit_plus_dummy_terminals_physically_routed": True,
            "edge_dummy_ring_placed_and_biased_separately": True,
            "routing": True,
            "magic_drc": True,
            "netgen_lvs": True,
            "full_flattened_rc_pex": True,
            "post_layout_adc_performance": False,
            "reference_switches_and_comparator_integrated": False,
        },
        "toolchain": {
            "container_image_sha256": "sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7",
            "pdk_version": placement["toolchain"]["pdk_version"],
            "magic": placement["toolchain"]["magic"],
            "klayout": placement["toolchain"]["klayout"],
            "netgen": "Netgen 1.5.323 (from raw logs)",
        },
        "checks": checks,
        "magic_drc_counts": drc_counts,
        "lvs": {
            "representative_tile": "unique_match",
            "p_side": "unique_match",
            "n_side": "unique_match",
            "differential_top": "unique_match",
            "top_port_count": len(top_pins),
            "side_port_count_each": len(EXPECTED_NETS),
            "note": "LVS references are generated from the frozen assignment CSV; direct extracted-topology-versus-CSV checks provide an additional independent guard against shared mapping errors.",
        },
        "extracted_topology": side_topologies,
        "rc_pex": {
            "representative_tile": probe_rc,
            "sides": side_rc,
            "differential_top": top_rc,
            "res_ext_bytes": res_ext_bytes,
            "res_ext_note": "All final .res.ext files are nonempty. An earlier in-process tile attempt retained the hierarchical extraction root and could not find parent .ext files; the preserved failure was corrected by running extresist all in a fresh Magic process.",
        },
        "routing_resources": generation["routing"],
        "route_summary": generation["route_summary"],
        "geometry": {
            "x_pitch_um": generation["pitch_um"]["x"],
            "y_pitch_um": generation["pitch_um"]["y"],
            "y_pitch_increase_vs_placement_percent": generation["pitch_change_percent"]["y"],
            "side_bbox_um": readback["p_side_bbox_um"],
            "differential_top_bbox_um": top_bbox,
            "differential_top_width_height_um": [top_width, top_height],
            "differential_top_area_um2": top_width * top_height,
            "differential_top_area_mm2": top_width * top_height / 1e6,
            "metal5_trunks_per_side": generation["route_summary"]["P"]["metal5_trunks"],
            "contiguous_row_runs_per_side": generation["route_summary"]["P"]["contiguous_row_runs"],
        },
        "klayout_readback": readback,
        "preserved_failures": [
            {
                "artifact": "artifacts/attempt1_capm11_194_per_side.log",
                "finding": "An internal M3 vertical trunk plus a wide edge trunk produced 194 capm.11 errors per side.",
                "resolution": "Moved TOP joining to the qualified boundary slot and narrowed vertical M3 trunks to 0.30 um.",
            },
            {
                "artifact": "artifacts/attempt2_stale_mag_replayed_194_per_side.log",
                "finding": "A rerun loaded an existing .mag and accumulated old paint, so the same 194 errors remained.",
                "resolution": "Generator now deletes only its named generated cells before rebuilding.",
            },
            {
                "artifact": "artifacts/attempt3_drc0_missing_b0_dummy_ports.log",
                "finding": "DRC was zero, but extraction omitted B0 and DUMMY because the one-trunk periphery wires did not reach their labels.",
                "resolution": "Every periphery wire now physically reaches the shared pin x; extraction exposes all 15 side ports.",
            },
            {
                "artifact": "probe_artifacts/attempt_in_process_extresist_root_failure.log",
                "finding": "Running extresist after hierarchy generation in the same Magic process could not find retained parent .ext files and produced no resistor network.",
                "resolution": "extract_probe_rc.tcl runs flattened RC extraction in a fresh process; final tile .res.ext and R network are nonempty.",
            },
            {
                "artifact": "artifacts/attempt4_drc0_side_lvs_ready_top_ports_missing.log",
                "finding": "Side cells had all physical ports, but the first hierarchical top emitted only two ports because parent labels did not overlap parent-level conductor shapes.",
                "resolution": "The generator now paints a parent-level M3/M4 landing under every prefixed top label; final top extraction exposes all 30 ports and matches uniquely.",
            },
        ],
        "limitations": [
            "This qualifies the standalone passive CDAC capacitor macro, not the complete SAR ADC or sensor readout core.",
            "Reference-selection switches, sampling switches, comparator, reference distribution devices, digital control, frontend, and bias are not integrated here.",
            "RC extraction is evidence of parasitics, not a post-layout INL/DNL, settling, noise, reference-droop, or SNDR pass.",
            "EDGE_BIAS must be tied to a quiet fixed bias in top-level integration; its shorted edge capacitors are deliberately outside TOP.",
            "No electromigration, IR-drop, antenna, density/fill, coupling-corner, or reliability signoff is claimed.",
            "Magic/Netgen/KLayout open SKY130 rules were used; this is not Cadence or foundry signoff.",
        ],
    }

    key_artifacts = [
        HERE / "generate_routed_cdac.py",
        ARTIFACTS / "generate_routed_cdac.tcl",
        ARTIFACTS / "cdac_diff_routed.gds",
        ARTIFACTS / "cdac_diff_routed.mag",
        ARTIFACTS / "cdac_diff_routed.lvs.spice",
        ARTIFACTS / "cdac_diff_routed.reference.spice",
        ARTIFACTS / "top_lvs.rpt",
        ARTIFACTS / "cdac_diff_routed_flat_rc.spice",
        ARTIFACTS / "cdac_diff_routed_flat_rc.res.ext",
        ARTIFACTS / "cdac_diff_routed.png",
        ARTIFACTS / "cdac_routing_detail.png",
        ARTIFACTS / "cdac_diff_routed_display_no_labels.png",
        ARTIFACTS / "cdac_routing_detail_display_no_labels.png",
        ARTIFACTS / "klayout_readback.json",
        PROBE / "cdac_route_probe.gds",
        PROBE / "lvs.rpt",
        PROBE / "cdac_route_probe_flat.rc.spice",
        HERE / "extract_rc.tcl",
        HERE / "extract_top_rc.tcl",
        HERE / "extract_probe_rc.tcl",
        HERE / "render_klayout.py",
        HERE / "README.md",
        HERE / "test_routed_cdac.py",
        Path(__file__),
    ]
    report["key_artifact_sha256"] = {
        str(path.relative_to(HERE)): sha256(path) for path in key_artifacts
    }
    (HERE / "qualification.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    print(json.dumps({"status": report["status"], "checks": checks, "geometry": report["geometry"], "rc_pex": report["rc_pex"]}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
