#!/usr/bin/env python3
"""Read-only fixed-I precision-control review; no simulation or gate changes."""
from pathlib import Path
from collections import Counter
import difflib, importlib.util, json, re
import numpy as np
HERE=Path(__file__).resolve().parent
CLOSURE=HERE.parents[1]
spec=importlib.util.spec_from_file_location('prior',HERE.parent/'native_ref_lte1_4p1us_review_r1/analyze.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
h=prior.h
RUNS={'strict_10fA':CLOSURE/'runs/task_20260924T074416052775Z/design/strict',
 'finer_1fA':CLOSURE/'runs/task_20260924T075605661855Z/design/finer',
 'finer_fixed_10fA':CLOSURE/'runs/task_20260924T081825369891Z/design/finer'}
def main():
    assert not (HERE/'review.json').exists(), 'Refusing to overwrite frozen review'
    profiles={};data={}
    for label,run in RUNS.items():
        m=json.loads((run/'manifest.json').read_text())
        raw=run/'amsdControl.raw/adc_closure_tran.tran.tran'
        log=(run/'xrun.log').read_text(errors='replace');lines=log.splitlines()
        data[label]=h.raw(run)
        with raw.open('rb') as f:
            f.seek(max(0,raw.stat().st_size-256));end=f.read().rstrip().endswith(b'END')
        inv=log.split('Circuit inventory:',1)[1].split('\n\n',1)[0]
        profiles[label]={**data[label][2],**h.logs(run),'raw_END_present':end,
          'input_identity':{n:h.sha(run/n)==v for n,v in m['files_sha256'].items()},
          'manifest_sha256':h.sha(run/'manifest.json'),
          'inventory':{a[1]:int(a[2]) for s in inv.splitlines() if (a:=re.fullmatch(r'\s*(\S+)\s+(\d+)\s*',s))},
          'printed_failed_iteration_solution_counts':dict(Counter(re.findall(r'convergence failed at solution:\s*(\S+)',log))),
          'printed_failed_iteration_residue_counts':dict(Counter(re.findall(r'convergence failed at residue:\s*(\S+)',log))),
          'recovery_notice_count':log.count('Disaster recovery algorithm is enabled'),
          'last_recovery_lines':[s for s in lines if 'Newton iteration fails to converge at time' in s][-4:],
          'errors':[s for s in lines if 'ERROR (' in s]}
    strict=RUNS['strict_10fA'];one=RUNS['finer_1fA'];new=RUNS['finer_fixed_10fA']
    oldtext=(strict/'amsdControl.scs').read_text();newtext=(new/'amsdControl.scs').read_text()
    expected=oldtext.replace('reltol=1e-6 vabstol=1e-9 iabstol=1e-14','reltol=1e-7 vabstol=1e-10 iabstol=1e-14').replace('maxstep=1n','maxstep=0.5n')
    manifest=json.loads((new/'manifest.json').read_text())
    unchanged={n:(strict/n).read_bytes()==(one/n).read_bytes()==(new/n).read_bytes() for n in manifest['files_sha256'] if n!='amsdControl.scs'}
    prepared=HERE.parent/'native_ref_finer_fixed_i_4p1us_r1/finer'
    headers=[profiles[n]['actual_header'] for n in RUNS]
    wanted={'reltol':(1e-7,1e-8,1e-8),'abstol(V)':(1e-9,1e-10,1e-10),
      'abstol(I)':(1e-14,1e-15,1e-14),'maxstep':(1e-9,.5e-9,.5e-9)}
    comparisons={}
    for key,other in [('strict_to_fixed_I_partial_precision','strict_10fA'),('one_fA_to_ten_fA_partial_control','finer_1fA')]:
        a=data[other];b=data['finer_fixed_10fA']
        lo=max(a[0][0],b[0][0]);hi=min(a[0][-1],b[0][-1])
        grid=np.union1d(a[0],b[0]);grid=grid[(grid>=lo)&(grid<=hi)]
        stats,columns=h.compare(a,b,grid)
        np.savetxt(HERE/(key+'.csv'),columns,delimiter=',',header='time_s,'+','.join(h.CHANNELS),comments='',fmt='%.16e')
        comparisons[key]={'domain_s':[float(lo),float(hi)],'accepted_union_points':len(grid),
          'four_channel_statistics':stats,'full_requested_0_to_4p1us_complete':False,
          'all_channels_within_limit_on_common_prefix_only':all(x['within_original_0p05_LSB'] for x in stats.values())}
    checks={'all_input_hashes_match':all(all(x['input_identity'].values()) for x in profiles.values()),
      'returned_input_matches_frozen_package':all((new/n).read_bytes()==(prepared/n).read_bytes() for n in manifest['files_sha256']) and (new/'manifest.json').read_bytes()==(prepared/'manifest.json').read_bytes(),
      'original_strict_to_new_only_voltage_relative_and_maxstep_tightening':expected==newtext,
      'failed_finer_to_new_only_Iabs_1fA_to_original_strict_10fA':(one/'amsdControl.scs').read_text().replace('iabstol=1e-15','iabstol=1e-14')==newtext,
      'all_other_input_files_byte_identical':all(unchanged.values()),
      'actual_precision_profiles_match_explicit_10fA_exception':all(np.isclose(headers[i].get(k,float('nan')),v[i],atol=0,rtol=1e-8) for k,v in wanted.items() for i in range(3)),
      'actual_same_method_environment':all(headers[0].get(k)==headers[1].get(k)==headers[2].get(k) for k in ['version','method','lteratio','relref','errpreset','temp','tnom','gmin','cmin']),
      'actual_cthresh_1p_all_profiles':all(p['cthresh_log_values']==['1e-12'] for p in profiles.values()),
      'circuit_inventories_identical':profiles['strict_10fA']['inventory']==profiles['finer_1fA']['inventory']==profiles['finer_fixed_10fA']['inventory'],
      'raw_files_parse_without_salvage_and_have_END':all(p['raw_END_present'] for p in profiles.values()),
      'fixed_I_completed_requested_0_to_4p1us':abs(profiles['finer_fixed_10fA']['last_time_s']-4.1e-6)<1e-20 and profiles['finer_fixed_10fA']['simulator_exit_code']==0}
    result={'status':'FIXED_I_PRECISION_CONTROL_INCOMPLETE_NO_REPAIR','checks':checks,
      'profiles':profiles,'comparisons':comparisons,'unchanged_noncontrol_files':unchanged,
      'original_gate_V':h.LIMIT,'original_full_domain_gate':'NOT_RUN_INCOMPLETE',
      'complete_ADC_qualified':False,'long_campaign_allowed':False,
      'analyzer_sha256':h.sha(Path(__file__)),'helper_sha256':h.sha(HERE.parent/'adaptive_trap_4p1us_review_r1/analyze.py'),
      'interpretation':['Original strict Iabstol remains 10 fA; relative/voltage tolerances and maxstep tighten. This does not independently establish absolute-current convergence.',
        'Timeout and all warnings retained. END means syntactically closed partial data, not completion of requested transient.',
        'Common-prefix union comparison uses linear interpolation without time shift or exclusion of switching edges. No extrapolation beyond saved time.',
        'Printed solution/residue counts are repeated Newton iterations, not independent causal events.',
        'No additional EDA or parameter search performed; no input, PDK, circuit, source waveform, or gate modified by review.'],
      'frozen_manifest_prose_correction':{'original_finer_true_last_time_s':profiles['finer_1fA']['last_time_s'],
        'incorrect_time_in_frozen_fixed_I_manifest_purpose_s':4.062500033593e-6,
        'reason':'Frozen purpose repeated the earlier partial-difference peak time. Raw-derived last_time_s is authoritative; frozen inputs preserved.'}}
    (HERE/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
    (HERE/'strict_to_fixed_I_input.diff').write_text(''.join(difflib.unified_diff(oldtext.splitlines(True),newtext.splitlines(True),fromfile='strict_10fA/amsdControl.scs',tofile='finer_fixed_10fA/amsdControl.scs')))
    print(json.dumps({'status':result['status'],'checks':checks,'comparisons':comparisons},indent=2))
    for n,p in profiles.items():print(n,json.dumps({k:p[k] for k in ['last_time_s','rows_read','Spectre_final_summary','warning_code_counts','diagnostic_statistics','recovery_notice_count']}))
if __name__=='__main__':main()
