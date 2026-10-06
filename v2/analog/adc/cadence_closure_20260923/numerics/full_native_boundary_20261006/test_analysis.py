"""Reject incomplete domains and preserve switching-edge discrepancies."""
import unittest
from analyze import STOP, LIMIT, compare


def rows(times, values):
    return [dict(time=t, TP_minus_TN=v, RP=1.1, RN=.7, VCM=.9) for t, v in zip(times, values)]


class AnalysisTests(unittest.TestCase):
    def test_zero_error_prefix_cannot_pass(self):
        a = rows([0., STOP], [0., 0.])
        b = rows([0., STOP / 2], [0., 0.])
        r = compare(a, b, ['TP_minus_TN', 'RP', 'RN', 'VCM'])
        self.assertFalse(r['short_numeric_control_pass'])
        self.assertFalse(r['complete_0_to_4p1us'])

    def test_edge_shift_is_not_aligned_away(self):
        a = rows([0., 1e-6, 1.001e-6, STOP], [0., 0., .1, .1])
        b = rows([0., 1.00001e-6, 1.00101e-6, STOP], [0., 0., .1, .1])
        r = compare(a, b, ['TP_minus_TN', 'RP', 'RN', 'VCM'])
        self.assertGreater(r['signals']['TP_minus_TN']['max_abs_difference_V'], LIMIT)
        self.assertFalse(r['short_numeric_control_pass'])

    def test_intermediate_accepted_point_is_preserved(self):
        a = rows([0., STOP], [0., 0.])
        b = rows([0., STOP / 2, STOP], [0., 2 * LIMIT, 0.])
        r = compare(a, b, ['TP_minus_TN', 'RP', 'RN', 'VCM'])
        self.assertEqual(r['union_points'], 3)
        self.assertFalse(r['short_numeric_control_pass'])


if __name__ == '__main__':
    unittest.main()
