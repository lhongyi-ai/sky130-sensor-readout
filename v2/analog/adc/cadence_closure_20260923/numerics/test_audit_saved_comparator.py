import unittest
import numpy as np
from audit_saved_comparator import absolute_compare


class AbsoluteTimeTests(unittest.TestCase):
    def test_distinct_grids_same_linear_wave(self):
        t = np.array([0., .1, .9, 1.])
        u = np.array([0., .3, .5, 1.])
        _, d, _ = absolute_compare(t, 3*t+2, u, 3*u+2)
        self.assertLess(np.max(abs(d)), 1e-14)

    def test_narrow_peak_is_not_dropped_by_common_coarse_grid(self):
        t = np.array([0., .5, .500001, .500002, 1.])
        u = np.array([0., .5, 1.])
        g, d, i = absolute_compare(t, np.array([0., 0., 1., 0., 0.]), u, np.zeros(3))
        self.assertEqual(g[i], .500001)
        self.assertEqual(abs(d[i]), 1.)

    def test_edge_shift_remains_a_voltage_difference(self):
        t = np.array([0., .5, .6, 1.])
        u = np.array([0., .51, .61, 1.])
        _, d, _ = absolute_compare(t, np.array([0., 0., 1., 1.]), u, np.array([0., 0., 1., 1.]))
        self.assertAlmostEqual(np.max(abs(d)), .1)

    def test_no_silent_extrapolation(self):
        with self.assertRaises(ValueError):
            absolute_compare(np.array([0., 1.]), np.zeros(2), np.array([0., .9]), np.zeros(2))


if __name__ == "__main__":
    unittest.main()
