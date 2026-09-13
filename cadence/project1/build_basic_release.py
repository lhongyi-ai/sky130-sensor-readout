#!/usr/bin/env python3
"""Build, validate and zip the basic-design delivery. Does not run Cadence."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

BASE=Path(__file__).resolve().parent
ROOT=BASE/'basic_design'
sys.path.insert(0,str(ROOT))
import build
import run

def skill_balance(text):
    depth=0;string=False;escape=False;comment=False
    for c in text:
        if comment:
            if c=='\n': comment=False
            continue
        if string:
            if escape: escape=False
            elif c=='\\': escape=True
            elif c=='"': string=False
            continue
        if c==';': comment=True
        elif c=='"': string=True
        elif c=='(': depth+=1
        elif c==')':
            depth-=1
            if depth<0: raise ValueError('Unbalanced SKILL close parenthesis')
    if depth or string: raise ValueError('Unbalanced SKILL/string: '+str(depth))

def main():
    build.build()
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'],capture_output=True,text=True)
    if test.returncode: raise RuntimeError(test.stdout+test.stderr)
    for path in ROOT.glob('*.il'): skill_balance(path.read_text())
    jobs=json.loads((ROOT/'jobs.json').read_text())
    for job in jobs:
        skill_balance(run.netlist_script(job,Path('/tmp/p1b_validation'),run.DEFAULT))
        skill_balance(run.export_script(job,Path('/tmp/p1b_validation'),{}))
    report=dict(status='PASS_LOCAL_CHECKS_ONLY',cadence_status='NOT_RUN',tests=re.sub(r'Ran (\d+) tests in [\d.]+s',r'Ran \1 tests (elapsed time omitted)',test.stderr),
                checks=['Frozen source and 52 raw PVT evidence hashes',
                        'Python behavior tests and original 13-point waveform measurement regression',
                        'SKILL lexical balance, 87 OCEAN netlist and 87 export scripts (not runtime validation)',
                        'Independent ZIP extraction and dependency/hash checks'],
                limitations=['No local Virtuoso, Spectre, school PDK or license execution',
                             'CDF callback behavior, native netlisting and result signal names await Linux execution'])
    (ROOT/'local_validation.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    exclude={'package_manifest.json','site.json','created.txt','create_status.txt','cdf_values.tsv','attempts.csv'}
    files=sorted(p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ['__pycache__','runs']) and p.name not in exclude and not p.name.endswith('.zip'))
    manifest=dict(version=build.VERSION,status='LOCAL_PREPARED_LINUX_NOT_RUN',files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (ROOT/'package_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    dest=BASE/'releases'/('project1_basic_design_v'+build.VERSION+'.zip');dest.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for path in files+[ROOT/'package_manifest.json']:
            info=zipfile.ZipInfo('project1_handoff/basic_design_v1_0_4/'+path.relative_to(ROOT).as_posix(),(2026,9,11,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,path.read_bytes())
    with tempfile.TemporaryDirectory(prefix='p1b_release_') as t:
        with zipfile.ZipFile(dest) as z:
            if z.testzip(): raise ValueError('Bad ZIP CRC')
            z.extractall(t)
        extracted=Path(t)/'project1_handoff/basic_design_v1_0_4'
        for arg in [['list'],['summary']]:
            result=subprocess.run([sys.executable,str(extracted/'run.py'),*arg],capture_output=True,text=True)
            if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        # The builder is also self-contained using the bundled frozen reference.
        result=subprocess.run([sys.executable,str(extracted/'build.py')],capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        result=subprocess.run([sys.executable,str(extracted/'run.py'),'list'],capture_output=True,text=True)
        if result.returncode: raise RuntimeError('Standalone rebuild is not deterministic: '+result.stderr)
    digest=hashlib.sha256(dest.read_bytes()).hexdigest()
    dest.with_suffix('.zip.sha256').write_text(digest+'  '+dest.name+'\n')
    print(json.dumps(dict(zip=str(dest),sha256=digest,files=len(files)+1,jobs=len(jobs),size_bytes=dest.stat().st_size),indent=2))

if __name__=='__main__': main()
