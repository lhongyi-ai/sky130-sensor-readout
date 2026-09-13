import unittest

import numpy as np

import timestep_convergence as tc


class TimestepTests(unittest.TestCase):
    def test_only_maxstep_and_observations_change(self):
        original = "title\n.options reltol=1e-5\nVclk clk 0 PULSE(0 1.8 1u 1n 1n 311.5n 625n)\n.save v(valid)\ntran 2n 62u 0 2n\nwrdata waveform.dat v(valid)\n"
        result = tc.instrument(original, 10)
        self.assertIn("tran 2n 62u 0 10n", result)
        self.assertIn(".options reltol=1e-5", result)
        self.assertIn("1u 1n 1n 311.5n 625n", result)
        self.assertEqual(result.count("v(xadc.tp)"), 2)
        with self.assertRaises(ValueError):
            tc.instrument(original, 20)
        with self.assertRaises(ValueError):
            tc.instrument(original.replace("62u", "60u"), 10)

    def test_crossings_are_interpolated(self):
        times = np.asarray([0, 1e-9, 2e-9, 3e-9])
        values = np.asarray([0, 0, 1.8, 1.8])
        np.testing.assert_allclose(tc.crossings(times, values, .9), [1.5e-9])

    def test_step_units_are_nanoseconds(self):
        values = np.zeros((4, 30))
        values[:, 0] = [0, 1e-12, 11e-12, 2.011e-9]
        result = tc.time_step_statistics(values)
        self.assertAlmostEqual(result["dt_ns_percentiles"]["min"], .001)
        self.assertAlmostEqual(result["dt_ns_percentiles"]["p50"], .01)
        self.assertAlmostEqual(result["dt_ns_percentiles"]["max"], 2)


if __name__ == "__main__":
    unittest.main()
