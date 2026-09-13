#!/usr/bin/env python3
"""Install OP export recovery on an intact 1.0.4p2 runtime (Python 3.6+)."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

HERE=Path(__file__).resolve().parent
BASE_MANIFEST='3502851b9bacef25d0c2e9f21aee3aef4de3baf5a88e9e7476bde57417e54933'
FILES=('run.py','analyze.py','passive_review.py','runtime_patch.json','package_manifest.json')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_package(root,manifest):
    for name,digest in manifest['files'].items():
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid manifest path: '+name)
        path=root/relative
        if not path.is_file() or path.is_symlink() or sha(path)!=digest:
            raise ValueError('Package file changed or missing: '+name)

def atomic_copy(source,destination):
    temp=destination.with_name(destination.name+'.p1tmp_'+uuid.uuid4().hex)
    try:
        with temp.open('xb') as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temp),str(destination))
    finally:
        if temp.exists(): temp.unlink()

def install(root):
    root=root.resolve()
    patch=json.loads((HERE/'patch_manifest.json').read_text())
    if set(patch['payload'])!=set(FILES):
        raise ValueError('Unexpected patch payload')
    for name,digest in patch['payload'].items():
        if sha(HERE/'payload'/name)!=digest:
            raise ValueError('Patch checksum mismatch: '+name)
    manifest_path=root/'package_manifest.json'
    current=json.loads(manifest_path.read_text())
    if sha(manifest_path)==patch['payload']['package_manifest.json']:
        verify_package(root,current)
        print('P1_RUNTIME_PATCH_ALREADY_APPLIED: 1.0.4p3')
        return
    if sha(manifest_path)!=BASE_MANIFEST:
        raise ValueError('This fix requires basic_design_v1_0_4 with runtime patch 1.0.4p2')
    verify_package(root,current)
    backup=root/'patch_backups'/'v1_0_4p3'
    if backup.exists():
        raise ValueError('Previous patch backup exists; preserve it and report this message')
    backup.mkdir(parents=True)
    for name in FILES:
        shutil.copy2(str(root/name),str(backup/name))
    written=[]
    try:
        # The package manifest is the last file replaced, after all payloads.
        for name in FILES:
            atomic_copy(HERE/'payload'/name,root/name)
            written.append(name)
        verify_package(root,json.loads(manifest_path.read_text()))
    except Exception:
        for name in reversed(written):
            if (backup/name).exists(): atomic_copy(backup/name,root/name)
            else: (root/name).unlink()
        raise
    print('P1_RUNTIME_PATCH_APPLIED: 1.0.4p3')
    print('Existing site.json, cells, created.txt and runs preserved.')
    print('Next, in the Linux terminal:')
    print('bash ~/cadence_skywater/p1_school_run_v1.sh recheck-passives')

if __name__=='__main__':
    try:
        if len(sys.argv)!=2: raise ValueError('Usage: install.py /path/to/basic_design_v1_0_4')
        install(Path(sys.argv[1]))
    except Exception as error:
        print('P1_RUNTIME_PATCH_STOPPED: '+str(error),file=sys.stderr)
        sys.exit(1)
