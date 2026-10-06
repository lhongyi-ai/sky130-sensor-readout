#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parent
m=json.loads((R/'manifest.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(R/'native_closed.scs')==m['native_sha256']
for p in m['profiles'].values():assert sha(R/p['file'])==p['sha256']
s=(R/'native_closed.scs').read_text();actual=[];sub=None
for l in s.splitlines():
 if l.startswith('subckt '):sub=l.split()[1]
 elif l.startswith('X'):
  name=l.split()[0];actual.append((name,hashlib.sha256(' '.join(l.split()).encode()).hexdigest()))
assert len(actual)==654 and len(set(n for n,h in actual))==654
expected=[(r['instance'],r['normalized_record_sha256']) for r in m['records']]
assert actual==expected
base=(R/'input_baseline.scs').read_text();strict=(R/'input_strict.scs').read_text()
def norm(t):
 return re.sub(r'(reltol|vabstol|iabstol|maxstep)=[^\s]+',lambda x:x[1]+'=PROFILE',t)
assert norm(base)==norm(strict)
assert 'XPHASE (SAMPLE_CMD TOP TOPB ACQ CONV VDD 0) sensor_phases' in base
assert len(m['fanout']['CONV'])==104
assert not re.search(r'^\S+ \(CONV [^\n]+\) (?:vsource|capacitor)',base,re.M)
assert m['expected_completed_frames']==0 and not m['complete_ADC']
print('FROZEN_INPUTS_PASS:654 unchanged native instances;104 CONV gate fanout;2 numerical-only profiles; no ADC completion claim')
