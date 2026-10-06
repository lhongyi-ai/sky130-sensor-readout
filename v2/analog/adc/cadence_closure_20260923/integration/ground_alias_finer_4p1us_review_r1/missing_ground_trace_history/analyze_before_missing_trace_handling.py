#!/usr/bin/env python3
"""Review only saved original/native ground finer attempts, preserving timeouts."""
from pathlib import Path
from collections import Counter
import hashlib,importlib.util,json,re,sys
import numpy as np
HERE=Path(__file__).resolve().parent
CLOSURE=HERE.parents[1]
spec=importlib.util.spec_from_file_location('prior',HERE.parent/'native_ref_lte1_4p1us_review_r1/analyze.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
h=prior.h
sys.path.insert(0,str(CLOSURE/'numerics'))
from psf_stream import Trace
RUNS={'original_finer':CLOSURE/'runs/task_20260924T075605661855Z/design/finer',
      'ground_alias_finer':CLOSURE/'runs/task_20260924T081210453008Z/design/finer'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inv(log):
    text=log.split('Circuit inventory:',1)[1].split('\n\n',1)[0]
    return {m[1]:int(m[2]) for s in text.splitlines() if (m:=re.fullmatch(r'\s*(\S+)\s+(\d+)\s*',s))}
def main():
    assert not (HERE/'review.json').exists()
    profiles={};data={}
    for label,run in RUNS.items():
        m=json.loads((run/'manifest.json').read_text());raw=run/'amsdControl.raw/adc_closure_tran.tran.tran'
        log=(run/'xrun.log').read_text(errors='replace');lines=log.splitlines()
        data[label]=h.raw(run)
        wanted=['vss','vdd','vcm','rp_source','rn_source']
        tr=Trace(raw,wanted={'p2_ams_reset1.'+n for n in wanted});minimum={n:float('inf') for n in wanted};maximum={n:float('-inf') for n in wanted};first=None
        for r in tr.rows():
            if first is None:first=r
            for n in wanted:
                minimum[n]=min(minimum[n],r['p2_ams_reset1.'+n]);maximum[n]=max(maximum[n],r['p2_ams_reset1.'+n])
        solution=Counter(re.findall(r'convergence failed at solution:\s*(\S+)',log))
        residue=Counter(re.findall(r'convergence failed at residue:\s*(\S+)',log))
        with raw.open('rb') as f:f.seek(max(0,raw.stat().st_size-256));end=f.read().rstrip().endswith(b'END')
        profiles[label]={**data[label][2],**h.logs(run),'input_identity':{n:sha(run/n)==v for n,v in m['files_sha256'].items()},
          'manifest_sha256':sha(run/'manifest.json'),'raw_END_present':end,'inventory':inv(log),
          'actual_voltage_ranges':{n:[minimum[n],maximum[n]] for n in wanted},'first_saved_source_voltages':first,
          'printed_failed_iteration_solution_counts':dict(solution),'printed_failed_iteration_residue_counts':dict(residue),
          'recovery_notice_count':log.count('Disaster recovery algorithm is enabled'),
          'last_recovery_lines':[s for s in lines if 'Newton iteration fails to converge at time' in s][-4:],
          'errors':[s for s in lines if 'ERROR (' in s],
          'original_vss_flow_failure_count':solution['p2_ams_reset1._cds_internal_p2_ams_reset1_:vss_flow'],
          'native_VGND_failure_count':solution['p2_ams_reset1.ground_ref.VGND:p'], 'observed_warning_line_count':sum(h.logs(run)['warning_code_counts'].values()), 'final_summary_available':bool(h.logs(run)['Spectre_final_summary'])}
    a,b=data.values();lo=max(a[0][0],b[0][0]);hi=min(a[0][-1],b[0][-1])
    grid=np.union1d(a[0],b[0]);grid=grid[(grid>=lo)&(grid<=hi)];stats,cols=h.compare(a,b,grid)
    np.savetxt(HERE/'partial_same_precision_representation_differences.csv',cols,delimiter=',',header='time_s,'+','.join(h.CHANNELS),comments='',fmt='%.16e')
    old,new=list(RUNS.values());prepared=HERE.parent/'ground_alias_finer_4p1us_r1/finer'
    newmanifest=json.loads((new/'manifest.json').read_text())
    headerfields=['version','reltol','abstol(V)','abstol(I)','maxstep','temp','tnom','method','lteratio','relref','errpreset','gmin','cmin']
    actualheaders=[data[n][2]['actual_header'] for n in RUNS]
    delta={k:profiles['ground_alias_finer']['inventory'].get(k,0)-profiles['original_finer']['inventory'].get(k,0) for k in profiles['ground_alias_finer']['inventory'].keys()|profiles['original_finer']['inventory'].keys()}
    checks={'all_input_hashes_match':all(all(p['input_identity'].values()) for p in profiles.values()),
      'matches_frozen_ground_input_package':all((new/n).read_bytes()==(prepared/n).read_bytes() for n in newmanifest['files_sha256']) and (new/'manifest.json').read_bytes()==(prepared/'manifest.json').read_bytes(),
      'actual_same_precision_method_and_environment':all(actualheaders[0].get(k)==actualheaders[1].get(k) for k in headerfields),
      'original_finer_actual_profile':all(x.get('reltol')==1e-8 and x.get('abstol(V)')==1e-10 and x.get('abstol(I)')==1e-15 and x.get('maxstep')==.5e-9 for x in actualheaders),
      'cthresh_1p_retained':all(x['cthresh_log_values']==['1e-12'] for x in profiles.values()),
      'actual_inventory_only_reference_node_removed':delta.get('nodes')==-1 and all(v==0 for k,v in delta.items() if k!='nodes'),
      'ground_declaration_and_no_explicit_ground_source_in_input':(new/'p2_ams_reset1.vams').read_text().count('  ground vss;')==1 and 'V(vss) <+ 0.0;' not in (new/'p2_ams_reset1.vams').read_text() and not (new/'ground_fixture.scs').exists(),
      'vss_exactly_zero_at_every_saved_time':all(x['actual_voltage_ranges']['vss']==[0.0,0.0] for x in profiles.values()),
      'both_profiles_completed_requested_0_to_4p1us':all(x['initial_time_s']==0 and abs(x['last_time_s']-4.1e-6)<1e-20 and x['simulator_exit_code']==0 for x in profiles.values())}
    result={'status':'GROUND_ALIAS_INCOMPLETE_NO_REPAIR','checks':checks,'profiles':profiles,
      'inventory_delta':delta,'partial_comparison_domain_s':[float(lo),float(hi)],
      'partial_same_precision_representation_statistics':stats,'comparison_is_not_precision_convergence_pair':True,
      'original_gate_V':h.LIMIT,'original_full_domain_gate':'NOT_RUN_INCOMPLETE','complete_ADC_qualified':False,
      'original_ground_preparation_audit_sha256':sha(HERE.parent/'ground_alias_finer_4p1us_r1/preparation_audit.json'),
      'analyzer_sha256':sha(Path(__file__)),'limits':['No time shifting, row deletion/filling, tolerance/model/input changes or EDA run by this review.',
        'Both actual timeout exits retained; complete file syntax does not imply complete time domain.',
        'Solution/residue frequencies count printed Newton iterations, not independent causes or events.',
        'Ground reference declaration removes the redundant branch from the input; remaining source/driver flow and body-residual failures prevent completion.',
        'Partial common prefix ends before the later known phase-transition error; it cannot satisfy the full numerical gate.']}
    (HERE/'review.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
    print(json.dumps({'status':result['status'],'checks':checks,'domain':result['partial_comparison_domain_s'],'stats':stats},indent=2))
    for p,x in profiles.items():print(p,json.dumps({k:x[k] for k in ['last_time_s','rows_read','Spectre_final_summary','warning_code_counts','diagnostic_statistics','recovery_notice_count','actual_voltage_ranges']}))
if __name__=='__main__':main()
