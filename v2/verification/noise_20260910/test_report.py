import json
from pathlib import Path
import unittest

from build_report import check_rc,accept_single_device


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.rows=json.loads((Path(__file__).parent/'results/20260910T062307Z/summary.json').read_text())['rc_controls']

    def test_real_rc_evidence(self):
        self.assertTrue(check_rc(self.rows)['all_checks_pass'])

    def test_incomplete_run_fails(self):
        self.rows[1]['end_s']=0.001
        self.assertFalse(check_rc(self.rows)['all_checks_pass'])

    def test_numerical_zero_not_noise(self):
        self.rows[1]['variance_over_ktc']=0
        self.assertFalse(check_rc(self.rows)['all_checks_pass'])

    def test_replay_mismatch_fails(self):
        self.rows[2]['waveform_sha256']='other'
        self.assertFalse(check_rc(self.rows)['all_checks_pass'])

    def test_independent_seed_required(self):
        self.rows[3]['waveform_sha256']=self.rows[1]['waveform_sha256']
        self.assertFalse(check_rc(self.rows)['all_checks_pass'])

    def test_missing_control_fails(self):
        self.assertFalse(check_rc(self.rows[1:])['all_checks_pass'])

    def test_actual_model_discrepancy_rejected(self):
        folder=Path(__file__).parent/'results/single_mos_20260910T063501Z'
        summary=json.loads((folder/'summary.json').read_text())
        extraction=json.loads((folder/'numeric_equivalence.json').read_text())
        self.assertFalse(accept_single_device(summary,extraction))

    def test_version_fallback_never_accepted_from_good_dc(self):
        self.assertFalse(accept_single_device(
            {'run':{'returncode':0},'unknown_version_fallback':True},
            {'native_bin_extraction_equivalent_at_tested_bias':True,
             'vacask_ac_max_relative_error':0,'vacask_noise_max_error_db':0}))

    def test_missing_noise_evidence_rejected(self):
        self.assertFalse(accept_single_device({'run':{'returncode':0},'unknown_version_fallback':False},{}))


if __name__=='__main__':unittest.main()
