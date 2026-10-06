#!/usr/bin/env python3
"""Bounded read-only statistics-entry inventory; return metadata, never PDK bodies."""
from pathlib import Path
import json
import hashlib
import re
from virtuoso_bridge.env import set_runtime_env_file
from virtuoso_bridge.transport.tunnel import SSHClient

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
LOG=REPO/'v2/cadence/linuxlab_20260923/runs/spectre_poles_20260923T101120120043Z/spectre.out'
PDK='/opt/cadence/CDK/sky130_release_0.0.3/'
selected=['models/sky130.lib.spice','models/all.spice','models/r+c.mrp1monte.spice',
          'models/parameters/typical.spice','models/parameters/lod.spice']
for p in re.findall(r'^Reading file:\s+(\S+)',LOG.read_text(),re.M):
    if p.startswith(PDK):
        rel=p[len(PDK):]
        if re.match(r'cells/(?:n|p)fet_01v8(?:_lvt)?/',rel):selected.append(rel)
selected=list(dict.fromkeys(selected))
code=r'''from pathlib import Path
import json,re,hashlib,collections
root=Path(PDKROOT);out=[]
for rel in FILES:
 p=root/rel
 if not p.is_file():out.append({'path':rel,'missing':True});continue
 raw=p.read_bytes();text=raw.decode('utf-8','replace');active=[];comment_hints=[]
 for n,line in enumerate(text.splitlines(),1):
  if line.lstrip().startswith(('*','//')):
   for k in ['statistics','mismatch','monte','gauss','random']:
    if k in line.lower():comment_hints.append({'line':n,'keyword':k})
   continue
  line=re.split(r'\s(?:\$|//)',line,maxsplit=1)[0]
  if line.lstrip().startswith('+') and active:active[-1][1]+=' '+line.lstrip()[1:]
  else:active.append([n,line])
 sections=[];includes=[];syntax=[];random_calls=[];switches=[]
 for n,line in active:
  m=re.match(r'(?i)^\s*\.lib\s+(\S+)\s*$',line)
  if m:sections.append({'line':n,'section':m.group(1)})
  m=re.match(r'(?i)^\s*(?:\.include|include)\s+["\']?([^"\'\s]+)',line)
  if m and (rel=='models/sky130.lib.spice' or re.search('mismatch|monte|stat|random',m.group(1),re.I)):
   includes.append({'line':n,'include':m.group(1)})
  for keyword in ['statistics','mismatch','process','vary','montecarlo']:
   if re.search(r'(?i)(?:^|\s)'+keyword+r'(?:\s*\{|\s+\w+)',line):
    syntax.append({'line':n,'keyword':keyword})
  funcs=re.findall(r'(?i)\b(agauss|gauss|aunif|unif|random|normal|lognormal|sgauss|mc_mm|mc_pr)\s*\(',line)
  if funcs:
   param=re.match(r'(?i)^\s*\.param\s+([^\s=]+)',line)
   random_calls.append({'line':n,'functions':funcs,'parameter':param.group(1) if param else None})
  for m in re.finditer(r'(?i)\b(mc_(?:mm|pr)_switch|sw_mm|sw_pr|mismatch_switch|process_switch)\s*=\s*([^\s]+)',line):
   switches.append({'line':n,'parameter':m.group(1),'value':m.group(2)})
 out.append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'section_names':sections,
   'include_entry_paths':includes,'active_statistics_syntax_hits':syntax,'active_random_function_calls':random_calls,
   'mc_switch_parameters':switches,'comment_keyword_counts':dict(collections.Counter(x['keyword'] for x in comment_hints)),
   'active_param_statement_count':sum(bool(re.match(r'(?i)^\s*\.param\b',l)) for _,l in active)})
print(json.dumps({'files':out,'raw_model_text_returned':False}))
'''.replace('PDKROOT',repr(PDK)).replace('FILES',repr(selected))
output=HERE/'school_statistics_entry_metadata.json'
if output.exists():raise SystemExit('Existing evidence preserved.')
set_runtime_env_file(str(Path.home()/'.virtuoso-bridge/.env'))
c=SSHClient.from_env(keep_remote_files=True)
r=c.spectre_runner.run_command("python3 - <<'P1_STAT_METADATA'\n"+code+"\nP1_STAT_METADATA\n",timeout=45)
if r.returncode:raise SystemExit(r.stderr)
d=json.loads(r.stdout);d['scope']='Bounded selected current top library, currently loaded four MOS families and three parameter/R-C entry files. No recursive PDK scan, no simulation.'
d['source_log_sha256']=hashlib.sha256(LOG.read_bytes()).hexdigest();d['query_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
output.write_text(json.dumps(d,indent=2)+'\n')
for f in d['files']:
 print(f['path'],{k:f.get(k) for k in ['section_names','active_statistics_syntax_hits','active_random_function_calls','mc_switch_parameters','active_param_statement_count']})
