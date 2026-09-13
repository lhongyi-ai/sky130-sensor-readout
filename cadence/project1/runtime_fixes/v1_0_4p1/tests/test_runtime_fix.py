import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

FIX=Path(__file__).resolve().parents[1]
BASE=FIX.parents[1]
sys.path.insert(0,str(BASE/'basic_design'))
spec=importlib.util.spec_from_file_location('patched_run',str(FIX/'payload/run.py'))
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
spec=importlib.util.spec_from_file_location('patch_installer',str(FIX/'install.py'))
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

# Transcribed from the user's school OCEAN output, not a simulated result.
BODY='''// Library name: project1
// Cell name: p1b_tb_res
// View name: schematic
R0 (TEST VSS VSS) res_high_po_0p35 r=979.33 l=350n w=350n
VSSSUP (VSS 0) vsource dc=0 type=dc
VTEST (TEST VSS) vsource dc=VTEST mag=1 type=dc
'''

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p1_runtime_selection_')
        self.addCleanup(self.temp.cleanup)
        self.out=Path(self.temp.name)/'new attempt'
        self.top=self.out/'native/p1b_tb_res/spectre/schematic/netlist'
        (self.top/'ihnl/cds0').mkdir(parents=True)
        (self.top/'netlist').write_text(BODY)
        (self.top/'ihnl/cds0/netlist').write_text(BODY)
        # Synthetic envelope for filesystem regression only. The actual school
        # input.scs content has not been returned; no simulation is claimed.
        (self.top/'input.scs').write_text('simulator lang=spectre\ninclude "school-model.spice" section=tt\n'+BODY)
        self.set_return(self.top/'input.scs')

    def set_return(self,path):
        (self.out/'netlist_return.txt').write_text(json.dumps(str(path))+'\n')

    def test_two_names_selects_returned_top_directory(self):
        self.assertEqual(len(list((self.out/'native').rglob('netlist'))),3)  # includes directory
        selected=runner.native_netlist_path(self.out)
        self.assertEqual(selected,(self.top/'netlist').resolve())
        self.assertEqual((self.out/'native_input.scs').read_bytes(),(self.top/'input.scs').read_bytes())
        evidence=json.loads((self.out/'native_selection.json').read_text())
        self.assertEqual(evidence['selected_body_sha256'],runner.sha(selected))
        design=json.loads((BASE/'basic_design/design.json').read_text())
        self.assertEqual(runner.check(selected.read_text(),design,'p1b_tb_res',{'VTEST':0})['status'],'PASS')
        self.assertIn('R0 (TEST VSS VSS)',runner.netlist_body(selected.read_text()))

    def test_does_not_fall_back_to_correct_internal_copy(self):
        (self.top/'netlist').write_text(BODY.replace('350n','350u'))
        selected=runner.native_netlist_path(self.out)
        design=json.loads((BASE/'basic_design/design.json').read_text())
        with self.assertRaises(ValueError):
            runner.check(selected.read_text(),design,'p1b_tb_res',{'VTEST':0})

    def test_rejects_previous_attempt(self):
        self.set_return(Path(self.temp.name)/'old/native/netlist/input.scs')
        with self.assertRaises(OSError): runner.native_netlist_path(self.out)

    def test_rejects_internal_return_path(self):
        self.set_return(self.top/'ihnl/cds0/netlist/input.scs')
        with self.assertRaises(OSError): runner.native_netlist_path(self.out)

    def test_rejects_missing_top_body_even_with_internal_copy(self):
        (self.top/'netlist').unlink()
        with self.assertRaises(OSError): runner.native_netlist_path(self.out)

    def test_rejects_missing_input(self):
        (self.top/'input.scs').unlink()
        with self.assertRaises(OSError): runner.native_netlist_path(self.out)

    def test_rejects_untrusted_or_nonpath_return(self):
        for value in ['nil','t','"relative/input.scs"','["/tmp/input.scs"]','__import__("os")']:
            (self.out/'netlist_return.txt').write_text(value)
            with self.assertRaises((OSError,ValueError)): runner.native_netlist_path(self.out)

    def test_rejects_body_symlink_escape(self):
        other=Path(self.temp.name)/'previous_netlist'
        other.write_text(BODY)
        (self.top/'netlist').unlink()
        (self.top/'netlist').symlink_to(other)
        with self.assertRaises(OSError): runner.native_netlist_path(self.out)

class EnvironmentTests(unittest.TestCase):
    def test_tools_receive_cadence_path_without_changing_parent(self):
        with tempfile.TemporaryDirectory(prefix='p1_runtime_env_') as tmp:
            root=Path(tmp)
            inp=root/'stdin';inp.write_text('retained input')
            env=dict(os.environ)
            env.pop('LD_LIBRARY_PATH',None)
            env['P1_RUNTIME_LD_LIBRARY_PATH']='/p1-test/cadence-only'
            with patch.dict(os.environ,env,clear=True):
                code=runner.invoke([sys.executable,'-c',
                    'import os,sys; print(os.environ.get("LD_LIBRARY_PATH")); '
                    'print("P1_RUNTIME_LD_LIBRARY_PATH" in os.environ); '
                    'print(sys.stdin.read()); sys.exit(7)'],root/'log',root,inp)
                self.assertNotIn('LD_LIBRARY_PATH',os.environ)
                self.assertEqual(code,7)
            self.assertEqual((root/'log').read_text().splitlines(),['/p1-test/cadence-only','False','retained input'])

    def test_launcher_clean_python_arguments_and_exit_status(self):
        with tempfile.TemporaryDirectory(prefix='p1_runtime_shell_') as tmp:
            root=Path(tmp)
            fake=root/'python3'
            fake.write_text('#!/bin/bash\n'
                'test "${LD_LIBRARY_PATH+x}" != x || exit 98\n'
                'test "$P1_RUNTIME_LD_LIBRARY_PATH" = "/p1-test/cadence-only" || exit 97\n'
                'printf "%s\\n" "$@"\nexit 7\n')
            fake.chmod(0o755)
            env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],LD_LIBRARY_PATH='/p1-test/cadence-only')
            result=subprocess.run(['bash',str(FIX/'payload/p1_run.sh'),'run','--group','passives','--retry'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
            self.assertEqual(result.returncode,7,result.stderr)
            self.assertEqual(result.stdout.splitlines(),[str(FIX/'payload/run.py'),'run','--group','passives','--retry'])

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='p1_runtime_install_')
        self.addCleanup(self.temp.cleanup)
        with zipfile.ZipFile(BASE/'releases/project1_basic_design_v1.0.4.zip') as archive:
            archive.extractall(self.temp.name)
        self.root=Path(self.temp.name)/'project1_handoff/basic_design_v1_0_4'

    def test_preserves_configuration_old_attempts_and_generation(self):
        site=self.root/'site.json';site.write_text('{"ocean":"/my/site/ocean"}\n')
        created=self.root/'created.txt';created.write_text('user-created-cell-marker\n')
        old=self.root/'runs/res_dc/old/status.json';old.parent.mkdir(parents=True);old.write_text('{"status":"ENV_BLOCKED"}\n')
        original_manifest=(self.root/'package_manifest.json').read_bytes()
        original_run=(self.root/'run.py').read_bytes()
        generator=(self.root/'create.il').read_bytes()
        installer.install(self.root)
        installer.install(self.root)  # idempotent without touching attempts
        self.assertEqual(site.read_text(),'{"ocean":"/my/site/ocean"}\n')
        self.assertEqual(created.read_text(),'user-created-cell-marker\n')
        self.assertEqual(old.read_text(),'{"status":"ENV_BLOCKED"}\n')
        self.assertEqual((self.root/'create.il').read_bytes(),generator)
        backup=self.root/'patch_backups/v1_0_4p1'
        self.assertEqual((backup/'run.py').read_bytes(),original_run)
        self.assertEqual((backup/'package_manifest.json').read_bytes(),original_manifest)
        listed=subprocess.run(['bash',str(self.root/'p1_run.sh'),'list'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        self.assertEqual(listed.returncode,0,listed.stderr)
        self.assertEqual(len(listed.stdout.splitlines()),87)
        # All original topology/measurement regressions run against the patched installation.
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(self.root/'tests'),'-q'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_changed_source_is_rejected_before_writes(self):
        original=(self.root/'package_manifest.json').read_bytes()
        (self.root/'run.py').write_text('user change\n')
        with self.assertRaises(ValueError): installer.install(self.root)
        self.assertEqual((self.root/'package_manifest.json').read_bytes(),original)
        self.assertFalse((self.root/'patch_backups').exists())

    def test_unmanaged_launcher_is_preserved(self):
        (self.root/'p1_run.sh').write_text('user file\n')
        with self.assertRaises(ValueError): installer.install(self.root)
        self.assertEqual((self.root/'p1_run.sh').read_text(),'user file\n')
        self.assertFalse((self.root/'patch_backups').exists())

    def test_install_error_rolls_back_original_files(self):
        original=(self.root/'run.py').read_bytes()
        atomic=installer.atomic_copy
        def fail(source,destination):
            if destination.name=='p1_run.sh': raise OSError('Injected write failure')
            return atomic(source,destination)
        with patch.object(installer,'atomic_copy',side_effect=fail):
            with self.assertRaises(OSError): installer.install(self.root)
        self.assertEqual((self.root/'run.py').read_bytes(),original)
        self.assertEqual(installer.sha(self.root/'package_manifest.json'),installer.BASE_MANIFEST)

if __name__=='__main__': unittest.main()
