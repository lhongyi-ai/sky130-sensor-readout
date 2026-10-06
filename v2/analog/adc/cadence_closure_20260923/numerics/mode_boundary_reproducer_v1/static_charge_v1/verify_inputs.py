from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parent;m=json.loads((R/'manifest.json').read_text())
for name,p in m['profiles'].items():
 s=(R/p['file']).read_text();assert hashlib.sha256(s.encode()).hexdigest()==p['sha256'];assert m['device_record'] in s
 assert 'what=models' not in s and 'tran ' not in s
 assert 'vsource dc=0.91642555277800053' in s and 'vsource dc=1.8' in s
 assert len(re.findall(r'^dc_\S+ dc ',s,re.M))==4
 for n,sw in p['sweeps'].items():
  l=next(l for l in s.splitlines() if l.startswith(n+' dc '));assert ('lin='+str(sw['lin_steps'])+' ') in l
  assert sw['expected_points']==sw['lin_steps']+1
 assert 'rbodymod=' not in s and 'capmod=' not in s
assert not m['complete_ADC'] and not m['full_ADC_accuracy_pass']
print('STATIC_INPUT_CHECK_PASS: exactMOSshape, documentedcharge/C fields,4DCsweeps/profile,noPDKselectoroverride,noADCclaim')
