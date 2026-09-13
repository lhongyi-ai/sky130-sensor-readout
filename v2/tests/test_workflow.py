import csv
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scripts.run_behavioral import ROOT, run, validate_config
from sensor_readout.analysis import apply_calibration


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="readout-workflow-test-")
        cls.output = Path(cls.temporary.name)
        cls.summary = run(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_truth_boundary_and_negative_controls(self):
        self.assertFalse(self.summary["physical_chip_qualified"])
        self.assertFalse(self.summary["pvt_verified"])
        self.assertFalse(self.summary["mismatch_verified"])
        self.assertEqual(self.summary["m2_gate"], "PARTIAL_PDK_FEASIBILITY_NOT_VERIFIED")
        self.assertTrue(all(self.summary["regression_assertions"].values()))

    def test_matrix_is_definition_not_fake_corner_results(self):
        with (self.output / "qualification_matrix.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 135)
        self.assertEqual(len({(r["corner"], r["vdd_v"], r["temperature_c"]) for r in rows}), 45)
        self.assertTrue(all(r["status"].startswith("NOT_RUN") for r in rows))

    def test_saved_calibration_reapplies_to_raw_samples(self):
        calibrations = json.loads((self.output / "calibration_coefficients.json").read_text())
        with (self.output / "tone_samples.csv").open() as stream:
            reader = csv.DictReader(stream)
            rows = [next(reader) for _ in range(128)]
        raw = np.array([int(r["raw_code"]) for r in rows])
        stored = np.array([float(r["corrected_code_float"]) for r in rows])
        np.testing.assert_array_equal(apply_calibration(raw, calibrations[rows[0]["gain"]]), stored)

    def test_holdout_points_are_independent(self):
        with (self.output / "calibration_holdout.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            fraction = float(row["sensor_input_v"]) * int(row["gain"]) / 0.4
            self.assertFalse(any(abs(fraction - c) < 1e-12 for c in [-0.8, 0.0, 0.8]))

    def test_configuration_rejects_shortcuts(self):
        config = json.loads((ROOT / "config/spec.json").read_text())
        config["analysis"]["calibration_input_fractions"] = [-0.5, 0, 0.5]
        with self.assertRaises(ValueError):
            validate_config(config)
        config["analysis"]["calibration_input_fractions"] = [-0.8, 0, 0.8]
        config["analysis"]["fft_samples"] = 1024
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_approved_limits_and_timing_cannot_silently_change(self):
        original = json.loads((ROOT / "config/spec.json").read_text())
        changes = [("spec", "full_scale_vpp", 1.6), ("spec", "master_clock_hz", 1e6),
                   ("qualification", "nominal_sndr_db", 40),
                   ("qualification", "process_corners", ["TT"]),
                   ("analysis", "tone_targets_hz", [10, 100]),
                   ("analysis", "amplitude_dbfs", -20)]
        for section, key, value in changes:
            config = copy.deepcopy(original)
            config[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(config)

    def test_outputs_are_reproducible(self):
        first = json.loads((self.output / "behavioral_manifest.json").read_text())
        with tempfile.TemporaryDirectory(prefix="readout-repeat-test-") as temporary:
            run(Path(temporary))
            repeated = json.loads((Path(temporary) / "behavioral_manifest.json").read_text())
        self.assertEqual(first["source_sha256"], repeated["source_sha256"])
        self.assertEqual(first["output_sha256"], repeated["output_sha256"])


if __name__ == "__main__":
    unittest.main()
