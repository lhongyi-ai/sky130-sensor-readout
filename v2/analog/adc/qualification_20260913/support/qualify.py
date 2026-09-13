#!/usr/bin/env python3
"""Immutable, bounded live-RTL ADC experiments. No full-ADC signoff claim."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
ADC = HERE.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ADC / 'verification_20260910'))
import static_campaign as sc
sys.path.insert(0, str(ADC / 'closure_20260911'))
import trace_replay as tr

REPAIR = ADC / 'closure_20260911/results/20260911T081221912898Z_bridge_fixed'
SOURCE = ADC / 'verification_20260910/campaigns/continuous_three_point'
INPUTS = [-.399, .399, -.25 * sc.LSB, .25 * sc.LSB] + [
    -.4 + (code + .5) * sc.LSB for code in (100, 3995, 1601, 3000, 1907, 2203, 2557, 3311)]
PROFILES = {'baseline': dict(maxstep_ns=2, reltol='1e-5', abstol='1e-13', vntol='1e-8'),
            'strict': dict(maxstep_ns=1, reltol='1e-6', abstol='1e-14', vntol='1e-9')}

def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def initialize():
    out = HERE / 'snapshot'
    if out.exists():
        return verify()
    original = sc.read_plan(SOURCE)
    repair = json.loads((REPAIR / 'bridge_certificate.json').read_text())
    assert repair['handshake']['status'] == 'BOUNDED_STATUS_PORTS_PASS'
    assert repair['comparator']['matched_decisions'] == 72
    old_summary = json.loads((REPAIR / 'summary.json').read_text())
    assert sc.sha(REPAIR / 'summary.json') == repair['summary_sha256']
    for name, expected in old_summary['source_and_output_sha256'].items():
        assert sc.sha(REPAIR / name) == expected, name
    out.mkdir()
    shutil.copytree(SOURCE / 'frozen', out / 'frozen')
    shutil.copy2(REPAIR / 'build/cosim_controller_fixed.so', out / 'cosim_controller_fixed.so')
    shutil.copy2(REPAIR / 'adc.spice', out / 'reference.spice')
    shutil.copy2(REPAIR / '.spiceinit', out / '.spiceinit')
    shutil.copy2(SOURCE / 'runtime.json', out / 'runtime.json')
    shutil.copy2(ADC.parents[1] / 'config/spec.json', out / 'spec.json')
    metadata = {'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_campaign_plan_sha256': original['plan_sha256'],
        'repair_certificate_sha256': sc.sha(REPAIR / 'bridge_certificate.json'),
        'runner_sha256': sc.sha(__file__), 'source_paths': {'campaign': str(SOURCE), 'repair': str(REPAIR)},
        'input_v': INPUTS, 'profiles': PROFILES,
        'conditions': {'corner': 'tt', 'vdd_v': 1.8, 'temperature_c': 27,
            'source_ohm_per_leg': 350, 'reference_ohm': 1, 'reference_cap_nf': 10,
            'clock_hz': 1600000, 'sample_rate_hz': 100000, 'edge_ns': 1,
            'reset_once': True, 'warmups_discarded': 0, 'duration_us': 122},
        'scope': '12 consecutive real-comparator conversions, unchanged SAR RTL, local corrected 33-bit shim; schematic only',
        'files': {str(p.relative_to(out)): sc.sha(p) for p in sorted(out.rglob('*')) if p.is_file()},
        'complete_adc_qualified': False}
    write(out / 'manifest.json', metadata)
    return metadata

def verify():
    out = HERE / 'snapshot'
    manifest = json.loads((out / 'manifest.json').read_text())
    if manifest['runner_sha256'] != sc.sha(__file__):
        raise ValueError('runner changed after source freeze')
    for name, expected in manifest['files'].items():
        if sc.sha(out / name) != expected:
            raise ValueError('snapshot changed: ' + name)
    return manifest

def deck_for(profile):
    manifest = verify()
    out = HERE / 'snapshot'
    deck = (out / 'reference.spice').read_text()
    deck = deck.replace(str(SOURCE / 'frozen'), str(out / 'frozen'))
    deck = deck.replace(str(REPAIR / 'build/cosim_controller_fixed.so'), str(out / 'cosim_controller_fixed.so'))
    seq = [{'input_v': v} for v in manifest['input_v']]
    deck = re.sub(r'^VIP sp 0 .*$', 'VIP sp 0 ' + sc.pwl_input(seq, .9, 1), deck, flags=re.M)
    deck = re.sub(r'^VIN sn 0 .*$', 'VIN sn 0 ' + sc.pwl_input(seq, .9, -1), deck, flags=re.M)
    numeric = manifest['profiles'][profile]
    deck = re.sub(r'^\.options .*$', '.options sparse method=gear ' + ' '.join(
        f'{key}={numeric[key]}' for key in ('reltol', 'abstol', 'vntol')), deck, flags=re.M)
    deck = deck.replace('tran 2n 62u 0 2n', f"tran 2n 122u 0 {numeric['maxstep_ns']}n")
    if 'd_cosim simulation=' not in deck or 'XADC inp inn decision decision_b' not in deck:
        raise ValueError('live feedback circuit missing')
    if str(REPAIR) in deck or str(SOURCE) in deck:
        raise ValueError('unfrozen deck dependency')
    return deck

def analyse(directory, rc):
    manifest = verify()
    result = {'status': 'INCOMPLETE', 'returncode': rc, 'complete_adc_qualified': False}
    waveform = directory / 'waveform.dat'
    if rc != 0 or not waveform.exists():
        result['reason'] = 'incomplete process or waveform; partial logged words do not count'
        return result
    values = np.loadtxt(waveform, skiprows=1)
    names = tr.save_vectors((directory / 'adc.spice').read_text())
    if values.ndim != 2 or values.shape[1] != len(names) + 1 or not np.isfinite(values).all():
        return dict(result, reason='malformed waveform')
    t = values[:, 0]
    if t[-1] < 122e-6 - 1e-12 or np.any(np.diff(t) <= 0):
        return dict(result, reason='incomplete time domain')
    def vector(name):
        return values[:, names.index('v(' + name + ')') + 1]
    def at(name, when):
        return np.interp(when, t, vector(name))
    n = len(manifest['input_v'])
    valid = tr.tc.crossings(t, vector('valid'), .9)
    evaluate = tr.tc.crossings(t, vector('evaluate'), .18)
    log = (directory / 'simulation.log').read_text()
    words = [int(x) for x in re.findall(r'COSIM_RESULT time_ns=[\d.]+ code=(\d+) gain_code=0', log)]
    if len(valid) != n or len(evaluate) != 12*n or len(words) != n:
        return dict(result, reason='conversion / evaluation / log count mismatch', valid_count=len(valid),
                    evaluation_count=len(evaluate), log_codes=words)
    desired_valid = (11.0035 + np.arange(n)*10)*1e-6
    desired_eval = np.asarray([3.8156 + f*10 + b*.625 for f in range(n) for b in range(12)])*1e-6
    decisions, frames, checks = [], [], []
    for f, end in enumerate(valid):
        volts = [at(f'data{i}', end + 10e-9) for i in range(11, -1, -1)]
        bus_valid = all(v <= .18 or v >= 1.62 for v in volts)
        bus = sum(int(v > .9) << (11-i) for i, v in enumerate(volts))
        actual = []
        for bit in range(11, -1, -1):
            centre = end - bit*625e-9
            lo, hi = centre-10e-9, centre+10e-9
            times = np.r_[lo, t[(t >= lo) & (t <= hi)], hi]
            q, qb = at('decision', times), at('decision_b', times)
            observed = 1 if q.min() >= 1.44 and qb.max() <= .36 else 0 if q.max() <= .36 and qb.min() >= 1.44 else None
            actual.append(observed)
            decisions.append({'frame': f, 'bit': bit, 'q_min_v': float(q.min()), 'q_max_v': float(q.max()),
                'qb_min_v': float(qb.min()), 'qb_max_v': float(qb.max()), 'observed': observed,
                'logged_bit': (words[f] >> bit)&1, 'accepted': observed == ((words[f] >> bit)&1),
                'window_s': [float(lo), float(hi)]})
        decision_word = sum(value << (11-i) for i, value in enumerate(actual)) if None not in actual else None
        frames.append({'frame': f, 'input_v': manifest['input_v'][f], 'valid_time_s': float(end),
            'bus_code': bus, 'log_code': words[f], 'comparator_word': decision_word,
            'bus_valid': bus_valid, 'passed': bus_valid and bus == words[f] == decision_word,
            'ideal_code_diagnostic_only': int(np.clip(np.floor((manifest['input_v'][f]+.4)/sc.LSB), 0, 4095))})
    phases = [(.2e-6, 0, 'reset'), (.8e-6, 1, 'idle')]
    for frame in range(n):
        phases.extend(( (2e-6+frame*10e-6, 0, 'acquiring'), (8e-6+frame*10e-6, 0, 'deciding'),
            (10.6e-6+frame*10e-6, 1, 'last_decision'), (11.2e-6+frame*10e-6, 0, 'next_acquisition')))
    for when, ready, phase in phases:
        r,b = float(at('ready', when)),float(at('busy', when))
        checks.append({'time_s': when, 'phase': phase, 'ready_v': r, 'busy_v': b,
            'passed': bool((r >= 1.44 and b <= .36) if ready else (r <= .36 and b >= 1.44))})
    passed = {'all_frames_bus_log_comparator_agree': all(f['passed'] for f in frames),
        'all_144_decisions_valid': all(d['accepted'] for d in decisions),
        'all_status_checks_pass': all(c['passed'] for c in checks),
        'valid_times_within_1ns': bool(np.max(np.abs(valid-desired_valid)) <= 1e-9),
        'eval_times_within_1ns': bool(np.max(np.abs(evaluate-desired_eval)) <= 1e-9)}
    return dict(result, status='CONTINUOUS_12_FRAME_FUNCTIONAL_PASS' if all(passed.values()) else 'CONTINUOUS_FUNCTIONAL_FAIL',
        checks=passed, frames=frames, comparator_decisions=decisions, handshake=checks,
        rows=len(values), stop_us=float(t[-1]*1e6), accepted_decisions=sum(d['accepted'] for d in decisions),
        valid_times_s=valid.tolist(), evaluate_times_s=evaluate.tolist(),
        interval_max_deviation_ns=float(np.max(np.abs(np.diff(valid)-10e-6))*1e9))

def run(profile, timeout):
    initialize()
    lock = HERE / 'worker.lock'
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    os.close(fd)
    try:
        if sc.runtime_identity() != json.loads((HERE / 'snapshot/runtime.json').read_text()):
            raise ValueError('PDK or runtime mismatch')
        directory = HERE / 'results' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '_' + profile)
        directory.mkdir(parents=True)
        (directory / 'adc.spice').write_text(deck_for(profile))
        shutil.copy2(HERE / 'snapshot/.spiceinit', directory / '.spiceinit')
        write(directory / 'summary.json', {'status': 'RUNNING', 'profile': profile, 'complete_adc_qualified': False})
        start = time.monotonic()
        try:
            proc = subprocess.run(['ngspice', '-b', '-o', 'native.log', 'adc.spice'], cwd=directory,
                env=dict(os.environ, SPICE_USERINIT_DIR=str(directory)), capture_output=True, text=True, timeout=timeout)
            rc, log = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired as exc:
            rc = None
            log = 'TIMEOUT\n' + (exc.stdout or b'').decode(errors='replace') + (exc.stderr or b'').decode(errors='replace')
        elapsed = time.monotonic() - start
        if (directory / 'native.log').exists():
            log += (directory / 'native.log').read_text(errors='replace')
        (directory / 'simulation.log').write_text(log)
        result = analyse(directory, rc)
        result.update(profile=profile, numeric=PROFILES[profile], wall_seconds=elapsed,
            timeout_seconds=timeout, snapshot_manifest_sha256=sc.sha(HERE / 'snapshot/manifest.json'),
            live_rtl_inside_analog_run=True, noise_enabled=False, schematic_only=True,
            artifact_sha256={p.name: sc.sha(p) for p in directory.iterdir() if p.is_file() and p.name != 'summary.json'})
        write(directory / 'summary.json', result)
        print(json.dumps({k: result[k] for k in ('status', 'profile', 'wall_seconds', 'returncode')}, indent=2), flush=True)
        print(str(directory), flush=True)
        return 0 if result['status'] == 'CONTINUOUS_12_FRAME_FUNCTIONAL_PASS' else 2
    finally:
        lock.unlink()

def compare(a, b):
    verify()
    summaries = [json.loads((p/'summary.json').read_text()) for p in (a,b)]
    for directory, summary in zip((a,b), summaries):
        for name, expected in summary['artifact_sha256'].items():
            if sc.sha(directory/name) != expected: raise ValueError('result changed: '+name)
    if any(s['status'] != 'CONTINUOUS_12_FRAME_FUNCTIONAL_PASS' for s in summaries):
        return {'status': 'NUMERICAL_PAIR_INCOMPLETE', 'complete_adc_qualified': False}
    va,vb = (np.loadtxt(p/'waveform.dat', skiprows=1) for p in (a,b))
    names = tr.save_vectors((a/'adc.spice').read_text())
    if names != tr.save_vectors((b/'adc.spice').read_text()): raise ValueError('vector mismatch')
    grid = np.union1d(va[:,0], vb[:,0])
    common = np.arange(122001)*1e-9
    pre = np.asarray(summaries[0]['evaluate_times_s'])-1e-9
    rows = {}
    for name, signals in {'cdac_differential': ['xadc.tp','xadc.tn'], 'rp':['rp'], 'rn':['rn'], 'vcm':['vcm']}.items():
        def signal(v, sample):
            def item(n): return np.interp(sample, v[:,0], v[:,names.index('v('+n+')')+1])
            return item(signals[0])-(item(signals[1]) if len(signals)>1 else 0)
        err = signal(vb,grid)-signal(va,grid)
        rows[name] = {'union_grid_max_error_v':float(np.max(np.abs(err))),
            'union_grid_max_error_lsb':float(np.max(np.abs(err))/sc.LSB),
            'worst_time_s':float(grid[np.argmax(np.abs(err))]),
            'common_1ns_max_error_v':float(np.max(np.abs(signal(vb,common)-signal(va,common)))),
            'predecision_max_error_v':float(np.max(np.abs(signal(vb,pre)-signal(va,pre))))}
    checks = {'all_waveforms_le_0_05lsb':all(r['union_grid_max_error_v']<=.05*sc.LSB for r in rows.values()),
        'all_predecision_le_0_05lsb':all(r['predecision_max_error_v']<=.05*sc.LSB for r in rows.values()),
        'same_codes': [r['log_code'] for r in summaries[0]['frames']]==[r['log_code'] for r in summaries[1]['frames']]}
    result = {'status': 'BOUNDED_NUMERICAL_CONVERGENCE_PASS' if all(checks.values()) else 'NUMERICAL_CONVERGENCE_FAIL',
        'checks':checks, 'threshold_lsb':.05, 'threshold_v':.05*sc.LSB, 'channels':rows,
        'reference':str(a), 'candidate':str(b), 'summary_sha256':[sc.sha(p/'summary.json') for p in (a,b)],
        'scope':'12 frames at TT only; union accepted-point linear interpolation, not continuous-time proof',
        'complete_adc_qualified':False, 'long_campaign_allowed':False}
    write(HERE/'numerical_comparison.json', result)
    print(json.dumps(result, indent=2))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    p=sub.add_parser('run'); p.add_argument('profile',choices=PROFILES); p.add_argument('--timeout',type=float,default=660)
    p=sub.add_parser('compare'); p.add_argument('reference',type=Path); p.add_argument('candidate',type=Path)
    args=parser.parse_args()
    if args.command=='init': initialize(); return 0
    if args.command=='run':
        if not 0<args.timeout<=900: raise ValueError('bounded run requires timeout <=900 s')
        return run(args.profile,args.timeout)
    result=compare(args.reference.resolve(),args.candidate.resolve())
    return 0 if result['status']=='BOUNDED_NUMERICAL_CONVERGENCE_PASS' else 2

if __name__=='__main__':
    raise SystemExit(main())
