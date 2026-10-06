#!/usr/bin/env python3
"""Analyze preserved adaptive_trap runs only; no simulation, relaxed gate, or shifted time."""
import csv, hashlib, json, re, sys
from collections import Counter
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
CLOSURE=HERE.parents[1]
sys.path.insert(0,str(CLOSURE/'numerics'))
from psf_stream import Trace
P='p2_ams_reset1.'
CHANNELS={'cdac_differential':('adc.XADC_TP','adc.XADC_TN'),'rp':('rp',),'rn':('rn',),'vcm':('vcm',)}
LIMIT=.05*.8/4096
RUN=CLOSURE/'runs/task_20260924T073009937369Z/design'
FILES=['sar_controller.v','p1_interfaces.vams','p2_ams_reset1.vams','p2_sequence.sv','profile.vh','reset1_native_bound.scs']
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def raw(run,short=False):
 p=run/'amsdControl.raw/adc_closure_tran.tran.tran'
 tr=Trace(p,wanted={P+n for c in CHANNELS.values() for n in c});rows=[]
 for row in tr.rows():
  rows.append(row)
  if short and row['time']>=4.1e-6:break
 t=np.array([x['time'] for x in rows]);v={}
 for name,c in CHANNELS.items():
  v[name]=np.array([x[P+c[0]]-(x[P+c[1]] if len(c)==2 else 0) for x in rows])
 return t,v,{'raw_sha256':sha(p),'raw_path':str(p),'actual_header':tr.header,'rows_read':len(rows),
   'initial_time_s':float(t[0]),'last_time_s':float(t[-1]),'all_voltage_trace_names':tr.names,
   'identical_duplicate_rows':tr.identical_duplicate_rows}
def logs(run):
 log=(run/'xrun.log').read_text(errors='replace')
 patterns={'accepted_steps':r'Total Number of Accepted steps\s*:\s*(\d+)',
 'LTE_rejections':r'Number of LTE rejected steps\s*:\s*(\d+)',
 'Newton_rejections':r'Number of Newton rejected steps\s*:\s*(\d+)',
 'device_rejections':r'Number of Device rejected steps\s*:\s*(\d+)',
 'recovery_steps':r'Number of steps to recover from drastic step size drop\s*=\s*(\d+)',
 'minimum_step_s':r'Minimum time step\s*=\s*([\deE+.-]+)'}
 counts={k:(float(m[1]) if k=='minimum_step_s' else int(m[1])) if (m:=re.search(p,log)) else None for k,p in patterns.items()}
 lines=log.splitlines();warning_lines=[x for x in lines if 'WARNING (' in x or 'amsspice: *Warning' in x]
 summary=re.findall(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?',log)
 return {'simulator_exit_code':int((run/'simulator_exit_code.txt').read_text()),
 'qualification_exit_code':int((run/'qualification_exit_code.txt').read_text()),
 'Spectre_final_summary':dict(zip(['errors','warnings','notices'],map(int,summary[-1]))) if summary else None,
 'warning_code_counts':dict(Counter(re.findall(r'WARNING \(([^)]+)\)',log))),
 'all_warning_lines':warning_lines,'diagnostic_statistics':counts,
 'printed_trapezoidal_ringing_mentions':len(re.findall('trapezoidal ringing',log,re.I)),
 'ringing_limiting_nodes':dict(Counter(re.findall(r'limiting signal: ([^ ]+) =.*?trapezoidal ringing',log))),
 'ringing_detected_end_notice':'Trapezoidal ringing is detected during tran analysis.' in log,
 'suppression_lines':[x for x in lines if re.search(r'further.*suppress|further.*not.*print|suppress.*notice|notice.*suppress',x,re.I)],
 'cthresh_log_values':re.findall(r'^\s*cthresh\s*=\s*(\S+)',log,re.M),
 'P2_FAIL_present':'P2_FAIL' in log,'frames':list(csv.DictReader((run/'frames.csv').open())),
 'decisions':list(csv.DictReader((run/'decisions.csv').open())),
 'log_sha256':sha(run/'xrun.log')}
def compare(a,b,grid):
 ta,va,_=a;tb,vb,_=b;result={};columns=[grid]
 assert grid[0]>=max(ta[0],tb[0])-1e-20 and grid[-1]<=min(ta[-1],tb[-1])+1e-20
 for name in CHANNELS:
  delta=np.interp(grid,tb,vb[name])-np.interp(grid,ta,va[name]);i=int(np.argmax(abs(delta)))
  result[name]={'max_abs_delta_V':float(abs(delta[i])),'worst_time_s':float(grid[i]),'within_original_0p05_LSB':bool(abs(delta[i])<=LIMIT)};columns.append(delta)
 return result,np.column_stack(columns)
def main():
 if (HERE/'review.json').exists():raise SystemExit('Refusing to overwrite frozen review')
 profiles={};data={};identity={};baseline_config=(RUN/'baseline/amsdControl.scs').read_text();strict_config=(RUN/'strict/amsdControl.scs').read_text()
 for prof in ['baseline','strict']:
  run=RUN/prof;manifest=json.loads((run/'manifest.json').read_text());identity[prof]={name:sha(run/name)==h for name,h in manifest['files_sha256'].items()}
  data[prof]=raw(run);profiles[prof]={**data[prof][2],**logs(run),'manifest_sha256':sha(run/'manifest.json')}
  profiles[prof]['original_v4_physical_files_unchanged']={name:sha(run/name)==sha(HERE.parent/f'reset1_2frames_{prof}_v4'/name) for name in FILES}
 bh,sh=[profiles[p]['actual_header'] for p in ['baseline','strict']]
 complete=all(abs(data[p][0][0])<=1e-20 and abs(data[p][0][-1]-4.1e-6)<=1e-20 for p in ['baseline','strict'])
 union=np.union1d(data['baseline'][0],data['strict'][0]);actual_stats,columns=compare(data['baseline'],data['strict'],union)
 np.savetxt(HERE/'all_accepted_union_differences.csv',columns,delimiter=',',header='time_s,'+','.join(CHANNELS),comments='',fmt='%.16e')
 old={p:raw(CLOSURE/f'runs/{rid}/design',short=True) for p,rid in [('baseline','task_20260924T050345927509Z'),('strict','task_20260924T051121445887Z')]}
 common=np.unique(np.concatenate([x[0] for x in list(data.values())+list(old.values())]+[np.array([0,4.1e-6,4.06315e-6,4.06335e-6])]))
 comparisons={}
 for label,lo,hi in [('same_0_to_4p1us',0,4.1e-6),('same_local_CONV_window',4.06315e-6,4.06335e-6)]:
  grid=common[(common>=lo)&(common<=hi)]
  comparisons[label]={'domain_s':[lo,hi],'common_grid_count':len(grid),'old':compare(old['baseline'],old['strict'],grid)[0],'adaptive_trap':compare(data['baseline'],data['strict'],grid)[0]}
 wanted={'reltol':(1e-6,1e-7),'abstol(V)':(1e-8,1e-9),'abstol(I)':(1e-13,1e-14),'maxstep':(2e-9,1e-9)}
 checks={'all_manifest_input_hashes_match':all(all(x.values()) for x in identity.values()),
 'physical_files_match_frozen_v4':all(all(profiles[p]['original_v4_physical_files_unchanged'].values()) for p in profiles),
 'pair_only_requested_accuracy_diff':baseline_config.replace('reltol=1e-5 vabstol=1e-8 iabstol=1e-13','reltol=1e-6 vabstol=1e-9 iabstol=1e-14').replace('maxstep=2n','maxstep=1n')==strict_config,
 'actual_same_tool_method_environment':all(k in bh and k in sh and bh[k]==sh[k] for k in ['version','method','relref','errpreset','lteratio','temp','tnom','gmin','cmin']),
 'actual_expected_tolerances':all(k in bh and k in sh and np.isclose(bh[k],v[0],rtol=1e-8,atol=0) and np.isclose(sh[k],v[1],rtol=1e-8,atol=0) for k,v in wanted.items()),
 'no_cthresh_override_in_inputs':'cthresh=' not in baseline_config and 'cthresh=' not in strict_config,
 'actual_adaptive_trap_method':bh.get('method')==sh.get('method')=='trap',
 'complete_zero_to_4p1us':complete,'both_processes_exit0':all(x['simulator_exit_code']==0 for x in profiles.values()),
 'no_completed_frames_expected':all(not x['frames'] and not x['decisions'] for x in profiles.values()),
 'no_P2_FAIL':all(not x['P2_FAIL_present'] for x in profiles.values()),
 'all_four_waveforms_within_original_limit':all(x['within_original_0p05_LSB'] for x in actual_stats.values()),
 'no_unexplained_numerical_warning':all(not x['warning_code_counts'] for x in profiles.values())}
 result={'status':'SHORT_DOMAIN_NUMERICAL_FAIL' if not all(checks.values()) else 'SHORT_DIAGNOSTIC_ONLY_NOT_FULL_ADC_PASS',
 'checks':checks,'threshold_V':LIMIT,'all_accepted_union_point_count':len(union),'full_short_domain_statistics':actual_stats,
 'profiles':profiles,'identity':identity,'same_domain_comparisons':comparisons,
 'old_source_evidence':{p:x[2] for p,x in old.items()},'analyzer_sha256':sha(Path(__file__)),
 'method_scope':'Actual method=trap verified from PSF; no cthresh override. Ringing is numerical diagnosis, not proof of physical oscillation.',
 'complete_ADC_qualified':False,'long_campaign_allowed':False,'original_two_frame_fail_retained':True,
 'limitations':['No time shifting or window exclusion from the short-domain four-channel check.','Old full-record prefixes share physical configuration but contain fewer diagnostics/saved device quantities; report this comparison as same-domain diagnostic, not a proven single-option execution identity.','Short probe has zero completed conversions; it cannot replace the planned two-frame or twelve-frame gate.','No PDK/model changes and no new EDA run from this analysis.']}
 (HERE/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else (_ for _ in ()).throw(TypeError(type(x).__name__)))+'\n')
 print(json.dumps({'status':result['status'],'checks':checks,'stats':actual_stats,'old_vs_adaptive_trap':{k:{p:v[p]['cdac_differential'] for p in ['old','adaptive_trap']} for k,v in comparisons.items()}},indent=2))
if __name__=='__main__':main()
