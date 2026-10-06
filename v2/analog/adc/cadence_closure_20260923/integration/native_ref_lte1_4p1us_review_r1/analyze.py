#!/usr/bin/env python3
"""Independent read-only evidence review of native-reference lteratio=1 pair."""
from pathlib import Path
import hashlib, importlib.util, json, re
import numpy as np
HERE=Path(__file__).resolve().parent
CLOSURE=HERE.parents[1]
RUN=CLOSURE/'runs/task_20260924T074416052775Z/design'
OLD=CLOSURE/'runs/task_20260924T073606929136Z/design'
spec=importlib.util.spec_from_file_location('prior_native',HERE.parent/'native_ref_cthresh_4p1us_review_r1/analyze.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
h=prior.h
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tail_end(p):
    with p.open('rb') as f:f.seek(max(0,p.stat().st_size-256));return f.read().rstrip().endswith(b'END')
def main():
    assert not (HERE/'review.json').exists()
    data={};olddata={};profiles={};single_factor={}
    for p in ['baseline','strict']:
        run=RUN/p;old=OLD/p;m=json.loads((run/'manifest.json').read_text())
        data[p]=h.raw(run);olddata[p]=h.raw(old)
        log=(run/'xrun.log').read_text(errors='replace');oldlog=(old/'xrun.log').read_text(errors='replace')
        oldcontrol=(old/'amsdControl.scs').read_text();control=(run/'amsdControl.scs').read_text()
        single_factor[p]={'only_lteratio_1_added':control==oldcontrol.replace('errpreset=conservative relref=sigglobal','errpreset=conservative lteratio=1 relref=sigglobal'),
          'all_other_manifest_inputs_byte_identical':all((run/n).read_bytes()==(old/n).read_bytes() for n in m['files_sha256'] if n!='amsdControl.scs'),
          'source_manifest_sha256_matches':m['source_manifest_sha256']==sha(old/'manifest.json')}
        profiles[p]={**data[p][2],**h.logs(run),
          'input_hashes_match':{n:sha(run/n)==v for n,v in m['files_sha256'].items()},
          'manifest_sha256':sha(run/'manifest.json'),'raw_END_present':tail_end(run/'amsdControl.raw/adc_closure_tran.tran.tran'),
          'actual_inventory':prior.inv(log),'inventory_unchanged_from_native_ref_lte10':prior.inv(log)==prior.inv(oldlog),
          'actual_fixture_portbind_creation_and_use_logged':"amsspice: *Notice (reference_fixture.scs): Creating and using port-bind file:" in log and 'p2_reference_fixture.pb' in log,
          'original_native_ref_binding_audit_sha256':sha(HERE.parent/'native_ref_cthresh_4p1us_review_r1/fixture_binding_review.json')}
    grid=np.union1d(data['baseline'][0],data['strict'][0]);stats,columns=h.compare(data['baseline'],data['strict'],grid)
    np.savetxt(HERE/'all_accepted_union_differences.csv',columns,delimiter=',',header='time_s,'+','.join(h.CHANNELS),comments='',fmt='%.16e')
    common=np.unique(np.concatenate([v[0] for v in list(data.values())+list(olddata.values())]+[np.array([0,4.1e-6,4.06315e-6,4.06335e-6])]))
    domains={}
    for label,lo,hi in [('full_0_to_4p1us',0,4.1e-6),('local_CONV',4.06315e-6,4.06335e-6)]:
        g=common[(common>=lo)&(common<=hi)]
        domains[label]={'domain_s':[lo,hi],'common_grid_count':len(g),
          'native_reference_lteratio10':h.compare(olddata['baseline'],olddata['strict'],g)[0],
          'native_reference_lteratio1':h.compare(data['baseline'],data['strict'],g)[0]}
    actual=[profiles[p]['actual_header'] for p in ['baseline','strict']]
    wanted={'reltol':(1e-6,1e-7),'abstol(V)':(1e-8,1e-9),'abstol(I)':(1e-13,1e-14),'maxstep':(2e-9,1e-9)}
    checks={'all_input_hashes_match':all(all(x['input_hashes_match'].values()) for x in profiles.values()),
      'one_factor_only_lteratio10_to1':all(all(x.values()) for x in single_factor.values()),
      'inventory_and_fixture_binding_preserved':all(x['inventory_unchanged_from_native_ref_lte10'] and x['actual_fixture_portbind_creation_and_use_logged'] for x in profiles.values()),
      'actual_method_gear2only_lteratio1':all(x.get('method')=='gear2only' and x.get('lteratio')==1 for x in actual),
      'actual_cthresh1p':all(x['cthresh_log_values']==['1e-12'] for x in profiles.values()),
      'actual_original_tolerances':all(np.isclose(actual[i][k],v[i],rtol=1e-8,atol=0) for k,v in wanted.items() for i in [0,1]),
      'same_tool_temperature_relative_reference':all(actual[0].get(k)==actual[1].get(k) for k in ['version','temp','tnom','relref','errpreset','gmin','cmin']),
      'complete_zero_to_4p1us_and_END':all(x['raw_END_present'] and x['initial_time_s']==0 and abs(x['last_time_s']-4.1e-6)<1e-20 for x in profiles.values()),
      'simulators_exit0':all(x['simulator_exit_code']==0 for x in profiles.values()),
      'expected_zero_conversions_no_functional_failure_marker':all(not x['frames'] and not x['decisions'] and not x['P2_FAIL_present'] for x in profiles.values()),
      'all_four_channels_within_original_gate':all(x['within_original_0p05_LSB'] for x in stats.values()),
      'no_unexplained_numerical_warnings':all(not x['warning_code_counts'] for x in profiles.values())}
    result={'status':'SHORT_DOMAIN_NUMERICAL_FAIL' if not all(checks.values()) else 'SHORT_DIAGNOSTIC_ONLY_NOT_ADC_QUALIFIED',
      'checks':checks,'original_gate_V':h.LIMIT,'all_accepted_union_points':len(grid),
      'full_short_domain_statistics':stats,'same_domain_comparison':domains,'profiles':profiles,
      'single_factor_audit':single_factor,'old_reference_evidence':{p:x[2] for p,x in olddata.items()},
      'analyzer_sha256':sha(Path(__file__)),'helper_sha256':sha(HERE.parent/'adaptive_trap_4p1us_review_r1/analyze.py'),
      'complete_ADC_qualified':False,'full_record_threshold_unchanged':True,
      'limits':['All accepted times and edges retained; no time shifting or gate relaxation.',
        'Union interpolation includes event-timing and interpolation contributions to the original metric.',
        'Equivalent reference equations apply to deterministic transient only; native resistor noise is separately relevant.',
        'Zero completed conversions in this short test; two-frame and twelve-frame ADC gates are not satisfied.']}
    (HERE/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
    print(json.dumps({k:result[k] for k in ['status','checks','full_short_domain_statistics','same_domain_comparison']},indent=2))
    for p,x in profiles.items():print(p,json.dumps({k:x[k] for k in ['Spectre_final_summary','warning_code_counts','diagnostic_statistics','suppression_lines']}))
if __name__=='__main__':main()
