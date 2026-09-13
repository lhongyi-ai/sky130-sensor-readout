#!/usr/bin/env python3
"""Read back and render the generated GDS with KLayout's Python API."""

from __future__ import annotations

import json
from pathlib import Path

import pya


HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
GDS = ARTIFACTS / "cdac_diff_floorplan.gds"
PNG = ARTIFACTS / "cdac_diff_floorplan.png"
PIN_PNG = ARTIFACTS / "cdac_pin_corridor.png"
SUMMARY = ARTIFACTS / "klayout_summary.json"


def bbox_um(box: pya.Box, dbu: float) -> list[float]:
    return [round(value * dbu, 6) for value in (box.left, box.bottom, box.right, box.top)]


def main() -> None:
    layout = pya.Layout()
    layout.read(str(GDS))
    top = layout.cell("cdac_diff_floorplan")
    p_side = layout.cell("cdac_side_p")
    n_side = layout.cell("cdac_side_n")
    primitive = layout.cell("mim_unit")
    if any(cell is None for cell in (top, p_side, n_side, primitive)):
        raise RuntimeError("expected hierarchy cells are missing")

    text_labels: list[str] = []
    direct_shapes = 0
    for layer_index in layout.layer_indices():
        for shape in top.shapes(layer_index).each():
            direct_shapes += 1
            if shape.is_text():
                text_labels.append(shape.text.string)

    cells = sorted(cell.name for cell in layout.each_cell())
    report = {
        "reader": "KLayout pya",
        "gds": GDS.name,
        "dbu_um": layout.dbu,
        "top_cell": top.name,
        "top_bbox_um": bbox_um(top.bbox(), layout.dbu),
        "side_p_bbox_um": bbox_um(p_side.bbox(), layout.dbu),
        "side_n_bbox_um": bbox_um(n_side.bbox(), layout.dbu),
        "top_direct_instances": sum(1 for _ in top.each_inst()),
        "side_p_direct_instances": sum(1 for _ in p_side.each_inst()),
        "side_n_direct_instances": sum(1 for _ in n_side.each_inst()),
        "top_direct_shapes_and_texts": direct_shapes,
        "planned_marker_labels": sorted(label for label in text_labels if label.startswith("PLAN_")),
        "cell_count": len(cells),
        "cells": cells,
    }
    SUMMARY.write_text(json.dumps(report, indent=2) + "\n")

    view = pya.LayoutView()
    view.load_layout(str(GDS))
    view.max_hier()
    view.add_missing_layers()
    view.zoom_fit()
    view.save_image(str(PNG), 2400, 1000)
    view.zoom_box(pya.DBox(390.0, 0.0, 425.0, 180.0))
    view.save_image(str(PIN_PNG), 900, 1600)
    if any(not path.exists() or path.stat().st_size == 0 for path in (PNG, PIN_PNG)):
        raise RuntimeError("KLayout did not produce both non-empty PNG renders")
    print(json.dumps({"status": "KLAYOUT_READBACK_PASS", **report}, indent=2))


if __name__ == "__main__":
    main()
