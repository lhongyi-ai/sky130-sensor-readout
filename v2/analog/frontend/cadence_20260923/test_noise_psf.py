"""Handwritten units/contribution/shape checks, no simulator or model claims."""
import unittest
import numpy as np
from parse_noise_psf import parse_noise, integrate_psd

FIXTURE = '''HEADER
TYPE
"V/sqrt(Hz)" FLOAT DOUBLE PROP(
"units" "V/sqrt(Hz)"
)
"resistor" STRUCT(
"rn" FLOAT DOUBLE PROP(
"units" "V^2/Hz"
)
"total" FLOAT DOUBLE PROP(
"units" "V^2/Hz"
)
) PROP(
"key" "inst"
)
SWEEP
"freq" "sweep"
TRACE
"R1" "resistor"
"R2" "resistor"
"out" "V/sqrt(Hz)"
VALUE
"freq" 1
"R1" (
1
1
)
"R2" (
1
1
)
"out" 1.4142135623730951
"freq" 3
"R1" (
1
1
)
"R2" (
1
1
)
"out" 1.4142135623730951
END
'''


class NoiseReaderChecks(unittest.TestCase):
    def test_asd_squared_and_totals_not_double_counted(self):
        d = parse_noise(FIXTURE)
        self.assertAlmostEqual(integrate_psd(d['frequency'],d['out_asd']**2,1,3),4)
        self.assertEqual(len(d['devices']),2)

    def test_psd_given_instead_of_asd_rejected_by_closure(self):
        with self.assertRaises(ValueError): parse_noise(FIXTURE.replace('1.4142135623730951','2'))

    def test_units_must_be_explicit(self):
        with self.assertRaises(ValueError): parse_noise(FIXTURE.replace('"units" "V^2/Hz"','"units" "A^2/Hz"'))
        with self.assertRaises(ValueError): parse_noise(FIXTURE.replace('"units" "V/sqrt(Hz)"','"units" "V^2/Hz"'))

    def test_struct_length_and_sum_checked(self):
        with self.assertRaises(ValueError): parse_noise(FIXTURE.replace('"R1" (\n1\n1\n)','"R1" (\n1\n)'))
        with self.assertRaises(ValueError): parse_noise(FIXTURE.replace('"R1" (\n1\n1\n)','"R1" (\n2\n1\n)'))

    def test_linear_psd_integral_partial_bins(self):
        self.assertAlmostEqual(integrate_psd(np.array([1.,3.]),np.array([1.,3.]),1.5,2.5),2)
        with self.assertRaises(ValueError): integrate_psd(np.array([1.,3.]),np.array([1.,3.]),.1,2)


if __name__=='__main__': unittest.main()
