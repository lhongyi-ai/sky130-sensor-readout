#!/usr/bin/env python3
"""Audit actual new local control artifacts, keeping DRC/LVS/PEX scopes separate."""
import sys
sys.dont_write_bytecode=True
import argparse,hashlib,importlib.util,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('audit_ro',HERE.parent/'cdac_repair_20260923/audit.py')
au=importlib.util.module_from_spec(spec);spec.loader.exec_module(au)
p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args();run=args.run.resolve()
man=json.loads((run/'manifest.json').read_text());gds=json.loads((run/'gds_readback.json').read_text())
assert gds['status']=='GDS_ONLY_M5_AGGRESSOR_POSITION_CHANGED'
assert hashlib.sha256((run/'mim_unit.mag').read_bytes()).hexdigest()==man['source_MIM_sha256']
results=[]
for label in ('inside','outside'):
 cell='p1cdac3_m5_'+label;log=(run/(label+'.log')).read_text()
 match=re.search(r'CONTROL_DRC_COUNT '+label+r' (\d+)',log);assert match and int(match[1])==0
 assert 'DRC style is now "drc(full)"' in log
 lvs=(run/(label+'_lvs.rpt')).read_text();assert 'Final result: Circuits match uniquely.' in lvs
 cap=au.parse(run/(cell+'.cap.spice'))
 assert set(cap['ports'])=={'TOP','BIT','AGG'} and cap['counts']['X']==128
 assert {pair for pair,value in cap['intrinsic'].items() if value!=0}=={('BIT','TOP')}
 assert cap['intrinsic'][('BIT','TOP')]==au.UNIT*128
 assert len(cap['nodes'])==4 and cap['components']==4
 values={name:float(au.pair(cap,*pair)) for name,pair in {'TOP_BIT_ff':('TOP','BIT'),'TOP_AGG_ff':('TOP','AGG'),'BIT_AGG_ff':('BIT','AGG'),'TOP_SUB_ff':('TOP','VSUBS'),'AGG_SUB_ff':('AGG','VSUBS')}.items()}
 results.append({'case':label,'full_DRC_count':0,'LVS_topology_match':True,'MIM_count':128,'MIM_unit_um':[3,3],'functional_MIM_total_ff':float(au.UNIT*128),'functional_C_basis':'Frozen prior open3x3 TT19.845fF unit characterization, not a new control simulation','reported_parasitic_capacitances':values,'extracted_ports':cap['ports'],'AGG_in_physical_cap_network':any('AGG' in pair for pair in cap['parasitic']),'LVS_note':'AGG intentionally disconnected in device-only LVS, because it is an isolated driven metal conductor. Its physical existence/connectivity is checked by GDS and nonzero extracted capacitance, not device LVS.'})
assert results[0]['reported_parasitic_capacitances']['TOP_BIT_ff']==results[1]['reported_parasitic_capacitances']['TOP_BIT_ff']
a=results[0]['reported_parasitic_capacitances']['TOP_AGG_ff'];b=results[1]['reported_parasitic_capacitances']['TOP_AGG_ff']
assert a>b
report={'status':'OPEN_3UM_GEOMETRY_LOCATION_CONTROL_COMPLETE','cases':results,'difference_inside_minus_outside_TOP_AGG_ff':a-b,'geometry_isolation':gds['status'],'conclusion':'This actual same-geometry-pair extraction shows internal M5 placement adds TOP coupling in this public Magic model; moving it outside removes the reported TOP-AGG item. It strengthens the routing hypothesis without qualifying the physical coefficient or repairing the full array.','zero_item_limitation':'No outside TOP-AGG capacitor was reported with cthresh0; do not interpret as measured physical zero or a guaranteed universal extraction error bound.','retained_failure':'../run_20260924T020658Z_4ba77ed4: initial thin M3 bridge control had192 full-DRC met3.3c violations. A common full-row M3 fill fixes both final controls.','not_executed':['school4x4 layout','complete binary array reroute','RC dynamic settling or transient noise','independent silicon calibration'],'formal_ADC_PEX_allowed':False,'full_CDAC_repair_pass':False}
(run/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
files={str(p.relative_to(run)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(run.iterdir()) if p.is_file() and p.name!='artifact_hashes.json'}
(run/'artifact_hashes.json').write_text(json.dumps(files,indent=2)+'\n')
print(json.dumps(report,indent=2))
