#!/usr/bin/env python3
"""Stdlib-only ZIP preflight and same-package school-canary gate. Python 3.6 syntax."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

STDLIB36=set(('__future__ abc argparse array ast base64 binascii bisect bz2 calendar cmath collections concurrent configparser contextlib copy csv ctypes datetime decimal difflib dis email enum errno faulthandler filecmp fileinput fnmatch fractions functools gc getopt getpass gettext glob gzip hashlib heapq hmac html http imaplib importlib inspect io ipaddress itertools json keyword linecache locale logging lzma math mimetypes mmap multiprocessing numbers operator os pathlib pickle pkgutil platform plistlib pprint queue random re resource sched select selectors shlex shutil signal site smtpd smtplib socket socketserver sqlite3 ssl stat statistics string struct subprocess sys tarfile tempfile textwrap threading time timeit tokenize traceback types typing unicodedata unittest urllib uuid warnings wave weakref webbrowser xml zipfile zlib').split())
MANIFEST='release_gate_manifest.json'

def sha(data):return hashlib.sha256(data).hexdigest()

def python36_tree(source,name):
    if sys.version_info[:2]==(3,6):return ast.parse(source,filename=name)
    try:return ast.parse(source,filename=name,feature_version=(3,6))
    except TypeError:raise ValueError('host Python cannot check the 3.6 grammar; use Python 3.6 or a supported local Python')

ELF_TARGETS={'x86_64':(64,'little',62),'aarch64':(64,'little',183)}
MACH_MAGIC={b'\xfe\xed\xfa\xce',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',b'\xca\xfe\xba\xbf',b'\xbf\xba\xfe\xca'}

def inspect_native(data,rel,target,errors):
    if data[:4] in MACH_MAGIC:
        errors.append('Mac Mach-O binary cannot be shipped to school Linux: '+rel);return None
    native=data.startswith(b'\x7fELF') or bool(re.search(r'\.so(?:\.\d+)*$',rel)) or rel.endswith('.dylib')
    if not native:return None
    if target not in ELF_TARGETS:errors.append('native binary requires declared supported school_target_machine: '+rel)
    if not data.startswith(b'\x7fELF') or len(data)<20:
        errors.append('native module is not a valid ELF header: '+rel);return None
    bits={1:32,2:64}.get(data[4]);endian={1:'little',2:'big'}.get(data[5])
    if bits is None or endian is None or data[6]!=1 or len(data)<(64 if bits==64 else 52):
        errors.append('invalid/truncated ELF class/endian/version/header: '+rel);return None
    machine=int.from_bytes(data[18:20],endian)
    if target in ELF_TARGETS and (bits,endian,machine)!=ELF_TARGETS[target]:errors.append('ELF architecture does not match school target: '+rel)
    return {'file':rel,'elf_class':bits,'endian':endian,'e_machine':machine}

def inspect_zip(path):
    errors=[]; result={'zip_sha256':sha(path.read_bytes()),'local_preflight_pass':False,'school_canary_pass':False,'batch_release_allowed':False,'errors':errors}
    try:
      with zipfile.ZipFile(str(path)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)):errors.append('duplicate ZIP member')
        bad=z.testzip()
        if bad:errors.append('ZIP CRC corruption: '+bad)
        roots=set()
        for i in infos:
            name=i.filename;p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or '\x00' in name or ':' in name:errors.append('unsafe ZIP path: '+name)
            if str(p)!=name.rstrip('/'):errors.append('non-canonical ZIP path: '+name)
            if any(c.isspace() for c in name):errors.append('whitespace inside ZIP path: '+name)
            if stat.S_ISLNK(i.external_attr >> 16):errors.append('ZIP symlink forbidden: '+name)
            if p.parts:roots.add(p.parts[0])
        if len(roots)!=1:errors.append('ZIP must have exactly one top-level directory');return result
        root=next(iter(roots));result['root_dir']=root
        if any('/' not in n.rstrip('/') for n in names if not n.endswith('/')):errors.append('file outside ZIP root')
        mname=root+'/'+MANIFEST
        if mname not in names:errors.append('complete release manifest missing');return result
        m=json.loads(z.read(mname).decode('utf-8'));result['release_id']=m.get('release_id')
        if not m.get('release_id') or m.get('root_dir')!=root:errors.append('release id/root mismatch')
        payload={n[len(root)+1:]:n for n in names if not n.endswith('/') and n!=mname}
        expected=m.get('files',{})
        if set(expected)!=set(payload):errors.append('manifest must cover every payload file exactly once')
        result['native_files']=[];result['school_target_machine']=m.get('school_target_machine')
        local_modules={PurePosixPath(n).stem for n in payload if n.endswith('.py')}
        for rel,full in payload.items():
            data=z.read(full)
            native=inspect_native(data,rel,m.get('school_target_machine'),errors)
            if native:result['native_files'].append(native)
            if expected.get(rel)!=sha(data):errors.append('SHA mismatch / mixed payload: '+rel)
            if 'patch_backups' in PurePosixPath(rel).parts:errors.append('historical patch backups must not enter a new release: '+rel)
            if rel.endswith(('.py','.sh','.il','.ocn')):
                if b'\r' in data:errors.append('CRLF/CR forbidden in school executable: '+rel)
                if data.startswith(b'\xef\xbb\xbf'):errors.append('UTF-8 BOM forbidden in executable: '+rel)
            if PurePosixPath(rel).name=='package_manifest.json':
                nested=json.loads(data.decode('utf-8'))
                if nested.get('version')!=m.get('version'):errors.append('mixed package versions: '+rel)
            if rel.endswith('.py'):
                try:tree=python36_tree(data.decode('utf-8'),rel)
                except (SyntaxError,ValueError,UnicodeError) as exc:errors.append('Python 3.6 syntax: '+rel+': '+str(exc));continue
                for node in ast.walk(tree):
                    modules=[]
                    if isinstance(node,ast.Import):modules=[n.name.split('.')[0] for n in node.names]
                    if isinstance(node,ast.ImportFrom) and node.level==0:modules=[(node.module or '').split('.')[0]]
                    for module in modules:
                        if module not in STDLIB36|local_modules:errors.append('non-Python-3.6-stdlib dependency: '+rel+': '+module)
                    if isinstance(node,ast.ImportFrom) and node.module=='__future__' and any(n.name=='annotations' for n in node.names):errors.append('future annotations unavailable in Python 3.6: '+rel)
                    if isinstance(node,ast.Call):
                        name=getattr(node.func,'id',getattr(node.func,'attr',''))
                        if name in ('__import__','import_module','exec','eval'):errors.append('dynamic dependency/code requires explicit review: '+rel)
                        if name in ('is_relative_to','fromisoformat','removeprefix','removesuffix'):errors.append('post-3.6 runtime API: '+rel+': '+name)
                        if any(k.arg in ('capture_output','text','dirs_exist_ok') for k in node.keywords):errors.append('post-3.6 keyword API: '+rel)
        result['file_count']=len(payload);result['manifest_sha256']=sha(z.read(mname))
        result['local_preflight_pass']=not errors
    except (OSError,ValueError,TypeError,KeyError,AttributeError,zipfile.BadZipFile,RuntimeError) as exc:errors.append('unreadable/corrupt package: '+str(exc))
    return result

FATAL_LOG = re.compile(r"\*Error\*|\bERROR\s*\(SPECTRE-[^)]+\)|\bFATAL\b|no such vector|undefined function|failed to find valid initialization|(?:export|output|result)[^\n]*(?:missing|failed|not found)|Traceback \(most recent call last\)",re.I)

def check_canary(result,path):
    errors=result['errors']
    result['school_canary_pass']=False;result['batch_release_allowed']=False
    if path is None:errors.append('same-package actual school canary is missing');return
    try:
        c=json.loads(path.read_text())
        if not isinstance(c,dict):raise ValueError('canary must be an object')
        env=c.get('environment',{})
        steps=c.get('steps',{});evidence=c.get('evidence',{})
        if not isinstance(env,dict) or not isinstance(steps,dict) or not isinstance(evidence,dict):raise ValueError('environment, steps and evidence must be objects')
        if c.get('package_zip_sha256')!=result['zip_sha256'] or c.get('release_id')!=result.get('release_id'):errors.append('stale or different-package canary')
        if c.get('execution_kind')!='ACTUAL_SCHOOL_CADENCE' or c.get('mock') is not False:errors.append('mock/local run cannot qualify a school canary')
        if env.get('python')!='3.6.8' or env.get('platform')!='Linux' or not str(env.get('virtuoso','')).startswith(('IC6.1.8','IC618')) or not str(env.get('spectre','')).startswith('21.'):errors.append('school environment mismatch')
        if c.get('completed') is not True or c.get('exit_code')!=0:errors.append('school canary did not complete successfully')
        required={'python_compile','native_create_or_open','spectre_canary','result_export'}
        if result.get('native_files'):
            required.add('native_load')
            if env.get('machine')!=result.get('school_target_machine'):errors.append('actual school canary machine mismatches native ELF target')
        if not required.issubset(steps):errors.append('school canary steps incomplete')
        if not evidence:errors.append('school raw evidence hashes missing')
        verified={}
        for rel,h in evidence.items():
            if not isinstance(rel,str) or not isinstance(h,str):errors.append('invalid evidence path/hash type');continue
            rp=PurePosixPath(rel)
            if rp.is_absolute() or '..' in rp.parts:errors.append('unsafe canary evidence path');continue
            p=path.parent/rel
            if not p.is_file():errors.append('missing canary raw evidence: '+rel);continue
            data=p.read_bytes()
            if not data or sha(data)!=h:errors.append('empty/stale canary raw evidence: '+rel);continue
            verified[rel]=data
        for name in required:
            step=steps.get(name,{})
            if not isinstance(step,dict):errors.append('invalid step object: '+name);continue
            log=step.get('log')
            if step.get('exit_code')!=0 or step.get('completed') is not True or not isinstance(log,str) or log not in verified:
                errors.append('missing successful evidence-bound step: '+name);continue
            text=verified[log].decode('utf-8',errors='replace')
            if FATAL_LOG.search(text):errors.append('fatal error in school raw log despite exit status: '+name)
            marker='P1_CANARY_STEP_V1 COMPLETE '+name+' '+result['zip_sha256']+' '+str(result.get('release_id'))
            if text.splitlines().count(marker)!=1:errors.append('missing/duplicate same-package V1 completion marker: '+name)
            if name=='native_load':
                modules=step.get('modules',[])
                if not isinstance(modules,list) or sorted(modules)!=sorted(x['file'] for x in result['native_files']):errors.append('native canary did not cover every shipped module')
            if name=='result_export':
                outputs=step.get('outputs',[])
                if not isinstance(outputs,list) or not outputs or not all(isinstance(x,str) and x!=log and x in verified for x in outputs):errors.append('exported result artifacts are missing/unverified')
        result['school_canary_pass']=not errors
        result['batch_release_allowed']=result['local_preflight_pass'] and result['school_canary_pass']
    except (OSError,ValueError,TypeError,AttributeError) as exc:errors.append('invalid canary: '+str(exc))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('zip',type=Path);ap.add_argument('--canary',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
    try:r=inspect_zip(args.zip)
    except OSError as exc:r={'local_preflight_pass':False,'batch_release_allowed':False,'errors':[str(exc)]}
    if r['local_preflight_pass']:check_canary(r,args.canary)
    r['status']='BATCH_RELEASE_ALLOWED' if r['batch_release_allowed'] else 'BATCH_RELEASE_BLOCKED'
    text=json.dumps(r,indent=2,ensure_ascii=False)+'\n'
    if args.output:args.output.write_text(text)
    print(text,end='');return 0 if r['batch_release_allowed'] else 2
if __name__=='__main__':sys.exit(main())
