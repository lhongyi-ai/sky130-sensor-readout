import csv
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

FIX=Path(__file__).resolve().parents[1];BASE=FIX.parents[1]
REPORT=BASE/'reports/basic_20260913T013329Z_e16ef8e0/received'
ATTEMPT='20260913T013236Z_ce589195'
sys.path[:0]=[str(FIX/'payload'),str(BASE/'runtime_fixes/v1_0_4p2/payload'),str(BASE/'basic_design'),str(BASE/'runtime_fixes')]
import run as runner
import passive_review
from test_pulse_cdf_v1 import balance
spec=importlib.util.spec_from_file_location('install_p3',str(FIX/'install.py'))
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='p1_op_export_test_');self.addCleanup(self.tmp.cleanup)
        with zipfile.ZipFile(BASE/'releases/project1_basic_design_v1.0.4.zip') as z:z.extractall(self.tmp.name)
        self.root=Path(self.tmp.name)/'project1_handoff/basic_design_v1_0_4'
        for version in ['v1_0_4p1','v1_0_4p2']:
            for p in (BASE/'runtime_fixes'/version/'payload').iterdir():
                if p.is_file():shutil.copy2(p,self.root/p.name)
        shutil.copytree(REPORT/'runs',self.root/'runs',dirs_exist_ok=True)
        shutil.copy2(REPORT/'site.json',self.root/'site.json')
        self.source=self.root/'runs/P01_op'/ATTEMPT
        self.state=json.loads((self.source/'status.json').read_text());self.cfg=self.state['site'];self.job=self.state['job']

    def model_mock(self):
        sha=runner.sha
        return patch.object(runner,'sha',side_effect=lambda p:self.state['model_entry_sha256'] if str(p)==self.cfg['model'] else sha(p))

    def test_all_leaf_names_are_in_actual_psf_and_generated_export(self):
        raw=(self.source/'psf/dcOpInfo.info').read_bytes()
        names=set(re.findall(rb'XOTA\.M[0-9]+[AB]?\.msky130_fd_pr__[np]fet_01v8',raw))
        self.assertEqual(names,{runner.op_leaf(d).encode() for d in runner.OP_DEVICES})
        script=runner.export_script(self.job,self.source,{})
        balance(script)
        self.assertNotIn('=pv(',script)
        self.assertIn("selectResult('dcOpInfo)",script)
        for name in names:self.assertIn(name.decode(),script)
        self.assertEqual(script.count('p1bDevice=getData(p1bName)'),13)
        self.assertTrue(script.startswith('procedure(p1bExportAll()'))
        self.assertIn('errset(p1bExportAll() t)',script)
        self.assertIn('else exit(1)',script)
        self.assertLess(script.index('export_complete.txt'),script.index('errset(p1bExportAll() t)'))

    def test_actual_errors_cannot_be_hidden_by_zero_exit_and_complete_marker(self):
        self.assertTrue((self.source/'export_complete.txt').is_file())
        with self.assertRaisesRegex(RuntimeError,'OCEAN export failed'):
            runner.validate_export(self.source,self.job,0)

    def synthetic_export(self,out):
        # Numerical values below are unit-test fixtures, never actual MOS results.
        shutil.copy2(self.source/'op.csv',out/'op.csv')
        rows=[]
        for dev in runner.OP_DEVICES:
            sign=-1 if dev in runner.OP_PMOS else 1
            rows.append([dev,sign*1e-5,.001,.00001,sign*.9,sign*.2])
        with (out/'op_devices.csv').open('w') as f:
            w=csv.writer(f);w.writerow(['device','ids','gm','gds','vds','vdsat']);w.writerows(rows)
        with (out/'op_instance_map.csv').open('w') as f:
            w=csv.writer(f);w.writerow(['device','signal']);w.writerows([[d,runner.op_leaf(d)] for d in runner.OP_DEVICES])
        (out/'ocean_export.log').write_text('SYNTHETIC_TEST_EXPORT\n')
        (out/'export_complete.txt').write_text('COMPLETE\n')

    def test_missing_row_nan_and_wrong_leaf_still_rejected(self):
        out=Path(self.tmp.name)/'fixture';out.mkdir();self.synthetic_export(out)
        runner.validate_export(out,self.job,0)
        p=out/'op_devices.csv';original=p.read_text()
        p.write_text('\n'.join(original.splitlines()[:-1])+'\n')
        with self.assertRaisesRegex(RuntimeError,'expected 13'):runner.validate_export(out,self.job,0)
        p.write_text(original.replace('0.001','nan',1))
        with self.assertRaisesRegex(RuntimeError,'Nonfinite'):runner.validate_export(out,self.job,0)
        p.write_text(original)
        p=out/'op_instance_map.csv';p.write_text(p.read_text().replace(runner.op_leaf('M1'),'XOTA.M1'))
        with self.assertRaisesRegex(RuntimeError,'mapping'):runner.validate_export(out,self.job,0)

    def test_recovery_only_calls_ocean_and_preserves_original_attempt(self):
        installer.install(self.root)
        original={p:p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        def fake_invoke(argv,log,cwd,stdin=None):
            self.assertEqual(argv,[self.cfg['ocean'],'-nograph'])
            self.synthetic_export(log.parent)
            return 0
        with patch.object(runner,'ROOT',self.root),self.model_mock(),patch.object(runner,'invoke',side_effect=fake_invoke) as invoked:
            result=runner.resume_export(self.job,ATTEMPT,self.cfg)
        self.assertEqual(invoked.call_count,1)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['simulation_origin'],'RETAINED_SPECTRE_RESULTS')
        self.assertEqual(original,{p:p.read_bytes() for p in original})
        new=next(p for p in (self.root/'runs/P01_op').iterdir() if p.name!=ATTEMPT)
        self.assertEqual((new/'psf/dcOpInfo.info').read_bytes(),(self.source/'psf/dcOpInfo.info').read_bytes())
        self.assertFalse(json.loads((new/'recovery_source.json').read_text())['new_spectre_execution'])

    def test_changed_source_stops_before_any_ocean_call(self):
        installer.install(self.root)
        p=self.source/'input.scs';p.write_text(p.read_text().replace('dc=10u','dc=20u'))
        with patch.object(runner,'ROOT',self.root),self.model_mock(),patch.object(runner,'invoke') as invoked:
            with self.assertRaisesRegex(ValueError,'simulation input changed'):runner.resume_export(self.job,ATTEMPT,self.cfg)
            invoked.assert_not_called()

    def test_install_repeat_original_regressions_and_passive_recheck(self):
        before={p:p.read_bytes() for p in [self.root/'create.il',self.root/'design.json',self.root/'site.json',self.source/'status.json']}
        installer.install(self.root);installer.install(self.root)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(self.root/'tests'),'-q'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        result=passive_review.review_passives(self.root,self.cfg,runner.deck,runner.netlist_body,runner.log_audit,check_model=False)
        self.assertEqual(result['status'],'PASS')

    def test_conflict_and_rollback_preserve_old_runtime(self):
        before={n:(self.root/n).read_bytes() for n in installer.FILES}
        atomic=installer.atomic_copy
        def fail(src,dst):
            if dst.name=='runtime_patch.json' and src.parent.name=='payload':raise OSError('Injected write error')
            return atomic(src,dst)
        with patch.object(installer,'atomic_copy',side_effect=fail):
            with self.assertRaises(OSError):installer.install(self.root)
        self.assertEqual(before,{n:(self.root/n).read_bytes() for n in before})
        (self.root/'run.py').write_text('user edit')
        with self.assertRaises(ValueError):installer.install(self.root)
        self.assertEqual((self.root/'run.py').read_text(),'user edit')


if __name__=='__main__':unittest.main()
