import hashlib
import json
from pathlib import Path
import unittest
from hybrid import qualification_gate

HERE=Path(__file__).resolve().parent


class FrozenEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q=json.loads((HERE/'qualification.json').read_text())

    def test_four_bounded_completed_runs(self):
        self.assertEqual(self.q['actual_run_count'],4)
        self.assertTrue(self.q['all_runs_completed'])
        for result in self.q['simulator_runs']:
            self.assertEqual(result['run']['returncode'],0)
            self.assertLess(result['run']['elapsed_s'],180)

    def test_noisetran_rejected(self):
        self.assertTrue(self.q['noisetran_rejected_all_runs'])

    def test_same_actual_model(self):
        result=self.q['same_real_sky130_single_device_regression']
        self.assertEqual(result['same_model_version'],'4.5')
        self.assertIn('BSIM4v5',result['same_model_implementation'])
        self.assertEqual(result['dc_current_relative_error'],0)
        self.assertLess(result['noise_psd']['max_relative_error'],1e-9)

    def test_real_osdi_noise_exists_only_in_stationary_analysis(self):
        result=self.q['native_rc_and_verilog_a_control']
        self.assertTrue(result['osdi_and_native_noise_off_are_zero'])
        self.assertTrue(result['rc_native_and_osdi_transient_noise_on_are_zero'])
        self.assertLess(result['osdi_psd_max_relative_error_to_4ktr_formula'],1e-5)

    def test_model_noise_is_not_process_monte_carlo(self):
        for result in self.q['planning_models'].values():
            self.assertEqual(result['noise_realizations'],128)
            self.assertEqual(result['process_or_device_mismatch_samples'],0)
            self.assertEqual(result['outside_band_noise'],'UNKNOWN_NOT_ASSERTED_ZERO')
            self.assertFalse(result['adc_sndr_computed'])

    def test_final_noise_cannot_pass(self):
        self.assertEqual(self.q['status'],'BLOCKED_NATIVE_INTRINSIC_SWITCHING_NOISE_UNAVAILABLE')
        self.assertFalse(self.q['adc_noise_qualified'])
        self.assertFalse(self.q['full_chain_sndr_qualified'])
        self.assertFalse(qualification_gate(self.q['final_noise_qualification_evidence']))

    def test_planning_checks_pass_only_within_scope(self):
        self.assertTrue(all(self.q['planning_method_acceptance_checks'].values()))
        self.assertIn('LTI_POWER_ACCOUNTING_ONLY',self.q['planning_method_status'])

    def test_evidence_hashes_match(self):
        for relative,expected in self.q['evidence_sha256'].items():
            self.assertEqual(hashlib.sha256((HERE/relative).read_bytes()).hexdigest(),expected,relative)


if __name__=='__main__':unittest.main()
