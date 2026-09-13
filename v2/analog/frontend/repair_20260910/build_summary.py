#!/usr/bin/env python3
"""Index every repair attempt without turning block diagnostics into signoff.

No circuit simulations or changes to historical experiment files are performed.
Rerun after experiments finish; running/failed/unanalysed directories remain visible.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from measurement_evidence import verify_manifest

FAILURE_TERMS=('error:','timestep too small','simulation(s) aborted','simulation interrupted')
LOCAL_GATES=('diagnostic_stability_gate','diagnostic_polarity_and_amplitude_gate','holdout_1LSB_gate','fixed_calibration_4LSB_gate',
             'all_dynamic_samples_pass','all_post_aperture_samples_pass',
             'common_mode_within_50mV','startup_gate_shutoff_below_0p2V','final_cm_within_50mV')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    def reject(value):
        raise ValueError('Nonfinite JSON number: '+value)
    return json.loads(Path(path).read_text(),parse_constant=reject)


def experiment_folders(root):
    parents=[root/'results',*sorted(root.glob('qualification*'))]
    return sorted({folder for parent in parents if parent.is_dir()
                   for folder in parent.iterdir() if folder.is_dir() and folder.name!='analyses'})


def index_folder(folder,root):
    row={'path':str(folder.relative_to(root)), 'full_frontend_qualified':False,
         'full_chip_qualified':False}
    summary_path=folder/'summary.json'
    summary={}
    if summary_path.exists():
        try:
            summary=read_json(summary_path)
            row['summary_sha256']=digest(summary_path)
        except (OSError,ValueError) as error:
            row['summary_read_error']=str(error)
    config={}
    if (folder/'experiment_config.json').exists():
        try:
            config=read_json(folder/'experiment_config.json')
        except (OSError,ValueError) as error:
            row['configuration_read_error']=str(error)
    arguments=summary.get('arguments',config)
    row.update(test=summary.get('test',config.get('test','static_step_diagnostic' if (folder/'bench.spice').exists() else 'unknown')),
               gain=summary.get('gain',arguments.get('gain')),
               corner=summary.get('corner',arguments.get('corner')),
               vdd_v=summary.get('vdd_v',arguments.get('vdd')),
               temp_c=summary.get('temp_c',arguments.get('temp',arguments.get('temperature'))),
               configuration=arguments)
    source=next((folder/name for name in ('candidate.spice','frontend_pdk_snapshot.spice','frontend_snapshot.spice','core_snapshot.spice')
                 if (folder/name).exists()),None)
    claimed=summary.get('circuit_sha256',summary.get('source_sha256'))
    row['claimed_source_sha256']=claimed
    row['source_sha256']=digest(source) if source else None
    row['source_snapshot']=source.name if source else None
    row['source_matches_claim']=row['source_sha256']==claimed if claimed else None
    try:
        verified=verify_manifest(folder)
        row['artifact_integrity_status']='VERIFIED_IMMUTABLE_MANIFEST' if verified else 'LEGACY_UNVERIFIED_NO_MANIFEST'
    except (OSError,ValueError,KeyError,TypeError) as error:
        row['artifact_integrity_status']='MANIFEST_INVALID_OR_CHANGED'
        row['artifact_integrity_error']=str(error)
    row['log_files']=[]
    error_lines=[]
    done=False
    for log in sorted(folder.glob('*.log')):
        text=log.read_text(errors='replace')
        row['log_files'].append(log.name)
        done=done or 'ngspice-47 done' in text
        for line in text.splitlines():
            if any(term in line.lower() for term in FAILURE_TERMS):
                error_lines.append({'log':log.name,'line':line[:500]})
    row['simulator_errors']=error_lines
    row['decks']=[path.name for path in sorted(folder.glob('*.spice'))
                  if path.name in ('bench.spice','sampling.spice','noise.spice','linearity.spice','startup.spice','gain.spice','cm.spice','dm.spice')]
    row['raw_files']=[{'name':path.name,'size_bytes':path.stat().st_size} for path in sorted(folder.glob('*.dat'))]
    row['declared_status']=summary.get('status')
    if 'cases' in summary:
        row['scope_note']='Batch index: its constituent PVT cases are retained in the referenced summary; this row is not a single analog operating condition.'
    if row['artifact_integrity_status']=='MANIFEST_INVALID_OR_CHANGED' or row['source_matches_claim'] is False:
        row['status']='INVALID_ARTIFACT_EVIDENCE'
    elif error_lines:
        row['status']='SIMULATOR_FAILURE' if summary else 'SIMULATOR_FAILURE_NO_SUMMARY'
    elif summary:
        row['status']=summary.get('status','BLOCK_ANALYSIS_COMPLETED_NOT_SIGNOFF')
    elif row.get('summary_read_error'):
        row['status']='UNREADABLE_SUMMARY_INCOMPLETE'
    elif done:
        row['status']='SIMULATION_DONE_NO_ANALYSIS_SUMMARY'
    else:
        row['status']='INCOMPLETE_OR_RUNNING_NO_SUMMARY'
    row['local_gates']={key:summary[key] for key in LOCAL_GATES if key in summary}
    row['failed_local_gates']=[key for key,value in row['local_gates'].items() if value is False]
    row['measurements']={key:value for key,value in summary.items()
        if key not in ('selected_mos_noise_contributors','extra_waveform_columns','arguments')}
    row['reanalyzed_reports']=[]
    for path in sorted((folder/'analyses').glob('*_summary.json')):
        try:
            analysis=read_json(path)
            row['reanalyzed_reports'].append({'path':str(path.relative_to(root)),
                'sha256':digest(path),'declared_artifact_integrity_status':analysis.get('artifact_integrity_status'),
                'current_base_manifest_status':row['artifact_integrity_status'],
                'analysis_code_sha256':analysis.get('analysis_code_sha256'),
                'local_gates':{key:analysis[key] for key in LOCAL_GATES if key in analysis},
                'note':'Indexed separately; does not replace or upgrade original evidence.'})
        except (OSError,ValueError) as error:
            row['reanalyzed_reports'].append({'path':str(path.relative_to(root)),'error':str(error)})
    return row


def add_same_source_noise_normalizations(records):
    """Never choose a best run or borrow calibration from a different circuit."""
    for noise in records:
        m=noise['measurements']
        raw=m.get('output_noise_1_to_1e+09Hz_rms_v')
        if raw is None:
            continue
        matches=[]
        for dc in records:
            if (dc['test']!='linearity' or dc['source_sha256']!=noise['source_sha256']
                or not dc['source_sha256'] or dc['gain']!=noise['gain'] or dc['corner']!=noise['corner']
                or dc['vdd_v']!=1.8 or dc['temp_c']!=27
                or dc['measurements'].get('gain_implementation')!=m.get('gain_implementation')
                or dc['status']!='BLOCK_ANALYSIS_COMPLETED_NOT_SIGNOFF'
                or noise['status']!='BLOCK_ANALYSIS_COMPLETED_NOT_SIGNOFF'):
                continue
            coefficients=dc['measurements'].get('calibration_coefficients',[])
            if len(coefficients)!=2:
                continue
            matches.append({'nominal_dc_report':dc['path']+'/summary.json',
                'source_sha256':dc['source_sha256'], 'calibration_scale':coefficients[0],
                'raw_continuous_noise_1Hz_to_1GHz_rms_v':raw,
                'calibration_normalized_continuous_noise_rms_v':raw*abs(coefficients[0]),
                'calibration_artifact_integrity_status':dc['artifact_integrity_status'],
                'scope':'Static continuous-time noise scaled by same-source nominal affine gain; NOT sampled noise, SNDR or a stability proof.'})
        noise['same_source_noise_normalizations']=matches


def build(root):
    records=[index_folder(folder,root) for folder in experiment_folders(root)]
    add_same_source_noise_normalizations(records)
    groups=defaultdict(list)
    for record in records:
        groups[record['source_sha256'] or 'UNKNOWN_SOURCE'].append(record)
    source_groups=[]
    for source,items in sorted(groups.items()):
        source_groups.append({'source_sha256':source,
            'gains_attempted':sorted({item['gain'] for item in items if item['gain'] is not None}),
            'experiment_paths':[item['path'] for item in items],
            'status_counts':dict(Counter(item['status'] for item in items)),
            'failed_local_gate_paths':[item['path'] for item in items if item['failed_local_gates']],
            'source_snapshot_mismatch_paths':[item['path'] for item in items if item['source_matches_claim'] is False],
            'full_frontend_qualified':False,
            'note':'Same core-source hash only. Gain, RISO, load, clock, stimulus and solver remain per-experiment conditions; their results are not interchangeable.'})
    return {'generated_utc':datetime.now(timezone.utc).isoformat(),
            'status':'IN_PROGRESS_FRONTEND_REPAIR_NOT_QUALIFIED',
            'full_frontend_qualified':False, 'full_chip_qualified':False,
            'all_non_cadence_work_complete':False,
            'experiment_count':len(records),
            'status_counts':dict(Counter(record['status'] for record in records)),
            'artifact_integrity_counts':dict(Counter(record['artifact_integrity_status'] for record in records)),
            'source_groups':source_groups, 'experiments':records,
            'limitations':[
                'Index of saved evidence, not a new simulator run or an electrical acceptance test.',
                'No best-of-different-candidates assembly; even same-source measurements use explicitly different benches.',
                'No missing-summary directory with a deck/log is silently treated as absent or passed.',
                'Legacy snapshots can match their recorded hash while raw/config/deck integrity remains unverified.',
                'Sampling summaries are acquisition/aperture-local; testbench reset shortens hold. Full 7.5 us conversion hold is not qualified.',
                'Continuous-time noise is not sampled/aliased system SNDR, and frontend rail power is not whole-chip power.',
                'Scalar loop margins do not provide a multi-loop RHP-pole count or formal stability signoff.',
                'The folder inventory and files can change while simulations run; rerun after they finish.']}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=HERE)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=build(args.root.resolve())
    output=args.output or args.root/'repair_summary.json'
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({'output':str(output),'experiments':result['experiment_count'],
                      'statuses':result['status_counts'],'integrity':result['artifact_integrity_counts'],
                      'full_frontend_qualified':False,'full_chip_qualified':False},indent=2))


if __name__=='__main__':
    main()
