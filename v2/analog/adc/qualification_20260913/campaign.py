#!/usr/bin/env python3
"""Prepare exact static grid; bounded resume stays closed until qualified."""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import shutil

import qualify as q

HERE=q.HERE

def prepare():
    snapshot=q.verify()
    campaign=HERE/'campaigns/ramp32'
    if campaign.exists():
        validate(campaign)
        return campaign
    original=q.sc.read_plan(q.SOURCE)
    campaign.mkdir(parents=True)
    shutil.copytree(HERE/'snapshot/frozen',campaign/'frozen')
    plan=dict(original)
    plan.pop('plan_sha256')
    plan.update(stage='ramp',steps_per_lsb=32,required_points=131073,
        input_v=q.sc.grid('ramp',32),batch_size=8,warmup_conversions=1,
        numeric_profile='strict',numeric=q.PROFILES['strict'],
        created_utc=datetime.now(timezone.utc).isoformat(),
        source_snapshot_sha256=q.sc.sha(HERE/'snapshot/manifest.json'),
        corrected_bridge=True,complete_adc_qualified=False)
    plan['plan_sha256']=q.sc.digest(plan)
    q.write(campaign/'plan.json',plan)
    (campaign/'build').mkdir()
    shutil.copy2(HERE/'snapshot/cosim_controller_fixed.so',campaign/'build/cosim_controller.so')
    q.write(campaign/'build/binary.json',{'sha256':q.sc.sha(campaign/'build/cosim_controller.so'),
        'plan_sha256':plan['plan_sha256'],'local_repaired_shim':True,
        'scope':'Container-specific binary; school-host ABI and simulator qualification not established'})
    shutil.copy2(HERE/'snapshot/runtime.json',campaign/'runtime.json')
    # A spectral record cannot be stitched from independently reset batches.
    spec=json.loads((HERE/'snapshot/spec.json').read_text())
    n=spec['analysis']['fft_samples']; fs=spec['spec']['sample_rate_hz']
    k=round(spec['analysis']['adc_tone_target_hz']/fs*n)
    while math.gcd(k,n)!=1: k+=1
    descriptor={'source_snapshot_sha256':plan['source_snapshot_sha256'],
        'status':'DESCRIPTORS_ONLY_NOT_SIMULATED','full_adc_qualified':False,
        'spectrum':{'samples':n,'sample_rate_hz':fs,'coherent_bin':k,
            'frequency_hz':k*fs/n,'input_amplitude_dbfs':spec['analysis']['amplitude_dbfs'],
            'differential_peak_v':.4*10**(spec['analysis']['amplitude_dbfs']/20),
            'stimulus':'continuous differential sine at analog source; never staircase code stimulus',
            'initial_warmup_conversions':256,'reset_during_retained_record_allowed':False,
            'noise_enabled':False,'deterministic_fft_is_noise_inclusive_sndr':False,
            'blockers':['12-frame numerical convergence and broader numerical coverage',
                'storage/streaming qualification without removing decision evidence',
                'continuous long-record restart semantics; XSPICE snapshot unsupported',
                'verified device transient-noise method before noise-inclusive SNDR claim']},
        'mismatch':{'required_independent_whole_adc_instances':spec['qualification']['mismatch_static_samples_min'],
            'proposed_seeds':list(range(spec['analysis']['seed'],spec['analysis']['seed']+200)),
            'model_section_candidate':'tt_mm','whole_adc_samples_completed':0,
            'seed_same_device_parameters_for_entire_sample':True,
            'blockers':['qualify exact composite device hierarchy under statistical section',
                'prove seed repeatability and independent-instance parameter variation',
                'do not combine separate CDAC-only and comparator-only samples as whole ADC yield',
                'spec-complete static sweep cost for 200 whole ADC instances']},
        'school_migration':{'spectre_ready':False,'automatic_batch_launch_allowed':False,
            'required':['school process models and license','Spectre syntax/model qualification',
                'real comparator-to-SAR bridge and 33-bit handshake qualification',
                'one short conversion case before any sweep']}}
    q.write(HERE/'campaigns/spectrum_and_mismatch.json',descriptor)
    return campaign

def validate(campaign):
    q.verify()
    plan=q.sc.read_plan(campaign)
    if plan['required_points']!=131073 or plan['steps_per_lsb']!=32 or len(plan['input_v'])!=131073:
        raise ValueError('full static coverage changed')
    if plan['source_snapshot_sha256']!=q.sc.sha(HERE/'snapshot/manifest.json'):
        raise ValueError('source snapshot changed')
    if q.sc.sha(campaign/'build/cosim_controller.so')!=q.sc.sha(HERE/'snapshot/cosim_controller_fixed.so'):
        raise ValueError('unqualified RTL bridge')
    return plan

def gate():
    path=HERE/'numerical_comparison.json'
    numeric=json.loads(path.read_text()) if path.exists() else {}
    return {'long_campaign_allowed':False,
        'bounded_numerical_status':numeric.get('status','NOT_YET_EVALUATED'),
        'reason':'No complete numerical campaign qualification certificate exists. A finite functional pass cannot qualify a long all-code sweep.',
        'required_full_grid':131073,'complete_adc_qualified':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','collect','gate','run'])
    p.add_argument('--retry-incomplete',action='store_true')
    args=p.parse_args()
    if args.command=='gate':
        print(json.dumps(gate(),indent=2));return 2
    campaign=prepare();validate(campaign)
    if args.command=='prepare':
        print(json.dumps({'status':'PLANNED_NOT_RUN','path':str(campaign),'points':131073}));return 0
    if args.command=='collect':
        with redirect_stdout(io.StringIO()): report=q.sc.collect(campaign)
        print(json.dumps({k:report[k] for k in ('status','required_points','completed_points','complete_adc_qualified')},indent=2))
        return 2 if report['status']=='INCOMPLETE_COVERAGE' else 0
    # Fail before sc.run, subprocess launch, or installing another tool.
    status=gate()
    if not status['long_campaign_allowed']:
        print(json.dumps(status,indent=2));return 2
    q.sc.run(campaign,1,900,args.retry_incomplete)
    return 0

if __name__=='__main__':raise SystemExit(main())
