#!/usr/bin/env python3
"""Original four physical ADC channels, all accepted times; never align or mask edges."""
import argparse,array,csv,gzip,hashlib,importlib.util,json,re
from pathlib import Path
import numpy as np
LSB=.8/4096
LIMIT=.05*LSB
# Identical definition to qualification_20260913/qualify.py: physical TP-TN, RP, RN, VCM.
CHANNELS={'cdac_differential':('TP','TN'),'rp':('RP',),'rn':('RN',),'vcm':('VCM',)}
SUFFIX={'TP':'adc.XADC_TP','TN':'adc.XADC_TN','RP':'rp','RN':'rn','VCM':'vcm','EVAL':'eval_e','VDD':'vdd'}

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read_csv(p):
 with p.open() as f:return list(csv.DictReader(f))
def parse(path):
 lookup={('p2_ams_reset1.'+s).lower():k for k,s in SUFFIX.items()}
 values={k:array.array('d') for k in ['time',*SUFFIX]};cur=None;aliases={};alias=None;active=False;head={};section=''
 def finish(row):
  if row is None:return
  if set(row)!=set(values):raise ValueError('Missing physical trace(s): '+str(set(values)-set(row)))
  for k in values:values[k].append(row[k])
 with path.open() as f:
  for line in f:
   if line.strip() in ['HEADER','TYPE','SWEEP','TRACE','VALUE']:section=line.strip()
   if section=='VALUE':active=True
   if not active:
    g=re.match(r'^"([^"]+)" GROUP (\d+)\s*$',line)
    if g:
     if g[2]!='1':raise ValueError('Unsupported multi-trace group')
     alias=g[1];continue
    if alias:
     g=re.match(r'^"([^"]+)"\s+"[^"]+"',line)
     if not g:raise ValueError('Malformed trace alias')
     aliases[alias]=g[1];alias=None;continue
   m=re.match(r'^"([^"]+)"\s+([-+.0-9eE]+)\s*$',line)
   if not m:continue
   name,x=m[1],float(m[2])
   if not active:
    if section=='HEADER':head[name]=x
    continue
   if name=='time':finish(cur);cur={'time':x};continue
   key=lookup.get(aliases.get(name,name).lower())
   if key:
    if cur is None:raise ValueError('Trace before first time')
    cur[key]=x
 finish(cur)
 v={k:np.asarray(a,dtype=float) for k,a in values.items()}
 if len(v['time'])<2 or not all(np.isfinite(x).all() for x in v.values()):raise ValueError('Missing or nonfinite raw waveform')
 if not np.all(np.diff(v['time'])>0):raise ValueError('Accepted times not strictly increasing; no automatic pruning')
 return head,v

def interpolate(v,channel,times):
 # Reject extrapolation, including silent filling at mismatched simulation endpoints.
 if np.min(times)<v['time'][0]-1e-18 or np.max(times)>v['time'][-1]+1e-18:raise ValueError('Comparison grid extends beyond actual saved time')
 a=np.interp(times,v['time'],v[channel[0]])
 return a-np.interp(times,v['time'],v[channel[1]]) if len(channel)==2 else a

def grid_stats(base,strict,grid):
 result={};diff=[]
 for name,channel in CHANNELS.items():
  delta=interpolate(strict,channel,grid)-interpolate(base,channel,grid)
  error=np.abs(delta);i=int(np.argmax(error))
  result[name]={'max_abs_error_V':float(error[i]),'max_abs_error_LSB':float(error[i]/LSB),'worst_time_s':float(grid[i]),'le_0p05_LSB':bool(error[i]<=LIMIT)}
  diff.append(delta)
 return result,np.column_stack([grid]+diff)

def crossings(v):
 delta=v['EVAL']-.1*v['VDD'];t=v['time'];ix=np.flatnonzero((delta[:-1]<0)&(delta[1:]>=0))
 return t[ix]-delta[ix]/(delta[ix+1]-delta[ix])*(t[ix+1]-t[ix])

def compare(base,strict,out,base_raw=None,strict_raw=None):
 if out.exists():raise ValueError('Refusing to overwrite comparison')
 ma,mb=[json.loads((x/'manifest.json').read_text()) for x in [base,strict]]
 if ma['accuracy_profile']!='baseline' or mb['accuracy_profile']!='strict' or ma['frames']!=mb['frames']:raise ValueError('Wrong profile pair')
 if ma['operating_condition']!=mb['operating_condition'] or ma['native_body_hashes']!=mb['native_body_hashes']:raise ValueError('Circuit or operating condition mismatch')
 for name in ['sar_controller.v','p1_interfaces.vams','p2_ams_reset1.vams','p2_sequence.sv','profile.vh','reset1_native_bound.scs']:
  if sha(base/name)!=sha(strict/name):raise ValueError('Non-solver input mismatch: '+name)
 expected=(base/'amsdControl.scs').read_text().replace('reltol=1e-5 vabstol=1e-8 iabstol=1e-13','reltol=1e-6 vabstol=1e-9 iabstol=1e-14').replace('maxstep=2n','maxstep=1n')
 if expected!=(strict/'amsdControl.scs').read_text():raise ValueError('More than intended solver settings differ')
 # Functional evidence check is independent; all raw warnings remain visible.
 spec=importlib.util.spec_from_file_location('ams_analysis',Path(__file__).with_name('analyze.py'));a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
 ar=a.analyze(base,base_raw);br=a.analyze(strict,strict_raw)
 if not ar['functional_pass'] or not br['functional_pass']:
  out.mkdir(parents=True);r={'status':'NUMERICAL_PAIR_INCOMPLETE','baseline_functional':ar['functional_pass'],'strict_functional':br['functional_pass'],'baseline_errors':ar['errors'],'strict_errors':br['errors'],'complete_ADC_qualified':False,'long_campaign_allowed':False}
  (out/'comparison.json').write_text(json.dumps(r,indent=2)+'\n');return r
 base_raw=base_raw or base/'amsdControl.raw/adc_closure_tran.tran.tran';strict_raw=strict_raw or strict/'amsdControl.raw/adc_closure_tran.tran.tran'
 bh,bv=parse(base_raw);sh,sv=parse(strict_raw)
 if abs(bv['time'][0]-sv['time'][0])>1e-18 or abs(bv['time'][-1]-sv['time'][-1])>1e-18:raise ValueError('Saved domains differ; no cropped intersection or endpoint extrapolation')
 for k in ['temp','tnom']:
  if k not in bh or k not in sh or bh[k]!=sh[k]:raise ValueError('Missing/mismatched actual temperature '+k)
 actual_tightening=all(k in bh and k in sh and 0<sh[k]<=bh[k]*.10000001 for k in ['reltol','abstol(V)','abstol(I)']) and 'maxstep' in bh and 'maxstep' in sh and 0<sh['maxstep']<=bh['maxstep']*.50000001
 frames_a,frames_b=[read_csv(x/'frames.csv') for x in [base,strict]]
 same_codes=[(x['data'],x['data_gain']) for x in frames_a]==[(x['data'],x['data_gain']) for x in frames_b]
 dec_a,dec_b=[read_csv(x/'decisions.csv') for x in [base,strict]]
 cap_a=np.array([float(x['time_ns'])*1e-9 for x in dec_a]);cap_b=np.array([float(x['time_ns'])*1e-9 for x in dec_b])
 if len(cap_a)!=12*ma['frames'] or not np.array_equal(cap_a,cap_b):raise ValueError('Capture schedule changed')
 ea,eb=crossings(bv),crossings(sv)
 # One extra evaluation belongs to the deliberate reset-abort test. Keep it.
 expected_evals=12*ma['frames']+1
 same_eval_count=len(ea)==len(eb)==expected_evals
 if not len(ea) or not len(eb):raise ValueError('Actual evaluation edges absent')
 union=np.union1d(bv['time'],sv['time']);start,end=float(union[0]),float(union[-1])
 common=np.arange(int(np.floor((end-start)/1e-9))+1)*1e-9+start
 if end>common[-1]:common=np.r_[common,end]
 grids={'union_accepted':union,'common_1ns_plus_final':common,
        'baseline_actual_pre_EVAL_minus_1ns':ea-1e-9,
        'strict_actual_pre_EVAL_minus_1ns':eb-1e-9,
        'all_RTL_capture_minus_1ns':cap_a-1e-9}
 out.mkdir(parents=True);stats={};artifacts={}
 for name,grid in grids.items():
  stats[name],data=grid_stats(bv,sv,grid)
  p=out/(name+'_differences.csv.gz')
  with gzip.open(p,'wt') as f:np.savetxt(f,data,delimiter=',',header='time_s,'+','.join(CHANNELS),comments='',fmt='%.16e')
  artifacts[p.name]={'sha256':sha(p),'rows':len(grid)}
 warnings={'baseline':ar['all_retained_warning_lines'],'strict':br['all_retained_warning_lines']}
 checks={'all_four_physical_waveforms_union_le_0p05_LSB':all(x['le_0p05_LSB'] for x in stats['union_accepted'].values()),'all_four_physical_waveforms_fixed_grid_le_0p05_LSB':all(x['le_0p05_LSB'] for x in stats['common_1ns_plus_final'].values()),'all_pre_EVAL_and_capture_le_0p05_LSB':all(x['le_0p05_LSB'] for g,s in stats.items() if g not in ['union_accepted','common_1ns_plus_final'] for x in s.values()),'same_raw_codes_and_data_gain':same_codes,'same_expected_actual_eval_count':same_eval_count,'actual_tolerances_tightened_10x_and_step_halved':bool(actual_tightening),'both_numeric_logs_clean':ar['numerical_log_clean'] and br['numerical_log_clean']}
 passed=all(checks.values());status='BOUNDED_12_FRAME_NUMERICAL_PASS' if passed and ma['frames']==12 else 'TWO_FRAME_NUMERICAL_DIAGNOSTIC_PASS' if passed else 'NUMERICAL_CONVERGENCE_FAIL'
 result={'status':status,'checks':checks,'frames':ma['frames'],'threshold_V':LIMIT,'threshold_LSB':.05,'physical_channels':{k:list(v) for k,v in CHANNELS.items()},'stats':stats,'grids':{k:len(v) for k,v in grids.items()},'complete_time_domain_s':[start,end],'actual_profiles':{'baseline':bh,'strict':sh},'actual_evaluation_edges_s':{'baseline':ea.tolist(),'strict':eb.tolist()},'actual_eval_edge_delta_s':(eb-ea).tolist() if len(ea)==len(eb) else None,'warnings':warnings,'raw_sha256':{'baseline':sha(base_raw),'strict':sha(strict_raw)},'manifest_sha256':{'baseline':sha(base/'manifest.json'),'strict':sha(strict/'manifest.json')},'difference_files':artifacts,'comparison_code_sha256':sha(Path(__file__)),'complete_ADC_qualified':False,'long_campaign_allowed':False,'limitations':['Same absolute time, all accepted points from both runs, no edge removal/time shifting.','Union-grid linear interpolation can contribute narrow peak differences; full1nsgrid and interpolation-based pre-EVAL/capture comparisons are retained as additional diagnostics, never replacements.','Two-frame agreement cannot satisfy twelve-frame qualification. Even bounded12frameagreement does not prove fullcode/noise/45PVT/mismatch/PEX.','All unexplained warnings prevent automatic numerical acceptance.']}
 (out/'baseline_functional_review.json').write_text(json.dumps(ar,indent=2,allow_nan=False)+'\n');(out/'strict_functional_review.json').write_text(json.dumps(br,indent=2,allow_nan=False)+'\n')
 (out/'comparison.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('strict',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline-raw',type=Path);p.add_argument('--strict-raw',type=Path);a=p.parse_args();r=compare(a.baseline,a.strict,a.output,a.baseline_raw,a.strict_raw);print(json.dumps({k:r[k] for k in ['status','complete_ADC_qualified','long_campaign_allowed']}));raise SystemExit(0 if r['status'].endswith('_PASS') else 2)
