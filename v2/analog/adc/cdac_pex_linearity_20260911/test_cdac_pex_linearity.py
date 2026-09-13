#!/usr/bin/env python3
"""Regression tests for the passive-CDAC static PEX analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze  # noqa: E402


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnalyticalKernelTests(unittest.TestCase):
    def test_spice_suffix_parser(self) -> None:
        self.assertEqual(analyze.parse_spice_number("0"), 0.0)
        self.assertAlmostEqual(analyze.parse_spice_number("0.64998p"), 0.64998e-12, places=24)
        self.assertAlmostEqual(analyze.parse_spice_number("20f"), 20e-15, places=27)
        self.assertEqual(analyze.parse_spice_number("1meg"), 1e6)

    def test_small_ideal_binary_matrix_and_sign(self) -> None:
        # Fourteen capacitors are sufficient to test a 12-bit binary ratio:
        # aggregate B11..B0 plus one fixed dummy.  The 3 ohm TOP split checks
        # resistor contraction without creating a large physical fixture.
        lines = [
            ".subckt ideal TOP B11 B10 B9 B8 B7 B6 B5 B4 B3 B2 B1 B0 DUMMY EDGE_BIAS",
            "Rtop TOP top_internal 3",
        ]
        for bit in range(12):
            lines.append(f"C{bit} top_internal B{bit} {1 << bit}f")
        lines.extend(["Cd top_internal DUMMY 1f", "Ce top_internal EDGE_BIAS 1f", ".ends", ""])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ideal.spice"
            path.write_text("\n".join(lines))
            network = analyze.parse_pex(path, intrinsic_unit_f=19.845e-15)

        self.assertEqual(network.resistor_count, 1)
        self.assertEqual(network.component_count, 16)  # 15 ports plus VSUBS
        self.assertFalse(network.orphan_components)
        self.assertFalse(network.port_collisions)
        incident = network.incident("TOP")
        total = sum(value.total_f for value in incident.values())
        weights = [incident[f"B{bit}"].total_f / total for bit in range(12)]
        values = analyze.code_values_from_weights(weights)
        metrics = analyze.endpoint_metrics(values)
        self.assertAlmostEqual(values[1] - values[0], 1 / 4097, places=15)
        self.assertAlmostEqual(metrics["max_abs_inl_lsb"], 0.0, places=12)
        self.assertAlmostEqual(metrics["min_dnl_lsb"], 0.0, places=12)
        self.assertAlmostEqual(metrics["max_dnl_lsb"], 0.0, places=12)
        self.assertTrue(metrics["monotonic"])
        self.assertTrue(metrics["missing_code_free_condition"])

    def test_underweight_b4_has_the_expected_negative_carry(self) -> None:
        weights = [1.0, 2.0, 4.0, 8.0, 12.0, *[float(1 << bit) for bit in range(5, 12)]]
        metrics = analyze.endpoint_metrics(analyze.code_values_from_weights(weights))
        self.assertLess(metrics["steps"][15], 0)
        self.assertLess(metrics["dnl"][15], -1)
        self.assertFalse(metrics["monotonic"])


class FrozenResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report_path = HERE / "qualification.json"
        cls.report = json.loads(cls.report_path.read_text())

    def test_analysis_is_valid_but_linearity_fails(self) -> None:
        self.assertEqual(self.report["status"], "CDAC_PEX_STATIC_LINEARITY_FAIL_NONMONOTONIC")
        self.assertTrue(self.report["analysis_valid"])
        self.assertFalse(self.report["linearity_pass"])
        self.assertFalse(self.report["complete_adc_qualified"])

    def test_every_real_port_and_all_codes_are_present(self) -> None:
        top = self.report["inputs"]["differential_top"]
        self.assertEqual(top["port_count"], 30)
        self.assertEqual(top["ports"], analyze.EXPECTED_TOP_PORTS)
        self.assertEqual(top["mim_device_count"], 8712)
        self.assertEqual(top["resistor_count"], 26210)
        self.assertEqual(top["orphan_component_count"], 0)
        self.assertEqual(top["port_collisions"], [])
        with (HERE / "results" / "all_4096_codes.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 4096)
        self.assertEqual(int(rows[0]["code"]), 0)
        self.assertEqual(int(rows[-1]["code"]), 4095)

    def test_all_capacitance_suffixes_are_parsed(self) -> None:
        top = self.report["inputs"]["differential_top"]
        self.assertEqual(top["extracted_cap_element_count_including_zero"], 17732)
        self.assertEqual(top["positive_extracted_cap_element_count"], 17730)
        self.assertEqual(top["zero_extracted_cap_element_count"], 2)
        self.assertEqual(top["extracted_cap_suffix_counts"], {"f": 17710, "none": 2, "p": 20})

    def test_standalone_sides_bind_the_top_result(self) -> None:
        match = self.report["cross_checks"]["standalone_side_vs_top"]
        self.assertTrue(match["P"]["all_code_driving_top_couplings_exact"])
        self.assertTrue(match["N"]["all_code_driving_top_couplings_exact"])
        self.assertLess(abs(match["P"]["top_total_difference_fF"]), 0.001)
        self.assertLess(abs(match["N"]["top_total_difference_fF"]), 0.001)

    def test_nonmonotonic_result_is_not_relabelled_as_adc_pass(self) -> None:
        result = self.report["results"]["differential"]
        self.assertAlmostEqual(result["min_dnl_lsb"], -3.8544717192719062, places=10)
        self.assertAlmostEqual(result["max_abs_inl_lsb"], 3.562071027099576, places=10)
        self.assertEqual(result["nonpositive_transition_count"], 255)
        self.assertEqual(result["dnl_le_minus_one_count"], 255)
        self.assertEqual(result["worst_min_dnl_transition"], 2047)
        self.assertFalse(result["monotonic"])
        self.assertFalse(result["missing_code_free_condition"])

    def test_csv_matrix_is_symmetric(self) -> None:
        path = HERE / "results" / "port_capacitance_matrix_fF.csv"
        with path.open(newline="") as handle:
            rows = list(csv.reader(handle))
        labels = rows[0][1:]
        matrix = {row[0]: [float(value) for value in row[1:]] for row in rows[1:]}
        self.assertEqual(set(labels), set(matrix))
        for i, left in enumerate(labels):
            self.assertEqual(matrix[left][i], 0.0)
            for j, right in enumerate(labels):
                self.assertAlmostEqual(matrix[left][j], matrix[right][i], places=9)

    def test_artifact_hashes_and_png_dimensions(self) -> None:
        for relative, metadata in self.report["artifacts"].items():
            path = HERE / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(file_sha256(path), metadata["sha256"], relative)
            self.assertEqual(path.stat().st_size, metadata["bytes"], relative)
        for name in ("static_linearity.png", "bit_weight_error.png"):
            data = (HERE / "results" / name).read_bytes()[:24]
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            width, height = struct.unpack(">II", data[16:24])
            self.assertGreaterEqual(width, 1500)
            self.assertGreaterEqual(height, 800)

    def test_input_and_source_hashes_bind_the_result(self) -> None:
        for key in ("differential_top", "standalone_p", "standalone_n"):
            metadata = self.report["inputs"][key]
            path = analyze.V2 / metadata["file"]
            self.assertEqual(file_sha256(path), metadata["sha256"], key)
        route_metadata = self.report["inputs"]["route_qualification"]
        self.assertEqual(
            file_sha256(analyze.V2 / route_metadata["file"]),
            route_metadata["sha256"],
        )
        self.assertEqual(file_sha256(Path(analyze.__file__)), self.report["source"]["sha256"])
        self.assertEqual(file_sha256(Path(__file__)), self.report["source"]["test_sha256"])


if __name__ == "__main__":
    unittest.main()
