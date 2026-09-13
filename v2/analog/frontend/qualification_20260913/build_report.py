#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,j):p.write_text(json.dumps(j,indent=2,allow_nan=False)+'\n')
rows=[];local=[];noise=[];matrix=[];pz=[];fail=[];canary=[]
for folder in sorted((HERE/'runs').iterdir()):
 if not (folder/'summary.json').exists():continue
 m=json.loads((folder/'manifest.json').read_text())
 for name,x in m['files'].items():
  if sha(folder/name)!=x['sha256']:raise ValueError(str(folder/name))
 j=json.loads((folder/'summary.json').read_text());j['path']=str(folder.relative_to(HERE));rows.append(j)
 if j['status'].startswith('COUPLED_PORT'):
  # Exact driver bytes are appended without rewriting the original manifest.
  target=folder/'multiport_driver_snapshot.py'
  if not target.exists():target.write_bytes((HERE/'run_multiport.py').read_bytes())
  provenance=folder/'supplemental_provenance.json'
  if not provenance.exists():save(provenance,{'original_manifest_sha256':sha(folder/'manifest.json'),'multiport_driver_snapshot_sha256':sha(target),'note':'Exact driver used for these six runs; appended before report publication. Original evidence remains unmodified.'})
  matrix.append(j)
 elif j['status']=='BILATERAL_LOCAL_DIAGNOSTICS_COMPLETE':local.append(j)
 elif j['status']=='STATIC_NOISE_DIAGNOSTIC_COMPLETE':
  c=abs(j['calibration_record']['calibration_coefficients'][0]);j['calibrated_output_rms_v']={k:c*v for k,v in j['output_rms_v'].items()}
  j['noise_formal_pass']=None
  j['budget_comparison_scope']='Diagnostic only. 113 uV is an older provisional frontend output screen, not a frozen sampled-noise limit for this exact resistor-input PGA/filter and sampler phase. This run is 1 Hz–1 GHz continuous-time output noise at FP-FN, including 350 ohm/leg source noise; acquisition/hold fixed states. No switching noise folding or 65 dB SNDR assertion.'
  noise.append(j)
 elif j['status']=='LOCAL_G4_CANARY_COMPLETE':
  target=folder/'canary_driver_snapshot.py'
  if not target.exists():target.write_bytes((HERE/'run_canary.py').read_bytes())
  provenance=folder/'supplemental_provenance.json'
  if not provenance.exists():save(provenance,{'original_manifest_sha256':sha(folder/'manifest.json'),'canary_driver_snapshot_sha256':sha(target)})
  canary.append(j)
 elif j['kind']=='pz':pz.append(j)
 else:fail.append(j)
report={'generated_utc':datetime.now(timezone.utc).isoformat(),'status':'LOCAL_PROGRESS__FORMAL_STABILITY_AND_SAMPLED_NOISE_NOT_QUALIFIED','candidate_sha256':sha(HERE/'candidate_06.spice'),'real_simulator_runs':len(rows),'simulator_runs_with_postprocess_failure':len(fail),'formal_stability_gate_pass':False,'sampled_noise_qualified':False,'pvt_45_run':False,'pvt_skip_reason':'Formal stability prerequisite remains unresolved. No relaxation of acceptance thresholds.','cadence_executed':False,'circuit_modified':False,'local_bilateral':local,'coupled_multiport':matrix,'static_noise':noise,'closed_loop_pz':pz,'migration_canary':canary,'preserved_failures':fail}
save(HERE/'qualification.json',report)
print(json.dumps({'runs':len(rows),'local':len(local),'matrix':len(matrix),'noise':len(noise),'pz':len(pz),'failures':len(fail)}))
