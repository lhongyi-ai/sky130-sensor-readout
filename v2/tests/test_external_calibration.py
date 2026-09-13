import copy
import unittest
from sensor_readout.external_calibration import fit_records, apply_records, validate_records


def records(fractions=(-0.8, 0, 0.8), count=4096, vdd=1.8, temp=27, drift=0):
    rows = []
    for index, fraction in enumerate(fractions):
        code = round((fraction*0.4+0.4)/(0.8/4096)-0.5 + 3 + drift)
        rows.extend({"instance_id": "simulated_example", "sample_id": f"p{index}s{i}", "gain": 4,
            "vdd_v": vdd, "temperature_c": temp, "sensor_input_v": fraction*0.4/4,
            "raw_code": code} for i in range(count))
    return rows


class ExternalCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = fit_records(records())

    def test_nominal_and_fixed_corner_holdout(self):
        for vdd, temp in ((1.8, 27), (1.62, 85)):
            report = validate_records(records((-0.7, 0.3, 0.7), 2048, vdd, temp), self.bundle)
            self.assertEqual(report["status"], "PROVIDED_HOLDOUT_POINTS_PASS")
            self.assertFalse(report["coefficients_refitted"])
            self.assertFalse(report["chip_qualified"])

    def test_refitting_at_corner_rejected(self):
        with self.assertRaises(ValueError):
            fit_records(records(vdd=1.62))

    def test_short_training_or_clipping_rejected(self):
        with self.assertRaises(ValueError):
            fit_records(records(count=4))
        rows = records()
        rows[0]["raw_code"] = 0
        with self.assertRaises(ValueError):
            fit_records(rows)

    def test_holdout_training_points_rejected(self):
        with self.assertRaises(ValueError):
            validate_records(records(count=2048), self.bundle)

    def test_insufficient_holdout_not_passed(self):
        result = validate_records(records((0.3,), 4), self.bundle)
        self.assertEqual(result["status"], "FAIL")

    def test_drift_exposed_not_refitted(self):
        result = validate_records(records((0.3,), 2048, 1.62, 85, drift=10), self.bundle)
        self.assertEqual(result["status"], "FAIL")
        self.assertGreater(result["test_points"][0]["mean_static_residual_lsb"], 9)

    def test_unrelated_instance_and_duplicate_samples_rejected(self):
        rows = records((0.3,), 2)
        rows[0]["instance_id"] = "another_chip"
        with self.assertRaises(ValueError):
            apply_records(rows, self.bundle)
        rows = records((0.3,), 2)
        rows[1]["sample_id"] = rows[0]["sample_id"]
        with self.assertRaises(ValueError):
            apply_records(rows, self.bundle)

    def test_unknown_input_raw_and_fractional_output_preserved(self):
        rows = records((0.3,), 1)
        rows[0].pop("sensor_input_v")
        original = copy.deepcopy(rows)
        output = apply_records(rows, self.bundle)
        self.assertEqual(rows, original)
        self.assertEqual(output[0]["raw_code"], rows[0]["raw_code"])
        self.assertIsInstance(output[0]["corrected_code_float"], float)

    def test_tampered_coefficient_provenance_rejected(self):
        bundle = copy.deepcopy(self.bundle)
        bundle["coefficients"][0]["vdd_v"] = 1.62
        with self.assertRaises(ValueError):
            apply_records(records((0.3,), 1), bundle)
