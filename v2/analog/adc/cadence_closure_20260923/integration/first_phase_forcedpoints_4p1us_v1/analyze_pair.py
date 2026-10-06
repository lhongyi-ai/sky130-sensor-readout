#!/usr/bin/env python3
"""Inspect real short-probe output. Never produce an ADC qualification PASS."""
import argparse, csv, hashlib, json, re
from pathlib import Path
import numpy as np
from psf_stream import Trace

HERE=Path(__file__).resolve().parent
PREFIX='p2_ams_reset1.'
NODES={'TP':'adc.XADC_TP','TN':'adc.XADC_TN','RP':'rp','RN':'rn','VCM':'vcm',
       'VDD':'vdd','CONV':'conv_e','GATE':'phases.XPHASE_XBCONV_B',
       'BODY':'phases.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8.int_b',
       'SAMPLE':'sample_cmd_e','EVAL':'eval_e','Q':'q_e','QB':'qb_e'}
CHANNELS={'cdac_differential':('TP','TN'),'rp':('RP',),'rn':('RN',),'vcm':('VCM',),
          'CONV':('CONV',),'local_gate':('GATE',),'internal_body':('BODY',),'external_VDS':('CONV','VDD')}
LIMIT=.05*.8/4096
TIME_MATCH_TOL_S=1e-20 # Text/float representation only: 0.00001 fs, not phase alignment.
def json_scalar(value):
    """JSON boundary only: retain scalar value, reject unsupported objects/arrays."""
    if isinstance(value,(np.bool_,np.integer,np.floating)):return value.item()
    raise TypeError('Unsupported JSON value: '+type(value).__name__)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def forced_indices(times, required):
    j=np.searchsorted(times,required)
    lo=np.clip(j-1,0,len(times)-1);hi=np.clip(j,0,len(times)-1)
    ix=np.where(abs(times[lo]-required)<abs(times[hi]-required),lo,hi)
    errors=abs(times[ix]-required);present=errors<=TIME_MATCH_TOL_S
    return ix,{'expected_count':len(required),'present_count':int(present.sum()),
        'missing_times_s':required[~present].tolist(),'max_nearest_time_error_s':float(errors.max()),
        'nonmatching_point_details':[{'requested_s':float(r),'nearest_saved_s':float(t),'signed_error_s':float(t-r)} for r,t in zip(required[~present],times[ix[~present]])],
        'match_tolerance_s':TIME_MATCH_TOL_S,'no_postprocessing_interpolation_used':True,
        'timestamp_presence_alone_does_not_prove_solver_step_origin':True}
def load(run,raw,contract):
    manifest=json.loads((run/'manifest.json').read_text())
    integrity={name:sha(run/name)==digest for name,digest in manifest['generated_file_hashes'].items()}
    expected_nodes={PREFIX+s for s in manifest['save_policy']['selected_nodes']}
    expected_nodes.update(PREFIX+'trial_e['+str(i)+']' for i in range(12))
    expected_nodes.update(PREFIX+NODES[k] for k in ['GATE','BODY'])
    assert len(expected_nodes)==76
    # Validate every required saved voltage in every accepted row, not just plotted traces.
    trace=Trace(raw,wanted=expected_nodes);rows=list(trace.rows())
    data={k:np.array([r[PREFIX+s] for r in rows]) for k,s in NODES.items()}
    data['time']=np.array([r['time'] for r in rows])
    forced=np.array(contract['forced_times_fs'],dtype=float)*1e-15
    ix,presence=forced_indices(data['time'],forced)
    log=(run/'xrun.log').read_text(errors='replace')
    driver=(run/'driver.log').read_text(errors='replace')
    exit_path=run/'simulator_exit_code.txt'
    actual_rc=int(exit_path.read_text().strip()) if exit_path.exists() else None
    frames=list(csv.DictReader((run/'frames.csv').open()))
    decisions=list(csv.DictReader((run/'decisions.csv').open()))
    code_counts={code:len(re.findall(re.escape(code),log)) for code in sorted(set(re.findall(r'\b(?:SPECTRE|AHDLLINT)-\d+\b',log)))}
    local=(data['time']>=4.06315e-6)&(data['time']<=4.06335e-6)
    crossings={}
    for name,voltage in [('CONV_halfrail',data['CONV']-.5*data['VDD']),('external_VDS_zero',data['CONV']-data['VDD'])]:
        j=np.flatnonzero((voltage[:-1]>=0)&(voltage[1:]<0)&local[:-1]&local[1:])
        crossings[name]=[{'time_s':float(data['time'][i]-voltage[i]*(data['time'][i+1]-data['time'][i])/(voltage[i+1]-voltage[i])),
          'actual_bracket_s':[float(data['time'][i]),float(data['time'][i+1])]} for i in j]
    unique_forced=set(ix[abs(data['time'][ix]-forced)<=TIME_MATCH_TOL_S])
    natural_count=len(data['time'])-len(unique_forced)
    summary={'raw_sha256':sha(raw),'actual_header':trace.header,'voltage_trace_count':len(trace.names),
      'all_76_required_traces_validated_every_row':True,
      'actual_interval_s':[float(data['time'][0]),float(data['time'][-1])],
      'accepted_unique_points':len(rows),'identical_duplicate_rows_recorded':trace.identical_duplicate_rows,
      'points_not_matching_forced_list':natural_count,
      'input_integrity_checks':integrity,'simulator_exit_code':actual_rc,
      'complete_short_interval':abs(data['time'][0])<=TIME_MATCH_TOL_S and abs(data['time'][-1]-contract['stop_s'])<=TIME_MATCH_TOL_S,
      'forced_point_presence':presence,'frames_completed':len(frames),'decisions_completed':len(decisions),
      'no_protocol_failure_marker':'P2_FAIL' not in driver,'warning_code_mentions':code_counts,
      'breakpoint_stepover_reported':'WARNING (SPECTRE-17087)' in log,
      'accepted_tran_steps_log':int(re.search(r'Number of accepted tran steps\s*=\s*(\d+)',log)[1]) if re.search(r'Number of accepted tran steps\s*=\s*(\d+)',log) else None,
      'all_warning_lines':[line for line in log.splitlines() if re.search(r'warning|LTE|recovery|recover',line,re.I)],
      'actual_local_crossings':crossings,
      'model_identity':'Requires root check of on-school PDK/model hashes; matching include pathname alone is not identity.'}
    return manifest,data,ix,summary
def channel(data,parts):
    return data[parts[0]]-data[parts[1]] if len(parts)==2 else data[parts[0]]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('baseline',type=Path);ap.add_argument('strict',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--baseline-raw',type=Path);ap.add_argument('--strict-raw',type=Path)
    a=ap.parse_args()
    if a.output.exists():raise SystemExit('Refusing to overwrite review')
    contract=json.loads((HERE/'forced_time_contract.json').read_text())
    runs=[a.baseline,a.strict]; raws=[a.baseline_raw,a.strict_raw]
    parsed=[load(r,raw or r/'amsdControl.raw/adc_closure_tran.tran.tran',contract) for r,raw in zip(runs,raws)]
    (bm,b,bi,bs),(sm,s,si,ss)=parsed
    shared_names=['sar_controller.v','p1_interfaces.vams','p2_ams_reset1.vams','p2_sequence.sv','profile.vh','reset1_native_bound.scs','forced_time_contract.json']
    physical_identity=all(sha(a.baseline/n)==sha(a.strict/n) for n in shared_names)
    ba=(a.baseline/'amsdControl.scs').read_text();sa=(a.strict/'amsdControl.scs').read_text()
    profile_only=ba.replace('reltol=1e-5 vabstol=1e-8 iabstol=1e-13','reltol=1e-6 vabstol=1e-9 iabstol=1e-14').replace('maxstep=2n','maxstep=1n')==sa
    bh,sh=bs['actual_header'],ss['actual_header']
    method_fields=['version','method','relref','errpreset','lteratio','temp','tnom','gmin','cmin']
    same_method=all(k in bh and k in sh and bh[k]==sh[k] for k in method_fields)
    actual_expected=all(h.get('version')==contract['required_tool_version'] and h.get('method')=='gear2only' and h.get('relref')=='sigglobal' and h.get('temp')==27 and h.get('tnom')==27 for h in [bh,sh])
    tolerances={'reltol':(1e-6,1e-7),'abstol(V)':(1e-8,1e-9),'abstol(I)':(1e-13,1e-14),'maxstep':(2e-9,1e-9)}
    actual_tols=all(k in bh and k in sh and np.isclose(bh[k],v[0],rtol=1e-8,atol=0) and np.isclose(sh[k],v[1],rtol=1e-8,atol=0) for k,v in tolerances.items())
    checks={'identical_physical_RTL_stimulus':physical_identity,'only_requested_profile_differences':profile_only,
      'same_actual_tool_method_environment':same_method,'expected_Spectre21_sigglobal_environment':actual_expected,
      'expected_actual_tolerances':bool(actual_tols),
      'both_inputs_integrity_verified':all(all(x['input_integrity_checks'].values()) for x in [bs,ss]),
      'both_complete_short_domains':all(x['complete_short_interval'] for x in [bs,ss]),
      'both_processes_exit0':all(x['simulator_exit_code']==0 for x in [bs,ss]),
      'both_zero_completed_frames_and_decisions':all(x['frames_completed']==0 and x['decisions_completed']==0 for x in [bs,ss]),
      'no_P2_FAIL':all(x['no_protocol_failure_marker'] for x in [bs,ss]),
      'all_forced_points_present_directly':all(x['forced_point_presence']['present_count']==contract['count'] for x in [bs,ss]),
      'no_solver_breakpoint_stepover_reported':not any(x['breakpoint_stepover_reported'] for x in [bs,ss]),
      'natural_points_outside_strobe_also_saved':all((x['points_not_matching_forced_list'] or 0)>0 for x in [bs,ss])}
    stats={}; a.output.mkdir(parents=True)
    forced=np.array(contract['forced_times_fs'])*1e-15
    both_present=(abs(b['time'][bi]-forced)<=TIME_MATCH_TOL_S)&(abs(s['time'][si]-forced)<=TIME_MATCH_TOL_S)
    shared_start=max(float(b['time'][0]),float(s['time'][0]));shared_stop=min(float(b['time'][-1]),float(s['time'][-1]))
    union=np.union1d(b['time'],s['time']);union=union[(union>=shared_start)&(union<=shared_stop)]
    # Missing endpoints/points remain failed checks. These explicitly partial views
    # diagnose available evidence; they are never a substitute passing domain.
    grids=[('partial_direct_common_saved_points',forced[both_present]),('partial_shared_actual_union',union)]
    for grid_name,times in grids:
        if len(times):
            result={};columns=[times]
            for name,parts in CHANNELS.items():
                if grid_name=='partial_direct_common_saved_points':delta=channel(s,parts)[si[both_present]]-channel(b,parts)[bi[both_present]]
                else:delta=np.interp(times,s['time'],channel(s,parts))-np.interp(times,b['time'],channel(b,parts))
                j=int(np.argmax(abs(delta)));columns.append(delta)
                result[name]={'max_abs_delta_V':float(abs(delta[j])),'time_s':float(times[j]),
                  'four_channel_reference_limit_only':name in ['cdac_differential','rp','rn','vcm'],
                  'below_original_limit_in_this_short_diagnostic':bool(abs(delta[j])<=LIMIT) if name in ['cdac_differential','rp','rn','vcm'] else None}
            stats[grid_name]=result
            np.savetxt(a.output/(grid_name+'.csv'),np.column_stack(columns),delimiter=',',header='time_s,'+','.join(CHANNELS),comments='',fmt='%.16e')
    report={'status':'SHORT_DIAGNOSTIC_REVIEW_COMPLETE_NOT_ADC_PASS' if all(checks.values()) else 'SHORT_DIAGNOSTIC_INCOMPLETE_OR_METHOD_MISMATCH',
      'checks':checks,'stats':stats,'runs':{'baseline':bs,'strict':ss},'reference_limit_V':LIMIT,
      'partial_diagnostic_domains':{'common_directly_saved_point_count':int(both_present.sum()),
        'shared_actual_interval_s':[shared_start,shared_stop],
        'shared_union_point_count':len(union),'does_not_replace_planned_zero_to_stop_domain':True},
      'original_two_frame_gate_status':'FAIL_RETAINED','complete_ADC_qualified':False,'long_campaign_allowed':False,
      'analyzer_sha256':sha(Path(__file__)),'PSF_reader_sha256':sha(HERE/'psf_stream.py'),
      'limitations':['This 4.1 us window contains no completed SAR conversion; it cannot prove ADC decision accuracy.',
        'Direct forced values avoid postprocessing interpolation but forcing points also changes adaptive integration.',
        'All accepted union comparison still uses linear interpolation; no dynamic phase alignment or cropping.',
        'Internal body differences are not missing-charge proof; terminal charge and branch current balance are not saved.',
        'All actual warning lines are retained; none are waived by this diagnostic.']}
    (a.output/'review.json').write_text(json.dumps(report,indent=2,allow_nan=False,default=json_scalar)+'\n')
    print(json.dumps({'status':report['status'],'checks':checks,'complete_ADC_qualified':False},indent=2,allow_nan=False,default=json_scalar))
    raise SystemExit(0 if all(checks.values()) else 2)
if __name__=='__main__':main()
