#!/usr/bin/env python3
"""Rebuild and qualify the placement-only differential CDAC floorplan.

Run inside the pinned IIC-OSIC/SKY130 container.  The script deliberately
stops before routing, LVS, PEX, or any post-layout performance claim.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ARTIFACTS = HERE / "artifacts"
PDK = Path("/foss/pdks/sky130A")
MAGIC_RC = PDK / "libs.tech/magic/sky130A.magicrc"
CONTAINER_IMAGE = "sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(label: str, command: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    output = result.stdout + result.stderr
    destination = ARTIFACTS / f"{label}.log"
    destination.write_text(output)
    return result.returncode, output


def magic_command(script: Path) -> list[str]:
    return [
        "/foss/tools/bin/magic",
        "-dnull",
        "-noconsole",
        "-rcfile",
        str(MAGIC_RC),
        str(script),
    ]


def topology_is_separate(path: Path) -> bool:
    if not path.exists():
        return False
    devices = []
    for line in path.read_text().splitlines():
        match = re.match(r"^XX[01]\s+(\S+)\s+(\S+)\s+mim_unit$", line)
        if match:
            devices.append(match.groups())
    return (
        len(devices) == 2
        and len({nodes[0] for nodes in devices}) == 2
        and len({nodes[1] for nodes in devices}) == 2
        and all(nodes[0] != nodes[1] for nodes in devices)
    )


def parse_pitch_results(log: str, directory: Path, stem: str) -> list[dict[str, object]]:
    results = []
    pattern = re.compile(r"PITCH_(?:PROBE|REFINE) ([xy]) ([\d.]+) DRC_COUNT (\d+)")
    for axis, pitch_text, count_text in pattern.findall(log):
        tag = pitch_text.replace(".", "p")
        netlist = directory / f"{stem}_{axis}_{tag}.spice"
        separate = topology_is_separate(netlist)
        count = int(count_text)
        results.append(
            {
                "axis": axis,
                "pitch_um": float(pitch_text),
                "drc_count": count,
                "terminal_topology_separate": separate,
                "safe": count == 0 and separate,
                "netlist": str(netlist.relative_to(HERE)),
            }
        )
    return results


def first_safe(results: list[dict[str, object]], axis: str) -> float | None:
    values = [float(item["pitch_um"]) for item in results if item["axis"] == axis and item["safe"]]
    return min(values) if values else None


def tool_version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return None
    text = (result.stdout + result.stderr).strip()
    return text.splitlines()[0] if result.returncode == 0 and text else None


def main() -> int:
    for path in (HERE / "probe_artifacts", HERE / "probe_refine", ARTIFACTS):
        if path.exists():
            shutil.rmtree(path)
    ARTIFACTS.mkdir(parents=True)

    generator = subprocess.run(
        ["python3", str(HERE / "generate_floorplan.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    (ARTIFACTS / "generator.log").write_text(generator.stdout + generator.stderr)

    coarse_rc, coarse_log = run(
        "pitch_probe",
        magic_command(HERE / "pitch_probe.tcl"),
        HERE,
        timeout=120,
    )
    refine_rc, refine_log = run(
        "pitch_probe_refine",
        magic_command(HERE / "pitch_probe_refine.tcl"),
        HERE,
        timeout=120,
    )
    floorplan_rc, floorplan_log = run(
        "magic_floorplan",
        magic_command(ARTIFACTS / "generate_cdac_floorplan.tcl"),
        HERE,
        timeout=300,
    )
    klayout_rc, _ = run(
        "klayout_render",
        ["python3", str(HERE / "render_klayout.py")],
        HERE,
        timeout=120,
    )

    pitch_results = parse_pitch_results(coarse_log, HERE / "probe_artifacts", "probe")
    pitch_results += parse_pitch_results(refine_log, HERE / "probe_refine", "refine")
    pitch_by_key = {(item["axis"], item["pitch_um"]): item for item in pitch_results}
    generation = json.loads((ARTIFACTS / "generation_manifest.json").read_text())
    klayout = json.loads((ARTIFACTS / "klayout_summary.json").read_text()) if klayout_rc == 0 else {}
    assignment = json.loads((HERE.parent / "cdac/assignment_summary.json").read_text())

    with (ARTIFACTS / "placement_index.csv").open(newline="") as handle:
        placed = list(csv.DictReader(handle))
    instance_names = [row["instance"] for row in placed]
    physical_counts = {
        polarity: sum(row["polarity"] == polarity for row in placed) for polarity in ("P", "N")
    }
    active_counts = {
        polarity: sum(row["polarity"] == polarity and row["electrical"] == "1" for row in placed)
        for polarity in ("P", "N")
    }
    edge_counts = {
        polarity: sum(row["polarity"] == polarity and row["net"] == "EDGE" for row in placed)
        for polarity in ("P", "N")
    }

    magic_counts = {}
    for key, pattern in {
        "p_side": r"SIDE_DRC P (\d+)",
        "n_side": r"SIDE_DRC N (\d+)",
        "top": r"FLOORPLAN_DRC_COUNT (\d+)",
    }.items():
        match = re.search(pattern, floorplan_log)
        magic_counts[key] = int(match.group(1)) if match else None

    side_bbox = klayout.get("side_p_bbox_um")
    top_bbox = klayout.get("top_bbox_um")
    side_width = side_bbox[2] - side_bbox[0] if side_bbox else None
    side_height = side_bbox[3] - side_bbox[1] if side_bbox else None
    side_area = side_width * side_height if side_width is not None and side_height is not None else None
    top_area = (
        (top_bbox[2] - top_bbox[0]) * (top_bbox[3] - top_bbox[1]) if top_bbox else None
    )
    provisional_side_area = 264.0 * 264.0
    active_plate_area = assignment["geometry"]["active_plate_area_um2_both_sides"]

    checks = {
        "generator_completed": generator.returncode == 0,
        "source_assignment_pass": assignment.get("status") == "PLACEMENT_ASSIGNMENT_PASS",
        "placement_index_has_8712_unique_instances": len(placed) == 8712 and len(set(instance_names)) == 8712,
        "each_side_has_4096_active_units": active_counts == {"P": 4096, "N": 4096},
        "each_side_has_260_edge_dummies": edge_counts == {"P": 260, "N": 260},
        "each_side_has_4356_physical_mim_units": physical_counts == {"P": 4356, "N": 4356},
        "coarse_pitch_probe_completed": coarse_rc == 0 and len(pitch_results) >= 17,
        "refined_pitch_probe_completed": refine_rc == 0,
        "four_um_x_is_rejected": not pitch_by_key.get(("x", 4.0), {}).get("safe", True),
        "four_um_y_is_rejected": not pitch_by_key.get(("y", 4.0), {}).get("safe", True),
        "x_5p99_fails_and_6p00_passes": (
            not pitch_by_key.get(("x", 5.99), {}).get("safe", True)
            and pitch_by_key.get(("x", 6.0), {}).get("safe") is True
        ),
        "y_4p53_fails_and_4p54_passes": (
            not pitch_by_key.get(("y", 4.53), {}).get("safe", True)
            and pitch_by_key.get(("y", 4.54), {}).get("safe") is True
        ),
        "used_pitch_matches_first_safe_boundary": (
            first_safe(pitch_results, "x") == generation["pitch_um"]["x"] == 6.0
            and first_safe(pitch_results, "y") == generation["pitch_um"]["y"] == 4.54
        ),
        "magic_floorplan_completed": floorplan_rc == 0,
        "placement_only_magic_drc_zero": magic_counts == {"p_side": 0, "n_side": 0, "top": 0},
        "klayout_readback_completed": klayout_rc == 0,
        "klayout_hierarchy_is_two_sides_of_4356_units": (
            klayout.get("top_direct_instances") == 2
            and klayout.get("side_p_direct_instances") == 4356
            and klayout.get("side_n_direct_instances") == 4356
            and klayout.get("cell_count") == 4
        ),
        "all_28_planning_markers_are_present": len(klayout.get("planned_marker_labels", [])) == 28,
        "render_is_nonempty": (
            (ARTIFACTS / "cdac_diff_floorplan.png").exists()
            and (ARTIFACTS / "cdac_diff_floorplan.png").stat().st_size > 0
            and (ARTIFACTS / "cdac_pin_corridor.png").exists()
            and (ARTIFACTS / "cdac_pin_corridor.png").stat().st_size > 0
        ),
    }

    report = {
        "status": "SKY130_CDAC_PLACEMENT_FLOORPLAN_PASS" if all(checks.values()) else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "Open-source SKY130A hierarchical placement floorplan with placement-only Magic DRC and KLayout GDS readback",
        "cadence_qualified": False,
        "final_cdac_layout": False,
        "completion": {
            "binary_assignment": True,
            "all_8192_active_units_placed": checks["each_side_has_4096_active_units"],
            "edge_dummy_ring_placed": checks["each_side_has_260_edge_dummies"],
            "placement_only_drc": checks["placement_only_magic_drc_zero"],
            "routing": False,
            "lvs": False,
            "pex": False,
            "post_layout_performance": False,
        },
        "toolchain": {
            "container_image_sha256": CONTAINER_IMAGE,
            "pdk_resolved_path": str(PDK.resolve()),
            "pdk_version": PDK.resolve().parts[-2] if PDK.exists() else None,
            "magic": re.search(r"Magic ([^\n]+)", floorplan_log).group(0) if re.search(r"Magic ([^\n]+)", floorplan_log) else None,
            "klayout": tool_version(["/foss/tools/klayout/klayout", "-v"]),
        },
        "primitive": {
            "type": "sky130_fd_pr__cap_mim_m3_1",
            "requested_plate_um": [3.0, 3.0],
            "actual_geometry_bbox_um": list(map(float, (-2.43, -1.70, 2.43, 1.70))),
            "actual_geometry_width_height_um": [4.86, 3.40],
            "source_mag": "v2/environment/results/physical_20260908T022855079643Z/mim_unit.mag",
            "source_mag_sha256": sha256(REPO / "v2/environment/results/physical_20260908T022855079643Z/mim_unit.mag"),
        },
        "pitch_qualification": {
            "provisional_csv_pitch_um": 4.0,
            "criterion": "Magic DRC count is zero AND both capacitor terminals remain separate in extracted two-cell topology",
            "minimum_safe_tested_pitch_um": {
                "x": first_safe(pitch_results, "x"),
                "y": first_safe(pitch_results, "y"),
            },
            "used_pitch_um": generation["pitch_um"],
            "relative_to_4um": {
                "x_increase_percent": 50.0,
                "y_increase_percent": 13.5,
            },
            "four_um_observation": {
                "x_drc_count": pitch_by_key.get(("x", 4.0), {}).get("drc_count"),
                "x_terminal_topology_separate": pitch_by_key.get(("x", 4.0), {}).get("terminal_topology_separate"),
                "y_drc_count": pitch_by_key.get(("y", 4.0), {}).get("drc_count"),
                "y_terminal_topology_separate": pitch_by_key.get(("y", 4.0), {}).get("terminal_topology_separate"),
            },
            "boundary_observations": {
                "x_5p99": pitch_by_key.get(("x", 5.99)),
                "x_6p00": pitch_by_key.get(("x", 6.0)),
                "y_4p53": pitch_by_key.get(("y", 4.53)),
                "y_4p54": pitch_by_key.get(("y", 4.54)),
            },
            "all_probes": pitch_results,
        },
        "instance_counts": {
            "physical_per_side": physical_counts,
            "active_per_side": active_counts,
            "edge_dummy_per_side": edge_counts,
            "physical_total": len(placed),
            "active_total": sum(active_counts.values()),
            "edge_dummy_total": sum(edge_counts.values()),
            "by_net": generation["instance_counts_by_net"],
        },
        "geometry": {
            "side_bbox_um": side_bbox,
            "side_width_um": side_width,
            "side_height_um": side_height,
            "side_area_um2": side_area,
            "differential_top_bbox_um": top_bbox,
            "differential_top_bbox_area_um2": top_area,
            "reserved_inter_side_routing_gap_um": 30.0,
            "provisional_4um_side_bbox_um": [264.0, 264.0],
            "side_area_increase_vs_provisional_percent": (
                (side_area / provisional_side_area - 1.0) * 100.0 if side_area else None
            ),
            "active_plate_area_um2_both_sides": active_plate_area,
            "active_plate_area_fraction_of_two_side_bboxes": (
                active_plate_area / (2.0 * side_area) if side_area else None
            ),
        },
        "magic_drc_counts": magic_counts,
        "klayout_readback": klayout,
        "checks": checks,
        "limitations": [
            "This is a placement-only floorplan. None of the MIM terminals are routed.",
            "The 28 metal5 labels are unconnected planning markers, not electrical pins.",
            "Placement-only DRC does not prove connectivity; LVS is intentionally not claimed.",
            "No parasitic extraction or post-layout ADC simulation has been performed on this floorplan.",
            "Reference switches, comparator, frontend, bias, and digital control are not placed in this floorplan.",
            "The measured pitch is the first passing pairwise placement boundary for this exact PCell, not a routed-array pitch guarantee.",
            "Magic/KLayout open decks were used; this is not Cadence or foundry signoff.",
        ],
    }

    artifact_files = sorted(
        path for path in ARTIFACTS.iterdir() if path.is_file() and path.name != "qualification.json"
    )
    report["artifact_sha256"] = {path.name: sha256(path) for path in artifact_files}
    report["source_sha256"] = {
        path.name: sha256(path)
        for path in (
            HERE / "generate_floorplan.py",
            HERE / "pitch_probe.tcl",
            HERE / "pitch_probe_refine.tcl",
            HERE / "render_klayout.py",
            Path(__file__),
        )
    }
    (HERE / "qualification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "checks": checks, "geometry": report["geometry"], "completion": report["completion"]}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
