#!/usr/bin/env python3
"""Generate a physically connected 12-bit differential SKY130 MIM CDAC.

The electrical assignment remains exactly the checked 64 x 64 assignment in
``v2/physical/cdac``.  Only the physical pitch and routing are added here.

Routing architecture
--------------------
* Every active C2 terminal is joined to TOP with a real metal3 mesh.
* Every active C1 terminal escapes vertically on metal4 to a row-channel bus.
* Real via4 contacts lift each contiguous bank run to metal5 trunks.
* Separate metal4 buses above the array join same-net trunks and expose pins.
* Edge dummy terminals are shorted together and tied to an independent
  EDGE_BIAS metal3 ring, so they do not add 260 units to the active TOP node.

No label is used as a substitute for connectivity: every same-net grouping is
formed by overlapping conductor shapes and contacts.  Labels only mark ports
after the conductor exists.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ASSIGNMENT_DIR = HERE.parent / "cdac"
SOURCE_LAYOUT_DIR = HERE.parent / "cdac_layout_20260911" / "artifacts"
ARTIFACTS = HERE / "artifacts"

ROWS = 66
COLS = 66
ACTIVE_MIN = 1
ACTIVE_MAX = 64
PITCH_X = 6.0
# The prior placement used 4.54 um.  A via4 landing is 1.18 um high and does
# not fit between the 3.40 um-tall PCells with required M4 spacing.  Six um
# provides a 2.60 um channel and was selected before full-array generation.
PITCH_Y = 6.0
C1_DX = -0.73
C2_DX = 2.17
ROW_BUS_DY = 3.0
SIDE_GAP = 30.0

NETS_DESC = [f"B{bit}" for bit in reversed(range(12))] + ["DUMMY"]
LARGE_NETS = {f"B{bit}" for bit in range(6, 12)}

# MIM physical envelope relative to placement origin, measured from the real
# PCell.  Used only for auditable area calculations.
MIM_BBOX = (-2.43, -1.70, 2.43, 1.70)

LEFT_TRUNKS = {f"B{bit}": -4.0 - 3.2 * (bit - 6) for bit in range(6, 12)}
RIGHT_TRUNKS = {f"B{bit}": 394.0 + 3.2 * (bit - 6) for bit in range(6, 12)}

PERIPHERY_Y0 = 396.0
PERIPHERY_PITCH = 2.0
PERIPHERY_Y = {net: PERIPHERY_Y0 + i * PERIPHERY_PITCH for i, net in enumerate(NETS_DESC)}

# Parent pin landing point shared by all switched-net buses.
PIN_X = 220.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(polarity: str) -> list[dict[str, object]]:
    path = ASSIGNMENT_DIR / f"cdac_{polarity.lower()}_assignment.csv"
    result: list[dict[str, object]] = []
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            result.append(
                {
                    "polarity": row["polarity"],
                    "row": int(row["physical_row"]),
                    "col": int(row["physical_col"]),
                    "net": row["net"],
                    "electrical": bool(int(row["electrical"])),
                }
            )
    if len(result) != ROWS * COLS:
        raise ValueError(f"{path}: expected {ROWS * COLS} rows, got {len(result)}")
    if any(row["polarity"] != polarity for row in result):
        raise ValueError(f"{path}: polarity mismatch")
    return result


def active_by_row(rows: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    out: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        if row["electrical"]:
            out[int(row["row"])].append(row)
    for values in out.values():
        values.sort(key=lambda item: int(item["col"]))
    return dict(out)


def contiguous_runs(values: list[dict[str, object]]) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for net, group in itertools.groupby(values, key=lambda item: str(item["net"])):
        units = list(group)
        cols = [int(unit["col"]) for unit in units]
        if cols != list(range(cols[0], cols[-1] + 1)):
            raise ValueError(f"non-contiguous grouped run {net}: {cols[0]}..{cols[-1]}")
        runs.append({"net": net, "start_col": cols[0], "end_col": cols[-1], "count": len(cols)})
    return runs


def x_c1(col: int) -> float:
    return col * PITCH_X + C1_DX


def x_c2(col: int) -> float:
    return col * PITCH_X + C2_DX


def y_center(row: int) -> float:
    return row * PITCH_Y


def choose_internal_anchor(start_col: int, end_col: int) -> float:
    # Always land on the C1 x coordinate of a real member of the run.  For an
    # even count, the lower of the two central members is deterministic.
    return x_c1((start_col + end_col) // 2)


def build_route_plan(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, list[float]]]:
    runs: list[dict[str, object]] = []
    trunks: dict[str, set[float]] = defaultdict(set)
    for row, units in sorted(active_by_row(rows).items()):
        for run in contiguous_runs(units):
            net = str(run["net"])
            start_col = int(run["start_col"])
            end_col = int(run["end_col"])
            if net in LARGE_NETS:
                if start_col == ACTIVE_MIN:
                    anchor = LEFT_TRUNKS[net]
                    escape = "left"
                elif end_col == ACTIVE_MAX:
                    anchor = RIGHT_TRUNKS[net]
                    escape = "right"
                else:
                    raise ValueError(f"{net} row {row} does not reach an array edge")
            else:
                anchor = choose_internal_anchor(start_col, end_col)
                escape = "internal"
            item = dict(run, row=row, anchor_x=anchor, escape=escape)
            runs.append(item)
            trunks[net].add(anchor)

    expected = Counter(str(row["net"]) for row in rows if row["electrical"])
    if expected != Counter({**{f"B{i}": 1 << i for i in range(12)}, "DUMMY": 1}):
        raise ValueError(f"binary count changed: {dict(expected)}")
    if set(trunks) != set(NETS_DESC):
        raise ValueError(f"missing routed nets: {set(NETS_DESC) - set(trunks)}")
    return runs, {net: sorted(xs) for net, xs in sorted(trunks.items())}


def rect(layer: str, x1: float, y1: float, x2: float, y2: float) -> str:
    return f"rectangle {layer} {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}"


def place_line(polarity: str, row: dict[str, object]) -> str:
    r = int(row["row"])
    c = int(row["col"])
    net = str(row["net"])
    return (
        f"getcell mim_unit child 0 0 parent {c * PITCH_X:.3f}um {r * PITCH_Y:.3f}um; "
        f"identify X{polarity}_r{r:02d}_c{c:02d}_{net}"
    )


def side_route_tcl(polarity: str, rows: list[dict[str, object]], runs: list[dict[str, object]], trunks: dict[str, list[float]]) -> list[str]:
    cell = f"cdac_side_{polarity.lower()}_routed"
    lines = [f"load {cell} -silent", "box values 0 0 0 0"]
    lines.extend(place_line(polarity, row) for row in rows)

    # Active TOP mesh.  M3 is the C2 electrode layer; these shapes overlap the
    # real C2 electrode at every active cell rather than depending on labels.
    x_left = ACTIVE_MIN * PITCH_X + MIM_BBOX[0]
    x_right = ACTIVE_MAX * PITCH_X + MIM_BBOX[2]
    for row in range(ACTIVE_MIN, ACTIVE_MAX + 1):
        y = y_center(row)
        lines.append(rect("metal3", x_left, y - 0.30, x_right, y + 0.30))
    # Join rows in the 3.0 um MIM-to-MIM slot between active column 64
    # and the right edge-dummy column.  A 0.30 um M3 trunk leaves 1.35 um
    # to the unrelated dummy MIM, just beyond capm.11's 1.34 um spacing.
    # Putting this trunk directly on a C2 access rail created 194 capm.11
    # violations in the preserved first full-array attempt.
    top_trunk_x = ACTIVE_MAX * PITCH_X + MIM_BBOX[2] - 0.16
    lines.append(rect("metal3", top_trunk_x - 0.15, y_center(ACTIVE_MIN), top_trunk_x + 0.15, y_center(ACTIVE_MAX)))

    # Edge dummy ring.  First short C1 to C2 locally on M4, then join every C2
    # electrode with a separate M3 ring.  This is intentionally not TOP.
    edge_rows = [row for row in rows if not bool(row["electrical"])]
    for row in edge_rows:
        x1 = x_c1(int(row["col"])) - 0.20
        x2 = x_c2(int(row["col"])) + 0.20
        y = y_center(int(row["row"]))
        lines.append(rect("metal4", x1, y - 0.20, x2, y + 0.20))
    edge_left = MIM_BBOX[0]
    edge_right = (COLS - 1) * PITCH_X + MIM_BBOX[2]
    edge_bottom = MIM_BBOX[1]
    edge_top = (ROWS - 1) * PITCH_Y + MIM_BBOX[3]
    lines.extend(
        [
            rect("metal3", edge_left, -0.30, edge_right, 0.30),
            rect("metal3", edge_left, y_center(ROWS - 1) - 0.30, edge_right, y_center(ROWS - 1) + 0.30),
            rect("metal3", x_c2(0) - 0.15, edge_bottom, x_c2(0) + 0.15, edge_top),
            rect("metal3", x_c2(COLS - 1) - 0.15, edge_bottom, x_c2(COLS - 1) + 0.15, edge_top),
        ]
    )

    # C1-to-row-channel escapes and run buses.
    by_row = active_by_row(rows)
    for row, units in sorted(by_row.items()):
        y = y_center(row)
        bus_y = y + ROW_BUS_DY
        for unit in units:
            x = x_c1(int(unit["col"]))
            lines.append(rect("metal4", x - 0.20, y - 0.20, x + 0.20, bus_y + 0.20))
    for run in runs:
        bus_y = y_center(int(run["row"])) + ROW_BUS_DY
        start_x = x_c1(int(run["start_col"]))
        end_x = x_c1(int(run["end_col"]))
        anchor = float(run["anchor_x"])
        lines.append(rect("metal4", min(start_x, anchor), bus_y - 0.20, max(end_x, anchor), bus_y + 0.20))
        lines.append(f"via45 {anchor:.3f} {bus_y:.3f}")

    # Metal5 trunks extend from the first attached row to the corresponding
    # M4 peripheral bus.  Same-net trunks are physically joined at that bus.
    route_ys: dict[tuple[str, float], list[float]] = defaultdict(list)
    for run in runs:
        route_ys[(str(run["net"]), float(run["anchor_x"]))].append(y_center(int(run["row"])) + ROW_BUS_DY)
    for net in NETS_DESC:
        bus_y = PERIPHERY_Y[net]
        xs = trunks[net]
        for x in xs:
            ys = route_ys[(net, x)]
            lines.append(rect("metal5", x - 0.80, min(ys) - 0.80, x + 0.80, bus_y + 0.80))
        # A genuine M4 connection even for a one-trunk net.  The 4 um stub
        # gives a visible/accessible pin and ample minimum area.
        # Every bus must reach the shared physical pin x.  The initial
        # one-trunk implementation left B0 and DUMMY's labels detached from
        # metal (caught because extraction omitted both ports).
        bus_left = min([*xs, PIN_X])
        bus_right = max([*xs, PIN_X])
        lines.append(rect("metal4", bus_left, bus_y - 0.20, bus_right, bus_y + 0.20))
        for x in xs:
            lines.append(f"via45 {x:.3f} {bus_y:.3f}")

    # Ports are labels on already-existing conductor, never detached markers.
    lines.append(
        f"pin TOP 1 metal3 {x_c2(ACTIVE_MIN)-0.30:.3f} {y_center(ACTIVE_MIN)-0.30:.3f} "
        f"{x_c2(ACTIVE_MIN)+0.30:.3f} {y_center(ACTIVE_MIN)+0.30:.3f}"
    )
    port_number = 2
    for net in NETS_DESC:
        y = PERIPHERY_Y[net]
        lines.append(f"pin {net} {port_number} metal4 {PIN_X-0.20:.3f} {y-0.20:.3f} {PIN_X+0.20:.3f} {y+0.20:.3f}")
        port_number += 1
    lines.append(f"pin EDGE_BIAS {port_number} metal3 {x_c2(0)-0.30:.3f} -0.300 {x_c2(0)+0.30:.3f} 0.300")

    lines.extend(
        [
            f"save {cell}",
            "select top cell",
            "expand",
            "drc on",
            "drc check",
            "drc catchup",
            f'puts "SIDE_DRC_COUNT {polarity} [drc list count total]"',
            f'puts "SIDE_DRC_DETAILS {polarity} [drc listall why]"',
            f"gds write {cell}.gds",
            "drc off",
            f"flatten {cell}_flat",
            f"load {cell}_flat",
            f"save {cell}_flat",
            "extract all",
            "ext2spice lvs",
            f"ext2spice -o {cell}_flat.lvs.spice",
            "ext2spice cthresh 0",
            "ext2spice rthresh 0",
            f"ext2spice -o {cell}_flat.cap.spice",
        ]
    )
    return lines


def parent_pin_tcl(prefix: str, origin_x: float, number0: int) -> tuple[list[str], int]:
    lines: list[str] = []
    number = number0
    x_top = origin_x + x_c2(ACTIVE_MIN)
    y_top = y_center(ACTIVE_MIN)
    lines.append(rect("metal3", x_top - 0.30, y_top - 0.30, x_top + 0.30, y_top + 0.30))
    lines.append(f"pin {prefix}_TOP {number} metal3 {x_top-0.30:.3f} {y_top-0.30:.3f} {x_top+0.30:.3f} {y_top+0.30:.3f}")
    number += 1
    for net in NETS_DESC:
        y = PERIPHERY_Y[net]
        x = origin_x + PIN_X
        lines.append(rect("metal4", x - 0.20, y - 0.20, x + 0.20, y + 0.20))
        lines.append(f"pin {prefix}_{net} {number} metal4 {x-0.20:.3f} {y-0.20:.3f} {x+0.20:.3f} {y+0.20:.3f}")
        number += 1
    x_edge = origin_x + x_c2(0)
    lines.append(rect("metal3", x_edge - 0.30, -0.30, x_edge + 0.30, 0.30))
    lines.append(f"pin {prefix}_EDGE_BIAS {number} metal3 {x_edge-0.30:.3f} -0.300 {x_edge+0.30:.3f} 0.300")
    return lines, number + 1


def write_magic_tcl(data: dict[str, tuple[list[dict[str, object]], list[dict[str, object]], dict[str, list[float]]]]) -> Path:
    path = ARTIFACTS / "generate_routed_cdac.tcl"
    # Positive origin keeps the full left-side M5 trunks within the top GDS
    # coordinate envelope.  The side cells themselves legitimately use
    # negative local coordinates.
    p_origin = 22.0
    side_bbox_width = 431.6
    n_origin = p_origin + side_bbox_width + SIDE_GAP
    lines = [
        "# Generated by generate_routed_cdac.py; actual conductor routing.",
        "set out /repo/v2/physical/cdac_route_20260911/artifacts",
        "file mkdir $out",
        "cd $out",
        # A failed/revised generation must not silently accumulate paint from
        # a prior .mag.  Delete only this generator's named cell products;
        # preserved attempt logs and independent references are untouched.
        "foreach cell {cdac_side_p_routed cdac_side_n_routed cdac_side_p_routed_flat cdac_side_n_routed_flat cdac_diff_routed} {",
        "    foreach suffix {mag ext gds} {file delete -force [file join $out ${cell}.${suffix}]} ",
        "}",
        "file copy -force /repo/v2/physical/cdac_layout_20260911/artifacts/mim_unit.mag [file join $out mim_unit.mag]",
        "snap internal",
        "drc off",
        "proc rectangle {layer x1 y1 x2 y2} {",
        "    box values ${x1}um ${y1}um ${x2}um ${y2}um",
        "    paint $layer",
        "}",
        "proc via45 {x y} {",
        "    rectangle metal4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]",
        "    rectangle via4   [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]",
        "    rectangle metal5 [expr {$x-0.80}] [expr {$y-0.80}] [expr {$x+0.80}] [expr {$y+0.80}]",
        "}",
        "proc pin {name number layer x1 y1 x2 y2} {",
        "    box values ${x1}um ${y1}um ${x2}um ${y2}um",
        "    label $name center $layer",
        "    port make $number",
        "    port class bidirectional",
        "    port use signal",
        "}",
    ]
    for polarity in ("P", "N"):
        rows, runs, trunks = data[polarity]
        lines.extend(side_route_tcl(polarity, rows, runs, trunks))

    lines.extend(
        [
            "load cdac_diff_routed -silent",
            "box values 0 0 0 0",
            f"getcell cdac_side_p_routed child 0 0 parent {p_origin:.3f}um 0um; identify X_CDAC_P",
            f"getcell cdac_side_n_routed child 0 0 parent {n_origin:.3f}um 0um; identify X_CDAC_N",
        ]
    )
    p_lines, next_number = parent_pin_tcl("P", p_origin, 1)
    n_lines, _ = parent_pin_tcl("N", n_origin, next_number)
    lines.extend(p_lines)
    lines.extend(n_lines)
    lines.extend(
        [
            "save cdac_diff_routed",
            "select top cell",
            "expand",
            "drc on",
            "drc check",
            "drc catchup",
            'puts "TOP_DRC_COUNT [drc list count total]"',
            'puts "TOP_DRC_DETAILS [drc listall why]"',
            "gds write cdac_diff_routed.gds",
            "extract all",
            "ext2spice lvs",
            "ext2spice -o cdac_diff_routed.lvs.spice",
            "ext2spice cthresh 0",
            "ext2spice rthresh 0",
            "ext2spice -o cdac_diff_routed.cap.spice",
            "quit -noprompt",
        ]
    )
    path.write_text("\n".join(lines) + "\n")
    return path


def write_side_reference(polarity: str, rows: list[dict[str, object]]) -> Path:
    cell = f"cdac_side_{polarity.lower()}_routed_flat"
    path = ARTIFACTS / f"{cell}.reference.spice"
    pins = ["TOP", *NETS_DESC, "EDGE_BIAS"]
    lines = [f"* Independent intended topology for {cell}.", f".subckt {cell} {' '.join(pins)}"]
    for row in rows:
        r = int(row["row"])
        c = int(row["col"])
        net = str(row["net"])
        if bool(row["electrical"]):
            c1, c2 = net, "TOP"
        else:
            # The physical edge-ring short makes both plates EDGE_BIAS.
            c1 = c2 = "EDGE_BIAS"
        lines.append(f"X{polarity}_r{r:02d}_c{c:02d}_{net} {c1} {c2} sky130_fd_pr__cap_mim_m3_1 w=3 l=3")
    lines.append(f".ends {cell}")
    path.write_text("\n".join(lines) + "\n")
    return path


def write_top_reference() -> Path:
    path = ARTIFACTS / "cdac_diff_routed.reference.spice"
    side_pins = ["TOP", *NETS_DESC, "EDGE_BIAS"]
    top_pins = [*[f"P_{pin}" for pin in side_pins], *[f"N_{pin}" for pin in side_pins]]
    lines = ["* Independent hierarchical reference for the routed differential CDAC."]
    for polarity in ("P", "N"):
        side_ref = ARTIFACTS / f"cdac_side_{polarity.lower()}_routed_flat.reference.spice"
        # Rename only the subcircuit declaration/end marker; device statements
        # remain independent source generated from the assignment CSV.
        text = side_ref.read_text().replace(
            f"cdac_side_{polarity.lower()}_routed_flat",
            f"cdac_side_{polarity.lower()}_routed",
        )
        lines.append(text.rstrip())
    lines.append(f".subckt cdac_diff_routed {' '.join(top_pins)}")
    lines.append(f"XP {' '.join(f'P_{pin}' for pin in side_pins)} cdac_side_p_routed")
    lines.append(f"XN {' '.join(f'N_{pin}' for pin in side_pins)} cdac_side_n_routed")
    lines.append(".ends cdac_diff_routed")
    path.write_text("\n".join(lines) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    data: dict[str, tuple[list[dict[str, object]], list[dict[str, object]], dict[str, list[float]]]] = {}
    route_summary: dict[str, object] = {}
    for polarity in ("P", "N"):
        rows = read_rows(polarity)
        runs, trunks = build_route_plan(rows)
        data[polarity] = (rows, runs, trunks)
        route_summary[polarity] = {
            "active_units": sum(bool(row["electrical"]) for row in rows),
            "edge_dummies": sum(not bool(row["electrical"]) for row in rows),
            "contiguous_row_runs": len(runs),
            "metal5_trunks": sum(len(xs) for xs in trunks.values()),
            "trunks_by_net_um": trunks,
            "counts_by_net": dict(sorted(Counter(str(row["net"]) for row in rows if row["electrical"]).items())),
        }

    tcl = write_magic_tcl(data)
    side_refs = [write_side_reference(polarity, data[polarity][0]) for polarity in ("P", "N")]
    top_ref = write_top_reference()

    min_x = min(min(LEFT_TRUNKS.values()) - 0.8, MIM_BBOX[0])
    max_x = max(max(RIGHT_TRUNKS.values()) + 0.8, (COLS - 1) * PITCH_X + MIM_BBOX[2])
    min_y = MIM_BBOX[1]
    max_y = max(max(PERIPHERY_Y.values()) + 0.8, (ROWS - 1) * PITCH_Y + MIM_BBOX[3])
    side_w = max_x - min_x
    side_h = max_y - min_y
    manifest = {
        "status": "GENERATED_NOT_YET_PHYSICALLY_QUALIFIED",
        "evidence_level": "Generated real-metal routing input; DRC/LVS/PEX determined only after tools run",
        "assignment_preserved": True,
        "pitch_um": {"x": PITCH_X, "y": PITCH_Y},
        "prior_pitch_um": {"x": 6.0, "y": 4.54},
        "pitch_change_percent": {"x": 0.0, "y": (PITCH_Y / 4.54 - 1.0) * 100.0},
        "routing": {
            "top": "metal3 mesh physically overlaps every active C2 terminal",
            "bank_escape": "metal4 C1 fingers and row-channel buses",
            "bank_trunks": "metal5 with real 1.18um via4 contacts and 1.60um-wide M5",
            "periphery": "distinct metal4 buses, 2.0um pitch",
            "edge_dummies": "both plates shorted and tied to separate EDGE_BIAS metal3 ring",
            "detached_connectivity_labels": False,
        },
        "route_summary": route_summary,
        "geometry": {
            "side_bbox_estimate_um": [min_x, min_y, max_x, max_y],
            "side_width_height_um": [side_w, side_h],
            "side_area_mm2": side_w * side_h / 1e6,
            "differential_bbox_estimate_um": [2 * side_w + SIDE_GAP, side_h],
            "differential_area_mm2": (2 * side_w + SIDE_GAP) * side_h / 1e6,
        },
        "sources_sha256": {
            str(path.relative_to(REPO)): sha256(path)
            for path in [
                ASSIGNMENT_DIR / "cdac_p_assignment.csv",
                ASSIGNMENT_DIR / "cdac_n_assignment.csv",
                ASSIGNMENT_DIR / "assignment_summary.json",
                SOURCE_LAYOUT_DIR / "mim_unit.mag",
            ]
        },
        "generated_sha256": {
            path.name: sha256(path) for path in [tcl, *side_refs, top_ref]
        },
    }
    (HERE / "generation_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": manifest["status"], "pitch_um": manifest["pitch_um"], "geometry": manifest["geometry"], "route_summary": route_summary}, indent=2))


if __name__ == "__main__":
    main()
