#!/usr/bin/env python3
"""Regression checks for the preserved routed-CDAC evidence.

These tests are deliberately independent of the physical-tool invocation.  They
re-read the final extraction products and the frozen placement assignment so a
green status cannot be obtained from a hand-edited summary alone.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
PROBE = HERE / "probe_artifacts"
sys.path.insert(0, str(HERE))

import qualify  # noqa: E402  (the timestamped directory is not a package)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RoutedCdacEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads((HERE / "qualification.json").read_text())

    def test_qualification_is_green_without_overclaim(self) -> None:
        self.assertEqual(self.report["status"], "SKY130_CDAC_ROUTED_OPEN_PDK_PASS")
        self.assertTrue(all(self.report["checks"].values()))
        self.assertFalse(self.report["cadence_used"])
        self.assertFalse(self.report["foundry_signoff"])
        self.assertFalse(self.report["final_complete_adc_layout"])
        self.assertFalse(self.report["completion"]["post_layout_adc_performance"])
        self.assertFalse(
            self.report["completion"]["reference_switches_and_comparator_integrated"]
        )

    def test_raw_extraction_matches_frozen_assignment(self) -> None:
        for polarity in ("P", "N"):
            with self.subTest(polarity=polarity):
                actual = qualify.side_topology(
                    ARTIFACTS
                    / f"cdac_side_{polarity.lower()}_routed_flat.lvs.spice",
                    polarity,
                )
                self.assertTrue(actual["matches_original_assignment"])
                self.assertEqual(actual["mim_devices"], 4356)
                self.assertTrue(actual["all_extracted_mims_are_3um_by_3um"])
                self.assertEqual(actual["edge_dummies_extracted"], 260)
                self.assertEqual(
                    actual["active_counts_extracted"],
                    {
                        "B0": 1,
                        "B1": 2,
                        "B10": 1024,
                        "B11": 2048,
                        "B2": 4,
                        "B3": 8,
                        "B4": 16,
                        "B5": 32,
                        "B6": 64,
                        "B7": 128,
                        "B8": 256,
                        "B9": 512,
                        "DUMMY": 1,
                    },
                )

    def test_lvs_is_unique_at_tile_sides_and_top(self) -> None:
        for report in (
            PROBE / "lvs.rpt",
            ARTIFACTS / "side_p_lvs.rpt",
            ARTIFACTS / "side_n_lvs.rpt",
            ARTIFACTS / "top_lvs.rpt",
        ):
            with self.subTest(report=report.name):
                self.assertTrue(qualify.lvs_unique(report))
        self.assertEqual(self.report["lvs"]["side_port_count_each"], 15)
        self.assertEqual(self.report["lvs"]["top_port_count"], 30)

    def test_drc_is_zero_at_both_sides_and_top(self) -> None:
        self.assertEqual(
            self.report["magic_drc_counts"], {"p_side": 0, "n_side": 0, "top": 0}
        )

    def test_rc_pex_is_real_and_nonempty(self) -> None:
        rc = self.report["rc_pex"]
        self.assertEqual(rc["representative_tile"]["mim_devices"], 4)
        self.assertEqual(rc["representative_tile"]["resistor_segments"], 9)
        self.assertGreater(rc["representative_tile"]["parasitic_capacitors"], 0)
        for polarity in ("P", "N"):
            with self.subTest(polarity=polarity):
                side = rc["sides"][polarity]
                self.assertEqual(side["pin_count"], 15)
                self.assertEqual(side["mim_devices"], 4356)
                self.assertEqual(side["resistor_segments"], 13105)
                self.assertGreater(side["parasitic_capacitors"], 8000)
                self.assertTrue(side["positive_rc_network"])
        top = rc["differential_top"]
        self.assertEqual(top["pin_count"], 30)
        self.assertEqual(top["mim_devices"], 8712)
        self.assertEqual(top["resistor_segments"], 26210)
        self.assertGreater(top["parasitic_capacitors"], 17000)
        self.assertTrue(top["positive_rc_network"])
        self.assertGreater(rc["res_ext_bytes"]["probe"], 0)
        self.assertGreater(rc["res_ext_bytes"]["p_side"], 1_000_000)
        self.assertGreater(rc["res_ext_bytes"]["n_side"], 1_000_000)
        self.assertGreater(rc["res_ext_bytes"]["top"], 3_000_000)

    def test_readback_and_geometry(self) -> None:
        readback = self.report["klayout_readback"]
        self.assertEqual(readback["top_direct_instances"], 2)
        self.assertEqual(readback["p_side_direct_mim_instances"], 4356)
        self.assertEqual(readback["n_side_direct_mim_instances"], 4356)
        self.assertEqual(readback["top_port_labels"], readback["expected_port_labels"])
        self.assertEqual(len(readback["top_port_labels"]), 30)
        self.assertAlmostEqual(self.report["geometry"]["differential_top_area_mm2"], 0.377377)
        self.assertEqual(
            qualify.png_dimensions(ARTIFACTS / "cdac_diff_routed.png"), [2800, 1400]
        )
        self.assertEqual(
            qualify.png_dimensions(ARTIFACTS / "cdac_routing_detail.png"), [2400, 1500]
        )
        self.assertEqual(
            qualify.png_dimensions(ARTIFACTS / "cdac_diff_routed_display_no_labels.png"),
            [2800, 1400],
        )
        self.assertEqual(
            qualify.png_dimensions(ARTIFACTS / "cdac_routing_detail_display_no_labels.png"),
            [2400, 1500],
        )
        self.assertTrue(readback["display_render"]["source_gds_unchanged"])
        self.assertGreater(readback["display_render"]["text_shapes_removed_in_memory"], 0)

    def test_key_artifact_hashes_still_match(self) -> None:
        for relative, expected in self.report["key_artifact_sha256"].items():
            path = HERE / relative
            with self.subTest(path=relative):
                self.assertTrue(path.is_file())
                self.assertEqual(digest(path), expected)

    def test_failed_attempts_remain_auditable(self) -> None:
        failure_paths = [HERE / item["artifact"] for item in self.report["preserved_failures"]]
        self.assertGreaterEqual(len(failure_paths), 5)
        for path in failure_paths:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
