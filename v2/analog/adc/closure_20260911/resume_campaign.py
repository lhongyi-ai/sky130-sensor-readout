#!/usr/bin/env python3
"""Bounded resumable runner using the locally repaired bridge, never old shim.

No simulation starts at initialization. Each explicit run invokes at most one
batch / 360 seconds. Incomplete attempts remain; retry is opt-in. The inherited
static runner's file hashes and exclusive worker lock remain enforced.
"""
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil

import trace_replay as tr


def verify_fixed_evidence(directory):
    record = json.loads((directory / 'bridge_certificate.json').read_text())
    if record['handshake']['status'] != 'BOUNDED_STATUS_PORTS_PASS':
        raise ValueError('fixed bridge status ports did not pass')
    if record['comparator']['matched_decisions'] != 72 or not record['installed_shim_unchanged']:
        raise ValueError('local bridge repair is not validated')
    summary = directory / 'summary.json'
    if tr.sc.sha(summary) != record['summary_sha256']:
        raise ValueError('fixed bridge summary changed')
    result = json.loads(summary.read_text())
    for name, expected in result['source_and_output_sha256'].items():
        if tr.sc.sha(directory / name) != expected:
            raise ValueError('fixed bridge evidence changed: ' + name)
    provenance = json.loads((directory / 'provenance.json').read_text())
    for name, expected in provenance['build_artifact_sha256'].items():
        if tr.sc.sha(directory / 'build' / name) != expected:
            raise ValueError('fixed bridge artifact changed: ' + name)
    return record


def initialize(campaign, stage, repair):
    if campaign.exists():
        raise ValueError('immutable campaign exists; use run to resume')
    evidence = verify_fixed_evidence(repair)
    _, original, _ = tr.read_original()
    points = tr.sc.grid(stage, 32, [.123, -.25 * tr.sc.LSB, .25 * tr.sc.LSB])
    campaign.mkdir(parents=True)
    shutil.copytree(tr.CAMPAIGN / 'frozen', campaign / 'frozen')
    plan = dict(original)
    plan.pop('plan_sha256')
    plan.update(stage=stage, input_v=points, required_points=len(points), steps_per_lsb=32,
                # Three retained inputs plus one warmup each fit the measured
                # approximately 200-second case; later batches add one replay.
                batch_size=3, warmup_conversions=1, created_utc=datetime.now(timezone.utc).isoformat())
    audit = {'repair_directory': str(repair), 'certificate_sha256': tr.sc.sha(repair / 'bridge_certificate.json'),
             'local_bridge_sha256': tr.sc.sha(repair / 'build/cosim_controller_fixed.so'),
             'status': 'BOUNDED_STATUS_AND_REAL_COMPARATOR_REVALIDATED',
             'old_bridge_qualification_scope_correction': 'The inherited record did not cover packed bits 32 and 31. Do not use it to qualify ready/busy.',
             'analog_numeric_equivalence_status': evidence['analog_comparison']['status'],
             'complete_adc_qualified': False, 'full_interface_qualified': False,
             'runner_sha256': tr.sc.sha(Path(__file__))}
    evidence_path = campaign / 'frozen/bridge_fixed_evidence.json'
    tr.sc.write_json(evidence_path, audit)
    plan['sources'] = dict(original['sources'])
    plan['sources']['bridge_fixed_evidence.json'] = {'source': str(repair), 'sha256': tr.sc.sha(evidence_path)}
    plan['bridge_status_scope'] = audit['status']
    plan['plan_sha256'] = tr.sc.digest(plan)
    tr.sc.write_json(campaign / 'plan.json', plan)
    (campaign / 'build').mkdir()
    binary = campaign / 'build/cosim_controller.so'
    shutil.copy2(repair / 'build/cosim_controller_fixed.so', binary)
    tr.sc.write_json(campaign / 'build/binary.json', {'sha256': tr.sc.sha(binary), 'plan_sha256': plan['plan_sha256'],
        'local_repaired_shim': True, 'reused_from': str(repair), 'new_compile_not_performed': True})
    shutil.copy2(tr.CAMPAIGN / 'runtime.json', campaign / 'runtime.json')
    print(json.dumps({'status': 'PLANNED_NOT_RUN', 'stage': stage, 'points': len(points), 'campaign': str(campaign),
                      'complete_adc_qualified': False}))


def validate_resume(campaign, for_execution=False):
    plan = tr.sc.read_plan(campaign)
    if plan['stage'] == 'ramp' and (plan['steps_per_lsb'] != 32 or plan['required_points'] != 131073):
        raise ValueError('strict full-grid coverage was reduced')
    if plan['stage'] == 'centres' and plan['required_points'] != 4096:
        raise ValueError('4096 centres are required')
    audit = json.loads((campaign / 'frozen/bridge_fixed_evidence.json').read_text())
    if tr.sc.sha(campaign / 'build/cosim_controller.so') != audit['local_bridge_sha256']:
        raise ValueError('refusing old or unrecorded bridge binary')
    if for_execution and audit['analog_numeric_equivalence_status'] != 'FINITE_TRACE_ANALOG_EQUIVALENCE_PASS':
        raise ValueError('NUMERICAL_GATE_BLOCKED: corrected bridge has not passed the strict 0.05 LSB full-waveform gate; no sweep started')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('campaign', type=Path)
    init.add_argument('--stage', choices=('smoke', 'centres', 'ramp'), required=True)
    init.add_argument('--repair', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('campaign', type=Path)
    run.add_argument('--retry-incomplete', action='store_true')
    collect = sub.add_parser('collect')
    collect.add_argument('campaign', type=Path)
    args = parser.parse_args()
    campaign = args.campaign.resolve()
    if tr.HERE not in campaign.parents:
        raise ValueError('campaign must be inside closure_20260911; old campaigns cannot be modified')
    if args.command == 'init':
        initialize(campaign, args.stage, args.repair.resolve())
    else:
        validate_resume(campaign, for_execution=args.command == 'run')
        if args.command == 'run':
            tr.sc.run(campaign, 1, 360, args.retry_incomplete)
        else:
            # The immutable coverage artifact keeps every missing batch; the
            # terminal only needs counts, not 43,691 unexecuted batch numbers.
            with redirect_stdout(io.StringIO()):
                report = tr.sc.collect(campaign)
            print(json.dumps({key: report[key] for key in ('status', 'stage', 'required_points', 'completed_points', 'complete_adc_qualified')}, indent=2))
            return 2 if report['status'] == 'INCOMPLETE_COVERAGE' else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
