#!/usr/bin/env python3
"""Local scope/hash guard; does not certify Spectre execution."""
from pathlib import Path
import hashlib, json, re, sys
root = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
m = json.loads((root/'manifest.json').read_text())
assert m['status'] == 'PREPARED_NOT_RUN'
assert not any(m[k] for k in ['complete_ADC', 'full_ADC_accuracy_pass', 'formal_ADC_PEX_allowed'])
assert [x['delta_D_minus_SB_V'] for x in m['cases'].values()] == [-20e-6,-5e-6,-1e-6,0,1e-6,5e-6,20e-6]
for name, case in m['cases'].items():
    p = root/case['input_path']; t = p.read_text()
    assert hashlib.sha256(p.read_bytes()).hexdigest() == case['sha256'], name
    assert t.splitlines().count(m['device_line']) == 1
    assert t.splitlines().count(m['model_include']) == 1
    assert 'VG (G 0) vsource dc=0.91642555277800053 type=dc mag=0 phase=0' in t
    assert 'VS (SB 0) vsource dc=1.8 type=dc mag=0 phase=0' in t
    assert 'VD (D 0) vsource dc=1.8+VDELTA type=dc mag=1 phase=0' in t
    assert float(re.search(r'^parameters VDELTA=(.+)$', t, re.M)[1]) == case['delta_D_minus_SB_V']
    assert len(re.findall(r'^\w+ ac ', t, re.M)) == 1
    assert 'acBoundary ac start=1000 stop=10000000 dec=10 ' in t
    assert not re.search(r'\b(rbodymod|capmod|cvchargemod|cmin)\s*=\s*(?!0\b)', t)
    assert not re.search(r'^\w+ tran\b|what=models|^model\b', t, re.M)
assert hashlib.sha256((root/'limited_model_metadata.py').read_bytes()).hexdigest()==m['metadata_script_sha256']
print('P1_AC_LOCAL_INPUT_SCOPE_AND_HASH_CHECK_PASS_NOT_EDA')
