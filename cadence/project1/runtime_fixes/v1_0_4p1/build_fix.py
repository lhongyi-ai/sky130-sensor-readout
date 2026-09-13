#!/usr/bin/env python3
"""Build the small runtime patch without changing the frozen full-package ZIP."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

FIX=Path(__file__).resolve().parent
BASE=FIX.parents[1]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    original=BASE/'basic_design/package_manifest.json'
    if sha(original)!='ba14bebdf9d118cebcd415ae9a79cb3900b0a4d3ac19c95811c5d007d08f3f33':
        raise ValueError('Base source manifest changed')
    metadata=dict(id='1.0.4p1',kind='runtime_only',base_package_version='1.0.4',
        base_package_manifest_sha256=sha(original),schematic_generation='UNCHANGED',cadence_status='NOT_RUN',
        changes=['Select same-directory top-level native body from OCEAN-returned input.scs',
                 'Keep system Python library environment separate from Cadence child processes',
                 'Preserve native input and selection hashes; display both result statuses'],
        evidence='User-reported school res_dc attempt 20260912T091436Z_823bf643; two native bodies with identical displayed content')
    write(FIX/'payload/runtime_patch.json',metadata)
    manifest=json.loads(original.read_text())
    manifest['version']='1.0.4p1'
    manifest['runtime_patch']='1.0.4p1'
    for name in ['run.py','p1_run.sh','runtime_patch.json']:
        manifest['files'][name]=sha(FIX/'payload'/name)
    write(FIX/'payload/package_manifest.json',manifest)
    write(FIX/'patch_manifest.json',dict(id='1.0.4p1',payload={name:sha(FIX/'payload'/name) for name in ['run.py','p1_run.sh','runtime_patch.json','package_manifest.json']}))
    for path in list((FIX/'payload').glob('*.py'))+[FIX/'install.py']:
        ast.parse(path.read_text(),feature_version=(3,6))
    for path in [FIX/'apply.sh',FIX/'payload/p1_run.sh']:
        subprocess.run(['bash','-n',str(path)],check=True)
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(FIX/'tests'),'-v'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    (FIX/'local_validation.log').write_text(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    write(FIX/'local_validation.json',dict(status='PASS_LOCAL_CHECKS_ONLY',cadence_status='NOT_RUN',
        checks=['Python 3.6 syntax compatibility (no actual Linux interpreter/loader validation)',
                'Top-level selection with two netlists, missing/stale/internal paths and wrong circuit rejection',
                'Subprocess environment, stdin and exit-code propagation; shell argument forwarding',
                'Clean ZIP install, repeat install, conflict rejection, rollback and old-state preservation',
                '87-job CLI and original 17 behavior regressions against patched installation'],
        limitation='No local Virtuoso, school PDK, Spectre or license execution'))
    files=[p for p in FIX.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    destination=BASE/'releases/project1_basic_runtime_fix_v1.0.4p1.zip'
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info=zipfile.ZipInfo('project1_handoff/basic_runtime_fix_v1_0_4p1/'+path.relative_to(FIX).as_posix(),(2026,9,12,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            archive.writestr(info,path.read_bytes())
    destination.with_suffix('.zip.sha256').write_text(sha(destination)+'  '+destination.name+'\n')
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip(): raise ValueError('ZIP integrity check failed')
    print(json.dumps(dict(zip=str(destination),sha256=sha(destination),size_bytes=destination.stat().st_size),indent=2))

if __name__=='__main__': main()
