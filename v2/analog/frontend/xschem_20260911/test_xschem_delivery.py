#!/usr/bin/env python3
"""Evidence tests for the Xschem review hierarchy."""

from __future__ import annotations

import hashlib
import json
import struct
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "artifact_manifest.json").read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"Not a PNG: {path}")
    return struct.unpack(">II", data[16:24])


class XschemDeliveryTests(unittest.TestCase):
    def test_manifest_is_honest_and_integral(self) -> None:
        self.assertTrue(MANIFEST["integrity_pass"])
        self.assertFalse(MANIFEST["scope"]["cadence_native"])
        self.assertFalse(MANIFEST["scope"]["signoff_schematic"])
        truth = MANIFEST["frozen_candidate_truth"]
        self.assertTrue(truth["all_three_static_pass"])
        self.assertTrue(truth["all_three_dynamic_pass"])
        self.assertTrue(truth["all_three_power_pass"])
        self.assertTrue(truth["all_three_device_region_pass"])
        self.assertTrue(truth["external_vcm_endpoint_tracking_pass"])
        self.assertTrue(truth["physical_parameter_audit_pass"])
        self.assertFalse(truth["formal_multiloop_stability_pass"])
        self.assertFalse(truth["pvt_45_run"])
        self.assertFalse(truth["noise_qualified"])
        self.assertFalse(truth["layout_drc_lvs_pex_complete"])

    def test_candidate_hash_is_still_pinned(self) -> None:
        sources = MANIFEST["authoritative_sources"]
        candidate = (HERE / sources["candidate_path_from_this_directory"]).resolve()
        local_q = HERE / sources["local_visual_qualification_path"]
        self.assertEqual(sha256(candidate), sources["candidate_sha256"])
        self.assertEqual(sha256(local_q), sources["local_visual_qualification_sha256"])
        self.assertTrue(sources["hash_matches_source_qualification"])
        self.assertTrue(sources["hash_matches_local_qualification"])
        self.assertEqual(
            sources["candidate_sha256"],
            "a4ed567d6a5b1f8853124602fd3f0503118e77c751a6fc3152f772b89483a5f1",
        )

    def test_ports_and_candidate_structure_match(self) -> None:
        self.assertTrue(all(item["pass"] for item in MANIFEST["port_audit"].values()))
        self.assertTrue(all(MANIFEST["structural_token_audit"].values()))

    def test_hierarchy_pages_describe_frozen_candidate(self) -> None:
        pages = {item["page"] for item in MANIFEST["hierarchy"]}
        self.assertEqual(pages, {"frontend_top.sch", "sky130_v2_switchable_pga.sch", "rd_fdota.sch"})
        for page in pages:
            self.assertGreater((HERE / page).stat().st_size, 1000)

        top = (HERE / "frontend_top.sch").read_text(encoding="utf-8")
        pga = (HERE / "sky130_v2_switchable_pga.sch").read_text(encoding="utf-8")
        ota = (HERE / "rd_fdota.sch").read_text(encoding="utf-8")
        self.assertIn("DETAIL PAGE: sky130_v2_switchable_pga.sch", top)
        self.assertIn("VERIFIED ASSEMBLY: 1.5 kohm / side", top)
        self.assertIn("SUBCIRCUIT DEFAULT: 1.8 kohm", top)
        self.assertIn("4096 SKY130 MIM units per side", top)
        self.assertIn("candidate_06.spice", top)

        for value in ("RFB = 10.35 kohm", "RFB = 41.4 kohm", "RFB = 165.6 kohm"):
            self.assertEqual(pga.count(value), 2)
        self.assertIn("DETAIL PAGE: rd_fdota.sch", pga)
        self.assertIn("All three real-load dynamic modes pass.", pga)
        self.assertIn("Formal multiloop stability is not closed.", pga)

        for device in ("XMIP", "XMIN", "XMTAIL", "XMSP", "XMSN", "XMOP", "XMON"):
            self.assertIn(device, ota)
        self.assertIn("PFET W/L = 64/1 um", ota)
        self.assertIn("NFET W/L = 9/1 um", ota)
        self.assertIn("XCCP 8 MIM units", ota)
        self.assertIn("NCM directly drives XMLP / XMLN gates.", ota)
        self.assertIn("CMG drives the 9/1 output sinks", ota)
        self.assertIn("FORMAL MULTILOOP STABILITY: NOT CLOSED", ota)

    def test_render_labels_are_ascii_and_symbols_resolve(self) -> None:
        for path in sorted(HERE.glob("*.sch")) + sorted(HERE.glob("*.sym")):
            path.read_text(encoding="ascii")
        for svg in sorted((HERE / "renders").glob("*.svg")):
            content = svg.read_text(encoding="utf-8")
            self.assertNotIn("MISSING SYMBOL", content)
            self.assertNotIn("\ufffd", content)

    def test_png_and_svg_renders_are_real(self) -> None:
        expected = {"frontend_top", "switchable_pga", "rd_fdota"}
        self.assertEqual({p.stem for p in (HERE / "renders").glob("*.png")}, expected)
        self.assertEqual({p.stem for p in (HERE / "renders").glob("*.svg")}, expected)
        for stem in expected:
            png = HERE / "renders" / f"{stem}.png"
            svg = HERE / "renders" / f"{stem}.svg"
            self.assertEqual(png_dimensions(png), (2400, 1600))
            self.assertGreater(png.stat().st_size, 50_000)
            self.assertGreater(svg.stat().st_size, 10_000)
            ET.parse(svg)

    def test_recorded_manual_visual_audit_passes(self) -> None:
        audit = MANIFEST["rendering"]["visual_no_overlap_audit"]
        self.assertIn("Manual visual inspection", audit["method"])
        self.assertFalse(audit["algorithmic_proof"])
        self.assertTrue(audit["all_pages_pass"])
        self.assertEqual(
            set(audit["pages"]),
            {"frontend_top.png", "switchable_pga.png", "rd_fdota.png"},
        )
        for page in audit["pages"].values():
            self.assertFalse(page["text_vs_text_overlap"])
            self.assertFalse(page["text_vs_wire_overlap"])
            self.assertFalse(page["text_vs_device_overlap"])
            self.assertFalse(page["text_vs_border_overlap"])
            self.assertTrue(page["module_spacing_clear"])
            self.assertFalse(page["missing_symbol_or_garbled_glyph"])

    def test_manifest_artifact_hashes(self) -> None:
        for item in MANIFEST["artifacts"]:
            path = HERE / item["path"]
            self.assertTrue(path.is_file(), item["path"])
            self.assertEqual(path.stat().st_size, item["bytes"], item["path"])
            self.assertEqual(sha256(path), item["sha256"], item["path"])

    def test_temporary_crash_dump_is_absent_and_incident_recorded(self) -> None:
        self.assertFalse((HERE / "core").exists())
        self.assertFalse(any(HERE.glob("core.*")))
        incident = MANIFEST["rendering"]["incident"]
        self.assertTrue(incident["occurred"])
        self.assertFalse(incident["affects_final_artifacts"])


if __name__ == "__main__":
    unittest.main()
