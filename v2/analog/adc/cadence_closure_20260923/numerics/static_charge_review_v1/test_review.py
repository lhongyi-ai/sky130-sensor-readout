"""Focused tests of real-schema adaptations and signed derivative semantics."""
import tempfile
import unittest
from pathlib import Path
from read_actual_dc import read_dc
from analyze_branches import fit, shared
from metadata_review import parse_struct, RUNS


def psf(value_rows):
    return '\n'.join([
        'HEADER', '"reltol" 1e-6', 'TYPE', '"sweep" FLOAT DOUBLE',
        'SWEEP', '"VDELTA" "sweep" PROP(', '"sweep_direction" 0',
        '"plot" 0', '"grid" 1', ')', 'TRACE', '"q" "Coul"',
        'VALUE', value_rows, 'END', '',
    ])


class ReviewTests(unittest.TestCase):
    def read_text(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'example.dc'
            p.write_text(text)
            return read_dc(p)

    def test_sweep_properties_are_not_additional_axes(self):
        h, axis, schema, rows = self.read_text(psf('"VDELTA" 1e-6\n"q" -2e-14\n"VDELTA" 0\n"q" -1e-14'))
        self.assertEqual(axis, 'VDELTA')
        self.assertEqual([r[axis] for r in rows], [1e-6, 0])
        self.assertEqual(h['reltol'], 1e-6)
        self.assertEqual(schema, {'q': 'Coul'})

    def test_duplicate_observable_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicatedactualsignal'):
            self.read_text(psf('"VDELTA" 0\n"q" 1\n"q" 2\n"VDELTA" 1\n"q" 3'))

    def test_missing_observable_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'IncompleteDCrow'):
            self.read_text(psf('"VDELTA" 0\n"VDELTA" 1\n"q" 3'))

    def test_signed_one_sided_fit_does_not_flip_pmos(self):
        rows = []
        for i in range(-5, 6):
            x = i * 1e-6
            q = -4e-14 + (-14e-15 if i < 0 else -9e-15) * x
            rows.append({'external_D_minus_S_V': x, 'q': q, 'reversed': int(i >= 0)})
        left = fit(rows, 'q', 1e-6, 5e-6, -1)
        right = fit(rows, 'q', 1e-6, 5e-6, 1)
        self.assertAlmostEqual(left['slope_dQ_dExternalD_F'] / -14e-15, 1, places=8)
        self.assertAlmostEqual(right['slope_dQ_dExternalD_F'] / -9e-15, 1, places=8)
        self.assertLess(abs(left['extrapolated_Q_at_0_C'] - right['extrapolated_Q_at_0_C']), 1e-27)

    def test_actual_metadata_sentinels_not_reported_as_options(self):
        fields = parse_struct(RUNS['strict'] / 'input.raw/element.info', ['w', 'l', 'rbodymod', 'rbpb'])
        self.assertEqual(fields['model_attribute'], 'XTEST.sky130_fd_pr__pfet_01v8__model.8')
        self.assertEqual(fields['fields']['w']['value'], 32e-6)
        self.assertIsNone(fields['fields']['rbodymod']['value'])
        self.assertEqual(fields['fields']['rbodymod']['status'], 'INTEGER_SENTINEL_NOT_AN_EFFECTIVE_VALUE')
        self.assertIsNone(fields['fields']['rbpb']['value'])


if __name__ == '__main__':
    unittest.main()
