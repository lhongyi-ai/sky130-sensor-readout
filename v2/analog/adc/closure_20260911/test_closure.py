"""Software and saved-evidence regression only; does not start ngspice."""
import unittest
from pathlib import Path

import numpy as np

import trace_replay as tr
from bridge_fix import correct_output_masks, handshake_certificate
from certify_trace import analog_comparison, comparator_certificate


class CompressionTests(unittest.TestCase):
    def test_linear_trace(self):
        t = np.arange(10, dtype=float)
        a, b, error = tr.compress_trace(t, 3 * t + 7)
        self.assertEqual(len(a), 2)
        self.assertEqual(error, 0)

    def test_preserve_edge(self):
        t = np.array([0, 1, 1.1, 1.3, 2, 4], dtype=float)
        v = np.array([0, 0, .7, 1.8, 1.8, 1.8])
        a, b, error = tr.compress_trace(t, v)
        self.assertLessEqual(error, 1e-10)
        self.assertLessEqual(np.max(np.abs(v - np.interp(t, a, b))), 1e-10)

    def test_duplicate_time_rejected(self):
        with self.assertRaises(ValueError):
            tr.compress_trace(np.array([0, 1, 1]), np.array([0, 0, 1]))

    def test_output_scope_does_not_force_analog(self):
        for name in ('decision', 'decision_b', 'top_sample', 'acq', 'conv', 'rp', 'rn', 'vcm'):
            self.assertNotIn(name, tr.OUTPUTS)

    def test_all_33_outputs_named(self):
        self.assertEqual(len(tr.OUTPUTS), 33)
        self.assertEqual(len(set(tr.OUTPUTS)), 33)
        self.assertEqual(tr.OUTPUTS[:2], ['ready', 'busy'])


class BridgeTests(unittest.TestCase):
    def test_two_masks_only(self):
        source = '(topp->name & (1 << i))\nINPUT 1 << i\n(topp->name & (1 << i))'
        fixed = correct_output_masks(source)
        self.assertEqual(fixed.count('uint64_t(1) << i'), 2)
        self.assertIn('INPUT 1 << i', fixed)

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            correct_output_masks('(topp->name & (1 << i))')

    def test_unsigned_64_masks_one_hot_33_bits(self):
        for hot in range(33):
            word = 1 << hot
            self.assertEqual([int(bool(word & (1 << i))) for i in range(33)],
                             [int(i == hot) for i in range(33)])


class SavedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tr.HERE / 'results/20260911T080054695882Z_live'
        cls.values = np.loadtxt(cls.directory / 'waveform.dat', skiprows=1)
        cls.words = [2677, 2677, 2047, 2047, 2048, 2048]

    def test_live_real_decisions(self):
        evidence = comparator_certificate(self.values, self.words)
        self.assertEqual(evidence['matched_decisions'], 72)
        self.assertFalse(evidence['complete_adc_qualified'])

    def test_wrong_prediction_rejected(self):
        wrong = self.words.copy()
        wrong[0] ^= 1
        evidence = comparator_certificate(self.values, wrong)
        self.assertEqual(evidence['status'], 'REJECTED_TRACE')
        self.assertIsNone(evidence['certified_codes'])

    def test_incomplete_word_list_rejected(self):
        with self.assertRaises(ValueError):
            comparator_certificate(self.values, self.words[:-1])

    def test_same_waveform_equivalent_not_full_adc(self):
        evidence = analog_comparison(self.values, self.values)
        self.assertEqual(evidence['status'], 'FINITE_TRACE_ANALOG_EQUIVALENCE_PASS')
        self.assertFalse(evidence['complete_adc_qualified'])

    def test_dac_error_above_strict_gate_fails(self):
        changed = self.values.copy()
        changed[:, 21] += .06 * tr.sc.LSB
        evidence = analog_comparison(self.values, changed)
        self.assertEqual(evidence['status'], 'FINITE_TRACE_ANALOG_EQUIVALENCE_FAIL')

    def test_old_status_ports_fail_even_with_accepted_codes(self):
        evidence = handshake_certificate(self.directory)
        self.assertEqual(evidence['status'], 'STATUS_PORTS_FAIL')
        evidence = comparator_certificate(self.values, self.words)
        self.assertEqual(evidence['matched_decisions'], 72)


if __name__ == '__main__':
    unittest.main(verbosity=2)
