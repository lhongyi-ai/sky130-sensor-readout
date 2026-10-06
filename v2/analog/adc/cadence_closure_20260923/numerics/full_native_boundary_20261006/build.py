#!/usr/bin/env python3
"""Prepare a full-device first-edge control, without changing the native design."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from psf_stream import Trace

STOP = 4.1e-6
PORTS = 'INP INN Q QB SAMPLE SAMPLEB ACQ CONV EVAL B11 B10 B9 B8 B7 B6 B5 B4 B3 B2 B1 B0 RP RN VCM VDD VSS RST_N'.split()
PHASE_PORTS = 'SAMPLE_CMD TOP TOPB ACQ CONV VDD VSS'.split()
PREFIX = 'p2_ams_reset1.'
CONSTANTS = {'vdd': 1.8, 'vss': 0., 'vcm': .9, 'rp_source': 1.1,
             'rn_source': .7, 'ip_source': .7005, 'in_source': 1.0995,
             'eval_e': 0., **{'trial_e[%d]' % i: 0. for i in range(12)}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ramp(t, start):
    return 1.8 * min(1., max(0., (t - start) / 1e-9))


def verify_boundary(rows):
    if not rows or rows[0]['time'] != 0 or abs(rows[-1]['time'] - STOP) > 1e-17:
        raise ValueError('Reference must cover the complete 0–4.1 us interval')
    errors = {}
    for name, value in CONSTANTS.items():
        errors[name] = max(abs(r[PREFIX + name] - value) for r in rows)
    for name, start in [('rst_n_e', 1.885e-6), ('sample_cmd_e', 4.0625e-6)]:
        errors[name] = max(abs(r[PREFIX + name] - ramp(r['time'], start)) for r in rows)
    if max(errors.values()) > 5e-12:
        raise ValueError('Frozen boundary is not equivalent at every saved point: ' + str(errors))
    return {'reference_rows': len(rows), 'max_errors_V': errors,
            'method': 'Analytic sources checked at every original accepted point; no waveform replay or comparator decisions.'}


def audit_native(text):
    flat = text.replace('\\\n', ' ')
    result = {}
    for name, ports, count in [('sensor_adc_reset1', PORTS, 693),
                               ('sensor_phases', PHASE_PORTS, 48)]:
        match = re.search(r'(?m)^subckt ' + name + r' \(([^\n]+)\)\n(.*?)^ends ' + name + r'\s*$', flat, re.S | re.M)
        if not match or match[1].split() != ports:
            raise ValueError('Native port contract changed: ' + name)
        records = [l.strip() for l in match[2].splitlines() if l.strip() and not l.lstrip().startswith('//')]
        names = [l.split()[0] for l in records]
        if len(records) != count or len(set(names)) != count:
            raise ValueError('Native instance count/uniqueness changed: ' + name)
        if any(not re.fullmatch(r'\S+\s+\([^)]+\)\s+\S+\s+.+', l) for l in records):
            raise ValueError('Unexpected native statement')
        result[name] = count
    if sum(l.lstrip().startswith(('XADC_XPRE_', 'XADC_XCMP_')) for l in flat.splitlines()) != 87:
        raise ValueError('All 87 preamp/comparator records must remain')
    return result


def prepare(native, reference, output, model, expected_native_sha):
    if output.exists():
        raise ValueError('Output exists; retained attempts must not be overwritten')
    if sha(native) != expected_native_sha:
        raise ValueError('Frozen native SHA-256 mismatch')
    if not model.startswith('/') or any(c in model for c in ['"', '\n', '\r']):
        raise ValueError('Model entry must be an explicit safe absolute path')
    body = native.read_text()
    counts = audit_native(body)
    wanted = {PREFIX + n for n in [*CONSTANTS, 'rst_n_e', 'sample_cmd_e']}
    trace = Trace(reference, wanted=wanted)
    verification = verify_boundary(list(trace.rows()))
    top = '''// Complete native devices; first-edge diagnosis only, no RTL conversion.
simulator lang=spectre
global 0
include "MODEL" section=tt
include "native_full.scs"
VVDD (VDD 0) vsource dc=1.8
VVCM (VCM 0) vsource dc=0.9
VRP (RPSRC 0) vsource dc=1.1
VRN (RNSRC 0) vsource dc=0.7
RRP (RPSRC RP) resistor r=1
RRN (RNSRC RN) resistor r=1
CRP (RP 0) capacitor c=10n
CRN (RN 0) capacitor c=10n
VIP (IPSRC 0) vsource dc=0.7005
VIN (INSRC 0) vsource dc=1.0995
RIP (IPSRC INP) resistor r=350
RIN (INSRC INN) resistor r=350
VRST (RST_N 0) vsource type=pwl dc=0 wave=[0 0 1.885u 0 1.886u 1.8 4.1u 1.8]
VCMD (SAMPLE_CMD 0) vsource type=pwl dc=0 wave=[0 0 4.0625u 0 4.0635u 1.8 4.1u 1.8]
VEVAL (EVAL 0) vsource dc=0
'''.replace('MODEL', model)
    top += ''.join('VB%d (B%d 0) vsource dc=0\n' % (i, i) for i in range(12))
    top += 'XADC (' + ' '.join('0' if p == 'VSS' else 'TOP' if p == 'SAMPLE' else 'TOPB' if p == 'SAMPLEB' else p for p in PORTS) + ') sensor_adc_reset1\n'
    top += 'XPHASE (SAMPLE_CMD TOP TOPB ACQ CONV VDD 0) sensor_phases\n'
    top += 'saveOptions options save=selected\nsave VDD VCM RPSRC RNSRC RP RN IPSRC INSRC INP INN SAMPLE_CMD RST_N EVAL TOP TOPB ACQ CONV Q QB\n'
    top += 'save XADC.XADC_TP XADC.XADC_TN XADC.XADC_PREP XADC.XADC_PREN\n'
    primitive = 'XPHASE.XPHASE_XBCONV_XI2_XP.msky130_fd_pr__pfet_01v8'
    top += 'save ' + primitive + ':int_b ' + primitive + ':dbnode ' + primitive + ':sbnode sigtype=node\n'
    top += 'save ' + primitive + ':vds ' + primitive + ':reversed ' + primitive + ':currents sigtype=dev\n'
    output.mkdir(parents=True)
    (output / 'native_full.scs').write_text(body)
    profiles = {}
    for name, r, v, i, step in [('baseline', '1e-5', '1e-8', '1e-13', '2n'), ('strict', '1e-6', '1e-9', '1e-14', '1n')]:
        text = top + 'simulatorOptions options temp=27 reltol=%s vabstol=%s iabstol=%s maxwarns=1000 maxwarnstologfile=1000 maxnotes=1000 maxnotestologfile=1000\n' % (r, v, i)
        text += 'full_boundary tran stop=4.1u maxstep=%s errpreset=conservative relref=sigglobal method=gear2only lteratio=10\n' % step
        f = output / ('input_' + name + '.scs')
        f.write_text(text)
        profiles[name] = {'file': f.name, 'sha256': sha(f)}
    manifest = {'status': 'PREPARED_NOT_SIMULATED', 'scope': 'FULL_NATIVE_FIRST_EDGE_BOUNDARY_DIAGNOSIS',
                'native_sha256': sha(native), 'reference_sha256': sha(reference),
                'native_counts': counts, 'retained_preamp_comparator_instances': 87,
                'boundary_verification': verification, 'profiles': profiles,
                'stop_s': STOP, 'numeric_limit_V': 9.765625e-6,
                'original_RTL_simulated': False, 'completed_frames': 0,
                'full_ADC_numeric_qualified': False, 'formal_ADC_PEX_allowed': False,
                'limitations': ['Native boundary R/C adds thermal noise unlike the original deterministic VAMS equations; no noise equivalence claimed.',
                                'Finite native PWL source handling differs from AMS; output equivalence must be measured.',
                                'This short-domain control cannot qualify two frames, reset-abort, 12 frames or PEX.']}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ['native', 'reference', 'output']:
        p.add_argument('--' + flag, required=True, type=Path)
    p.add_argument('--model', required=True)
    p.add_argument('--native-sha256', required=True)
    a = p.parse_args()
    m = prepare(a.native, a.reference, a.output, a.model, a.native_sha256)
    print(json.dumps({'status': m['status'], 'native_counts': m['native_counts']}))
