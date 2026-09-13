#!/usr/bin/env python3
"""Collect measured feasibility, bridge correction and strict failed routes."""
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

import trace_replay as tr
from bridge_fix import handshake_certificate


def profile(directory):
    summary = json.loads((directory / 'summary.json').read_text())
    log = (directory / 'native.log').read_text()
    stats = {}
    for line in log.splitlines():
        match = re.fullmatch(r'([A-Za-z ()\-]+) = ([\d.eE+\-]+)\s*', line)
        if match:
            stats[match[1]] = float(match[2])
    return {'directory': str(directory), 'summary_sha256': tr.sc.sha(directory / 'summary.json'),
            'wall_seconds': summary['wall_seconds'], 'rows': summary.get('rows'),
            'rusage': stats, 'time_step_statistics': summary.get('time_step_statistics'),
            'rusage_scope': 'ngspice rusage all inside each process, one thread; command wall includes loading/output. Not a repeated hardware benchmark.'}


def main():
    live = tr.HERE / 'results/20260911T080054695882Z_live'
    replay = tr.HERE / 'results/20260911T080430354263Z_replay'
    repairs = sorted((tr.HERE / 'results').glob('*_bridge_fixed'))
    repair = repairs[-1]
    fixed = json.loads((repair / 'bridge_certificate.json').read_text())
    provenance = json.loads((replay / 'provenance.json').read_text())
    profiles = {label: profile(directory) for label, directory in (('live_old_shim', live), ('known_trace_replay', replay), ('live_fixed_shim', repair))}
    # Conservative measured process wall per conversion, including a share of
    # load/OP/output in each conversion; do not subtract overlapping rusage times.
    seconds_per_conversion = profiles['live_fixed_shim']['wall_seconds'] / 6
    estimates = {}
    for stage, count in (('centres_4096', 4096), ('ramp_32_points_per_lsb', 131073)):
        for batch in (3, 8):
            batches = math.ceil(count / batch)
            conversions = 2 * count + batches - 1
            days = conversions * seconds_per_conversion / 86400
            estimates[f'{stage}_batch{batch}'] = {'input_points': count, 'batches': batches, 'conversions': conversions,
                'days_one_worker_one_pvt': days, 'days_ideal_three_independent_workers': days / 3,
                'scope': 'Linear extrapolation from six conversions; not a runtime guarantee; includes one warmup/input and one previous-input replay/batch.'}
    values = np.loadtxt(repair / 'waveform.dat', skiprows=1)
    times = tr.tc.crossings(values[:, 0], values[:, 1], .9) + 20e-9
    saved = tr.save_vectors((repair / 'adc.spice').read_text())
    exported_codes = [sum((int(np.interp(t, values[:, 0], values[:, saved.index(f'v(data{bit})') + 1]) >= .9) << bit)
                          for bit in range(12)) for t in times]
    oldvalues = np.loadtxt(live / 'waveform.dat', skiprows=1)
    grid = np.arange(62001) * 1e-9
    lower31 = {name: float(np.max(np.abs(np.interp(grid, values[:, 0], values[:, saved.index(f'v({name})') + 1])
                                       - np.interp(grid, oldvalues[:, 0], oldvalues[:, saved.index(f'v({name})') + 1]))))
               for name in tr.OUTPUTS[2:]}
    test = subprocess.run([sys.executable, '-m', 'unittest', '-v', 'test_closure'], cwd=tr.HERE, capture_output=True, text=True, timeout=60)
    report = {
        'scope': 'Three bounded deterministic TT/1.8 V/27 C real-circuit runs, three inputs/six conversions; NOT all-code, noise, PVT or physical signoff.',
        'complete_adc_qualified': False, 'full_code_problem_resolved': False,
        'profiles': profiles,
        'old_bridge_status_regression': handshake_certificate(live),
        'fixed_bridge_certificate': fixed,
        'fixed_exported_raw_codes': exported_codes,
        'fixed_lower31_common_1ns_grid_max_delta_v': lower31,
        'known_replay_total_retained_pwl_points': sum(row['kept_points'] for row in provenance['compressed_driver_errors'].values()),
        'known_replay_predictive_capability_tested': False,
        'known_replay_certificate': json.loads(sorted(replay.glob('certificate_*.json'))[-1].read_text()),
        'estimated_remaining_runtime': estimates,
        'software_tests': {'returncode': test.returncode, 'stdout': test.stdout, 'stderr': test.stderr,
                           'scope': 'Software/saved-waveform regression; not additional circuit coverage.'},
        'source_sha256': {p.name: tr.sc.sha(p) for p in tr.HERE.glob('*.py')},
        'installed_shim_sha256': tr.sc.sha(Path('/foss/tools/ngspice/share/ngspice/scripts/src/verilator_shim.cpp')),
    }
    path = tr.HERE / 'results/feasibility_and_bridge_report.json'
    if path.exists():
        raise ValueError('immutable report exists')
    tr.sc.write_json(path, report)
    print(json.dumps({'report': str(path), 'tests_returncode': test.returncode, 'fixed_exported_raw_codes': exported_codes,
                      'fixed_status': fixed['handshake']['status'], 'numerical_gate': fixed['analog_comparison']['status'],
                      'estimates': estimates}, indent=2))


if __name__ == '__main__':
    main()
