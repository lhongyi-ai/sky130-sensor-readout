#!/usr/bin/env python3
"""Verify frozen diagnostic inputs without invoking any EDA tool."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'manifest.json').read_text())
for name,expected in manifest['generated_file_hashes'].items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Hash mismatch: '+name)
for name,expected in manifest['source_probe_hashes'].items():
    if name=='amsdControl.scs':continue
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
        raise SystemExit('Non-save change from verified probe: '+name)
control=(ROOT/'amsdControl.scs').read_text()
for line in manifest['new_save_requests']:
    if control.count(line+'\n')!=1:raise SystemExit('Missing/duplicated new save')
    control=control.replace(line+'\n','')
if hashlib.sha256(control.encode()).hexdigest()!=manifest['source_probe_hashes']['amsdControl.scs']:
    raise SystemExit('Change beyond the four approved save statements')
print('P1_BODY_NETWORK_INPUT_HASHES_OK: PREPARED_ONLY, NOT A SIMULATION PASS')
