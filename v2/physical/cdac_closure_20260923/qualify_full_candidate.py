#!/usr/bin/env python3
"""Audit original assignment -> extracted spatial terminals ->4096-code static C model."""
import sys
sys.dont_write_bytecode=True
import argparse,collections,csv,hashlib,importlib.util,json,re,shlex
from decimal import Decimal as D
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
s=importlib.util.spec_from_file_location('audit_ro',HERE.parent/'cdac_repair_20260923/audit.py');au=importlib.util.module_from_spec(s);s.loader.exec_module(au)
p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();run=a.run.resolve()
placement=json.loads((run/'placement.json').read_text());gds=json.loads((run/'full_gds_readback.json').read_text());assert gds['status']=='GDS_STRUCTURE_AND_UNIT_BODY_MATCH'
checks=[];sources={}
for side in ['P','N','TOP']:
 base=side.lower();log=(run/(base+'.log')).read_text();assert f'CANDIDATE_DRC_COUNT {side} 0' in log
 assert 'DRC style is now "drc(full)"' in log
 assert 'Final result: Circuits match uniquely.' in (run/(base+'_lvs.rpt')).read_text()
 checks.append({'object':side,'DRC_full_count':0,'LVS_unique_match':True})
# Unit extraction position comes from the frozen source .ext; 600 internal units =3um.
unitext=HERE.parent/'cdac_route_20260911/artifacts/mim_unit.ext';u=shlex.split(next(l for l in unitext.read_text().splitlines() if l.startswith('device ')))
assert set(u[7:9])=={'w=600','l=600'};xanchor,yanchor=int(u[3]),int(u[4]);grid_um=D(3)/600
spatial=[]
for side in ['P','N']:
 ass=HERE.parent/f'cdac/cdac_{side.lower()}_assignment.csv'
 original={(int(r['physical_row']),int(r['physical_col'])):r for r in csv.DictReader(ass.open())}
 sources[str(ass.relative_to(ROOT))]=hashlib.sha256(ass.read_bytes()).hexdigest()
 expected={}
 for punit in placement[side]:
  src=original[(punit['row'],punit['col'])];assert src['net']==punit['net'] and bool(int(src['electrical']))==punit['electrical']
  pt=(round(punit['x_um']/float(grid_um))+xanchor,round(punit['y_um']/float(grid_um))+yanchor)
  expected[pt]=(src['net'],'TOP') if punit['electrical'] else ('EDGE_BIAS','EDGE_BIAS')
 actual={}
 for line in (run/f'c3gap_{side.lower()}_flat.ext').read_text().splitlines():
  if not line.startswith('device '):continue
  t=shlex.split(line);assert t[1:3]==['csubckt','sky130_fd_pr__cap_mim_m3_1'] and set(t[7:9])=={'w=600','l=600'}
  pt=(int(t[3]),int(t[4]));assert pt not in actual;actual[pt]=(t[10],t[13])
 assert actual==expected,(side,len(actual),len(expected))
 spatial.append({'side':side,'checked_unit_locations':len(actual),'actual_extracted_terminal_pairs_match_original_csv_at_each_position':True})
netpath=run/'c3gap_diff.cap.spice';net=au.parse(netpath);assert net['counts']['X']==8712 and net['counts']['X_self_loop']==520 and len(net['ports'])==30 and net['components']==31
assert all(v==0 for pair,v in net['parasitic'].items() if pair[0].startswith('N_') and pair[1].startswith('P_'))
totals={side:net['matrix'][net['nodes'].index(side+'_TOP')][net['nodes'].index(side+'_TOP')] for side in ['P','N']}
weights=[];perbit=[]
for i in range(12):
 w=D(0)
 for side in ['P','N']:
  intrinsic=au.pair(net,side+'_TOP',side+'_B'+str(i),'intrinsic');assert intrinsic==au.UNIT*(1<<i)
  par=au.pair(net,side+'_TOP',side+'_B'+str(i));w+=(intrinsic+par)/totals[side]
  perbit.append({'side':side,'bit':i,'MIM_count':1<<i,'functional_ff':str(intrinsic),'extracted_TOP_bit_parasitic_ff':str(par),'TOP_total_ff':str(totals[side])})
 weights.append(w)
metrics=au.metrics(weights);assert metrics['pass_static_limits']
lsb=sum(weights)/D(4095);values=[sum((weights[i] for i in range(12) if code&(1<<i)),D(0)) for code in range(4096)]
with (run/'code_transfer.csv').open('w',newline='') as f:
 wr=csv.writer(f);wr.writerow(['code','dimensionless_differential_charge_transfer','endpoint_LSB_value','INL_LSB','DNL_to_next_LSB'])
 for code,value in enumerate(values):wr.writerow([code,str(value),str(value/lsb),str(value/lsb-code),str((values[code+1]-value)/lsb-1) if code<4095 else ''])
with (run/'bit_couplings.csv').open('w',newline='') as f:
 wr=csv.DictWriter(f,fieldnames=list(perbit[0]));wr.writeheader();wr.writerows(perbit)
old=json.loads((HERE/'static_decomposition.json').read_text())['full_network'];area_growth=gds['area_um2']/377377-1
report={'status':'OPEN_3UM_CDAC_STATIC_CANDIDATE_PASS','actual_DRC_LVS':checks,'spatial_assignment_checks':spatial,'raw_elements':net['counts'],'ports':30,'electrical_components_including_substrate':31,'source_sha256':sources,'unit_anchor_source_sha256':hashlib.sha256(unitext.read_bytes()).hexdigest(),'raw_cap_netlist_sha256':hashlib.sha256(netpath.read_bytes()).hexdigest(),'old_static':old,'new_static':metrics,'full_GDS_area_um2':gds['area_um2'],'area_growth_fraction_vs_old':area_growth,'functional_unit_ff':str(au.UNIT),'functional_unit_basis':'Frozen prior open3x3 TT characterization; constant-C approximation, not new silicon or Cadence result','analysis_scope':'Complete actual top-level capacitance extraction plus binary functional MIM weights; ideal settled reference/bit voltages, endpoint INL/DNL, 4096 codes. No extracted parasitics deleted or scaled.','formal_ADC_PEX_allowed':False,'school4x4_layout':False,'full_RC_transient_and_noise_validation':False,'full_ADC_linearity_validation':False,'geometry_moments':'All unit counts and first-moment offsets maintained; y second moments change with center channel and are explicitly reported.','tool_limitations':['Magic public coefficient accuracy not independently silicon-qualified','Netgen MIM placeholders compare topology/properties; GDS and extracted spatial terminals separately checked','This run is capacitance-only, not RC dynamic signoff','No mismatch/statistical/noise/sample-switch/reference-droop evidence from this experiment']}
(run/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
files={str(p.relative_to(run)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run.iterdir()) if p.is_file() and p.name!='artifact_hashes.json'};(run/'artifact_hashes.json').write_text(json.dumps(files,indent=2)+'\n')
print(json.dumps({'status':report['status'],'new_static':metrics,'area_um2':gds['area_um2'],'area_growth_percent':area_growth*100,'spatial':spatial},indent=2))
