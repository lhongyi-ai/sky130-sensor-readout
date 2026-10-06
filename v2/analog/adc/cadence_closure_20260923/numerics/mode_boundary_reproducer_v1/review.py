#!/usr/bin/env python3
"""Model-isolation analysis only. No ADC qualification, synthetic fills or time alignment."""
import argparse,bisect,gzip,hashlib,json,math,re
from collections import Counter
from pathlib import Path
from psf_stream import Trace
P='XTEST.msky130_fd_pr__pfet_01v8.'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def configuration(s,allow_method_difference=False):
 s=re.sub(r'(?m)^\s*//.*$','',s)
 for k in ['reltol','vabstol','iabstol','maxstep']+(['method'] if allow_method_difference else []):s=re.sub(r'\b'+k+r'=\S+',k+'=<allowed>',s)
 return ' '.join(s.split())
def waveform(run):
 candidates=list((run/'input.raw').glob('mode_boundary*.tran'))
 if len(candidates)>1:raise ValueError('Multiple raw transient candidates; inspect provenance')
 raw=candidates[0] if candidates else run/'trace.tran.gz'
 trace=Trace(raw,accepted_types=('V','I','-enum'));rows=list(trace.rows())
 # Pure Spectre uses colon terminal/OP labels; AMS uses dot/$flow labels.
 # Retain an explicit bijection to actual saved labels, never synthesize values.
 original_types=dict(trace.types);actual_to_canonical={}
 for name in trace.names:
  canonical=name
  if name.startswith(P[:-1]+':'):
   suffix=name[len(P):]
   canonical=P+(suffix+'_$flow' if suffix in 'dgsb' and len(suffix)==1 and trace.types[name]=='I' else suffix)
  if canonical in actual_to_canonical.values():raise ValueError('Ambiguous actual signal alias')
  actual_to_canonical[name]=canonical
 rows=[{actual_to_canonical.get(k,k):v for k,v in r.items()} for r in rows]
 trace.names=[actual_to_canonical[n] for n in trace.names]
 trace.types={actual_to_canonical[n]:k for n,k in original_types.items()}
 trace.original_types=original_types;trace.canonical_to_actual={v:k for k,v in actual_to_canonical.items()}
 required={'D','G','SB',P+'int_b',P+'dbnode',P+'sbnode',P+'vds',P+'reversed',*[P+c+'_$flow' for c in 'dgsb']}
 if not required.issubset(trace.names):raise ValueError('Actual required output missing: '+str(required-set(trace.names)))
 if trace.types[P+'reversed']!='-enum':raise ValueError('Unexpected actual reversed schema')
 values=set(r[P+'reversed'] for r in rows)
 if not values.issubset({0.,1.}):raise ValueError('Unexpected actual enum values: '+str(values))
 return trace,rows

def analyze(run):
 tr,rows=waveform(run);times=[r['time'] for r in rows]
 man=json.loads((run/'package_manifest.json').read_text());case=(run/'case.txt').read_text().strip();profile=(run/'profile.txt').read_text().strip()
 if 'cases' not in man:
  if man.get('case')!=case or man.get('profile')!=profile or sha(run/'input.scs')!=man.get('input_sha256'):raise ValueError('Method addendum input/identity mismatch')
  parent=json.loads((Path(__file__).parent/'manifest.json').read_text())
  if parent['cases'][case]['files']['strict']['sha256']!=man['parent_input_sha256']:raise ValueError('Unverified method addendum parent')
  man=parent
 c=man['cases'][case]
 log=(run/'spectre.out').read_text(errors='replace');exitcode=int((run/'exit_code.txt').read_text())
 warnings=dict(Counter(re.findall(r'WARNING \(([^)]+)\)',log)))
 transitions=[]
 for i,(a,b) in enumerate(zip(rows,rows[1:])):
  if a[P+'reversed']!=b[P+'reversed']:
   def sample(r):return {k:r[k] for k in ['time','D','G','SB',P+'int_b',P+'dbnode',P+'sbnode',P+'vds',P+'reversed',*[P+c+'_$flow' for c in 'dgsb']]}
   transitions.append({'before':sample(a),'after':sample(b),'duration_s':b['time']-a['time'],'external_VDS_before_V':a['D']-a['SB'],'external_VDS_after_V':b['D']-b['SB'],'body_change_V':{n:b[P+n]-a[P+n] for n in ['int_b','dbnode','sbnode']},'adjacent_raw_points':[sample(x) for x in rows[max(0,i-3):min(len(rows),i+5)]]})
 observed_source_errors={}
 for node,offset,amplitude,sign in [('DSRC' if c['series_ohm'] else 'D',1.8,c['drain_source_amplitude_V'],1),('GSRC' if c['series_ohm'] else 'G',c['gate_source_mean_V'],c['gate_source_amplitude_V'],-1)]:
  observed_source_errors[node]={'max_abs_difference_from_frozen_analytic_wave_V':max(abs(r[node]-(offset+sign*amplitude*math.cos(2*math.pi*c['freq_Hz']*r['time']))) for r in rows)}
 expected=c['stop_s'];full=times[0]==0 and abs(times[-1]-expected)<=max(1e-24,expected*1e-10)
 result={'status':'ISOLATED_DEVICE_DIAGNOSTIC_ONLY','case':case,'profile':profile,'run':str(run),'raw_sha256':sha(tr.path),'input_sha256':sha(run/'input.scs'),'log_sha256':sha(run/'spectre.out'),'simulator_exit_code':exitcode,'points':len(rows),'interval_s':[times[0],times[-1]],'expected_interval_s':[0,expected],'complete_diagnostic_interval':full,'actual_trace_types':tr.original_types,'canonical_to_actual_saved_aliases':tr.canonical_to_actual,'actual_solver':tr.header,'warnings':warnings,'log_completion_summary':re.findall(r'spectre completes with [^\n]+',log),'mode_transition_count':len(transitions),'all_mode_transitions':transitions,'body_minus_external_bulk_range_V':{n:[min(r[P+n]-r['SB'] for r in rows),max(r[P+n]-r['SB'] for r in rows)] for n in ['int_b','dbnode','sbnode']},'terminal_current_sum_max_abs_A':max(abs(sum(r[P+x+'_$flow'] for x in 'dgsb')) for r in rows),'analytic_drive_checks':observed_source_errors,'smallest_accepted_step_s':min(b-a for a,b in zip(times,times[1:])),'complete_ADC':False,'full_ADC_accuracy_pass':False,'limits':['These ideal source drives remove native ADC feedback/load and do not recreate original stored-charge history.','The full accepted interval and every mode edge remain in the analysis. Total currents include displacement terms; KCL cannot prove physical correctness.','No absence of warnings or success of this isolated simulation authorizes ADC acceptance.']}
 return result,tr,rows

def compare_samples(a,b,types):
 ta=[r['time'] for r in a];tb=[r['time'] for r in b]
 lo=max(ta[0],tb[0]);hi=min(ta[-1],tb[-1]);ts=sorted(set(t for t in ta+tb if lo<=t<=hi));names=set(types)
 def value(rows,times,t,n):
  i=bisect.bisect_right(times,t)-1
  if i<0 or t>times[-1]:raise ValueError('No extrapolation')
  if types[n]=='-enum' or t==times[i] or i==len(times)-1:return rows[i][n]
  q=(t-times[i])/(times[i+1]-times[i]);return rows[i][n]+q*(rows[i+1][n]-rows[i][n])
 out={n:{'type':types[n],'maximum_absolute_difference':0.,'worst_time_s':lo} for n in names}
 for t in ts:
  for n in names:
   x=value(a,ta,t,n);y=value(b,tb,t,n);d=y-x
   if abs(d)>out[n]['maximum_absolute_difference']:out[n].update(maximum_absolute_difference=abs(d),signed_strict_minus_baseline=d,worst_time_s=t,baseline_value=x,strict_value=y)
 return {'shared_interval_s':[lo,hi],'full_saved_intervals_equal':ta[0]==tb[0] and ta[-1]==tb[-1],'all_union_points':len(ts),'signals':out,'method':'Every accepted time from both runs; piecewise-linear interpolation for analog scalar values, left-held sampled enum. No time alignment, removed edges, resampling-only audit or extrapolation.'}

def pair(a,b,allow_method_difference=False):
 ar,at,aa=analyze(a);br,bt,bb=analyze(b)
 if ar['case']!=br['case']:raise ValueError('Different source cases')
 ident=configuration((a/'input.scs').read_text(),allow_method_difference)==configuration((b/'input.scs').read_text(),allow_method_difference)
 if not ident:raise ValueError('Unexpected nonprecision input change')
 if set(at.types)!=set(bt.types) or at.types!=bt.types:raise ValueError('Mismatched actual trace schemas')
 r=compare_samples(aa,bb,at.types)
 strict=all(bt.header[k]<=at.header[k]*.10000001 for k in ['reltol','abstol(V)','abstol(I)']) and bt.header['maxstep']<=at.header['maxstep']*.50000001
 same=all(at.header[k]==bt.header[k] for k in ['method','relref','version','temp','tnom','gmin','cmin','lteratio','ic','skipdc'])
 r.update(status='ISOLATED_PAIR_DIAGNOSTIC_NOT_ADC_QUALIFICATION',baseline=ar,strict=br,physical_input_identity=ident,strict_actual_precision_tightening=strict,same_actual_solver_method_environment=same,allow_method_difference=allow_method_difference,complete_ADC=False,full_ADC_accuracy_pass=False)
 return r

def main():
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
 a=s.add_parser('single');a.add_argument('run',type=Path);a.add_argument('output',type=Path)
 a=s.add_parser('pair');a.add_argument('baseline',type=Path);a.add_argument('strict',type=Path);a.add_argument('output',type=Path);a.add_argument('--allow-method-difference',action='store_true')
 args=p.parse_args();r=analyze(args.run)[0] if args.mode=='single' else pair(args.baseline,args.strict,args.allow_method_difference)
 args.output.write_text(json.dumps(r,indent=2)+'\n')
 summary={k:r[k] for k in ['status','complete_ADC','full_ADC_accuracy_pass']}
 if args.mode=='single':summary.update({k:r[k] for k in ['points','warnings','mode_transition_count']})
 else:summary.update({k:r[k] for k in ['strict_actual_precision_tightening','same_actual_solver_method_environment','signals']})
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
