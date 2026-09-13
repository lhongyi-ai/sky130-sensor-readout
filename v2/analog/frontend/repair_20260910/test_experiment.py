"""Topology-generator safety tests, not analog performance tests."""
import unittest

from experiment import BASE, candidate, replace_once


class CandidateSafety(unittest.TestCase):
    def setUp(self):
        self.source = BASE.read_text()

    def test_baseline_byte_identical(self):
        self.assertEqual(candidate(self.source, 'baseline'), self.source)

    def test_reject_missing_marker(self):
        with self.assertRaises(ValueError):
            replace_once('no expected topology', 'XT TAIL', 'replacement')

    def test_reject_ambiguous_marker(self):
        with self.assertRaises(ValueError):
            replace_once('XT TAIL\nXT TAIL', 'XT TAIL', 'replacement')

    def test_reject_unknown_variant(self):
        with self.assertRaises(ValueError):
            candidate(self.source, 'unknown')

    def test_long_tail_is_physical(self):
        result = candidate(self.source, 'long_tail')
        self.assertEqual(result.count('TAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=4 W=640'), 3)
        self.assertNotIn('XT TAIL BN', result)

    def test_cascode_updates_both_pair_ports(self):
        result = candidate(self.source, 'cascoded_tail')
        self.assertIn('.subckt fdda_error_pair IP IM DP DM BN BT VSS', result)
        self.assertEqual(result.count('BN BT VSS fdda_error_pair'), 2)
        self.assertEqual(result.count('TAIL BT TS VSS sky130_fd_pr__nfet_01v8'), 2)
        self.assertIn('XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8', result)

    def test_cm_cap_variant_keeps_physical_bank(self):
        result = candidate(self.source, 'cascoded_tail_cm4p')
        self.assertIn('XCCM CMCTL VSS frontend_c4p', result)
        self.assertNotIn('XCCM CMCTL VSS frontend_c1p', result)


if __name__ == '__main__':
    unittest.main()
