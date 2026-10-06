#!/usr/bin/env python3
from pathlib import Path
import re,json
R=Path(__file__).resolve().parent
raw=R.parent/'private_runtime/reset1_comparator_001/reset_decide.tran.tran'
want={'EVAL','RST_N','Q','QB','XCMP.XADC_XCMP_S_BAR','XCMP.XADC_XCMP_R_BAR'}
rows=[];active=False;cur={}
for line in raw.open():
 if line.strip()=='VALUE':active=True;continue
 if not active:continue
 m=re.match(r'^"([^"]+)"\s+([-+eE.0-9]+)\s*$',line)
 if not m:continue
 n,v=m.group(1),float(m.group(2))
 if n=='time':
  if cur:rows.append(cur)
  cur={'time':v}
 elif n in want:cur[n]=v
if cur:rows.append(cur)
events=[]
for a,b in zip(rows,rows[1:]):
 for name in sorted(want):
  for v,label in [(.54,'logic_low'),(.9,'half_supply'),(1.26,'logic_high')]:
   if a[name]<v<=b[name] or a[name]>v>=b[name]:
    t=a['time']+(v-a[name])/(b[name]-a[name])*(b['time']-a['time'])
    events.append({'signal':name,'time_s':t,'threshold_V':v,'threshold':label,'direction':'rising' if b[name]>a[name] else 'falling'})
cycles=[]
for i in range(7):
 t=(5+.625*i)*1e-6;positive=i<3;name='XCMP.XADC_XCMP_S_BAR' if positive else 'XCMP.XADC_XCMP_R_BAR'
 e=[x for x in events if x['signal']==name and x['threshold']=='logic_low' and x['direction']=='falling' and t<x['time_s']<t+201e-9]
 q=[x for x in events if x['signal']=='Q' and x['threshold']==('logic_high' if positive else 'logic_low') and x['direction']==('rising' if positive else 'falling') and t<x['time_s']<t+201e-9]
 cycles.append({'eval_start_s':t,'input_sign':'positive' if positive else 'negative','physical_set_or_reset_first_activation_s':e[0]['time_s'] if e else None,'activation_delay_from_eval_start_s':e[0]['time_s']-t if e else None,'Q_actual_transition_s':q[0]['time_s'] if q else None,'interrupted_by_global_reset':i==2})
o={'status':'DIAGNOSIS_ONLY_NOT_NUMERICAL_PASS','notes':['Original150ns snapshots are retained, not changed to pass. Original ADC permits312.5ns EVAL high; this fixture used200ns.','Real S/R activation is evidence of analog regeneration, distinct from Q initially forced byglobalreset.','Negativepolarity did not requireQ1-to-Q0transition because midrunreset already clearedQ; another sequence must coverthat transition.'],'cycles':cycles,'events':events}
p=R/'comparator_fixture/regeneration_events_001.json';assert not p.exists();p.write_text(json.dumps(o,indent=2)+'\n');print(json.dumps(cycles,indent=2))
