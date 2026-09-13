"""Read-only audit of the eight bounded diagnostics; no electrical simulation."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from measurement_evidence import verify_manifest


class ClosureEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths=sorted((HERE/'diagnostics').glob('*/summary.json'))
        cls.rows=[json.loads(path.read_text()) for path in cls.paths]

    def test_budget_and_all_results_retained(self):
        self.assertEqual(len(self.paths),8)
        self.assertEqual(sorted(row['ordinal'] for row in self.rows),list(range(1,9)))
        self.assertTrue(all(row['status']=='DIAGNOSTIC_COMPLETE' for row in self.rows))

    def test_every_manifest_and_frozen_source(self):
        for path,row in zip(self.paths,self.rows):
            with self.subTest(path=path):
                self.assertTrue(verify_manifest(path.parent))
                self.assertEqual(hashlib.sha256((path.parent/'frontend_pdk_snapshot.spice').read_bytes()).hexdigest(),row['source_sha256'])

    def test_each_dc_full_range_and_nominal_fitting(self):
        for path,row in zip(self.paths,self.rows):
            if not (path.parent/'dc.dat').exists():continue
            with self.subTest(path=path):
                data=np.loadtxt(path.parent/'dc.dat',skiprows=1)
                columns=json.loads((path.parent/'columns.json').read_text())
                index={name:i for i,name in enumerate(columns)}
                target=(data[:,index['v(sp)']]-data[:,index['v(sn)']])*row['gain']
                np.testing.assert_allclose(target,np.linspace(-.4,.4,81),atol=1e-10,rtol=0)
                if (row['vdd_v'],row['temp_c'])!=(1.8,27):
                    self.assertTrue((path.parent/'calibration_source_summary.json').exists())
                    self.assertIn('frozen',row['calibration_source'])
                expected_limit=1 if (row['vdd_v'],row['temp_c'])==(1.8,27) else 4
                self.assertEqual(row['static_accuracy_limit_lsb'],expected_limit)
                self.assertEqual(row['static_accuracy_pass'],row['max_holdout_error_lsb']<=expected_limit)

    def test_same_source_three_gains_and_failure_not_hidden(self):
        rows=[r for r in self.rows if r.get('configuration',{}).get('variant')=='headroom_c']
        self.assertEqual({r['gain'] for r in rows},{1,4,16})
        self.assertEqual(len({r['source_sha256'] for r in rows}),1)
        self.assertEqual({r['gain']:r['static_accuracy_pass'] for r in rows},{1:False,4:True,16:False})
        self.assertTrue(all(r['preliminary_quiet_window_gate'] is False for r in rows))

    def test_no_frontend_or_chip_signoff(self):
        for row in self.rows:
            self.assertIs(row['full_frontend_qualified'],False)
            self.assertIs(row['full_chip_qualified'],False)
        index=json.loads((HERE/'closure_summary.json').read_text())
        self.assertEqual(index['new_full_pvt_status'],'NOT_RUN_PREREQUISITE_GATES_FAILED')
        self.assertEqual(index['full_45_pvt_screen_count'],0)
        self.assertTrue(all(g['same_source_three_gain_nominal_static_pass'] is False for g in index['source_groups'].values()))

    def test_settling_analysis_retains_original_threshold(self):
        paths=sorted((HERE/'settling_analysis').glob('*/summary.json'))
        self.assertTrue(paths)
        for path in paths:
            self.assertTrue(verify_manifest(path.parent))
            report=json.loads(path.read_text())
            self.assertEqual({r['gain'] for r in report['rows']},{1,4,16})
            for row in report['rows']:
                self.assertFalse(row['all_static_cap_load_step_windows_pass'])
                for window in row['windows']:
                    self.assertEqual(window['limit_v'],.8/4096*.25)
                    self.assertAlmostEqual(window['elapsed_from_step_onset_s'],2.476847754e-6)
                    self.assertEqual(window['dynamic_residual_within_0p25_lsb'],
                                     abs(window['dynamic_minus_dc_residual_v'])<=.8/4096*.25)


if __name__=='__main__':unittest.main()
