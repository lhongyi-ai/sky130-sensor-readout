#!/usr/bin/env python3
"""Actual first-edge closed-load diagnosis; no ADC qualification or edge deletion."""
import argparse,bisect,hashlib,json,re,math
from pathlib import Path
from collections import Counter
from psf_stream import Trace
ROOT=Path(__file__).resolve().parent
P='XPHASE.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8:'
FULL='p2_ams_reset1.phases.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8.'
MAP={'CONV':'p2_ams_reset1.conv_e','SAMPLE_CMD':'p2_ams_reset1.sample_cmd_e','TOP':'p2_ams_reset1.top_e','TOPB':'p2_ams_reset1.topb_e','ACQ':'p2_ams_reset1.acq_e','VDD':'p2_ams_reset1.vdd','RP':'p2_ams_reset1.rp','RN':'p2_ams_reset1.rn','VCM':'p2_ams_reset1.vcm','XLOAD.XADC_TP':'p2_ams_reset1.adc.XADC_TP','XLOAD.XADC_TN':'p2_ams_reset1.adc.XADC_TN','XPHASE.XPHASE_XBCONV_B':'p2_ams_reset1.phases.XPHASE_XBCONV_B'}
MAP.update({P+n:FULL+n for n in ['int_b','dbnode','sbnode','vds','reversed']})
MAP.update({P+n:FULL+n+'_$flow' for n in 'dgsb'})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def command_value(t):
 u=max(0.,min(1.,(t-4.0625e-6)/1e-9))
 return .9*(1-math.cos(math.pi*u))
def read(path):
 tr=Trace(path,accepted_types=('V','I','-enum'));rows=list(tr.rows())
 if not rows:raise ValueError('Empty waveform')
 return tr,rows
def raw(run):
 files=list((run/'input.raw').glob('closed_phase*.tran'))
 if len(files)>1:raise ValueError('Ambiguous raw waveform')
 return files[0] if files else run/'trace.tran.gz'
def compare(a,b,types):
 ta=[r['time'] for r in a];tb=[r['time'] for r in b];lo=max(ta[0],tb[0]);hi=min(ta[-1],tb[-1])
 if hi<lo:raise ValueError('No common domain')
 ts=sorted(set(t for t in ta+tb if lo<=t<=hi));result={n:{'max_abs_difference':0.,'worst_time_s':lo,'type':k} for n,k in types.items()}
 def v(rs,times,t,n):
  i=bisect.bisect_right(times,t)-1
  if i<0 or t>times[-1]:raise ValueError('Extrapolation forbidden')
  if times[i]==t or i==len(times)-1 or types[n]=='-enum':return rs[i][n]
  q=(t-times[i])/(times[i+1]-times[i]);return rs[i][n]+q*(rs[i+1][n]-rs[i][n])
 for t in ts:
  for n in types:
   av,bv=v(a,ta,t,n),v(b,tb,t,n);d=bv-av
   if abs(d)>result[n]['max_abs_difference']:result[n].update(max_abs_difference=abs(d),worst_time_s=t,first=av,second=bv,signed_second_minus_first=d)
 return {'interval_s':[lo,hi],'both_complete_same_saved_domain':ta[0]==tb[0] and ta[-1]==tb[-1],'all_union_points':len(ts),'signals':result,'method':'All accepted timepoints from both runs; linear analog/left-held enum interpolation; no edge removal, alignment or extrapolation.'}
def events(rows):
 names=['time','CONV','VDD','XPHASE.XPHASE_XBCONV_B',*[P+n for n in ['int_b','dbnode','sbnode','vds','reversed','d','g','s','b']]]
 out=[]
 for i,(a,b) in enumerate(zip(rows,rows[1:])):
  if a[P+'reversed']!=b[P+'reversed']:
   out.append({'before_s':a['time'],'after_s':b['time'],'delta_s':b['time']-a['time'],'body_delta_V':b[P+'int_b']-a[P+'int_b'],'actual_neighbors':[{n:r[n] for n in names} for r in rows[max(0,i-3):i+5]]})
 return out
def analyze(run):
 tr,rows=read(raw(run));m=json.loads((run/'package_manifest.json').read_text());profile=(run/'profile.txt').read_text().strip()
 if sha(run/'input.scs')!=m['profiles'][profile]['sha256'] or sha(run/'native_closed.scs')!=m['native_sha256']:raise ValueError('Frozen input mismatch')
 missing=set(MAP)-set(tr.names)
 if missing:raise ValueError('Missing saved observable(s):'+str(missing))
 if tr.types[P+'reversed']!='-enum' or not set(r[P+'reversed'] for r in rows)<={0.,1.}:raise ValueError('Unexpected reversed schema; no zero replacement')
 log=(run/'spectre.out').read_text(errors='replace')
 command_error=max(abs(r['SAMPLE_CMD']-command_value(r['time'])) for r in rows)
 active=[r for r in rows if 4.0625e-6<r['time']<4.0635e-6]
 bins={int(min(3,(r['time']-4.0625e-6)/1e-9*4)) for r in active}
 linear_error=max(abs(r['SAMPLE_CMD']-min(1.8,max(0.,(r['time']-4.0625e-6)*1.8e9))) for r in rows)
 shape={'intended_model':'raised cosine:0.9*(1-cos(pi*u))','accepted_points_inside_edge':len(active),'represented_edge_quarters':sorted(bins),'max_error_to_intended_half_sine_V':command_error,'max_error_to_original_linear_V':linear_error,'classification':('INTENDED_HALF_SINE_OBSERVED' if bins=={0,1,2,3} and command_error<1e-7 and linear_error>1e-3 else 'SOURCE_SHAPE_NOT_VERIFIED'),'scope':'Shape diagnostic thresholds only; no ADC accuracy acceptance. Require resolved evidence in all four edge quarters, not merely exact source endpoints.'}
 times=[r['time'] for r in rows];knots=[]
 for t in [4.0625e-6,4.0635e-6]:
  i=bisect.bisect_right(times,t)-1;before=rows[i];after=rows[min(i+1,len(rows)-1)]
  q=(t-before['time'])/(after['time']-before['time']) if after['time']!=before['time'] else 0.
  interpolated=before['SAMPLE_CMD']+q*(after['SAMPLE_CMD']-before['SAMPLE_CMD'])
  knots.append({'command_knot_s':t,'present_in_saved_points':t in times,'before':{n:before[n] for n in ['time','SAMPLE_CMD','CONV']},'after':{n:after[n] for n in ['time','SAMPLE_CMD','CONV']},'saved_trace_interpolated_command_V':interpolated,'difference_from_known_command_V':interpolated-command_value(t)})
 lines=log.splitlines();warnings=[]
 for i,line in enumerate(lines):
  if 'WARNING (' in line:
   start=max(0,i-2)
   while start>max(0,i-5) and 'Warning from spectre' not in lines[start]:start-=1
   warnings.append({'file':str(run/'spectre.out'),'line_1based':i+1,'context':'\n'.join(lines[start:i+4])})
 for r in rows:r['TP_minus_TN']=r['XLOAD.XADC_TP']-r['XLOAD.XADC_TN']
 tr.types['TP_minus_TN']='V'
 complete=rows[0]['time']==0 and abs(rows[-1]['time']-4.1e-6)<1e-17
 review={'status':'CLOSED_SUBNETWORK_DIAGNOSTIC_ONLY','run':str(run),'profile':profile,'raw_sha256':sha(tr.path),'input_sha256':sha(run/'input.scs'),'native_sha256':sha(run/'native_closed.scs'),'points':len(rows),'actual_saved_schema':tr.types,'actual_solver':tr.header,'domain_s':[rows[0]['time'],rows[-1]['time']],'complete_diagnostic_domain':complete,'exit_code':int((run/'exit_code.txt').read_text()),'warnings_printed':dict(Counter(re.findall(r'WARNING \(([^)]+)\)',log))),'warning_contexts':warnings,'command_knots':knots,'command_shape_assessment':shape,'active_command_accepted_point_count':sum(4.0625e-6<r['time']<4.0635e-6 for r in rows),'completion_summary':re.findall(r'spectre completes with [^\n]+',log),'smallest_accepted_step_s':min(b['time']-a['time'] for a,b in zip(rows,rows[1:])),'command_max_error_from_frozen_source_V':command_error,'all_mode_events':events(rows),'terminal_current_sum_max_abs_A':max(abs(sum(r[P+n] for n in 'dgsb')) for r in rows),'complete_ADC':False,'full_ADC_accuracy_pass':False,'limitations':['Preamp/comparator87instances omitted and their CDAC loading/history may matter.','Raw accepted-point voltage/current/mode evidence is necessary; no-warning or small KCL residual cannot establish physical correctness.','Original chip numeric criterion unchanged; no first-edge diagnostic can authorize12frames.']}
 return review,tr,rows
def norm(s):
 for k in ['reltol','vabstol','iabstol','maxstep']:s=re.sub(r'\b'+k+r'=\S+',k+'=<profile>',s)
 return s
def main():
 p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('output',type=Path);p.add_argument('--strict',type=Path);p.add_argument('--original-full-probe',type=Path);a=p.parse_args()
 out,tr,rows=analyze(a.run)
 if a.strict:
  other,ot,ors=analyze(a.strict)
  if norm((a.run/'input.scs').read_text())!=norm((a.strict/'input.scs').read_text()):raise ValueError('Unexpected physical/method input difference')
  if tr.types!=ot.types:raise ValueError('Mismatched schema')
  out={'status':'CLOSED_PAIR_DIAGNOSTIC_ONLY','baseline':out,'strict':other,'pair':compare(rows,ors,tr.types),'strict_actual_precision_tightening':all(ot.header[k]<=tr.header[k]*.10000001 for k in ['reltol','abstol(V)','abstol(I)']) and ot.header['maxstep']<=tr.header['maxstep']*.50000001,'same_actual_method':all(tr.header[k]==ot.header[k] for k in ['method','relref','version','temp','tnom','gmin','cmin','lteratio','ic','skipdc']),'complete_ADC':False,'full_ADC_accuracy_pass':False}
 if a.original_full_probe:
  paths=list((a.original_full_probe/'amsdControl.raw').glob('*.tran'))
  if len(paths)!=1:raise ValueError('Expected exactly one originalfullprobe transient')
  ft,fr=read(paths[0]);mapped=[]
  for r in fr:
   mapped.append({'time':r['time'],**{n:r[v] for n,v in MAP.items()},'TP_minus_TN':r[MAP['XLOAD.XADC_TP']]-r[MAP['XLOAD.XADC_TN']]})
  ty={n:tr.types[n] for n in MAP};ty['TP_minus_TN']='V'
  out['original_full_probe_comparison']={'kind':'DIFFERENT_PHYSICAL_BOUNDARY_AND_ENGINE_NOT_NUMERICAL_CONVERGENCE','original_raw_sha256':sha(paths[0]),'comparison':compare(mapped,rows,ty),'original_modes':events(mapped),'closed_modes':events(rows)}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({k:out[k] for k in ['status','complete_ADC','full_ADC_accuracy_pass']}))
if __name__=='__main__':main()
