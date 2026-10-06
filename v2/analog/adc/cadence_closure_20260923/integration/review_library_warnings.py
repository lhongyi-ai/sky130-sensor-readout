#!/usr/bin/env python3
"""Classify only exact observed library warnings; never change acceptance or suppress logs."""
import argparse,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def classify(run,allowlist):
 manifest=json.loads((run/'manifest.json').read_text())
 payload=run/'reset1_native_bound.scs'
 if sha(payload)!=manifest['generated_file_hashes']['reset1_native_bound.scs']:raise ValueError('Native payload hash differs')
 active=[]
 for k,count in [('adc',693),('phase',48)]:
  p=run/f'audits/{k}_native_audit.json'
  if sha(p)!=manifest['generated_file_hashes'][f'audits/{k}_native_audit.json']:raise ValueError('Native audit changed')
  report=json.loads(p.read_text())
  if report['status']!='NATIVE_NETLIST_AUDIT_PASS' or report['actual_count']!=count:raise ValueError('Native audit not qualified')
  active.extend(report['instances'])
 models=sorted(set(x['model'] for x in active));target={'res_generic_nd','res_generic_pd','sky130_fd_pr__res_generic_nd','sky130_fd_pr__res_generic_pd'}
 direct_absence=not set(models)&target and all(t not in payload.read_text() for t in target)
 known=set(allowlist['exact_observed_warning_lines'])
 occurrences=[];files={}
 for name in ['driver.log','xrun.log']:
  p=run/name
  if not p.exists():continue
  files[name]=sha(p)
  for i,line in enumerate(p.read_text(errors='replace').splitlines(),1):
   if not re.search(r'WARNING|Warning|\*W,|Newton iteration|LTE|minimum time step|relax',line):continue
   exact=line.strip()
   reviewed=direct_absence and exact in known
   occurrences.append({'file':name,'line':i,'text':line,'classification':'UNUSED_LIBRARY_PARSE_WARNING_REVIEWED' if reviewed else 'UNREVIEWED_WARNING_REQUIRES_SEPARATE_ANALYSIS','reason':'Exact warning text/path/model/line matches preserved v2 SPICE-parser evidence; all741native instances use other models.' if reviewed else 'Not an exact match to the two reviewed parser diagnostics.','automatically_waived':False})
 return {'status':'WARNING_CLASSIFICATION_ONLY_NO_ACCEPTANCE_CHANGE','active_native_instances':len(active),'active_native_models':models,'no_direct_generic_nd_pd_instances':direct_absence,'scope_limit':'This verifies the native741-instance graph. It does not establish all transitive internals of vendor model subcircuits; no PDK file was copied or modified.','known_warning_evidence_sha256':allowlist['evidence_hashes'],'current_log_hashes':files,'occurrences':occurrences,'counts':{'reviewed_exact_unused_library_parser':sum(x['classification']=='UNUSED_LIBRARY_PARSE_WARNING_REVIEWED' for x in occurrences),'unreviewed':sum(x['classification']!='UNUSED_LIBRARY_PARSE_WARNING_REVIEWED' for x in occurrences)},'automatic_gate_change':False,'retained_numerical_policy':'Original analyze.py remains conservative. LTE/recovery/time-step relaxation/save misses/host warnings are not waived by this classification.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise SystemExit('Refusing to overwrite review')
 allow=json.loads((HERE/'observed_library_warning_lines.json').read_text());r=classify(a.run,allow);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'status':r['status'],'counts':r['counts'],'no_direct_generic_nd_pd_instances':r['no_direct_generic_nd_pd_instances']}))
