#!/usr/bin/env python3
"""Read-only selected literals/hash metadata, not a model-file export."""
import hashlib,json,re,sys
from pathlib import Path
BASE=Path('/opt/cadence/CDK/sky130_release_0.0.3')
FILES=[BASE/'models/sky130.lib.spice',BASE/'cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.corner.spice',BASE/'cells/pfet_01v8/sky130_fd_pr__pfet_01v8__tt.pm3.spice']
ALLOWED=['level','version','capmod','cvchargemod','rbodymod','rdsmod','rgatemod','trnqsmod','acnqsmod','xpart','rbpb','rbpd','rbps','rbdb','rbsb','gbmin','tnom']
out={'scope':'SELECTED_FILE_LITERALS_AND_HASHES_ONLY','effective_selected_bin_verified':False,'note':'Counts span modelbins. Missingliteral isunknownhere; do not substitutehelpdefault or claim effectiveinstancevalue. NoPDKfilebody exported.','files':[]}
for p in FILES:
 b=p.read_bytes();entry={'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
 if p.name.endswith('.pm3.spice'):
  s=b.decode(errors='strict');literal={n:[] for n in ALLOWED};nonliteral={n:0 for n in ALLOWED}
  number=re.compile(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?')
  for line in s.splitlines():
   if line.lstrip().startswith(('*','//')):continue
   line=line.split('//',1)[0].split('$',1)[0]
   assignments=list(re.finditer(r'(?i)(?<![\w])([a-z_]\w*)\s*=\s*',line))
   for i,a in enumerate(assignments):
    n=a[1].lower()
    if n not in literal:continue
    end=assignments[i+1].start() if i+1<len(assignments) else len(line)
    value=line[a.end():end].strip().rstrip(')').strip()
    if number.fullmatch(value):literal[n].append(value)
    else:nonliteral[n]+=1
  d={n:{'literal_values':sorted(set(literal[n])),'occurrences':len(literal[n]),'nonliteral_assignments_not_evaluated':nonliteral[n],'effective_instance_value':'NOT_DETERMINED'} for n in ALLOWED}
  entry['selected_parameter_literals']=d
 out['files'].append(entry)
Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+'\n')
