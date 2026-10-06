#!/usr/bin/env python3
"""Analyze returned native external RC pair; no EDA, model or gate changes."""
from pathlib import Path
import hashlib, importlib.util, json, re, sys
import numpy as np
HERE=Path(__file__).resolve().parent
CLOSURE=HERE.parents[1]
RUN=CLOSURE/'runs/task_20260924T073606929136Z/design'
OLD=CLOSURE/'runs/task_20260924T070754684209Z/design'
spec=importlib.util.spec_from_file_location('helper',HERE.parent/'adaptive_trap_4p1us_review_r1/analyze.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inv(log):
    section=log.split('Circuit inventory:',1)[1].split('\n\n',1)[0]
    return {m[1]:int(m[2]) for line in section.splitlines() if (m:=re.fullmatch(r'\s*(\S+)\s+(\d+)\s*',line))}
def fixture_audit(run,old):
    a=(old/'p2_ams_reset1.vams').read_text();b=(run/'p2_ams_reset1.vams').read_text()
    lines=['    I(rp_source,rp) <+ V(rp_source,rp)/1.0;','    I(rn_source,rn) <+ V(rn_source,rn)/1.0;',
           '    I(rp,vss) <+ 10n*ddt(V(rp,vss));','    I(rn,vss) <+ 10n*ddt(V(rn,vss));']
    insert='\n  // Equation-equivalent external reference source impedance and decoupling.\n  p2_reference_fixture refp(.SRC(rp_source),.REF(rp),.VSS(vss));\n  p2_reference_fixture refn(.SRC(rn_source),.REF(rn),.VSS(vss));\n'
    reconstructed=a.replace('\n'.join(lines)+'\n','').replace('  end\n\n  sar_controller','  end\n'+insert+'\n  sar_controller')
    source=(run/'reference_fixture.scs').read_text()
    expected='simulator lang=spectre\n// External bench only. Same 1 ohm and 10 nF as removed VAMS branch contributions.\nsubckt p2_reference_fixture (SRC REF VSS)\nRREF (SRC REF) resistor r=1\nCREF (REF VSS) capacitor c=10n\nends p2_reference_fixture\n'
    control=(run/'amsdControl.scs').read_text();oldcontrol=(old/'amsdControl.scs').read_text()
    expected_control=oldcontrol.replace('include "reset1_native_bound.scs"','include "reset1_native_bound.scs"\ninclude "reference_fixture.scs"').replace('amsd {','amsd {\n portmap subckt=p2_reference_fixture\n config cell=p2_reference_fixture use=spice')
    log=(run/'xrun.log').read_text(errors='replace');oldlog=(old/'xrun.log').read_text(errors='replace')
    inventory=inv(log);oldinventory=inv(oldlog)
    delta={k:inventory.get(k,0)-oldinventory.get(k,0) for k in inventory.keys()|oldinventory.keys()}
    checks={'each_original_contribution_once':all(a.count(x)==1 for x in lines),
      'all_four_contributions_removed':all(x not in b for x in lines),
      'only_exact_expected_VAMS_change':reconstructed==b,
      'fixture_exact_1ohm_10nF_and_nodes':source==expected,
      'only_expected_control_include_and_binding_change':control==expected_control,
      'actual_log_portbind_created_and_used':"amsspice: *Notice (reference_fixture.scs): Creating and using port-bind file:" in log and 'p2_reference_fixture.pb' in log,
      'actual_inventory_only_two_R_two_C_added':delta.get('capacitor')==2 and delta.get('resistor')==2 and all(v==0 for k,v in delta.items() if k not in ['capacitor','resistor'])}
    return {'checks':checks,'new_inventory':inventory,'old_inventory':oldinventory,'inventory_delta':delta,
      'fixture_sha256':sha(run/'reference_fixture.scs'),
      'actual_named_instance_connections_independent_generated_evidence':'PENDING_MINIMAL_REMOTE_READBACK',
      'noise_equivalence':False,'scope':'Deterministic transient equations only; primitive resistor noise differs from noiseless VAMS contribution.'}
def main():
    assert not (HERE/'review.json').exists()
    data={};olddata={};profiles={};identity={}
    for p in ['baseline','strict']:
        run=RUN/p;m=json.loads((run/'manifest.json').read_text())
        data[p]=h.raw(run);olddata[p]=h.raw(OLD/p)
        identity[p]={n:sha(run/n)==v for n,v in m['files_sha256'].items()}
        profiles[p]={**data[p][2],**h.logs(run),'input_identity':identity[p],
          'manifest_sha256':sha(run/'manifest.json'),
          'prepared_manifest_identical':(run/'manifest.json').read_bytes()==(HERE.parent/'native_ref_cthresh_4p1us_r1'/p/'manifest.json').read_bytes(),
          'chip_RTL_and_other_stimulus_files_unchanged':{n:(run/n).read_bytes()==(OLD/p/n).read_bytes() for n in h.FILES if n!='p2_ams_reset1.vams'},
          'fixture_audit':fixture_audit(run,OLD/p)}
    common=np.unique(np.concatenate([x[0] for x in list(data.values())+list(olddata.values())]+[np.array([0,4.1e-6,4.06315e-6,4.06335e-6])]))
    domains={}
    for label,lo,hi in [('full_short',0,4.1e-6),('local_CONV',4.06315e-6,4.06335e-6)]:
        grid=common[(common>=lo)&(common<=hi)]
        domains[label]={'domain_s':[lo,hi],'same_grid_count':len(grid),
          'old_VAMS_cthresh':h.compare(olddata['baseline'],olddata['strict'],grid)[0],
          'native_RC_cthresh':h.compare(data['baseline'],data['strict'],grid)[0]}
    grid=np.union1d(data['baseline'][0],data['strict'][0]);stats,cols=h.compare(data['baseline'],data['strict'],grid)
    np.savetxt(HERE/'all_accepted_union_differences.csv',cols,delimiter=',',header='time_s,'+','.join(h.CHANNELS),comments='',fmt='%.16e')
    actual=[profiles[p]['actual_header'] for p in ['baseline','strict']]
    wanted={'reltol':(1e-6,1e-7),'abstol(V)':(1e-8,1e-9),'abstol(I)':(1e-13,1e-14),'maxstep':(2e-9,1e-9)}
    checks={'all_input_hashes_match':all(all(v.values()) for v in identity.values()),
      'all_expected_fixture_static_and_inventory_checks':all(all(x['fixture_audit']['checks'].values()) for x in profiles.values()),
      'same_tool_method_temperature_options':all(actual[0].get(k)==actual[1].get(k) for k in ['version','method','relref','errpreset','lteratio','temp','tnom','gmin','cmin']),
      'actual_original_gear_method_and_lteratio':all(x.get('method')=='gear2only' and x.get('lteratio')==10 for x in actual),
      'actual_expected_tolerances':all(np.isclose(actual[i][k],v[i],atol=0,rtol=1e-8) for k,v in wanted.items() for i in [0,1]),
      'actual_cthresh_1p':all(x['cthresh_log_values']==['1e-12'] for x in profiles.values()),
      'complete_zero_to_4p1us':all(x[0][0]==0 and abs(x[0][-1]-4.1e-6)<1e-20 for x in data.values()),
      'both_simulator_exit0':all(x['simulator_exit_code']==0 for x in profiles.values()),
      'zero_frames_and_decisions_expected':all(not x['frames'] and not x['decisions'] for x in profiles.values()),
      'all_four_channels_within_original_gate':all(x['within_original_0p05_LSB'] for x in stats.values()),
      'no_unexplained_numeric_warning':all(not x['warning_code_counts'] for x in profiles.values())}
    result={'status':'SHORT_DOMAIN_NUMERICAL_FAIL' if not all(checks.values()) else 'SHORT_DIAGNOSTIC_NOT_ADC_QUALIFICATION',
      'checks':checks,'threshold_V':h.LIMIT,'union_points':len(grid),'all_accepted_union_statistics':stats,
      'same_domain_cthresh_representation_comparisons':domains,'profiles':profiles,
      'old_cthresh_evidence':{p:x[2] for p,x in olddata.items()},'analyzer_sha256':sha(Path(__file__)),
      'helper_sha256':sha(HERE.parent/'adaptive_trap_4p1us_review_r1/analyze.py'),
      'original_full_ADC_gate_unchanged':True,'complete_ADC_qualified':False,'long_campaign_allowed':False,
      'limits':['All accepted times retained, no time shift or switching-edge exclusion.',
        'Equivalent deterministic reference equations only; native resistor noise changes future noise model.',
        'cthresh application to original VAMS ddt was a hypothesis, not previously proven absent.',
        'Short run contains zero conversions; it cannot qualify full ADC or twelve-frame operation.']}
    (HERE/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
    print(json.dumps({'status':result['status'],'checks':checks,'stats':stats,'comparison':domains},indent=2))
    for p,d in profiles.items():print(p,json.dumps({k:d[k] for k in ['Spectre_final_summary','warning_code_counts','diagnostic_statistics','cthresh_log_values']}))
if __name__=='__main__':main()
