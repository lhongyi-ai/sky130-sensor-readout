#!/usr/bin/env python3
"""Fixed absolute-time comparison; no phase alignment or excluded switching edges."""
import argparse,gzip,hashlib,json,re
from pathlib import Path
import numpy as np
LSB=.8/4096;LIMIT=.05*LSB

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def parse(p):
 phase='header';head={};names=[];rows=[];cur=None
 for line in p.open():
  if line.strip()=='TRACE':phase='trace';continue
  if line.strip()=='VALUE':phase='value';continue
  if phase=='trace':
   m=re.match(r'^"([^"]+)"\s+"V"',line)
   if m:names.append(m.group(1))
   continue
  m=re.match(r'^"([^"]+)"\s+([-+.0-9eE]+)\s*$',line)
  if not m:continue
  n,v=m.group(1),float(m.group(2))
  if phase=='header':head[n]=v;continue
  if n=='time':
   if cur is not None:rows.append(cur)
   cur={'time':v}
  elif n in names:cur[n]=v
 if cur:rows.append(cur)
 assert names and len(names)==len(set(names))
 values=np.array([[r['time']]+[r[n] for n in names] for r in rows]);assert np.isfinite(values).all()
 assert np.all(np.diff(values[:,0])>0) and abs(values[-1,0]-9.2e-6)<1e-15
 return head,names,values

def crossing(t,v,threshold,direction):
 if direction=='rising':ix=np.flatnonzero((v[:-1]<threshold)&(v[1:]>=threshold))
 else:ix=np.flatnonzero((v[:-1]>threshold)&(v[1:]<=threshold))
 return t[ix]+(threshold-v[ix])/(v[ix+1]-v[ix])*(t[ix+1]-t[ix])

def compare(base,strict,out):
 assert not out.exists();out.mkdir()
 braw=base/'reset_decide.tran.tran';sraw=strict/'reset_decide.tran.tran'
 bh,bn,b=parse(braw);sh,sn,s=parse(sraw);assert set(bn)==set(sn)
 snidx={n:i+1 for i,n in enumerate(sn)};s=s[:,[0]+[snidx[n] for n in bn]];t=b[:,0];u=s[:,0]
 assert sha(base/'comparator_native_bound.scs')==sha(strict/'comparator_native_bound.scs')
 expected=(base/'input.scs').read_text().replace('reltol=1e-5 vabstol=1e-8 iabstol=1e-13','reltol=1e-6 vabstol=1e-9 iabstol=1e-14').replace('maxstep=2n','maxstep=1n')
 assert expected==(strict/'input.scs').read_text(),'Non-solver input change'
 idx={n:i+1 for i,n in enumerate(bn)}
 eval_pre=crossing(t,b[:,idx['EVAL']],.18,'rising')-1e-9;assert len(eval_pre)==7
 captures=(5+np.arange(7)*.625+.3115)*1e-6
 grids={'union_accepted':np.union1d(t,u),'common_1ns':np.arange(9201)*1e-9,'all_pre_EVAL_10pct_minus_1ns':eval_pre,'all_RTL_capture_minus_1ns':captures}
 channels={n:(idx[n],) for n in bn};channels['preamp_differential']=(idx['XCMP.XADC_PREP'],idx['XCMP.XADC_PREN']);channels['ideal_input_differential_not_CDAC']=(idx['TN'],idx['TP'])
 summaries={n:{} for n in channels};files={}
 for label,grid in grids.items():
  diffs=[]
  for name,columns in channels.items():
   av=np.interp(grid,t,b[:,columns[0]]);bv=np.interp(grid,u,s[:,columns[0]])
   if len(columns)==2:av-=np.interp(grid,t,b[:,columns[1]]);bv-=np.interp(grid,u,s[:,columns[1]])
   delta=bv-av;differences=np.abs(delta);i=int(np.argmax(differences))
   summaries[name][label]={'max_abs_error_v':float(differences[i]),'max_abs_error_lsb':float(differences[i]/LSB),'worst_time_s':float(grid[i]),'le_diagnostic_0_05lsb':bool(differences[i]<=LIMIT)};diffs.append(delta)
  p=out/(label+'_differences.csv.gz')
  with gzip.open(p,'wt') as f:np.savetxt(f,np.column_stack([grid]+diffs),delimiter=',',header='time_s,'+','.join(channels),comments='',fmt='%.16e')
  files[p.name]={'sha256':sha(p),'rows':len(grid),'channels':len(channels)}
 edgecompare={}
 for signal,threshold,direction in [('Q',1.26,'rising'),('Q',.54,'falling'),('EVAL',.18,'rising'),('XCMP.XADC_XCMP_S_BAR',.54,'falling'),('XCMP.XADC_XCMP_R_BAR',.54,'falling')]:
  aa=crossing(t,b[:,idx[signal]],threshold,direction);bb=crossing(u,s[:,idx[signal]],threshold,direction);eq=len(aa)==len(bb)
  edgecompare[signal+'_'+direction]={'baseline_s':aa.tolist(),'strict_s':bb.tolist(),'same_edge_count':eq,'delta_s':(bb-aa).tolist() if eq else None,'max_abs_delta_s':float(np.max(np.abs(bb-aa))) if eq and len(aa) else None}
 profiles={'baseline':{k:bh.get(k) for k in ['reltol','abstol(V)','abstol(I)','maxstep']},'strict':{k:sh.get(k) for k in ['reltol','abstol(V)','abstol(I)','maxstep']}}
 tightened=all(sh[k]<=bh[k]*.10000001 for k in ['reltol','abstol(V)','abstol(I)']) and sh['maxstep']<=bh['maxstep']/2
 warnings={}
 for label,d in [('baseline',base),('strict',strict)]:
  log=(d/'spectre.out').read_text();m=re.search(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?',log);assert m
  warnings[label]={'summary':dict(zip(['errors','warnings','notices'],map(int,m.groups()))),'LTE':log.count('WARNING (SPECTRE-16780)'),'log_sha256':sha(d/'spectre.out')}
 all_small=all(v[g]['le_diagnostic_0_05lsb'] for v in summaries.values() for g in grids)
 result={'status':'COMPARATOR_NUMERICAL_SENSITIVITY_ONLY','all_reported_analog_nodes_le_0_05lsb':all_small,'actual_tolerances_tightened_10x_and_maxstep_halved':tightened,'threshold_v':LIMIT,'threshold_lsb':.05,'complete_ADC_original_gate':'NOT_RUN_PHYSICAL_CDAC_RP_RN_VCM_ABSENT_FROM_87_DEVICE_FIXTURE','profiles':profiles,'logs':warnings,'raw_sha256':{'baseline':sha(braw),'strict':sha(sraw)},'public_voltage_nodes':len(bn),'additional_differential_channels':2,'grids':{k:len(v) for k,v in grids.items()},'pre_EVAL_times_s':eval_pre.tolist(),'RTL_capture_times_s':captures.tolist(),'channels':summaries,'edges':edgecompare,'difference_artifacts':files,'limitations':['All switching edges retained, no time shifts. Union-grid linear interpolation can contribute to narrow peak differences; common1nsgrid separately reported.','Ideal-driven TN/TP agreement is stimulus identity, not CDAC convergence evidence.','Even identical output decisions do not waive waveform discrepancies or LTE warnings.','The0.05LSB test on other87-device nodes is an additional conservative diagnostic, not a substitute for original fullADC observation gates.']}
 (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'status':result['status'],'actual_tolerances_tightened':tightened,'all_nodes_small':all_small,'profiles':profiles,'preamp_differential':summaries['preamp_differential'],'logs':warnings},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('strict',type=Path);p.add_argument('output',type=Path);a=p.parse_args();compare(a.baseline,a.strict,a.output)
