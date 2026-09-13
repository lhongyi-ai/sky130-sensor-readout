from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DynamicClosureEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.q = json.loads((HERE / "qualification.json").read_text())

    def test_bounded_real_diagnostic_inventory(self) -> None:
        self.assertEqual(self.q["bounded_real_ngspice_diagnostics_used"], 8)
        self.assertEqual(self.q["bounded_real_ngspice_diagnostics_limit"], 8)
        folders = [path for path in (HERE / "diagnostics").iterdir() if path.is_dir()]
        self.assertEqual(len(folders), 8)
        self.assertEqual([item["ordinal"] for item in self.q["diagnostic_inventory"]], list(range(1, 9)))

    def test_selected_frozen_manifests(self) -> None:
        for key in ("selected_dynamic_evidence", "selected_loop_evidence"):
            folder = HERE / self.q[key]
            manifest = json.loads((folder / "evidence_manifest.json").read_text())
            for name, expected in manifest["files"].items():
                path = folder / name
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, expected["size_bytes"])
                self.assertEqual(digest(path), expected["sha256"])

    def test_same_source_nominal_dynamic_gates(self) -> None:
        self.assertEqual(digest(HERE / self.q["candidate_path"]), self.q["candidate_sha256"])
        self.assertTrue(self.q["nominal_dynamic_prerequisites_pass"])
        self.assertTrue(all(self.q["nominal_dynamic_gates"].values()))
        for result in self.q["gains"].values():
            self.assertLessEqual(result["max_acquisition_error_v"], 0.8 / 4096 / 4)
            self.assertLessEqual(result["max_post_aperture_error_v"], 0.8 / 4096 / 4)
            self.assertLessEqual(max(result["reference_peak_to_peak_v"]), 0.8 / 4096 / 40)

    def test_external_vcm_is_used_and_endpoints_pass(self) -> None:
        source = (HERE / "candidate_06.spice").read_text()
        self.assertIn("XCMR CMG VCM CR", source)
        self.assertTrue(self.q["nominal_dynamic_gates"]["external_vcm_reference_used"])
        self.assertEqual(set(self.q["external_vcm_endpoint_tracking"]), {"0.85", "0.95"})
        self.assertTrue(all(item["full_input_range_gate_pass"] for item in self.q["external_vcm_endpoint_tracking"].values()))

    def test_low_value_resistors_are_not_subminimum(self) -> None:
        physical = self.q["physical_device_legality"]
        self.assertTrue(physical["gate_pass"])
        self.assertGreaterEqual(physical["miller_zero_length_um"], physical["minimum_pcell_length_um"])
        self.assertGreaterEqual(physical["isolation_resistor_length_um"], physical["minimum_pcell_length_um"])

    def test_raw_loop_false_positive_is_superseded(self) -> None:
        audit = self.q["loop_audit"]
        self.assertEqual(audit["raw_run_status_superseded"], "LOOP_STABILITY_PASS")
        self.assertFalse(audit["formal_multiloop_stability_gate_pass"])
        self.assertFalse(self.q["formal_stability_gate_pass"])
        self.assertTrue(any(not modes["dm"]["high_frequency_upcrossing_absent"] for modes in audit["audited_loops"].values()))
        self.assertFalse(audit["audited_loops"]["1"]["stage1_cm"]["low_frequency_negative_feedback_sign"])
        self.assertFalse(audit["audited_loops"]["4"]["stage1_cm"]["low_frequency_negative_feedback_sign"])

    def test_pvt_and_full_frontend_not_claimed(self) -> None:
        self.assertFalse(self.q["pvt_45_screen_allowed"])
        self.assertFalse(self.q["pvt_45_screen_run"])
        self.assertFalse(self.q["noise_qualified"])
        self.assertFalse(self.q["full_frontend_qualified"])
        self.assertFalse(self.q["full_chip_qualified"])
        self.assertFalse(self.q["cadence_used"])
        self.assertFalse(self.q["layout_drc_lvs_pex_complete"])

    def test_setup_failure_is_retained_separately(self) -> None:
        self.assertTrue((HERE / self.q["setup_failure_not_counted_as_real_ngspice_run"]).is_dir())

    def test_delivery_manifest_hashes(self) -> None:
        manifest = json.loads((HERE / "delivery_manifest.json").read_text())
        for name, expected in manifest["files"].items():
            path = HERE / name
            self.assertEqual(path.stat().st_size, expected["size_bytes"])
            self.assertEqual(digest(path), expected["sha256"])


if __name__ == "__main__":
    unittest.main()
