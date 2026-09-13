import unittest
from analyze import parse_poles,classify


class PoleAuditTests(unittest.TestCase):
    def test_signed_exponents(self):
        self.assertEqual(parse_poles('pole(1) = -1.23e+07,1e-08')[0],
            {'index':1,'real_per_s':-1.23e7,'imag_rad_per_s':1e-8})

    def test_nonfinite_progress_detected(self):
        self.assertTrue(classify('Reference value : nan')['nonfinite_progress_value_seen'])

    def test_reported_rhp_not_certified(self):
        result=classify('pole(1) = 100,0\nngspice-47 done')
        self.assertEqual(result['reported_rhp_count'],1)
        self.assertFalse(result['roots_residual_validated'])

    def test_lhp_only_not_stability_proof(self):
        self.assertFalse(classify('pole(1) = -100,0')['complete_stability_qualified'])

    def test_empty_does_not_pass(self):
        self.assertFalse(classify('')['complete_stability_qualified'])


if __name__=='__main__':unittest.main()
