#!/usr/bin/env python3
"""Regression checks for the placement-only CDAC floorplan evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import struct
import unittest


HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
SOURCE = HERE.parent / "cdac"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not PNG")
    return struct.unpack(">II", data[16:24])


class FloorplanEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads((HERE / "qualification.json").read_text())
        cls.klayout = json.loads((ARTIFACTS / "klayout_summary.json").read_text())

    def test_final_status_and_truthful_scope(self) -> None:
        self.assertEqual(self.report["status"], "SKY130_CDAC_PLACEMENT_FLOORPLAN_PASS")
        self.assertTrue(all(self.report["checks"].values()))
        self.assertFalse(self.report["cadence_qualified"])
        self.assertFalse(self.report["final_cdac_layout"])
        self.assertFalse(self.report["completion"]["routing"])
        self.assertFalse(self.report["completion"]["lvs"])
        self.assertFalse(self.report["completion"]["pex"])
        self.assertFalse(self.report["completion"]["post_layout_performance"])

    def test_assignment_binding_and_coordinates(self) -> None:
        source = {}
        for polarity in ("P", "N"):
            with (SOURCE / f"cdac_{polarity.lower()}_assignment.csv").open(newline="") as handle:
                for row in csv.DictReader(handle):
                    key = (polarity, int(row["physical_row"]), int(row["physical_col"]))
                    source[key] = (row["net"], row["electrical"])
        with (ARTIFACTS / "placement_index.csv").open(newline="") as handle:
            placed = list(csv.DictReader(handle))
        self.assertEqual(len(placed), 8712)
        self.assertEqual(len(source), 8712)
        names = set()
        for row in placed:
            key = (row["polarity"], int(row["physical_row"]), int(row["physical_col"]))
            self.assertEqual((row["net"], row["electrical"]), source[key])
            self.assertAlmostEqual(float(row["local_x_um"]), key[2] * 6.0, places=9)
            self.assertAlmostEqual(float(row["local_y_um"]), key[1] * 4.54, places=9)
            names.add(row["instance"])
        self.assertEqual(len(names), 8712)

    def test_magic_hierarchy_and_labels(self) -> None:
        for polarity in ("p", "n"):
            mag = (ARTIFACTS / f"cdac_side_{polarity}.mag").read_text()
            self.assertEqual(sum(line.startswith("use mim_unit ") for line in mag.splitlines()), 4356)
        top = (ARTIFACTS / "cdac_diff_floorplan.mag").read_text().splitlines()
        self.assertEqual(sum(line.startswith("use cdac_side_") for line in top), 2)
        self.assertEqual(sum(" PLAN_" in line and line.startswith("rlabel metal5") for line in top), 28)

    def test_klayout_readback(self) -> None:
        self.assertEqual(self.klayout["top_direct_instances"], 2)
        self.assertEqual(self.klayout["side_p_direct_instances"], 4356)
        self.assertEqual(self.klayout["side_n_direct_instances"], 4356)
        self.assertEqual(len(self.klayout["planned_marker_labels"]), 28)
        self.assertEqual(self.klayout["top_bbox_um"], [-2.43, -1.7, 817.29, 296.8])

    def test_pitch_boundary(self) -> None:
        pitch = self.report["pitch_qualification"]
        self.assertEqual(pitch["minimum_safe_tested_pitch_um"], {"x": 6.0, "y": 4.54})
        self.assertFalse(pitch["boundary_observations"]["x_5p99"]["safe"])
        self.assertTrue(pitch["boundary_observations"]["x_6p00"]["safe"])
        self.assertFalse(pitch["boundary_observations"]["y_4p53"]["safe"])
        self.assertTrue(pitch["boundary_observations"]["y_4p54"]["safe"])

    def test_artifact_hashes(self) -> None:
        for name, expected in self.report["artifact_sha256"].items():
            self.assertEqual(sha256(ARTIFACTS / name), expected, name)

    def test_render_dimensions(self) -> None:
        self.assertEqual(png_dimensions(ARTIFACTS / "cdac_diff_floorplan.png"), (2400, 1000))
        self.assertEqual(png_dimensions(ARTIFACTS / "cdac_pin_corridor.png"), (900, 1600))


if __name__ == "__main__":
    unittest.main(verbosity=2)
