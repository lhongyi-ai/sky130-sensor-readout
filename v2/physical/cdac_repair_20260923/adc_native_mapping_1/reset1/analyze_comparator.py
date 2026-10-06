#!/usr/bin/env python3
"""Analyze genuine saved comparator waveforms; reset preload never counted as decision."""
import argparse,bisect,hashlib,json,re
from pathlib import Path

def analyze(raw,log):
 wanted={'VDD','TN','TP','EVAL','RST_N','Q','QB','XCMP.XADC_PREP','XCMP.XADC_PREN','XCMP.XADC_XCMP_DPOS','XCMP.XADC_XCMP_DNEG','XCMP.XADC_XCMP_BP','XCMP.XADC_XCMP_BN','XCMP.XADC_XCMP_S_BAR','XCMP.XADC_XCMP_R_BAR'}
 rows=[];active=False;cur=None;head={}
 for line in raw.open():
  if line.strip()=='VALUE':active=True;continue
  m=re.match(r'^"([^"]+)"\s+([-+.0-9eE]+)\s*$',line)
  if not m:continue
  name,value=m.group(1),float(m.group(2))
  if not active:head[name]=value;continue
  if name=='time':
   if cur is not None:rows.append(cur)
   cur={'time':value}
  elif name in wanted:cur[name]=value
 if cur:rows.append(cur)
 assert len(rows)>10 and abs(rows[-1]['time']-9e-6)<1e-15,'Incomplete9uswaveform'
 for r in rows:assert set(r)=={'time',*wanted},'Missing requested trace'
 tt=[r['time'] for r in rows];assert all(b>=a for a,b in zip(tt,tt[1:]))
 def point(t):
  i=bisect.bisect_left(tt,t)
  if tt[i]==t:return rows[i]
  a,b=rows[i-1],rows[i];f=(t-a['time'])/(b['time']-a['time']);return {k:a[k]+f*(b[k]-a[k]) for k in a}
 checks=[]
 def check(t,kind,q,ev,rst):
  r=point(t*1e-6);hi=.7*r['VDD'];lo=.3*r['VDD']
  def digit(x):return 1 if x>=hi else 0 if x<=lo else None
  observed={k:digit(r[k]) for k in ['Q','QB','EVAL','RST_N']}
  expected={'Q':q,'QB':1-q,'EVAL':ev,'RST_N':rst}
  checks.append({'time_s':t*1e-6,'kind':kind,'counts_as_real_comparator_decision':kind=='decision','expected':expected,'observed':observed,'voltages':r,'pass':observed==expected})
 for t in [0,.5]:check(t,'global_reset',0,0,0)
 check(1.5,'reset_release_hold',0,0,1)
 for t in [5.150,5.775,6.350]:check(t,'decision',1,1,1)
 for t in [5.300,5.925]:check(t,'decision_retention',1,0,1)
 check(6.450,'reset_during_evaluation',0,1,0)
 check(6.600,'reset_release_hold',0,0,1)
 for t in [7.025,7.650,8.275,8.900]:check(t,'decision',0,1,1)
 for t in [7.175,7.800,8.425]:check(t,'decision_retention',0,0,1)
 precharge=[]
 for t in [1.5,5.3,5.925,6.6,7.175,7.8,8.425]:
  r=point(t*1e-6);ok=min(r['XCMP.XADC_XCMP_DPOS'],r['XCMP.XADC_XCMP_DNEG'])>=.7*r['VDD'];precharge.append({'time_s':t*1e-6,'DPOS_V':r['XCMP.XADC_XCMP_DPOS'],'DNEG_V':r['XCMP.XADC_XCMP_DNEG'],'pass':ok})
 text=log.read_text();m=re.search(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?',text);assert m
 summary=dict(zip(['errors','warnings','notices'],map(int,m.groups())))
 functional=all(c['pass'] for c in checks+precharge);numeric=summary['errors']==0 and summary['warnings']==0 and 'Newton iteration fails' not in text
 with raw.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
 return {'status':'BOUNDED_NOMINAL_RESET_COMPARATOR_PASS' if functional and numeric else 'NOT_PASSED','functional_checks_pass':functional,'numeric_log_clean':numeric,'spectre_summary':summary,'actual_solver':{k:head.get(k) for k in ['reltol','abstol(V)','abstol(I)','maxstep','temp']},'raw_sha256':h,'sample_count':len(rows),'stop_s':rows[-1]['time'],'checks':checks,'precharge_checks':precharge,'scope':'87 actual PDK devices.7 actual ±1mV decisions; reset preload not counted. TT1.8V27C only. No ADC conversions/noise/PVT/minimum reset pulse/offset precision signoff.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('raw',type=Path);p.add_argument('log',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();r=analyze(a.raw,a.log);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:r[k] for k in ['status','functional_checks_pass','numeric_log_clean','spectre_summary','actual_solver','sample_count']},indent=2))
