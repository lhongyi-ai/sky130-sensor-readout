#!/usr/bin/env python3
"""Independent GDS readback and PNG rendering of the routed differential CDAC."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pya


HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
GDS = ARTIFACTS / "cdac_diff_routed.gds"
FULL_PNG = ARTIFACTS / "cdac_diff_routed.png"
DETAIL_PNG = ARTIFACTS / "cdac_routing_detail.png"
DISPLAY_FULL_PNG = ARTIFACTS / "cdac_diff_routed_display_no_labels.png"
DISPLAY_DETAIL_PNG = ARTIFACTS / "cdac_routing_detail_display_no_labels.png"
SUMMARY = ARTIFACTS / "klayout_readback.json"


def bbox_um(box: pya.Box, dbu: float) -> list[float]:
    return [round(value * dbu, 6) for value in (box.left, box.bottom, box.right, box.top)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_text_for_display(layout: pya.Layout) -> int:
    """Remove GDS text from the in-memory display copy only.

    The source GDS is never written by this function.  Original labeled renders
    remain the extraction/readback evidence; the two additional renders are for
    human-readable presentation without labels covering wires or capacitor cells.
    """
    removed = 0
    for cell in layout.each_cell():
        for layer_index in layout.layer_indices():
            for shape in list(cell.shapes(layer_index).each()):
                if shape.is_text():
                    shape.delete()
                    removed += 1
    return removed


def main() -> None:
    source_hash_before = sha256(GDS)
    layout = pya.Layout()
    layout.read(str(GDS))
    names = sorted(cell.name for cell in layout.each_cell())
    top = layout.cell("cdac_diff_routed")
    p_side = layout.cell("cdac_side_p_routed")
    n_side = layout.cell("cdac_side_n_routed")
    mim = layout.cell("mim_unit")
    if any(cell is None for cell in (top, p_side, n_side, mim)):
        raise RuntimeError(f"missing expected hierarchy: {names}")

    labels: list[str] = []
    direct_shapes = 0
    for layer_index in layout.layer_indices():
        for shape in top.shapes(layer_index).each():
            direct_shapes += 1
            if shape.is_text():
                labels.append(shape.text.string)

    expected_ports = [
        *[f"P_{name}" for name in ["TOP", *[f"B{i}" for i in reversed(range(12))], "DUMMY", "EDGE_BIAS"]],
        *[f"N_{name}" for name in ["TOP", *[f"B{i}" for i in reversed(range(12))], "DUMMY", "EDGE_BIAS"]],
    ]
    report = {
        "reader": "KLayout pya independent GDS readback",
        "gds": GDS.name,
        "dbu_um": layout.dbu,
        "cells": names,
        "top_bbox_um": bbox_um(top.bbox(), layout.dbu),
        "p_side_bbox_um": bbox_um(p_side.bbox(), layout.dbu),
        "n_side_bbox_um": bbox_um(n_side.bbox(), layout.dbu),
        "top_direct_instances": sum(1 for _ in top.each_inst()),
        "p_side_direct_mim_instances": sum(1 for _ in p_side.each_inst()),
        "n_side_direct_mim_instances": sum(1 for _ in n_side.each_inst()),
        "top_direct_shapes_and_texts": direct_shapes,
        "top_port_labels": sorted(label for label in labels if label in expected_ports),
        "expected_port_labels": sorted(expected_ports),
    }
    view = pya.LayoutView()
    view.load_layout(str(GDS))
    view.max_hier()
    view.add_missing_layers()
    view.zoom_fit()
    view.save_image(str(FULL_PNG), 2800, 1400)

    # Detail view: P-side center rows, where B0...B6/DUMMY escape into M5,
    # plus the upper M4 pin buses.  This makes physical connectivity visible
    # rather than rendering 8,712 caps as an indistinguishable solid block.
    view.zoom_box(pya.DBox(0.0, 175.0, 455.0, 423.0))
    view.save_image(str(DETAIL_PNG), 2400, 1500)

    # Create separate presentation renders from an in-memory copy with every
    # text shape hidden.  This avoids the repeated C1/C2 and dense port labels
    # obscuring geometry.  Do not save this modified layout: GDS stays intact.
    display_layout = pya.Layout()
    display_layout.read(str(GDS))
    removed_texts = remove_text_for_display(display_layout)
    display_view = pya.LayoutView()
    display_view.show_layout(display_layout, True)
    display_view.max_hier()
    display_view.add_missing_layers()
    display_view.zoom_fit()
    display_view.save_image(str(DISPLAY_FULL_PNG), 2800, 1400)
    # Tight crop around the central one-trunk B0/DUMMY region.  The 66 x 41 um
    # window shows individual MIM cells, M4 escape fingers, via4 landings and
    # the two M5 trunks at readable scale.
    display_view.zoom_box(pya.DBox(164.0, 174.0, 230.0, 215.0))
    display_view.save_image(str(DISPLAY_DETAIL_PNG), 2400, 1500)

    source_hash_after = sha256(GDS)
    report["display_render"] = {
        "source_gds_unchanged": source_hash_before == source_hash_after,
        "source_gds_sha256_before": source_hash_before,
        "source_gds_sha256_after": source_hash_after,
        "text_shapes_removed_in_memory": removed_texts,
        "full_png": DISPLAY_FULL_PNG.name,
        "detail_png": DISPLAY_DETAIL_PNG.name,
        "note": "All GDS text is hidden only in presentation renders; physical port labels remain in the verified GDS and original evidence renders.",
    }
    SUMMARY.write_text(json.dumps(report, indent=2) + "\n")

    for path in (FULL_PNG, DETAIL_PNG, DISPLAY_FULL_PNG, DISPLAY_DETAIL_PNG):
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"KLayout did not render {path}")
    print(json.dumps({"status": "KLAYOUT_ROUTED_READBACK_PASS", **report}, indent=2))


if __name__ == "__main__":
    main()
