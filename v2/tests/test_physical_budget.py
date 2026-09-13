import math
import unittest
import numpy as np
from sensor_readout.physical_budget import (resistor_output_psd, sampled_one_pole_psd,
                                          one_pole_noise, make_physical_budget, K_B)


class PhysicalBudgetTests(unittest.TestCase):
    def test_resistor_network_not_signal_gain_noise_gain(self):
        actual = resistor_output_psd(4, 10000)
        self.assertAlmostEqual(actual / (8*K_B*300.15*(40000**2/10000+40000)), 1)

    def test_alias_total_preserves_noise(self):
        f = np.linspace(0, 50000, 100001)
        for pole in (1000, 25000, 600000):
            total = np.trapezoid(sampled_one_pole_psd(f, 1, pole, 100000), f)
            self.assertAlmostEqual(total / (math.pi*pole/2), 1, places=8)

    def test_closed_form_matches_explicit_alias_sum(self):
        f = np.array([0, 1000, 5000, 45000, 50000])
        terms = np.arange(-100000, 100001)
        direct = np.sum(1/(1+((f[:, None]+terms*100000)/25000)**2), axis=1)
        closed = sampled_one_pole_psd(f, 1, 25000, 100000)
        np.testing.assert_allclose(closed, direct, rtol=3e-6)

    def test_aliasing_adds_inband_noise(self):
        result = one_pole_noise(1e-16, 600000, 100000)
        self.assertGreater(result["signal_band_variance_alias_multiplier"], 18)
        self.assertLess(result["signal_band_sampled_rms_v"], result["full_nyquist_sampled_rms_v"])

    def test_invalid_inputs(self):
        for gain, resistance in ((0, 100), (1, 0), (float("nan"), 100)):
            with self.assertRaises(ValueError):
                resistor_output_psd(gain, resistance)
        with self.assertRaises(ValueError):
            sampled_one_pole_psd([51000], 1, 1000, 100000)

    def test_mim_model_and_high_gain_warning(self):
        budget = make_physical_budget()
        self.assertAlmostEqual(budget["mim"]["combined_model_nominal_unit_f"] / 19.845e-15, 1)
        large = budget["resistor_noise_cases"][-1]
        self.assertEqual(large["gain"], 16)
        self.assertFalse(large["resistor_noise_alone_fits_total_sndr_allowance"])
        self.assertEqual(large["noise_gain"], 17)
