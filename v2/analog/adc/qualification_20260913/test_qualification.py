"""Adversarial contract/evidence checks; these are not new circuit samples."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import qualify as q
import campaign
import run_checked

class QualificationTests(unittest.TestCase):
    def test_strict_profile_reduces_tolerance(self):
        a,b=(q.PROFILES[n] for n in ('baseline','strict'))
        self.assertLess(b['maxstep_ns'],a['maxstep_ns'])
        for key in ('reltol','abstol','vntol'):
            self.assertLess(float(b[key]),float(a[key]))

    def test_frozen_live_circuit_preserved(self):
        deck=q.deck_for('strict')
        self.assertIn('d_cosim simulation=',deck)
        self.assertIn('XADC inp inn decision decision_b',deck)
        self.assertIn('tran 2n 122u 0 1n',deck)
        self.assertNotIn('VTRACE',deck)
        self.assertNotIn('Vdecision',deck)
        self.assertEqual(deck.count('.include '),6)

    def test_exact_full_grid(self):
        plan=campaign.validate(q.HERE/'campaigns/ramp32')
        values=np.asarray(plan['input_v'])
        self.assertEqual(len(values),131073)
        self.assertEqual(values[0],-.4)
        self.assertEqual(values[-1],.4)
        self.assertLess(float(np.max(np.abs(np.diff(values)-q.sc.LSB/32))),1e-15)

    def test_modified_plan_rejected(self):
        plan=json.loads((q.HERE/'campaigns/ramp32/plan.json').read_text())
        plan['required_points']=4096
        with tempfile.TemporaryDirectory(dir=q.HERE) as tmp:
            path=Path(tmp)
            (path/'plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'plan was changed'):
                q.sc.read_plan(path)

    def test_long_run_gate_does_not_launch(self):
        with patch.object(q.sc,'run') as run:
            self.assertFalse(campaign.gate()['long_campaign_allowed'])
            run.assert_not_called()

    def test_timeout_never_counts_partial_words(self):
        result=q.analyse(q.HERE/'does-not-exist',None)
        self.assertEqual(result['status'],'INCOMPLETE')

    def test_wrong_school_host_architecture_rejected(self):
        with patch.object(run_checked.platform,'system',return_value='Linux'), patch.object(run_checked.platform,'machine',return_value='x86_64'):
            with self.assertRaisesRegex(ValueError,'LOCAL_RUNTIME_ONLY'):
                run_checked.check()

class SavedCircuitNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        options=sorted(q.HERE.glob('results/*_baseline/summary.json'))
        if not options:raise unittest.SkipTest('completed baseline unavailable')
        cls.directory=options[-1].parent
        summary=json.loads(options[-1].read_text())
        if summary['status']!='CONTINUOUS_12_FRAME_FUNCTIONAL_PASS':
            raise unittest.SkipTest('completed passing baseline unavailable')
        cls.values=np.loadtxt(cls.directory/'waveform.dat',skiprows=1)
        cls.names=q.tr.save_vectors((cls.directory/'adc.spice').read_text())

    def test_reanalyse_real_waveform(self):
        with patch.object(q.np,'loadtxt',return_value=self.values):
            result=q.analyse(self.directory,0)
        self.assertEqual(result['status'],'CONTINUOUS_12_FRAME_FUNCTIONAL_PASS')
        self.assertEqual(result['accepted_decisions'],144)

    def test_truncated_waveform_rejected(self):
        values=self.values[self.values[:,0]<120e-6]
        with patch.object(q.np,'loadtxt',return_value=values):
            result=q.analyse(self.directory,0)
        self.assertEqual(result['status'],'INCOMPLETE')

    def test_invalid_comparator_window_rejected(self):
        values=self.values.copy()
        # First actual bit-read window is around 4.1285 us, not EVAL onset.
        use=(values[:,0]>4.12e-6)&(values[:,0]<4.135e-6)
        values[use,self.names.index('v(decision)')+1]=.9
        with patch.object(q.np,'loadtxt',return_value=values):
            result=q.analyse(self.directory,0)
        self.assertEqual(result['status'],'CONTINUOUS_FUNCTIONAL_FAIL')
        self.assertLess(result['accepted_decisions'],144)

    def test_unsettled_output_bus_rejected(self):
        values=self.values.copy()
        use=(values[:,0]>11.01e-6)&(values[:,0]<11.03e-6)
        values[use,self.names.index('v(data0)')+1]=.9
        with patch.object(q.np,'loadtxt',return_value=values):
            result=q.analyse(self.directory,0)
        self.assertEqual(result['status'],'CONTINUOUS_FUNCTIONAL_FAIL')
        self.assertFalse(result['frames'][0]['bus_valid'])

    def test_numerical_self_comparison_passes(self):
        with patch.object(q.np,'loadtxt',side_effect=[self.values,self.values]), patch.object(q,'write'), patch('builtins.print'):
            result=q.compare(self.directory,self.directory)
        self.assertEqual(result['status'],'BOUNDED_NUMERICAL_CONVERGENCE_PASS')
        self.assertFalse(result['long_campaign_allowed'])

    def test_0_06_lsb_error_rejected_even_when_codes_match(self):
        values=self.values.copy()
        values[:,self.names.index('v(xadc.tp)')+1]+=.06*q.sc.LSB
        with patch.object(q.np,'loadtxt',side_effect=[self.values,values]), patch.object(q,'write'), patch('builtins.print'):
            result=q.compare(self.directory,self.directory)
        self.assertEqual(result['status'],'NUMERICAL_CONVERGENCE_FAIL')
        self.assertTrue(result['checks']['same_codes'])
        self.assertFalse(result['checks']['all_waveforms_le_0_05lsb'])

if __name__=='__main__':unittest.main()
