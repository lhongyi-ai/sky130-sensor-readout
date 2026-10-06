#!/usr/bin/env python3
import json,sys,hashlib
from pathlib import Path
D=Path(__file__).resolve().parent;R=D.parent;P=R.parents[2]
sys.path.insert(0,str(P/'analog/frontend/cadence_20260923'));import audit_native_netlist as a
F=D/'comparator_fixture';F.mkdir(exist_ok=False)
objs=json.loads((D/'objects.json').read_text());sel=[x for x in objs if x['name'].startswith(('XADC_XPRE_','XADC_XCMP_'))];assert len(sel)==87
names={o['name'] for o in sel};native=R/'private_runtime/si_reset1_001/netlist'
body='\n'.join(line for n,line in a.logical_lines(native.read_text()) if line.split()[0] in names)+'\n';assert len(body.splitlines())==87
(F/'native_body.scs').write_text(body);(F/'objects.json').write_text(json.dumps(sel,indent=2)+'\n')
ports=['XADC_TN','XADC_TP','Q','QB','EVAL','VDD','VSS','RST_N']
(F/'comparator_native_bound.scs').write_text('simulator lang=spectre\nsubckt p1_actual_cmp_reset1 ('+' '.join(ports)+')\n'+body+'ends p1_actual_cmp_reset1\n')
(F/'input.scs.in').write_text('''simulator lang=spectre
global 0
include "__SCHOOL_MODEL_ENTRY__" section=tt
include "comparator_native_bound.scs"
VVDD (VDD 0) vsource dc=1.8
VTN (TN 0) vsource type=pulse val0=.9005 val1=.8995 delay=6.55u rise=1n fall=1n width=20u period=40u
VTP (TP 0) vsource type=pulse val0=.8995 val1=.9005 delay=6.55u rise=1n fall=1n width=20u period=40u
VEVAL (EVAL 0) vsource type=pulse val0=0 val1=1.8 delay=5u rise=1n fall=1n width=200n period=625n
VRST (RST_N 0) vsource type=pwl wave=[0 0 1u 0 1.001u 1.8 6.36u 1.8 6.361u 0 6.5u 0 6.501u 1.8]
XCMP (TN TP Q QB EVAL VDD 0 RST_N) p1_actual_cmp_reset1
simulatorOptions options temp=27 reltol=1e-5 vabstol=1e-8 iabstol=1e-13
saveOptions options save=allpub
reset_decide tran stop=9u maxstep=2n errpreset=conservative
''')
(F/'manifest.json').write_text(json.dumps({'status':'PREPARED_NOT_SIMULATED','native_source_cell':'p2adc_core_reset1_school_r1','native_source_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'primitives':87,'ports':ports,'rst_initial_low_until_s':1e-6,'midrun_reset_s':[6.36e-6,6.501e-6],'midrun_reset_asserted_during_real_EVAL':True,'positive_TN_minus_TP_V':.001,'negative_TN_minus_TP_V':-.001,'positive_decision_expected_Q':1,'negative_decision_expected_Q':0,'reset_Q':0,'reset_QB':1,'qualification_excludes_reset_preload_as_decision':True,'not_coverage':['power ramp','PVT','offset/noise','small input precision threshold','ADC conversions','physical reset driver skew']},indent=2)+'\n')
