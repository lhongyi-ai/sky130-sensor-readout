#!/usr/bin/env python3
"""Compare the two retained actual r4 noise runs; no simulations are performed."""
from pathlib import Path
import hashlib
import json
import re
from parse_noise_psf import parse_noise, integrate_psd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROOT = REPO/'v2/cadence/linuxlab_20260923/runs'
OLD = ROOT/'spectre_noise_screen_20260923T110907590483Z'
NEW = ROOT/'spectre_noise_screen_20260923T112542186497Z'
OUTPUT = HERE/'r4_dc_pivot_control_independent_review.json'
HASHES = {}


def read(p):
    HASHES[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p.read_text()


def body(s):
    # Remove only timestamp-bearing HEADER. Retain TYPE, SWEEP, TRACE, VALUE.
    return s.split('\nTYPE\n', 1)[1]


def main():
    if OUTPUT.exists():
        raise SystemExit('Output exists; preserve earlier evidence.')
    read(Path(__file__).resolve())
    read(HERE/'parse_noise_psf.py')
    a = read(OLD/'input.scs'); b = read(NEW/'input.scs')
    assert a.count('simOptions options ') == 1
    assert b == a.replace('simOptions options ', 'simOptions options dc_pivot_check=yes ', 1)
    assert read(OLD/'native_netlist') == read(NEW/'native_netlist')
    equal = {}
    for name in ['dcOp.dc', 'dcOpInfo.info', 'ac.ac']:
        old = read(OLD/'input.raw'/name); new = read(NEW/'input.raw'/name)
        equal[name] = body(old) == body(new)
        assert equal[name]
    noise = {}
    for g in [1, 4, 16]:
        for stage in ['front', 'track']:
            name = 'g{}_{}.noise'.format(g, stage)
            old = read(OLD/'input.raw'/name); new = read(NEW/'input.raw'/name)
            equal[name] = body(old) == body(new)
            assert equal[name]
            d = parse_noise(new)
            noise[name] = {
                'saved_frequency_count': len(d['frequency']),
                'all_ASD_and_every_device_PSD_values_exactly_equal': True,
                'rms_v_both_runs': {
                    label: integrate_psd(d['frequency'], d['out_asd']**2, lo, hi)**0.5
                    for label, lo, hi in [('1Hz_50kHz', 1., 5e4),
                                          ('one_fft_bin_50kHz', 1e5/16384, 5e4),
                                          ('1Hz_100MHz', 1., 1e8)]}}
    logs = {}
    for p in [OLD, NEW]:
        s = read(p/'spectre.out')
        read(p/'provenance.json'); read(p/'completion.json')
        counts = re.search(r'spectre completes with (\d+) errors?, (\d+) warnings?, and (\d+) notices?\.', s)
        logs[p.name] = {
            'errors_warnings_notices': [int(x) for x in counts.groups()],
            'bad_pivoting_notice': 'Bad pivoting' in s,
            'gmin_dc_notice_count': s.count('GminDC ='),
            'warning_codes': re.findall(r'WARNING \(([^)]+)\)', s)}
    assert logs[OLD.name]['errors_warnings_notices'] == [0, 2, 11]
    assert logs[NEW.name]['errors_warnings_notices'] == [0, 2, 10]
    assert logs[OLD.name]['bad_pivoting_notice'] and not logs[NEW.name]['bad_pivoting_notice']
    result = {
        'status': 'MATCHED_NUMERICAL_CONTROL_NO_SAVED_RESULT_CHANGE',
        'old_run': str(OLD.relative_to(REPO)), 'new_run': str(NEW.relative_to(REPO)),
        'input_change': 'Exactly one setting added: dc_pivot_check=yes. All other deck bytes identical.',
        'native_netlist_identical': True,
        'raw_body_exact_equal': equal,
        'op_scope': 'Initial dcOp/DC device information only. The initial deck gain is 4. Noise-internal DC solutions at each other gain are not separately exported; do not claim their independent OP equality.',
        'noise': noise, 'logs': logs,
        'interpretation': [
            'Bad-pivot notice is removed by the recommended option without any change in saved OP, AC, noise ASD or device PSD values at written precision.',
            'This control supports robustness to this one solver option only. Gmin dependence and model/noise control qualification remain separate.',
            'Two unchanged warnings are SPECTRE-16939 no-op alter statements. Four GminDC notices remain.',
            'No new circuit pass: r4 range and temperature failures remain; these are fixed-state proxy CT noise data, not dynamic SNDR.'],
        'hashes': HASHES}
    OUTPUT.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'all_9_raw_bodies_equal': all(equal.values()), 'logs': logs}, indent=2))


if __name__ == '__main__':
    main()
