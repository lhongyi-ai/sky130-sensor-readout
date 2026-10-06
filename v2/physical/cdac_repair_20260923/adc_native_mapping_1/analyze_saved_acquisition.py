#!/usr/bin/env python3
"""Read existing PSF ASCII; never alters circuit, simulator or raw evidence."""
import argparse, csv, hashlib, json, re
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def analyze(path,out):
 prefix='p1_ams_acquire_alignment.dut.'
 wanted={'SAMPLE_CMD','TOP','TOPB','ACQ','CONV','INP','INN','RP','RN','Q','QB','VDD'}
 wanted.update('XADC.XADC_'+s for s in ['TP','TN','BP0','BN0','BP11','BN11','DP','DN'])
 for branch in ['XP1','XN4','XN11','XDP']:
  wanted.update('XADC.XADC_'+branch+'_'+s for s in ['NL','PH','ACQB','NLB','PHB'])
 wanted.update('XPHASE.XPHASE_'+s for s in ['CMD_B','CMD_B_DELAY','ACQ_DELAY','CONV_DELAY','ACQ_RAW','CONV_RAW','TOP_RAW_B'])
 rows=[]; cur=None; head={}; active=False; aliases={}; alias_pending=None
 with path.open() as f:
  for line in f:
   if line.strip()=='VALUE': active=True;continue
   if not active:
    g=re.match(r'^"([^"]+)" GROUP ([0-9]+)\s*$',line)
    if g:
     if g.group(2)!='1':raise ValueError('Unsupported multi-signal PSF group')
     alias_pending=g.group(1);continue
    if alias_pending:
     g=re.match(r'^"([^"]+)"\s+"[^"]+"',line)
     if not g:raise ValueError('Malformed PSF group trace')
     aliases[alias_pending]=g.group(1);alias_pending=None;continue
   m=re.match(r'^"([^"]+)"\s+([^ ]+)\s*$',line)
   if not m: continue
   name,s=m.groups()
   if not active:
    try:head[name]=float(s)
    except ValueError: pass
    continue
   if name=='time':
    if cur is not None: rows.append(cur)
    cur={'time':float(s)};continue
   name=aliases.get(name,name)
   name=name.removeprefix(prefix)
   if name.startswith('p1_ams_acquire_alignment.'):
    name=name.removeprefix('p1_ams_acquire_alignment.').upper()
   if name in wanted:
    try:cur[name]=float(s)
    except ValueError:raise ValueError('non-real selected trace '+line)
 if cur:rows.append(cur)
 names=sorted(set().union(*(r.keys() for r in rows))-{'time'})
 for r in rows:
  if set(r)!={'time',*names}:raise ValueError('Incomplete waveform row')
 out.mkdir(exist_ok=False)
 with (out/'selected_waveforms.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['time']+names);w.writeheader();w.writerows(rows)
 timing={}
 for key in ['SAMPLE_CMD','CONV','ACQ','TOP','TOPB','XPHASE.XPHASE_ACQ_DELAY']:
  hits=[]
  for a,b in zip(rows,rows[1:]):
   if a[key]==b[key]:continue
   if (a[key]<.9<=b[key]) or (a[key]>.9>=b[key]):
    t=a['time']+(.9-a[key])/(b[key]-a[key])*(b['time']-a['time'])
    if 4e-6<t<4.2e-6:hits.append({'time_s':t,'direction':'rising' if b[key]>a[key] else 'falling'})
  timing[key]=hits
 win=[r for r in rows if 4.05e-6<=r['time']<=4.15e-6]
 result={'status':'DIAGNOSIS_ONLY_AUTOMATIC_LTE_RELAXATION_PRESENT','raw_sha256':sha(path),'raw_bytes':path.stat().st_size,'sample_count':len(rows),'end_time_s':rows[-1]['time'],'actual_solver_header':{k:head.get(k) for k in ['reltol','abstol(V)','abstol(I)','maxstep','gmin','cmin']},'half_supply_crossings':timing,'transition_window_s':[4.05e-6,4.15e-6],'transition_ranges':{n:{'min':min(r[n] for r in win),'max':max(r[n] for r in win)} for n in names},'initial_values':rows[0],'final_values':rows[-1],'limitation':'Half-supply crossing is a logic timing measure, not proof of analog TG nonoverlap or device-off current. Waveforms were produced with LTE relaxations and cannot establish ADC precision.'}
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('raw',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=analyze(a.raw,a.output)
 print(json.dumps({k:r[k] for k in ['raw_sha256','sample_count','end_time_s','half_supply_crossings']},indent=2))
