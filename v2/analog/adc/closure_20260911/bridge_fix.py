#!/usr/bin/env python3
"""Rebuild only a local 33-bit bridge shim; frozen RTL / ADC are unchanged.

Generated Verilator objects and headers are reused read-only and hash-recorded.
The ngspice installation is never written. This fixes output masks only, not
generic wide input/inout support or any unrelated installed shim issue.
"""
import json
from pathlib import Path
import re
import subprocess
import time

import numpy as np

import trace_replay as tr
from certify_trace import analog_comparison, comparator_certificate

SOURCE = Path('/foss/tools/ngspice/share/ngspice/scripts/src/verilator_shim.cpp')
SOURCE_SHA = 'ddf28192068013b402f1481be2530407036c62a6ac0bf9093fce59f90174c77e'
LIVE = tr.HERE / 'results/20260911T080054695882Z_live'


def correct_output_masks(source):
    old = '(topp->name & (1 << i))'
    if source.count(old) != 2:
        raise ValueError('expected exactly timing and non-timing output masks')
    return source.replace(old, '(topp->name & (uint64_t(1) << i))')


def handshake_certificate(directory):
    values = np.loadtxt(directory / 'waveform.dat', skiprows=1)
    saved = tr.save_vectors((directory / 'adc.spice').read_text())
    def at(name, t):
        return np.interp(t, values[:, 0], values[:, saved.index(f'v({name})') + 1])
    # At least 20 ns clear of every status edge; the last decision interval
    # intentionally deasserts busy to accept the next start on completion.
    samples = [(0.2e-6, 0, 'reset'), (.8e-6, 1, 'idle')]
    for frame in range(6):
        samples.extend(((2e-6 + frame * 10e-6, 0, 'acquiring'),
                        (8e-6 + frame * 10e-6, 0, 'deciding'),
                        (10.6e-6 + frame * 10e-6, 1, 'last_decision'),
                        (11.2e-6 + frame * 10e-6, 0, 'next_acquisition')))
    checks = []
    for t, ready, phase in samples:
        r, b = float(at('ready', t)), float(at('busy', t))
        ok = (r >= 1.44 if ready else r <= .36) and (b <= .36 if ready else b >= 1.44)
        checks.append(dict(time_s=t, phase=phase, expected_ready=ready, ready_v=r, busy_v=b, passed=bool(ok)))
    r = values[:, saved.index('v(ready)') + 1]
    b = values[:, saved.index('v(busy)') + 1]
    grid = np.arange(1001, 62001) * 1e-9
    complement = float(np.max(np.abs(at('ready', grid) + at('busy', grid) - 1.8)))
    return {'status': 'BOUNDED_STATUS_PORTS_PASS' if all(c['passed'] for c in checks) and complement < 1e-6 else 'STATUS_PORTS_FAIL',
            'samples': checks, 'post_1us_complement_error_v': complement,
            'ready_rise_times_s': tr.tc.crossings(values[:, 0], r, .9).tolist(),
            'busy_fall_times_s': tr.tc.crossings(values[:, 0], 1.8 - b, .9).tolist(),
            'scope': 'Reset, idle, acquiring, deciding and final-bit backpressure in six continuous conversions; not exhaustive interface testing.'}


def main():
    source, plan, record = tr.read_original()
    if tr.sc.sha(SOURCE) != SOURCE_SHA:
        raise ValueError('installed shim changed; do not patch an unknown version')
    directory = tr.start_directory('bridge_fixed')
    build = directory / 'build'
    build.mkdir()
    original = SOURCE.read_text()
    (build / 'installed_shim_affected_fragment.txt').write_text(''.join(
        f'{i}: {line}\n' for i, line in enumerate(original.splitlines(), 1) if 95 <= i <= 146))
    fixed = build / 'verilator_shim_fixed.cpp'
    fixed.write_text(correct_output_masks(original))
    objects = tr.CAMPAIGN / 'build/cosim_controller_obj_dir'
    if (objects / 'outputs.h').read_text().strip().splitlines()[-1] != 'VL_DATA(64,digital_outputs,32,0)':
        raise ValueError('expected the frozen exactly 33-bit packed output interface')
    commands = [
        ['g++', '-Os', '-fPIC', '-I' + str(objects), '-I/foss/tools/verilator/share/verilator/include',
         '-I/foss/tools/verilator/share/verilator/include/vltstd', '-I' + str(SOURCE.parent),
         '-DVERILATOR=1', '-DVM_COVERAGE=0', '-DVM_SC=0', '-DVM_TIMING=0', '-DVM_TRACE=0',
         '-c', str(fixed), '-o', str(build / 'verilator_shim.o')],
        ['g++', '--shared', str(build / 'verilator_shim.o'), str(objects / 'verilated.o'),
         str(objects / 'verilated_threads.o'), str(objects / 'Vlng__ALL.a'), '-pthread', '-lpthread',
         '-o', str(build / 'cosim_controller_fixed.so')],
        ['g++', '-Os', '-std=c++17', str(tr.HERE / 'mask_reproducer.cpp'), '-o', str(build / 'mask_reproducer')],
        [str(build / 'mask_reproducer')],
        ['g++', '--version'],
    ]
    started = time.monotonic()
    records = []
    for command in commands:
        process = subprocess.run(command, capture_output=True, text=True, timeout=60)
        records.append({'command': command, 'returncode': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr})
        if process.returncode:
            tr.sc.write_json(build / 'build_records.json', records)
            raise RuntimeError('local bridge build failed; evidence kept')
    tr.sc.write_json(build / 'build_records.json', records)
    binary = build / 'cosim_controller_fixed.so'
    frozen_binary = tr.CAMPAIGN / 'build/cosim_controller.so'
    deck = tr.instrument(source)
    if deck.count(str(frozen_binary)) != 1:
        raise ValueError('unexpected frozen binary references')
    deck = deck.replace(str(frozen_binary), str(binary))
    tr.sc.write_json(directory / 'provenance.json', {
        'installed_shim_path': str(SOURCE), 'installed_shim_sha256': SOURCE_SHA,
        'correction': 'Exactly two output-mask expressions: 1 << i becomes uint64_t(1) << i. Inputs and RTL unchanged.',
        'packed_output_width': 33, 'scope': 'Local testbench software bridge correction, not an ADC architecture change.',
        'original_deck_sha256': tr.sc.sha(tr.BASELINE / 'adc.spice'), 'plan_sha256': plan['plan_sha256'],
        'runtime_sha256': tr.sc.sha(tr.CAMPAIGN / 'runtime.json'),
        'reused_object_sha256': {p.name: tr.sc.sha(p) for p in objects.iterdir() if p.is_file()},
        'build_artifact_sha256': {p.name: tr.sc.sha(p) for p in build.iterdir() if p.is_file()},
        'build_wall_seconds': time.monotonic() - started,
        'installed_source_unchanged_after_build': tr.sc.sha(SOURCE) == SOURCE_SHA,
        'runner_sha256': tr.sc.sha(Path(__file__)),
    })
    (directory / 'bridge_fix.py').write_bytes(Path(__file__).read_bytes())
    # live_record is exact: actual comparator decisions still reach the unchanged
    # real RTL at run time. No speculative PWL source is present in this run.
    result = tr.execute(directory, deck, 'live_record', record['raw_codes'])
    if result['status'] == 'TRANSISTOR_WAVEFORM_COMPLETE_NOT_CERTIFIED':
        values = np.loadtxt(directory / 'waveform.dat', skiprows=1)
        reference = np.loadtxt(LIVE / 'waveform.dat', skiprows=1)
        tr.sc.write_json(directory / 'bridge_certificate.json', {
            'handshake': handshake_certificate(directory),
            'comparator': comparator_certificate(values, record['raw_codes']),
            'analog_comparison': analog_comparison(reference, values),
            'summary_sha256': tr.sc.sha(directory / 'summary.json'),
            'reference_summary_sha256': tr.sc.sha(LIVE / 'summary.json'),
            'complete_adc_qualified': False,
            'full_interface_qualified': False,
            'installed_shim_unchanged': tr.sc.sha(SOURCE) == SOURCE_SHA,
        })


if __name__ == '__main__':
    main()
