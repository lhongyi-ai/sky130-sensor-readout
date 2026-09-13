#!/usr/bin/env python3
"""One-worker, <=300 s, G16-only 45-PVT DC screen of one frozen core.

Run inside the existing SKY130 container. This does not test ADC conversions,
sampling, noise, gain1/gain4, mismatch, layout, or the complete frontend/chip.
Every invocation creates a new directory; earlier runs are never reused/edited.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
FRONT=HERE.parent
SOURCE=HERE/'results/20260910T062811944809Z_cascoded_tail_g16/candidate.spice'
EXPECTED_SOURCE='564f4776c4c61872de63648816ef5aaf51555769edeca326042f287880ae1a3c'
sys.path.insert(0,str(FRONT))
from measurement_evidence import verify_manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def stop_owned_process_group(process):
    """The group was created by this script for this one case only."""
    try:
        os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGKILL)
        process.wait(timeout=2)


def run_case(row,batch,deadline,per_case,core,nominal=None):
    remaining=deadline-time.monotonic()
    # Reserve termination/reaping time inside the stated wall-clock limits.
    cleanup_reserve=5
    if min(per_case,remaining)<=cleanup_reserve:
        row['status']='NOT_RUN_TOTAL_TIME_LIMIT'
        return
    case_name=f"linearity_{row['corner']}_{row['vdd_v']:g}_{row['temp_c']:g}_g16_r1_sw_iso2600.0"
    folder=batch/case_name
    row.update(status='RUNNING',path=str(folder.relative_to(HERE)),
               permitted_wall_seconds=min(per_case,remaining))
    row['subprocess_wait_timeout_s']=row['permitted_wall_seconds']-cleanup_reserve
    command=[sys.executable,str(FRONT/'qualify_advanced.py'),'linearity','--switchable','--gain','16',
             '--corner',row['corner'],'--vdd',str(row['vdd_v']),'--temp',str(row['temp_c']),
             '--isolation-r','2600','--core',str(core.relative_to(FRONT)),
             '--out',str(batch.relative_to(FRONT))]
    if nominal is not None:
        command+=['--calibration-from',str((nominal/'summary.json').relative_to(FRONT))]
        row['calibration_source']=str((nominal/'summary.json').relative_to(HERE))
        row['calibration_source_summary_sha256']=sha(nominal/'summary.json')
    else:
        row['calibration_source']='self, same corner at 1.8 V and 27 C only'
    row['command']=command
    output_log=batch/(case_name+'_driver.log')
    row['driver_log']=str(output_log.relative_to(HERE))
    environment=dict(os.environ,SPICE_USERINIT_DIR='/foss/pdks/sky130A/libs.tech/ngspice',
                     OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    started=time.monotonic()
    timed_out=False
    with output_log.open('x') as stream:
        process=subprocess.Popen(command,cwd=FRONT,env=environment,stdout=stream,
                                 stderr=subprocess.STDOUT,start_new_session=True)
        try:
            process.wait(timeout=row['subprocess_wait_timeout_s'])
        except subprocess.TimeoutExpired:
            timed_out=True
            stop_owned_process_group(process)
    row['elapsed_s']=time.monotonic()-started
    row['returncode']=process.returncode
    if timed_out:
        row['status']='TIMEOUT_INCOMPLETE'
        return
    if process.returncode:
        row['status']='SIMULATION_OR_ANALYSIS_FAILED'
        return
    summary_path=folder/'summary.json'
    try:
        summary=json.loads(summary_path.read_text())
        if not verify_manifest(folder):
            raise ValueError('New PVT screen requires immutable manifest, not legacy evidence')
        actual_core=folder/'frontend_pdk_snapshot.spice'
        if sha(actual_core)!=EXPECTED_SOURCE or summary['circuit_sha256']!=EXPECTED_SOURCE:
            raise ValueError('Source does not match this batch frozen circuit')
        if (summary['gain'],summary['corner'],summary['vdd_v'],summary['temp_c'])!=(16,row['corner'],row['vdd_v'],row['temp_c']):
            raise ValueError('Unexpected case metadata')
        row.update(summary_sha256=sha(summary_path),manifest_sha256=sha(folder/'evidence_manifest.json'),
                   source_sha256=sha(actual_core),artifact_integrity_status='VERIFIED_IMMUTABLE_MANIFEST',
                   calibration_coefficients=summary['calibration_coefficients'],
                   max_holdout_error_lsb=summary['max_holdout_error_lsb'],
                   max_output_cm_error_v=summary['max_output_cm_error_v'])
        if nominal is not None:
            if sha(folder/'calibration_source_summary.json')!=row['calibration_source_summary_sha256']:
                raise ValueError('Frozen calibration copy differs from the selected nominal calibration')
            row['frozen_calibration_summary_sha256']=sha(folder/'calibration_source_summary.json')
        gate='holdout_1LSB_gate' if nominal is None else 'fixed_calibration_4LSB_gate'
        row['static_accuracy_gate_name']=gate
        row['static_accuracy_limit_lsb']=1 if nominal is None else 4
        row['static_accuracy_pass']=summary[gate] is True
        row['status']='STATIC_ACCURACY_PASS' if row['static_accuracy_pass'] else 'STATIC_ACCURACY_FAIL'
    except (OSError,ValueError,KeyError,TypeError) as error:
        row.update(status='EVIDENCE_VALIDATION_FAILED',error=str(error))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--per-case-seconds',type=float,default=40)
    parser.add_argument('--total-seconds',type=float,default=300)
    parser.add_argument('--continue-from',type=Path,
                        help='Index completed prior cases and attempt remaining cases in a new batch, under the ORIGINAL total deadline')
    args=parser.parse_args()
    if not 0<args.per_case_seconds<=40 or not 0<args.total_seconds<=300:
        parser.error('Limits must be positive and no larger than 40 s per case / 300 s total')
    if sha(SOURCE)!=EXPECTED_SOURCE:
        raise ValueError('Requested immutable 564f candidate changed; refusing another circuit')
    prior=None
    if args.continue_from:
        prior=json.loads(args.continue_from.read_text())
        if prior['status']=='RUNNING' or prior['source_sha256']!=EXPECTED_SOURCE:
            raise ValueError('Continuation requires a completed, same-source batch index')
    batch=HERE/'qualification_g16_pvt'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    batch.mkdir(parents=True)
    core=batch/'frontend_snapshot.spice'
    core.write_bytes(SOURCE.read_bytes())
    corners=['tt','ff','ss','fs','sf']
    points=[(1.8,27)]+[(v,t) for v in [1.62,1.8,1.98] for t in [-20,27,85] if (v,t)!=(1.8,27)]
    rows=[{'corner':corner,'vdd_v':vdd,'temp_c':temp,'gain':16,'status':'NOT_RUN',
           'source_sha256':EXPECTED_SOURCE} for corner in corners for vdd,temp in points]
    if prior:
        rows=prior['cases']
        for row in rows:
            if row['status'] in ('BLOCKED_NO_VALID_NOMINAL_CALIBRATION','NOT_RUN_TOTAL_TIME_LIMIT','NOT_RUN'):
                row['prior_batch_status']=row['status']
                row['status']='NOT_RUN'
    report={'status':'RUNNING','created_utc':datetime.now(timezone.utc).isoformat(),
            'source_origin':str(SOURCE.relative_to(HERE)),'source_sha256':EXPECTED_SOURCE,
            'script_sha256':sha(Path(__file__)),'worker_count':1,
            'per_case_limit_s':args.per_case_seconds,'total_launch_and_wait_budget_s':args.total_seconds,
            'planned_cases':45,'gain':16,'points_per_case':81,'differential_sensor_range_v':[-0.025,0.025],
            'output_equivalent_range_v':[-0.4,0.4],'source_r_ohm_per_side':350,
            'requested_isolation_r_ohm_per_side':2600,
            'isolation_scope':'The existing DC bench drives no DC sampling current; it does not instantiate RISO. 2600 is recorded configuration, not a switched-load test.',
            'scope':'G16 frontend-only, 81-point deterministic DC transfer, three-point per-corner nominal calibration and fixed coefficients at other VT.',
            'calibration_policy':'Each corner needs a completed, integrity-verified nominal fit. A >1 LSB nominal static residual remains a specification FAIL but its valid fixed coefficients can still diagnose VT; this does not qualify the corner.',
            'full_frontend_qualified':False,'full_chip_qualified':False,'all_non_cadence_work_complete':False,
            'full_135_gain_pvt_chain_qualified':False,'noise_included':False,'mismatch_included':False,
            'cases':rows}
    report['budget_origin_utc']=(prior.get('budget_origin_utc',prior['created_utc']) if prior else report['created_utc'])
    if prior:
        report['continued_from_summary']=str(args.continue_from.resolve().relative_to(HERE))
        report['continued_from_summary_sha256']=sha(args.continue_from)
        report['continuation_note']='Prior raw cases and summaries are not modified; this new index references them and adds previously blocked/unrun VT diagnoses.'
    summary=batch/'summary.json'
    save(summary,report)
    started=time.monotonic()
    # One final second remains for bounded summary serialization after cases.
    deadline=started+args.total_seconds-1
    if prior:
        budget_end=datetime.fromisoformat(report['budget_origin_utc']).timestamp()+args.total_seconds
        deadline=started+max(0,budget_end-time.time())-1
    nominal_folders={}
    # First calibrate each corner fairly before spending the budget on VT sweeps.
    for corner in corners:
        row=next(row for row in rows if row['corner']==corner and (row['vdd_v'],row['temp_c'])==(1.8,27))
        if row['status']=='NOT_RUN':
            run_case(row,batch,deadline,args.per_case_seconds,core)
        if row['status'] in ('STATIC_ACCURACY_PASS','STATIC_ACCURACY_FAIL'):
            folder=HERE/row['path']
            if verify_manifest(folder) and sha(folder/'frontend_pdk_snapshot.spice')==EXPECTED_SOURCE:
                nominal_folders[corner]=folder
        row['nominal_spec_pass']=row.get('static_accuracy_pass',False)
        row['nominal_calibration_valid']=corner in nominal_folders
        print(json.dumps({key:row.get(key) for key in ['corner','vdd_v','temp_c','status','max_holdout_error_lsb','elapsed_s']}),flush=True)
        save(summary,report)
    for row in rows:
        if row['status']!='NOT_RUN':
            continue
        nominal=nominal_folders.get(row['corner'])
        if nominal is None:
            row['status']='BLOCKED_NO_VALID_NOMINAL_CALIBRATION'
        else:
            run_case(row,batch,deadline,args.per_case_seconds,core,nominal)
            print(json.dumps({key:row.get(key) for key in ['corner','vdd_v','temp_c','status','max_holdout_error_lsb','elapsed_s']}),flush=True)
        save(summary,report)
    report['elapsed_s']=time.monotonic()-started
    report['total_elapsed_since_budget_origin_s']=time.time()-datetime.fromisoformat(report['budget_origin_utc']).timestamp()
    counts=Counter(row['status'] for row in rows)
    report['case_status_counts']=dict(counts)
    report['completed_dc_cases']=sum(row['status'] in ('STATIC_ACCURACY_PASS','STATIC_ACCURACY_FAIL') for row in rows)
    report['all_45_static_accuracy_cases_pass']=counts['STATIC_ACCURACY_PASS']==45
    report['status']=('COMPLETE_G16_STATIC_ACCURACY_SCREEN_ONLY' if report['completed_dc_cases']==45
                      else 'INCOMPLETE_G16_STATIC_SCREEN')
    report['failed_accuracy_cases']=[{key:row[key] for key in ['corner','vdd_v','temp_c','max_holdout_error_lsb']}
                                     for row in rows if row['status']=='STATIC_ACCURACY_FAIL']
    report['corner_status']={corner:{
        'nominal_spec_pass':next(row for row in rows if row['corner']==corner and (row['vdd_v'],row['temp_c'])==(1.8,27)).get('nominal_spec_pass',False),
        'nominal_calibration_valid':corner in nominal_folders,
        'all_9_static_accuracy_cases_pass':all(row['status']=='STATIC_ACCURACY_PASS' for row in rows if row['corner']==corner),
        'corner_qualified':False} for corner in corners}
    report['limitations']=['Deterministic DC sweep is not noise-bearing dynamic accuracy, sampled SNDR, ADC INL/DNL or settling.',
                          'Only gain16; not three-gain 135-point whole-chain verification.',
                          'A DC operating point may exist for an unstable circuit; this screen cannot establish stability.',
                          'No mismatch, startup, reference switching, layout or parasitic extraction.',
                          'Timeouts, failed calibrations and unrun points remain incomplete; no lower threshold is substituted.']
    save(summary,report)
    print(json.dumps({'batch_summary':str(summary),'status':report['status'],
                      'counts':dict(counts),'elapsed_s':report['elapsed_s'],
                      'all_45_static_accuracy_cases_pass':report['all_45_static_accuracy_cases_pass'],
                      'full_frontend_qualified':False,'full_chip_qualified':False},indent=2),flush=True)


if __name__=='__main__':
    main()
