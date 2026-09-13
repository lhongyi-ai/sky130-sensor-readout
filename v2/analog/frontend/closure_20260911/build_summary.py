#!/usr/bin/env python3
"""Rebuild a conservative same-source index; never edit experiment evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from measurement_evidence import verify_manifest


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    experiments=[];groups={}
    for folder in sorted((HERE/'diagnostics').iterdir()):
        if not folder.is_dir():continue
        path=folder/'summary.json'
        if not path.exists():
            log=(folder/'simulator.log').read_text(errors='replace') if (folder/'simulator.log').exists() else ''
            experiments.append({'path':str(folder.relative_to(HERE)),'status':'INCOMPLETE_NO_SUMMARY',
                                'timestep_failure':'timestep too small' in log.lower(),'qualified':False})
            continue
        report=json.loads(path.read_text())
        row={'path':str(path.relative_to(HERE)),'summary_sha256':sha(path),
             **{k:report[k] for k in ('status','ordinal','gain','source_sha256','elapsed_s') if k in report}}
        try:
            verified=verify_manifest(folder)
            row['integrity_status']='VERIFIED_IMMUTABLE_MANIFEST' if verified else 'UNVERIFIED_LEGACY'
            row['manifest_sha256']=sha(folder/'evidence_manifest.json') if verified else None
            if sha(folder/'frontend_pdk_snapshot.spice')!=report['source_sha256']:
                raise ValueError('Reported source hash differs from frozen source')
        except (ValueError,OSError) as error:
            row.update(integrity_status='EVIDENCE_INVALID',error=str(error))
        for key in ('corner','vdd_v','temp_c','max_holdout_error_lsb','static_accuracy_limit_lsb',
                    'static_accuracy_pass','max_output_cm_error_v','step_max_output_cm_error_v',
                    'preliminary_quiet_window_gate','preliminary_step_amplitude_gate',
                    'frontend_vdd_and_vcm_power_w','loops','step_windows'):
            if key in report:row[key]=report[key]
        row['frontend_or_chip_qualified']=False
        experiments.append(row)
        group=groups.setdefault(report['source_sha256'],{'source_sha256':report['source_sha256'],
                   'experiments':[],'full_frontend_qualified':False,'full_chip_qualified':False})
        group['experiments'].append(row)
    for group in groups.values():
        nominal=[r for r in group['experiments'] if (r.get('corner'),r.get('vdd_v'),r.get('temp_c'))==('tt',1.8,27)
                 and r.get('status')=='DIAGNOSTIC_COMPLETE' and r.get('integrity_status')=='VERIFIED_IMMUTABLE_MANIFEST']
        group['nominal_gains_with_complete_dc']=sorted({r['gain'] for r in nominal if 'static_accuracy_pass' in r})
        group['same_source_three_gain_nominal_static_pass']=bool(
            group['nominal_gains_with_complete_dc']==[1,4,16] and
            all(r.get('static_accuracy_pass') is True for r in nominal if 'static_accuracy_pass' in r))
        group['same_source_three_gain_preliminary_step_pass']=bool(
            {r['gain'] for r in nominal if 'preliminary_quiet_window_gate' in r}=={1,4,16} and
            all(r.get('preliminary_quiet_window_gate') is True and r.get('preliminary_step_amplitude_gate') is True
                for r in nominal if 'preliminary_quiet_window_gate' in r))
    analyses=[]
    for p in sorted((HERE/'baseline_analysis').glob('*/summary.json')):
        analyses.append({'path':str(p.relative_to(HERE)),'sha256':sha(p),
                         'manifest_verified':verify_manifest(p.parent)})
    settling=[]
    for p in sorted((HERE/'settling_analysis').glob('*/summary.json')):
        settling.append({'path':str(p.relative_to(HERE)),'sha256':sha(p),
                         'manifest_verified':verify_manifest(p.parent)})
    latest_source=sha(HERE/'candidates/headroom_c.spice')
    result={'status':'INCOMPLETE_FRONTEND_CLOSURE','updated_utc':datetime.now(timezone.utc).isoformat(),
            'diagnostic_count':len(experiments),'diagnostic_limit':8,'full_45_pvt_screen_count':0,
            'full_45_pvt_screen_limit':2,'new_full_pvt_status':'NOT_RUN_PREREQUISITE_GATES_FAILED',
            'worker_count':1,'latest_candidate_sha256':latest_source,'source_groups':groups,
            'experiments':experiments,'baseline_45_pvt_analyses':analyses,
            'static_cap_load_settling_analyses':settling,
            'full_frontend_qualified':False,'full_chip_qualified':False,'all_non_cadence_work_complete':False,
            'static_noise_qualified':False,'sampled_sndr_qualified':False,'pvt_qualified':False,
            'scope_notes':['All new DC cases use 81 full-range points. Three-point fitting is only at the nominal VT; the baseline hot case uses frozen baseline nominal coefficients.',
                           'DC+step diagnostics use RISO2600,4pF and static81.285pF per side, not a real SAR switched load.',
                           'Transient tests contain a +50mV input common-mode step and ±0.36V output-equivalent differential steps. They do not cover negative common-mode perturbation, startup, overdrive or all corners.',
                           'Quiet-window gates are preliminary and do not establish the 2.476847754us acquisition settling requirement.',
                           'The 50mV output-CM diagnostic bound is not the separate specified input-CM range.',
                           'Loop scalar down-crossing results are not formal stability when additional up-crossings or unknown RHP poles exist.',
                           'Reported power includes the frontend VDD and VCM ports only, not ADC/control/reference full-chip power.',
                           'Never combine candidate A static pass with candidate C reduced ringing or baseline noise to claim one passing frontend.']}
    output=HERE/'closure_summary.json'
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'summary_path':str(output),'diagnostic_count':len(experiments),
                      'latest_source_sha256':latest_source,'status':result['status']},indent=2))


if __name__=='__main__':main()
