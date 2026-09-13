"""Meaningful fail-closed and interface tests; no circuit performance claim."""
import copy,json,unittest
from pathlib import Path
from prepare import ROOT,HERE,subckt,spice_lines
from postlayout_gate import evaluate

class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bindings=json.loads((HERE/'extracted_view_bindings.json').read_text())
    def test_missing_macros_refuse_readiness(self):
        report=evaluate(self.bindings);self.assertFalse(report['ready_to_simulate']);self.assertIn('full core extracted view missing',report['reasons'])
    def test_changed_source_hash_is_rejected(self):
        b=copy.deepcopy(self.bindings);b['frozen_source_sha256']['v2/config/spec.json']='0'*64
        self.assertTrue(any('stale source: v2/config/spec.json' in x for x in evaluate(b)['reasons']))
    def test_schematic_as_extracted_is_rejected(self):
        b=copy.deepcopy(self.bindings);b['bindings']['digital']['view_kind']='analog_extracted_rc'
        self.assertIn('unextracted analog view: digital',evaluate(b)['reasons'])
    def test_port_order_is_checked(self):
        b=copy.deepcopy(self.bindings);b['bindings']['sampling_switch']['pins'][:2]=['B','A']
        self.assertIn('port mismatch: sampling_switch',evaluate(b)['reasons'])
    def test_adapter_exports_substrate_and_preserves_devices(self):
        b=self.bindings['bindings']['cdac'];src=ROOT/b['view'];dst=ROOT/b['bound_view']
        self.assertEqual(subckt(dst,b['bound_subckt']),['VSUBS']+b['pins'])
        elem=lambda p:[x for x in spice_lines(p) if not x.lower().startswith(('.subckt','.ends'))]
        self.assertEqual(elem(src),elem(dst))
    def test_fixture_binds_substrate_and_keeps_clamp_direction(self):
        lines=spice_lines(HERE/'cdac_clamp_pex_partial.spice')
        self.assertTrue(any(x.startswith('XCDAC VSS P_TOP') for x in lines))
        self.assertIn('XCLAMP_P VCM_CLAMP P_TOP SAMPLE SAMPLEB VDD VSS adc_tgate_flat',lines)
        self.assertIn('XCLAMP_N VCM_CLAMP N_TOP SAMPLE SAMPLEB VDD VSS adc_tgate_flat',lines)
    def test_matrix_is_exactly_135_unrun_points(self):
        d=json.loads((HERE/'postlayout_acceptance_matrix.json').read_text())
        self.assertEqual(len(d['rows']),135);self.assertEqual(len({r['id'] for r in d['rows']}),135)
        self.assertTrue(all(r['status']=='NOT_RUN' for r in d['rows']))
if __name__=='__main__':unittest.main(verbosity=2)
