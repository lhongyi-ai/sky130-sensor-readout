import csv
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

FIX = Path(__file__).resolve().parents[1]
BASE = FIX.parents[1]
REPORT = BASE/'reports/basic_20260913T010855Z_58477ef8/received'
sys.path[:0] = [str(FIX/'payload'), str(BASE/'basic_design')]
import passive_review
import passive_models
import run as runner

spec = importlib.util.spec_from_file_location('installer_p2', str(FIX/'install.py'))
installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)


class PassiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='p1_passive_review_')
        self.addCleanup(self.tmp.cleanup)
        with zipfile.ZipFile(BASE/'releases/project1_basic_design_v1.0.4.zip') as z:
            z.extractall(self.tmp.name)
        self.root = Path(self.tmp.name)/'project1_handoff/basic_design_v1_0_4'
        for p in (BASE/'runtime_fixes/v1_0_4p1/payload').iterdir():
            if p.is_file(): shutil.copy2(p, self.root/p.name)
        shutil.copytree(REPORT/'runs', self.root/'runs', dirs_exist_ok=True)
        shutil.copy2(REPORT/'site.json', self.root/'site.json')
        self.cfg = json.loads((self.root/'site.json').read_text())

    def latest(self, ident):
        return sorted((self.root/'runs'/ident).glob('*/status.json'))[-1].parent

    def review(self, model=False):
        return passive_review.review_passives(self.root, self.cfg, runner.deck, runner.netlist_body, runner.log_audit, check_model=model)

    def model_mock(self):
        original = passive_review.sha
        digest = json.loads((self.latest('mim_ac')/'status.json').read_text())['model_entry_sha256']
        return patch.object(passive_review, 'sha', side_effect=lambda p: digest if str(p) == self.cfg['model'] else original(p))

    def rewrite_curve(self, ident, name, transform):
        path = self.latest(ident)/(name+'.csv')
        with path.open() as f: rows = list(csv.DictReader(f))
        rows = transform(rows)
        with path.open('w') as f:
            w = csv.DictWriter(f, fieldnames=['x','real','imag']); w.writeheader(); w.writerows(rows)

    def test_actual_three_jobs_recheck_and_immutable_failures(self):
        before = {p: p.read_bytes() for ident in passive_review.IDENTS for p in [self.latest(ident)/'status.json',self.latest(ident)/'metrics.json']}
        result = self.review()
        self.assertEqual(result['status'], 'PASS')
        self.assertFalse(result['current_site_model_checked'])
        self.assertEqual(result['records']['res_dc']['source_performance_status'], 'FAIL')
        self.assertEqual(result['records']['rc_step']['source_performance_status'], 'FAIL')
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertAlmostEqual(result['records']['rc_step']['metrics']['model_delay_s']*1e12,42.9836125,places=6)

    def test_wrong_resistor_current_fails(self):
        def corrupt(rows):
            for row in rows: row['real'] = str(float(row['real'])*1.03)
            return rows
        self.rewrite_curve('res_dc','VTEST_p',corrupt)
        self.assertEqual(self.review()['status'],'FAIL')

    def test_wrong_mim_capacitance_fails(self):
        def corrupt(rows):
            for row in rows: row['imag'] = str(float(row['imag'])*1.2)
            return rows
        self.rewrite_curve('mim_ac','VTEST_p',corrupt)
        self.assertEqual(self.review()['status'],'FAIL')

    def test_bad_rc_waveform_fails(self):
        def corrupt(rows):
            for row in rows: row['real'] = str(float(row['real'])*.99)
            return rows
        self.rewrite_curve('rc_step','VOUT',corrupt)
        result=self.review()
        self.assertEqual(result['status'],'FAIL')
        self.assertFalse(result['records']['rc_step']['metrics']['criteria']['charge_balance_within_250uV'])

    def test_missing_curve_point_rejected(self):
        self.rewrite_curve('mim_ac','TEST',lambda rows: rows[:-1])
        with self.assertRaises(ValueError): self.review()

    def test_latest_failed_attempt_cannot_fall_back(self):
        out=self.root/'runs/res_dc/20990101T000000Z_latest';out.mkdir()
        (out/'status.json').write_text('{"status":"ENV_BLOCKED"}')
        with self.assertRaisesRegex(ValueError,'Latest res_dc'): self.review()

    def test_input_or_model_inconsistency_rejected(self):
        p=self.latest('rc_step')/'input.scs';p.write_text(p.read_text().replace('maxstep=0.5p','maxstep=5p'))
        with self.assertRaisesRegex(ValueError,'Executed analysis'): self.review()

    def test_review_gate_detects_changed_evidence_and_model(self):
        installer.install(self.root)
        with self.model_mock(), patch.object(runner,'ROOT',self.root):
            saved=self.review(model=True)
            out=self.root/'runs/passive_reviews/20260913T020000Z_review';out.mkdir(parents=True)
            (out/'review.json').write_text(json.dumps(saved))
            runner.prerequisites({'group':'nominal'})
            # Even numerically harmless CSV formatting changes invalidate the saved review.
            p=self.latest('res_dc')/'TEST.csv';p.write_text(p.read_text()+'\n')
            with self.assertRaisesRegex(ValueError,'evidence changed'): runner.prerequisites({'group':'nominal'})
        with patch.object(passive_review,'sha',side_effect=lambda p: 'changed' if str(p)==self.cfg['model'] else installer.sha(p)):
            with self.assertRaisesRegex(ValueError,'Installed model entry changed'): self.review(model=True)

    def test_install_repeat_preserves_sources_and_original_regressions(self):
        originals={p:p.read_bytes() for p in [self.root/'create.il',self.root/'design.json',self.root/'site.json',self.latest('rc_step')/'metrics.json']}
        installer.install(self.root);installer.install(self.root)
        self.assertEqual(originals,{p:p.read_bytes() for p in originals})
        self.assertEqual(installer.sha(self.root/'patch_backups/v1_0_4p2/package_manifest.json'),installer.BASE_MANIFEST)
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(self.root/'tests'),'-q'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        listed=subprocess.run(['bash',str(self.root/'p1_run.sh'),'list'],capture_output=True,text=True)
        self.assertEqual(listed.returncode,0,listed.stderr)
        self.assertEqual(len(listed.stdout.splitlines()),87)

    def test_conflicting_file_stops_before_install(self):
        p=self.root/'passive_models.py';p.write_text('user file')
        with self.assertRaises(ValueError): installer.install(self.root)
        self.assertEqual(p.read_text(),'user file')
        self.assertFalse((self.root/'patch_backups/v1_0_4p2').exists())

    def test_installer_rolls_back_write_failure(self):
        before={n:(self.root/n).read_bytes() for n in ['run.py','analyze.py','runtime_patch.json','package_manifest.json']}
        atomic=installer.atomic_copy
        def fail(source,destination):
            if destination.name=='passive_models.py': raise OSError('Injected disk write failure')
            return atomic(source,destination)
        with patch.object(installer,'atomic_copy',side_effect=fail):
            with self.assertRaises(OSError): installer.install(self.root)
        self.assertEqual(before,{n:(self.root/n).read_bytes() for n in before})


if __name__=='__main__': unittest.main()
