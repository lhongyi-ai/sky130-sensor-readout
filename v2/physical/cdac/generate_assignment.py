#!/usr/bin/env python3
"""Generate a deterministic common-centroid assignment for the differential CDAC.

This produces placement intent, not a fabricated or DRC-clean layout.  Each
polarity contains exactly 4096 active 3 um x 3 um MIM units in a 64 x 64 core.
An unconnected perimeter is added as physical edge dummies.  B11..B1 are made
of inversion-symmetric pairs.  B0 and the electrical DUMMY occupy the central
mirror pair, so their combined centroid is also at the array centre.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
CORE_N = 64
PITCH_UM = 4.0
UNIT_PLATE_UM = 3.0
EDGE_DUMMY_RINGS = 1


def bit_reverse(value: int, width: int) -> int:
    return int(f"{value:0{width}b}"[::-1], 2)


def mirror(coord: tuple[int, int]) -> tuple[int, int]:
    row, col = coord
    return CORE_N - 1 - row, CORE_N - 1 - col


def pair_representatives() -> list[tuple[int, int]]:
    reps = []
    for row in range(CORE_N):
        for col in range(CORE_N):
            coord = (row, col)
            if coord < mirror(coord):
                reps.append(coord)
    assert len(reps) == CORE_N * CORE_N // 2
    return reps


def assignment() -> dict[tuple[int, int], str]:
    reps = pair_representatives()
    central = (CORE_N // 2 - 1, CORE_N // 2 - 1)
    assert central in reps
    remaining = [coord for coord in reps if coord != central]

    # Bit-reversed ordering prevents the large banks from being allocated as
    # one contiguous block.  The rank's number of trailing zeroes gives exact
    # binary bank counts: 1024 pairs for B11 down to one pair for B1.
    remaining.sort(key=lambda rc: bit_reverse(rc[0] * CORE_N + rc[1], 12))
    cells: dict[tuple[int, int], str] = {}
    for rank, coord in enumerate(remaining, start=1):
        trailing_zeroes = (rank & -rank).bit_length() - 1
        bit = 11 - trailing_zeroes
        if bit < 1:
            raise AssertionError(f"unexpected rank allocation at {rank}")
        label = f"B{bit}"
        cells[coord] = label
        cells[mirror(coord)] = label

    cells[central] = "B0"
    cells[mirror(central)] = "DUMMY"
    assert len(cells) == CORE_N * CORE_N
    return cells


def transformed(cells: dict[tuple[int, int], str]) -> dict[tuple[int, int], str]:
    """Mirror the N array locally to make the two physical halves symmetric."""
    return {(row, CORE_N - 1 - col): label for (row, col), label in cells.items()}


def centroid(points: list[tuple[int, int]]) -> list[float]:
    return [sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points)]


def analyze(cells: dict[tuple[int, int], str]) -> dict:
    by_label: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for coord, label in cells.items():
        by_label[label].append(coord)
    expected = {f"B{bit}": 1 << bit for bit in range(12)} | {"DUMMY": 1}
    counts = Counter(cells.values())
    array_center = [(CORE_N - 1) / 2, (CORE_N - 1) / 2]
    centroids = {label: centroid(points) for label, points in sorted(by_label.items())}
    errors = {label: [value - array_center[i] for i, value in enumerate(center)]
              for label, center in centroids.items() for i in [0]}
    checks = {
        "exact_binary_counts": dict(counts) == expected,
        "all_core_locations_assigned_once": len(cells) == CORE_N * CORE_N,
        "b11_through_b1_exact_common_centroid": all(
            centroids[f"B{bit}"] == array_center for bit in range(1, 12)),
        "b0_plus_dummy_are_central_mirror_pair": (
            mirror(by_label["B0"][0]) == by_label["DUMMY"][0]
            and centroid(by_label["B0"] + by_label["DUMMY"]) == array_center),
    }
    return {
        "counts": dict(sorted(counts.items())),
        "centroids_row_col": centroids,
        "centroid_error_cells": errors,
        "checks": checks,
    }


def color(label: str) -> str:
    palette = {
        "B11": "#124e78", "B10": "#2878a8", "B9": "#5aa7d1",
        "B8": "#82c9e8", "B7": "#2a9d8f", "B6": "#63c7a6",
        "B5": "#94d2bd", "B4": "#e9c46a", "B3": "#f4a261",
        "B2": "#e76f51", "B1": "#a44a3f", "B0": "#6d597a",
        "DUMMY": "#222222", "EDGE": "#d7dde3",
    }
    return palette[label]


def write_csv(path: Path, polarity: str, cells: dict[tuple[int, int], str]) -> None:
    ring_n = CORE_N + 2 * EDGE_DUMMY_RINGS
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "polarity", "physical_row", "physical_col", "core_row", "core_col",
            "net", "electrical", "x_um", "y_um"))
        writer.writeheader()
        for prow in range(ring_n):
            for pcol in range(ring_n):
                core = (prow - EDGE_DUMMY_RINGS, pcol - EDGE_DUMMY_RINGS)
                electrical = core in cells
                writer.writerow({
                    "polarity": polarity,
                    "physical_row": prow,
                    "physical_col": pcol,
                    "core_row": core[0] if electrical else "",
                    "core_col": core[1] if electrical else "",
                    "net": cells[core] if electrical else "EDGE",
                    "electrical": int(electrical),
                    "x_um": f"{pcol * PITCH_UM:.3f}",
                    "y_um": f"{prow * PITCH_UM:.3f}",
                })


def write_svg(path: Path, p_cells: dict[tuple[int, int], str],
              n_cells: dict[tuple[int, int], str]) -> None:
    scale = 4
    ring_n = CORE_N + 2 * EDGE_DUMMY_RINGS
    array_px = ring_n * scale
    gap = 44
    left = 38
    top = 58
    width = left * 2 + array_px * 2 + gap
    height = top + array_px + 108
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfcfe"/>',
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#17202a}.t{font-size:18px;font-weight:700}.s{font-size:11px}.l{font-size:10px}</style>',
        '<text class="t" x="38" y="29">12-bit differential CDAC placement assignment</text>',
        '<text class="s" x="38" y="46">64 x 64 active units per side; one physical edge-dummy ring; colors show bottom-plate nets</text>',
    ]
    for index, (name, cells) in enumerate((("P side", p_cells), ("N side (locally mirrored)", n_cells))):
        x0 = left + index * (array_px + gap)
        parts.append(f'<text class="s" x="{x0}" y="{top - 9}">{name}</text>')
        for prow in range(ring_n):
            for pcol in range(ring_n):
                core = (prow - EDGE_DUMMY_RINGS, pcol - EDGE_DUMMY_RINGS)
                label = cells.get(core, "EDGE")
                x = x0 + pcol * scale
                y = top + (ring_n - 1 - prow) * scale
                parts.append(f'<rect x="{x}" y="{y}" width="{scale}" height="{scale}" fill="{color(label)}"/>')
        parts.append(f'<rect x="{x0}" y="{top}" width="{array_px}" height="{array_px}" fill="none" stroke="#17202a" stroke-width="1"/>')
    legend = [f"B{bit}" for bit in reversed(range(12))] + ["DUMMY", "EDGE"]
    for i, label in enumerate(legend):
        x = left + (i % 7) * 72
        y = top + array_px + 27 + (i // 7) * 24
        parts.append(f'<rect x="{x}" y="{y - 10}" width="12" height="12" rx="2" fill="{color(label)}"/>')
        parts.append(f'<text class="l" x="{x + 17}" y="{y}">{label}</text>')
    parts.append(f'<text class="s" x="{left}" y="{height - 17}">Placement intent only — routing, DRC, LVS, extraction and post-layout performance remain separate gates.</text>')
    parts.append('</svg>')
    path.write_text("\n".join(parts) + "\n")


def main() -> None:
    p_cells = assignment()
    n_cells = transformed(p_cells)
    p_report = analyze(p_cells)
    n_report = analyze(n_cells)
    write_csv(HERE / "cdac_p_assignment.csv", "P", p_cells)
    write_csv(HERE / "cdac_n_assignment.csv", "N", n_cells)
    write_svg(HERE / "cdac_assignment.svg", p_cells, n_cells)
    report = {
        "status": "PLACEMENT_ASSIGNMENT_PASS" if all(p_report["checks"].values()) and all(n_report["checks"].values()) else "FAIL",
        "evidence_level": "Deterministic unit-capacitor placement assignment; not GDS/DRC/LVS/PEX",
        "geometry": {
            "active_rows": CORE_N,
            "active_columns": CORE_N,
            "active_units_per_side": CORE_N * CORE_N,
            "differential_active_units": 2 * CORE_N * CORE_N,
            "edge_dummy_rings": EDGE_DUMMY_RINGS,
            "physical_units_per_side_including_edge_dummies": (CORE_N + 2 * EDGE_DUMMY_RINGS) ** 2,
            "unit_plate_um": [UNIT_PLATE_UM, UNIT_PLATE_UM],
            "provisional_pitch_um": PITCH_UM,
            "provisional_array_bbox_um_per_side": [
                (CORE_N + 2 * EDGE_DUMMY_RINGS) * PITCH_UM,
                (CORE_N + 2 * EDGE_DUMMY_RINGS) * PITCH_UM,
            ],
            "active_plate_area_um2_both_sides": 2 * CORE_N * CORE_N * UNIT_PLATE_UM ** 2,
        },
        "p_side": p_report,
        "n_side": n_report,
        "limitations": [
            "No metal routing, shields, taps, reference switches, comparator or frontend are placed.",
            "The 4 um pitch is provisional until the routed SKY130 DRC result is known.",
            "Edge dummies are physical placeholders and are not part of the 4096-unit electrical sum.",
            "B0 and electrical DUMMY are a central mirror pair; each singleton cannot independently have an exact centroid.",
            "No spatial-gradient, parasitic, reference-droop, noise or mismatch result is inferred from this assignment.",
        ],
    }
    generated = [HERE / "cdac_p_assignment.csv", HERE / "cdac_n_assignment.csv", HERE / "cdac_assignment.svg"]
    report["artifact_sha256"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in generated
    }
    (HERE / "assignment_summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "status": report["status"],
        "active_units": report["geometry"]["differential_active_units"],
        "checks": {"p": p_report["checks"], "n": n_report["checks"]},
    }, indent=2))


if __name__ == "__main__":
    main()
