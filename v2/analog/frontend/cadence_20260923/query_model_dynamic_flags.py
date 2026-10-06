#!/usr/bin/env python3
"""Read-only remote model metadata query. Never downloads PDK model bodies."""
from pathlib import Path
import hashlib
import json
import re
from virtuoso_bridge.env import set_runtime_env_file
from virtuoso_bridge.transport.tunnel import SSHClient

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
LOG=REPO/'v2/cadence/linuxlab_20260923/runs/spectre_poles_20260923T101120120043Z/spectre.out'
PDK='/opt/cadence/CDK/sky130_release_0.0.3/'
flags=['acnqsmod','trnqsmod','nqsmod','rgatemod','rbodymod','rdsmod','capmod','tnoimod','fnoimod']
files=[]
for p in re.findall(r'^Reading file:\s+(\S+)',LOG.read_text(),re.M):
    if not p.startswith(PDK): continue
    rel=p[len(PDK):]
    if re.match(r'cells/(?:n|p)fet_01v8(?:_lvt)?/',rel) or rel in ['models/sky130.lib.spice','models/all.spice']:
        if rel not in files:files.append(rel)
code=r'''import pathlib,re,json,hashlib,collections
base=pathlib.Path(PDK_ROOT)
out=[]
for rel in FILES:
 p=base/rel
 if not p.is_file():out.append({'relative_path':rel,'missing':True});continue
 raw=p.read_bytes();text=raw.decode('utf-8','replace')
 records={k:[] for k in FLAGS}
 model_count=0
 for no,line in enumerate(text.splitlines(),1):
  stripped=line.strip()
  if not stripped or stripped.startswith(('*','//')):continue
  if re.match(r'(?i)\.model\s',stripped):model_count+=1
  for k in FLAGS:
   for match in re.finditer(r'(?i)\b'+k+r'\s*=\s*([^\s,)]+)',line):
    records[k].append({'line':no,'value':match.group(1)})
 out.append({'relative_path':rel,'sha256':hashlib.sha256(raw).hexdigest(),
             'model_declaration_count':model_count,
             'flags':{k:{'count':len(v),'value_counts':dict(collections.Counter(x['value'] for x in v)),
                         'line_numbers':[x['line'] for x in v]} for k,v in records.items() if v}})
print(json.dumps({'files':out,'model_contents_returned':False}))
'''.replace('PDK_ROOT',repr(PDK)).replace('FILES',repr(files)).replace('FLAGS',repr(flags))
output=HERE/'school_model_dynamic_flags_readonly.json'
if output.exists():raise SystemExit('Existing evidence preserved.')
set_runtime_env_file(str(Path.home()/'.virtuoso-bridge/.env'))
c=SSHClient.from_env(keep_remote_files=True)
r=c.spectre_runner.run_command("python3 - <<'P1_READ_FLAGS'\n"+code+"\nP1_READ_FLAGS\n",timeout=45)
if r.returncode:raise SystemExit('Remote read-only query failed: '+r.stderr)
d=json.loads(r.stdout)
d['source_log']=str(LOG.relative_to(REPO));d['source_log_sha256']=hashlib.sha256(LOG.read_bytes()).hexdigest()
d['query_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
d['scope']='Only flags, counts, line numbers and SHA256 from four MOS families loaded by the actual r1 PZ run; no simulation, no model bodies copied.'
output.write_text(json.dumps(d,indent=2)+'\n')
for f in d['files']:
    print(f['relative_path'],{k:v['value_counts'] for k,v in f.get('flags',{}).items()})
