#!/usr/bin/env python3
"""Entry point checking every imported helper before a bounded reproduction."""
import argparse
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys
import qualify as q

def check():
    q.verify()
    binary=(q.HERE/'snapshot/cosim_controller_fixed.so').read_bytes()
    if binary[:4]!=b'\x7fELF' or binary[4:6]!=bytes([2,1]) or struct.unpack('<H',binary[18:20])[0]!=183:
        raise ValueError('unexpected repaired-bridge ELF identity')
    if platform.system()!='Linux' or platform.machine().lower() not in ('aarch64','arm64'):
        raise ValueError('LOCAL_RUNTIME_ONLY: bridge is Linux AArch64, not a qualified school-host binary')
    manifest=json.loads((q.HERE/'support/manifest.json').read_text())
    root=q.HERE.parents[3]
    for name,expected in manifest['active_source_sha256'].items():
        if q.sc.sha(root/name)!=expected:raise ValueError('active helper changed: '+name)
    for name,expected in manifest['snapshot_sha256'].items():
        if q.sc.sha(q.HERE/'support'/name)!=expected:raise ValueError('helper snapshot changed: '+name)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('profile',choices=('baseline','strict','check'))
    args=p.parse_args();check()
    if args.profile=='check':print('ALL_LOCAL_SOURCE_HASHES_MATCH');return 0
    return subprocess.run([sys.executable,str(q.HERE/'qualify.py'),'run',args.profile,'--timeout','900']).returncode

if __name__=='__main__':raise SystemExit(main())
