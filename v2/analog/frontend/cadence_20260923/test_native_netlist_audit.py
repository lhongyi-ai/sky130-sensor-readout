"""Handwritten, independent small examples and deliberate netlisting failures.

These are parser/auditor tests, not Cadence simulations or a mock circuit pass.
"""
import unittest
from copy import deepcopy
from fractions import Fraction
from audit_native_netlist import affine, audit, scalar

MANIFEST = [
    {'name': 'N80', 'originalpath': 'OTA/INPUT', 'kind': 'mos', 'cell': 'nfet_01v8',
     'props': {'w': '80u', 'fw': '40u', 'l': '1u', 'fingers': '2', 'm': '1'},
     'source_parameters': {'W': 80}, 'nets': {'D': 'DRAIN', 'G': 'GATE', 'S': 'TAIL', 'B': '0'}},
    {'name': 'RISO', 'kind': 'resistor', 'cell': 'res_high_po_0p35',
     'props': {'segL': '.545u', 'segW': '.35u'}, 'nets': {'PLUS': 'DRAIN', 'MINUS': 'FILTER', 'B': '0'}},
    {'name': 'CBANK', 'kind': 'mim', 'cell': 'cap_mim_m3__base',
     'props': {'w': '4u', 'l': '4u', 'm': '4096'}, 'nets': {'PLUS': 'HOLD', 'MINUS': 'VCM'}},
    {'name': 'VINP', 'kind': 'testbench_source', 'cell': 'vdc',
     'props': {'dc': '0.9+SW/8', 'acm': '.125', 'acp': '0'}, 'nets': {'PLUS': 'VINP', 'MINUS': '0'}},
    {'name': 'VINN', 'kind': 'testbench_source', 'cell': 'vdc',
     'props': {'dc': '0.9-SW/8', 'acm': '.125', 'acp': '180'}, 'nets': {'PLUS': 'VINN', 'MINUS': '0'}},
    {'name': 'RLEAK', 'kind': 'testbench_resistor', 'cell': 'res',
     'props': {'r': '1G'}, 'nets': {'PLUS': 'HOLD', 'MINUS': 'VCM'}},
]
GOLDEN = '''// Handwritten format fixture, not a simulator result
N80 (DRAIN GATE TAIL 0) nfet_01v8 w=(40u) l=1000n as=10.6p ad=5.6p \\
    ps=80.53u pd=40.28u m=(1)*(2)
RISO (DRAIN FILTER 0) res_high_po_0p35 r=1.19625K l=545n w=350n
CBANK (HOLD VCM) cap_mim_m3_1 l=4u w=4u m=4096
VINP (VINP 0) vsource dc=0.9+SW/8 mag=.125 phase=0 type=dc
VINN (VINN 0) vsource dc=(.9 - .125*SW) mag=125m phase=180 type=dc
RLEAK (HOLD VCM) resistor r=1G
'''


class NativeAuditChecks(unittest.TestCase):
    def assert_fault(self, text, kind, manifest=None):
        report = audit(manifest or MANIFEST, text)
        self.assertNotEqual(report['status'], 'NATIVE_NETLIST_AUDIT_PASS')
        self.assertIn(kind, [e['kind'] for e in report['errors']])

    def test_independent_golden_with_expression_and_units(self):
        report = audit(MANIFEST, GOLDEN)
        self.assertEqual(report['status'], 'NATIVE_NETLIST_AUDIT_PASS', report['errors'])
        self.assertEqual(report['actual_count'], 6)

    def test_numeric_suffix_and_exact_affine(self):
        self.assertEqual(scalar('1G'), 1000000000)
        self.assertEqual(scalar('1m'), Fraction(1, 1000))
        self.assertEqual(scalar('1M'), 1000000)
        self.assertEqual(scalar('(1)*(4)'), 4)
        self.assertEqual(affine('.9 - SW/8'), (Fraction(9, 10), Fraction(-1, 8)))
        for value in ('sin(SW)', 'SW*SW', '1/SW', '__import__("os")', 'nan', 'inf'):
            with self.assertRaises((ValueError, SyntaxError)):
                affine(value)

    def test_drain_source_swap_and_body_miswire(self):
        self.assert_fault(GOLDEN.replace('(DRAIN GATE TAIL 0)', '(TAIL GATE DRAIN 0)'), 'CONNECTIVITY_MISMATCH')
        self.assert_fault(GOLDEN.replace('(DRAIN GATE TAIL 0)', '(DRAIN GATE TAIL TAIL)'), 'CONNECTIVITY_MISMATCH')

    def test_label_short(self):
        self.assert_fault(GOLDEN.replace('(DRAIN FILTER 0)', '(DRAIN DRAIN 0)'), 'CONNECTIVITY_MISMATCH')

    def test_width_and_finger_silent_changes(self):
        self.assert_fault(GOLDEN.replace('w=(40u)', 'w=(50u)'), 'PARAMETER_MISMATCH')
        self.assert_fault(GOLDEN.replace('m=(1)*(2)', 'm=(1)*(1)'), 'TOTAL_MOS_WIDTH_MISMATCH')
        # Equal total W does not excuse differing finger width/multiplicity.
        self.assert_fault(GOLDEN.replace('w=(40u)', 'w=(20u)').replace('m=(1)*(2)', 'm=4'), 'PARAMETER_MISMATCH')

    def test_explicit_mapped_width_is_target_with_original_retained(self):
        manifest = deepcopy(MANIFEST)
        manifest[0]['mapped_parameters'] = {'W': '81.2'}
        manifest[0]['props'].update(w='81.2u', fw='40.6u')
        report = audit(manifest, GOLDEN.replace('w=(40u)', 'w=(40.6u)'))
        self.assertEqual(report['status'], 'NATIVE_NETLIST_AUDIT_PASS', report['errors'])
        mapping = report['instances'][0]['width_mapping']
        self.assertEqual(mapping['original_source_w_um'], 80)
        self.assertEqual(mapping['target_w_um'], 81.2)
        self.assertTrue(mapping['intentional_width_change'])
        self.assertEqual(mapping['target_field'], 'mapped_parameters.W')

    def test_mapped_width_does_not_excuse_fw_fingers_inconsistency(self):
        manifest = deepcopy(MANIFEST)
        manifest[0]['mapped_parameters'] = {'W': '81.2'}
        # Export matches unchanged props, but disagrees with explicit target W.
        self.assert_fault(GOLDEN, 'TOTAL_MOS_WIDTH_MISMATCH', manifest)

    def test_without_mapped_width_still_enforces_source_width(self):
        manifest = deepcopy(MANIFEST)
        manifest[0]['props'].update(w='81.2u', fw='40.6u')
        self.assert_fault(GOLDEN.replace('w=(40u)', 'w=(40.6u)'), 'TOTAL_MOS_WIDTH_MISMATCH', manifest)
        mapping = audit(MANIFEST, GOLDEN)['instances'][0]['width_mapping']
        self.assertFalse(mapping['intentional_width_change'])
        self.assertEqual(mapping['target_field'], 'source_parameters.W')

    def test_mapped_width_requires_explicit_finite_positive_decimal_um(self):
        for value in ('unknown', 'SW', '80u', '40*2', 'nan', 'inf', '0', '-1', None, {'W': 80}):
            manifest = deepcopy(MANIFEST)
            manifest[0]['mapped_parameters'] = {'W': value}
            self.assert_fault(GOLDEN, 'INVALID_MOS_WIDTH_TARGET', manifest)
        manifest = deepcopy(MANIFEST)
        manifest[0]['mapped_parameters'] = None
        self.assert_fault(GOLDEN, 'INVALID_MOS_WIDTH_TARGET', manifest)

    def test_mim_missing_multiplier_and_double_multiplication(self):
        self.assert_fault(GOLDEN.replace('m=4096', 'm=1'), 'PARAMETER_MISMATCH')
        self.assert_fault(GOLDEN.replace('m=4096', 'm=16777216'), 'PARAMETER_MISMATCH')
        self.assert_fault(GOLDEN.replace('m=4096', 'm=4096 mult=4096'), 'UNREVIEWED_PARAMETER')

    def test_resistor_grid_and_length_clamp(self):
        self.assert_fault(GOLDEN.replace('l=545n', 'l=544n'), 'RESISTOR_OFF_5NM_GRID')
        self.assert_fault(GOLDEN.replace('l=545n', 'l=100u'), 'PARAMETER_MISMATCH')
        self.assert_fault(GOLDEN.replace('l=545n', 'l=100.005u'), 'ILLEGAL_RESISTOR_LENGTH_RANGE')

    def test_cdf_r_not_used_as_measured_resistance(self):
        self.assertEqual(audit(MANIFEST, GOLDEN.replace('r=1.19625K', 'r=999'))['status'], 'NATIVE_NETLIST_AUDIT_PASS')
        self.assert_fault(GOLDEN.replace('resistor r=1G', 'resistor r=1m'), 'PARAMETER_MISMATCH')

    def test_missing_vdc_and_wrong_stimulus(self):
        self.assert_fault(GOLDEN.replace('dc=0.9+SW/8 ', ''), 'INVALID_DC_STIMULUS')
        self.assert_fault(GOLDEN.replace('dc=0.9+SW/8', 'dc=0'), 'DC_STIMULUS_MISMATCH')
        self.assert_fault(GOLDEN.replace('phase=180', 'phase=0'), 'PARAMETER_MISMATCH')
        self.assert_fault(GOLDEN.replace('mag=.125', 'mag=1'), 'PARAMETER_MISMATCH')

    def test_missing_extra_duplicate_and_unexpected_hierarchy(self):
        self.assert_fault(GOLDEN.replace('RLEAK (HOLD VCM) resistor r=1G\n', ''), 'MISSING_INSTANCE')
        self.assert_fault(GOLDEN+'RNEW (A 0) resistor r=1\n', 'UNEXPECTED_INSTANCE')
        self.assert_fault(GOLDEN+'RLEAK (HOLD VCM) resistor r=1G\n', 'PARSE_ERROR')
        self.assert_fault('subckt hidden A B\n'+GOLDEN+'ends hidden\n', 'PARSE_ERROR')

    def test_headers_only_allow_default_expected_setup(self):
        good = 'simulator lang=spectre\nglobal 0\nparameters SW=0\n'+GOLDEN
        self.assertEqual(audit(MANIFEST, good)['status'], 'NATIVE_NETLIST_AUDIT_PASS')
        self.assert_fault('global 0 VDD\n'+GOLDEN, 'PARSE_ERROR')
        self.assert_fault('parameters SW=1\n'+GOLDEN, 'PARSE_ERROR')


if __name__ == '__main__':
    unittest.main()
