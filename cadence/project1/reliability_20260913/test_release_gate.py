import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from release_gate import inspect_zip,check_canary,python36_tree

class GateTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
    def package(self,payload=None,extra=None,target=None):
        files=payload or {'run.py':b'import json\nprint(json.dumps({"ok": True}))\n'}
        m={'release_id':'synthetic-v1','version':'1','root_dir':'synthetic_v1','files':{n:hashlib.sha256(d).hexdigest() for n,d in files.items()}}
        if target:m['school_target_machine']=target
        p=self.base/'external path with spaces.zip'
        with zipfile.ZipFile(str(p),'w') as z:
            for n,d in files.items():z.writestr('synthetic_v1/'+n,d)
            z.writestr('synthetic_v1/release_gate_manifest.json',json.dumps(m))
            if extra:
                for n,d in extra.items():z.writestr(n,d)
        return p
    def test_clean_local_package_still_cannot_release(self):
        r=inspect_zip(self.package());self.assertTrue(r['local_preflight_pass']);check_canary(r,None);self.assertFalse(r['batch_release_allowed'])
    def test_multiple_roots_and_unlisted_file_rejected(self):
        for extra in [{'second/run.py':b''},{'synthetic_v1/old.py':b''}]:self.assertFalse(inspect_zip(self.package(extra=extra))['local_preflight_pass'])
    def test_crlf_internal_spaces_new_syntax_dependency_rejected(self):
        for payload in [{'run.py':b'print(1)\r\n'},{'bad name.py':b'print(1)\n'},{'run.py':b'if (x := 1): print(x)\n'},{'run.py':b'import numpy\n'},{'run.py':b'import dataclasses\n'}]:self.assertFalse(inspect_zip(self.package(payload))['local_preflight_pass'])
    def test_wrong_sha_rejected(self):
        p=self.package()
        with zipfile.ZipFile(str(p)) as z:payload={n:z.read(n) for n in z.namelist()}
        payload['synthetic_v1/run.py']=b'print(999)\n'
        with zipfile.ZipFile(str(p),'w') as z:
            for n,d in payload.items():z.writestr(n,d)
        self.assertTrue(any('SHA mismatch' in x for x in inspect_zip(p)['errors']))
    def test_corrupted_zip_rejected(self):
        p=self.base/'broken.zip';p.write_bytes(b'not a ZIP');self.assertFalse(inspect_zip(p)['local_preflight_pass'])
    def test_mixed_version_rejected(self):
        self.assertFalse(inspect_zip(self.package({'package_manifest.json':b'{"version":"old"}'}))['local_preflight_pass'])
    def test_stale_mock_canary_rejected(self):
        r=inspect_zip(self.package());p=self.base/'canary.json';p.write_text(json.dumps({'package_zip_sha256':'0'*64,'release_id':'old','execution_kind':'LOCAL_MOCK','mock':True}))
        check_canary(r,p);self.assertFalse(r['batch_release_allowed']);self.assertIn('stale or different-package canary',r['errors'])
    def synthetic_canary(self,result,fatal=None,omit_marker=False):
        steps={};evidence={}
        for name in ['python_compile','native_create_or_open','spectre_canary','result_export']:
            data=('P1_CANARY_STEP_V1 COMPLETE '+name+' '+result['zip_sha256']+' '+result['release_id']+'\n') if not omit_marker else 'no completion marker\n'
            if fatal and name=='spectre_canary':data=fatal+'\n'+data
            rel=name+'.log';(self.base/rel).write_text(data);evidence[rel]=hashlib.sha256((self.base/rel).read_bytes()).hexdigest()
            steps[name]={'completed':True,'exit_code':0,'log':rel}
        (self.base/'export.csv').write_text('x,y\n0,1\n');evidence['export.csv']=hashlib.sha256((self.base/'export.csv').read_bytes()).hexdigest();steps['result_export']['outputs']=['export.csv']
        c={'package_zip_sha256':result['zip_sha256'],'release_id':result['release_id'],'execution_kind':'ACTUAL_SCHOOL_CADENCE','mock':False,'completed':True,'exit_code':0,'environment':{'platform':'Linux','python':'3.6.8','virtuoso':'IC6.1.8','spectre':'21.1'},'steps':steps,'evidence':evidence}
        p=self.base/'synthetic_canary.json';p.write_text(json.dumps(c));return p
    def test_same_package_exit_zero_fatal_raw_log_rejected(self):
        for fatal in ['*Error* invalid CDF','ERROR (SPECTRE-16385): circuit failed','no such vector vout','result export missing']:
            r=inspect_zip(self.package());p=self.synthetic_canary(r,fatal=fatal);check_canary(r,p)
            self.assertFalse(r['batch_release_allowed']);self.assertTrue(any('fatal error in school raw log' in x for x in r['errors']))
    def test_missing_raw_completion_marker_rejected(self):
        r=inspect_zip(self.package());p=self.synthetic_canary(r,omit_marker=True);check_canary(r,p)
        self.assertFalse(r['batch_release_allowed']);self.assertTrue(any('completion marker' in x for x in r['errors']))
    def test_nonobject_canary_steps_evidence_rejected(self):
        for field in [None,'steps','evidence','environment']:
            r=inspect_zip(self.package());p=self.synthetic_canary(r);c=json.loads(p.read_text())
            if field is None:c=[]
            else:c[field]=[]
            p.write_text(json.dumps(c));check_canary(r,p);self.assertFalse(r['batch_release_allowed']);self.assertTrue(any('invalid canary' in x for x in r['errors']))
    def elf_header(self,machine):
        data=bytearray(64);data[:7]=b'\x7fELF\x02\x01\x01';data[18:20]=machine.to_bytes(2,'little');data[52:54]=(64).to_bytes(2,'little');return bytes(data)
    def test_arm_bridge_rejected_for_x86_school(self):
        r=inspect_zip(self.package({'bridge.so':self.elf_header(183)},target='x86_64'))
        self.assertFalse(r['local_preflight_pass']);self.assertTrue(any('ELF architecture does not match' in x for x in r['errors']))
    def test_correct_elf_metadata_does_not_grant_school_release(self):
        r=inspect_zip(self.package({'bridge.so':self.elf_header(62)},target='x86_64'))
        self.assertTrue(r['local_preflight_pass']);self.assertEqual(r['native_files'][0]['elf_class'],64);check_canary(r,None);self.assertFalse(r['batch_release_allowed'])
    def test_checker_itself_has_python36_syntax(self):python36_tree(Path(__file__).with_name('release_gate.py').read_text(),'release_gate.py')
if __name__=='__main__':unittest.main(verbosity=2)
