"""Local environment-wiring tests only; fake tools never simulate Cadence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

BASE=Path(__file__).resolve().parents[1]
LAUNCHER=BASE/'releases/p1_school_run_v1.sh'

class SchoolLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p1_school_env_')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.site=self.root/'school tools'
        self.package=self.root/'package with spaces'
        self.package.mkdir()
        shutil.copy2(str(BASE/'runtime_fixes/v1_0_4p1/payload/p1_run.sh'),str(self.package/'p1_run.sh'))
        (self.site/'ic/bin').mkdir(parents=True)
        (self.site/'ic/tools/dfII/bin').mkdir(parents=True)
        virtuoso=self.site/'ic/bin/virtuoso'
        virtuoso.write_text('#!/usr/bin/env bash\n'
            'test -n "$LD_LIBRARY_PATH" || exit 91\n'
            'test "${CDS_LIC_FILE+x}" != x || exit 92\n'
            'printf "%s\\n" "$CDSHOME" "$LM_LICENSE_FILE" "$LD_LIBRARY_PATH" "$@"\n'
            'exit "${P1_TEST_TOOL_EXIT:-0}"\n')
        virtuoso.chmod(0o755)
        ocean=self.site/'ic/tools/dfII/bin/ocean'
        ocean.write_text('#!/usr/bin/env bash\nexec virtuoso "$@"\n')
        ocean.chmod(0o755)
        # Exercise the actual shipped invoke() with a fake OCEAN/virtuoso chain.
        text='''import importlib.util,json,os,sys
from pathlib import Path
assert 'LD_LIBRARY_PATH' not in os.environ, 'System Python inherited Cadence LD path'
assert 'P1_RUNTIME_LD_LIBRARY_PATH' in os.environ
sys.path.insert(0, BASIC)
spec=importlib.util.spec_from_file_location('shipped_runner', PATCHED_RUN)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
log=Path('fake_tool.log')
code=module.invoke([str(Path(os.environ['CDSHOME'])/'tools/dfII/bin/ocean'),'-nograph'],log,Path.cwd())
assert 'LD_LIBRARY_PATH' not in os.environ
print(json.dumps({'args':sys.argv[1:],'cwd':str(Path.cwd()),'tool_log':log.read_text(),'exit_code':code}))
sys.exit(code)
'''
        text='BASIC='+repr(str(BASE/'basic_design'))+'\nPATCHED_RUN='+repr(str(BASE/'runtime_fixes/v1_0_4p1/payload/run.py'))+'\n'+text
        (self.package/'run.py').write_text(text)
        self.env=dict(os.environ)
        for name in ['LD_LIBRARY_PATH','CDSHOME','LM_LICENSE_FILE','P1_RUNTIME_LD_LIBRARY_PATH']:
            self.env.pop(name,None)
        self.env.update(P1_SCHOOL_CADENCE_ROOT=str(self.site),P1_BASIC_PACKAGE_DIR=str(self.package),CDS_LIC_FILE='stale-test-locator')

    def launch(self,*args):
        return subprocess.run(['bash',str(LAUNCHER)]+list(args),cwd=self.root,env=self.env,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)

    def test_clean_terminal_restores_paths_and_keeps_python_isolated(self):
        result=self.launch('run','--job','mim_ac','--retry')
        self.assertEqual(result.returncode,0,result.stderr)
        payload=json.loads(result.stdout)
        self.assertEqual(payload['args'],['run','--job','mim_ac','--retry'])
        self.assertEqual(Path(payload['cwd']),self.package.resolve())
        lines=payload['tool_log'].splitlines()
        self.assertEqual(lines[0],str(self.site/'ic'))
        self.assertEqual(lines[1],'27021@licensing02.seas.wustl.edu')
        dirs=lines[2].split(':')
        self.assertEqual(len(dirs),14)
        self.assertIn(str(self.site/'ic/tools.lnx86/python/64bit/lib'),dirs)
        self.assertIn(str(self.site/'ic/tools.lnx86/dfII/lib/64bit'),dirs)
        self.assertEqual(lines[3],'-nograph')

    def test_exit_code_is_preserved(self):
        self.env['P1_TEST_TOOL_EXIT']='7'
        result=self.launch('run','--job','rc_step','--retry')
        self.assertEqual(result.returncode,7,result.stderr)
        self.assertEqual(json.loads(result.stdout)['exit_code'],7)

    def test_missing_virtuoso_stops_before_python(self):
        (self.site/'ic/bin/virtuoso').unlink()
        result=self.launch('list')
        self.assertEqual(result.returncode,2)
        self.assertIn('Virtuoso launcher missing',result.stderr)
        self.assertFalse((self.package/'fake_tool.log').exists())

    def test_missing_runtime_patch_stops(self):
        (self.package/'p1_run.sh').unlink()
        result=self.launch('list')
        self.assertEqual(result.returncode,2)
        self.assertIn('runtime patch 1.0.4p1 is required',result.stderr)

if __name__=='__main__':
    subprocess.run(['bash','-n',str(LAUNCHER)],check=True)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SchoolLauncherTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        digest=hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()
        (BASE/'releases/p1_school_run_v1.sh.sha256').write_text(digest+'  '+LAUNCHER.name+'\n')
        (BASE/'releases/p1_school_run_v1.validation.json').write_text(json.dumps(dict(
            status='PASS_LOCAL_CHECKS_ONLY',school_cadence_status='NOT_RUN',tests_run=result.testsRun,
            launcher_sha256=digest,checks=['bash syntax','Clean-terminal restoration of all 14 library directories and tool search PATH',
                'Actual p1_run.sh and shipped invoke() with fake OCEAN -> bare virtuoso lookup',
                'Python library isolation, argument forwarding, spaces in paths and exit propagation',
                'Missing launcher/runtime patch stop before job execution']),indent=2)+'\n')
    sys.exit(0 if result.wasSuccessful() else 1)
