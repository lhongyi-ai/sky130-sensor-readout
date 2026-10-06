#!/usr/bin/env python3
"""Frozen 3x3 open-PDK CDAC charge-network diagnosis; no new PEX claimed."""
import sys
sys.dont_write_bytecode = True
import csv, hashlib, importlib.util, json
from decimal import Decimal
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=HERE.parent/'cdac_repair_20260923/audit.py'
spec=importlib.util.spec_from_file_location('old_cdac_readonly',OLD)
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
D=Decimal

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def metrics(w):return audit.metrics(w)
def csvout(name,rows):
 with (HERE/name).open('w',newline='') as f:
  wr=csv.DictWriter(f,fieldnames=list(rows[0]));wr.writeheader();wr.writerows(rows)

def main():
 path=HERE.parent/'cdac_route_20260911/artifacts/cdac_diff_routed_flat_rc.spice'
 net=audit.parse(path)
 total={s:net['matrix'][net['nodes'].index(s+'_TOP')][net['nodes'].index(s+'_TOP')] for s in ('P','N')}
 par={s:[audit.pair(net,s+'_TOP',s+'_B'+str(i)) for i in range(12)] for s in ('P','N')}
 intr=[audit.UNIT*(1<<i) for i in range(12)]
 sides={s:[(intr[i]+par[s][i])/total[s] for i in range(12)] for s in ('P','N')}
 func=[sum(intr[i]/total[s] for s in ('P','N')) for i in range(12)]
 para=[sum(par[s][i]/total[s] for s in ('P','N')) for i in range(12)]
 full=[func[i]+para[i] for i in range(12)]
 lsb=sum(full)/D(4095)
 normalized={s:[x/(sum(sides[s])/D(4095)) for x in sides[s]] for s in ('P','N')}
 difference=[(normalized['P'][i]-normalized['N'][i])/2 for i in range(12)]
 diff_codes=[sum((difference[i] for i in range(12) if c&(1<<i)),D(0)) for c in range(4096)]
 rows=[]
 for i in range(12):
  # Exact endpoint-normalized error decomposition, with common full-network LSB.
  ferror=(func[i]-D(1<<i)*sum(func)/D(4095))/lsb
  perror=(para[i]-D(1<<i)*sum(para)/D(4095))/lsb
  assert abs(ferror)<D('1e-34')
  rows.append({'bit':i,'units':1<<i,'functional_ff_per_side':str(intr[i]),'P_parasitic_ff':str(par['P'][i]),'N_parasitic_ff':str(par['N'][i]),'functional_bit_error_LSB':str(ferror),'parasitic_bit_error_LSB':str(perror),'P_minus_N_half_normalized_error_LSB':str(difference[i])})
 csvout('bit_error_decomposition.csv',rows)
 pdiag=[]
 for pair,c in sorted(net['parasitic'].items()):
  category='TOP_to_bit' if any(n.endswith('_TOP') for n in pair) and any('_B' in n and not n.endswith('_BIAS') for n in pair) else 'TOP_to_fixed_other' if any(n.endswith('_TOP') for n in pair) else 'between_driven_non_TOP'
  pdiag.append({'node_a':pair[0],'node_b':pair[1],'capacitance_ff':str(c),'static_role':category})
 csvout('collapsed_capacitance_edges.csv',pdiag)
 # Dimensionless sensitivity only; no output netlist is altered or exported.
 slopes={s:par[s][8]/D(256) for s in ('P','N')}
 excess={s:[par[s][i]-slopes[s]*(1<<i) if i<=5 else D(0) for i in range(12)] for s in ('P','N')}
 def reduced(alpha):
  revised={s:[par[s][i]-(1-alpha)*excess[s][i] for i in range(12)] for s in ('P','N')}
  rt={s:total[s]-(1-alpha)*sum(excess[s]) for s in ('P','N')}
  return metrics([sum((intr[i]+revised[s][i])/rt[s] for s in ('P','N')) for i in range(12)])
 sweep=[{'retained_low_bit_excess_fraction':a/20,**reduced(D(a)/20)} for a in range(21)]
 csvout('excess_sensitivity.csv',sweep)
 lo,hi=D(0),D(1)
 assert reduced(lo)['pass_static_limits'] and not reduced(hi)['pass_static_limits']
 for _ in range(30):
  mid=(lo+hi)/2
  if reduced(mid)['pass_static_limits']:lo=mid
  else:hi=mid
 budget={'maximum_retained_low_bit_excess_fraction_pass_boundary':str(lo),'minimum_removed_fraction_near_boundary':str(1-lo),'pass_side':reduced(lo),'fail_side':reduced(hi),'meaning':'Diagnostic interpolation only; not a routing performance guarantee, measured tolerance or new circuit.'}
 report={'status':'STATIC_COMPONENT_ANALYSIS_COMPLETED','source_sha256':{str(path.relative_to(ROOT)):sha(path),str(OLD.relative_to(ROOT)):sha(OLD)},'unit_model_scope':'Frozen open-PDK 3x3 19.845 fF only; school4x4 excluded','reference_assumptions':['ideal settled bit/reference voltages','fixed DUMMY, EDGE_BIAS and substrate','linear capacitor values from historical extractor','all R connected nodes equilibrated; not a transient/settling result'],'full_network':metrics(full),'functional_only_with_same_TOP_denominators':metrics(func),'P_side':metrics(sides['P']),'N_side':metrics(sides['N']),'maximum_half_P_minus_N_INL_LSB':float(max(map(abs,diff_codes))),'sensitivity_boundary':budget,'causal_scope':'All endpoint-normalized static error is from non-binary TOP-bit parasitic weights in this frozen linear network. This does not validate extractor physical coefficients. Geometry isolation requires the control extraction.','between_driven_non_TOP_capacitances':'Do not alter this ideal-source static transfer; they still affect finite impedance reference current, settling and noise.','TOP_fixed_capacitances':'Change total gain/loading; binary intrinsic weights remain linear under endpoint normalization.','formal_ADC_PEX_allowed':False,'layout_repair_pass':False}
 (HERE/'static_decomposition.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
