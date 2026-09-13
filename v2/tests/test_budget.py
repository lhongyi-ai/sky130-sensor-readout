import json
from pathlib import Path
import unittest

from sensor_readout.budget import calculate_budget


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).parents[1] / "config/spec.json").read_text())
        self.budget = calculate_budget(self.config)

    def test_locked_time_and_resolution(self):
        self.assertAlmostEqual(self.budget["lsb_v"], 195.3125e-6)
        self.assertAlmostEqual(self.budget["settling_error_limit_v"], 48.828125e-6)
        self.assertAlmostEqual(self.budget["acquisition_time_s"], 2.5e-6)
        self.assertAlmostEqual(self.budget["frame_time_s"], 1e-5)

    def test_budget_truth_and_units(self):
        self.assertEqual(self.budget["evidence_level"], "ANALYTICAL_BUDGET_ONLY")
        self.assertAlmostEqual(self.budget["candidate_cdac_total_per_side_f"], 81.92e-12)
        self.assertGreater(self.budget["minimum_cap_per_side_from_ktc_only_f"], 0)
        self.assertLess(self.budget["candidate_differential_ktc_v_rms"], 35e-6)

    def test_noise_failure_not_hidden(self):
        self.config["illustrative_budget_scenario"]["frontend"]["noise_input_rms_v"] = 100e-6
        stressed = calculate_budget(self.config)
        self.assertFalse(stressed["gains"][-1]["allocation_fits"])
        self.assertLess(stressed["gains"][-1]["rms_margin_v"], 0)


if __name__ == "__main__":
    unittest.main()
