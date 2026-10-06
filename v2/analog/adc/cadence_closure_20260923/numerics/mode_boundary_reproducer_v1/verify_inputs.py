#!/usr/bin/env python3
import hashlib,json,re
from pathlib import Path
p=Path(__file__).resolve().parent
m=json.loads((p/'manifest.json').read_text())
for name,want in m['file_hashes'].items():
 if hashlib.sha256((p/name).read_bytes()).hexdigest()!=want:raise SystemExit('Hash mismatch '+name)
for case,c in m['cases'].items():
 texts=[]
 for profile,x in c['files'].items():
  t=(p/x['relative_path']).read_text()
  if hashlib.sha256(t.encode()).hexdigest()!=x['sha256']:raise SystemExit('Input hash mismatch')
  for key in ['reltol','vabstol','iabstol','maxstep']:t=re.sub(r'\b'+key+r'=\S+',key+'=<precision>',t)
  texts.append(t)
 if texts[0]!=texts[1]:raise SystemExit('Nonprecision change in '+case)
print('INPUT_INTEGRITY_ONLY_OK; NOT A SIMULATION PASS')
