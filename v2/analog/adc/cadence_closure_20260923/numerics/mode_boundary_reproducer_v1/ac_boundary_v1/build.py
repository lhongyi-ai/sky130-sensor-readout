#!/usr/bin/env python3
"""Prepare isolated native Spectre AC diagnostics; never invokes an EDA tool."""
from pathlib import Path
import hashlib, json, re, shutil

ROOT = Path(__file__).resolve().parent
CLOSURE = ROOT.parents[2]
SOURCE = ROOT.parent / 'static_charge_v1/input_strict.scs'
HELP = {
    'ac': CLOSURE / 'runs/task_20260924T081638283126Z/ac_help.txt',
    'vsource': CLOSURE / 'runs/task_20260924T070407785387Z/vsource_help.txt',
}
CASES = [('dn20u', -20e-6), ('dn5u', -5e-6), ('dn1u', -1e-6),
         ('d0', 0.0), ('dp1u', 1e-6), ('dp5u', 5e-6), ('dp20u', 20e-6)]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    source = SOURCE.read_text()
    device = next(s for s in source.splitlines() if s.startswith('XTEST '))
    include = next(s for s in source.splitlines() if s.startswith('include '))
    options = next(s for s in source.splitlines() if s.startswith('simulatorOptions '))
    assert device == 'XTEST (D G SB SB) pfet_01v8 w=(32u) l=150n as=8.48p ad=8.48p ps=64.53u pd=64.53u m=(1)*(1)'
    help_evidence = {}
    for name, path in HELP.items():
        lines = path.read_text().splitlines()
        patterns = ([r'\bstart=0\s', r'\bstop\s+Stop sweep', r'\bdec\s+Points per decade',
                     r'\boppoint=no\s', r'\bprevoppoint=no\s', r'\bskipdc=no\s'] if name == 'ac'
                    else [r'\bmag=0 V\s+Small signal voltage', r'\bphase=0 Deg\s+Small signal phase'])
        entries = []
        for pattern in patterns:
            hits = [i for i, line in enumerate(lines) if re.search(pattern, line)]
            assert len(hits) == 1, (name, pattern, hits)
            i = hits[0]
            entries.append({'line_1based': i+1, 'text': '\n'.join(lines[i:i+3])})
        help_evidence[name] = {'path': str(path.relative_to(CLOSURE)), 'sha256': sha(path), 'selected_syntax_evidence': entries}
    manifest = {
        'status': 'PREPARED_NOT_RUN',
        'scope': 'SAME_PFET_EXTERNAL_THREE_PORT_D_EXCITATION_AC_COLUMN_ONLY',
        'source_input': str(SOURCE.relative_to(CLOSURE)), 'source_sha256': sha(SOURCE),
        'device_line': device, 'model_include': include,
        'gate_dc_V': 0.91642555277800053, 'source_body_dc_V': 1.8,
        'source_and_body_remain_tied': True,
        'AC_sources': {'VD': {'mag_V': 1, 'phase_deg': 0}, 'VG': {'mag_V': 0, 'phase_deg': 0}, 'VS': {'mag_V': 0, 'phase_deg': 0}},
        'frequency_Hz': {'start': 1000, 'stop': 10000000, 'points_per_decade': 10, 'expected_points': 41},
        'precision': 'same_as_static_charge_v1_strict',
        'signed_measurement': 'For each external port k, I_device_k=-I_source_positive_terminal_k; Y_kD=I_device_k/V_D with V_G=V_SB=0; G=Re(Y), C_effective=Im(Y)/(2*pi*f). Do not negate PFET signs again or exchange D/S on reversed.',
        'not_claimed': ['complete Y matrix', 'individual source/body separation', 'Q field interpretation resolved', 'physical model correctness', 'transient LTE repair', 'ADC accuracy', 'MIM/PEX qualification'],
        'complete_ADC': False, 'full_ADC_accuracy_pass': False, 'formal_ADC_PEX_allowed': False,
        'help_evidence': help_evidence, 'cases': {},
    }
    for name, delta in CASES:
        folder = ROOT / 'cases' / name
        folder.mkdir(parents=True, exist_ok=True)
        text = f'''// Same-PFET external-port AC column. Diagnostic only; no ADC qualification.
simulator lang=spectre
global 0
parameters VDELTA={delta:.17g}
{include}
VD (D 0) vsource dc=1.8+VDELTA type=dc mag=1 phase=0
VG (G 0) vsource dc=0.91642555277800053 type=dc mag=0 phase=0
VS (SB 0) vsource dc=1.8 type=dc mag=0 phase=0
{device}
{options}
saveOptions options save=selected
save D G SB
save VD:currents VG:currents VS:currents XTEST.msky130_fd_pr__pfet_01v8:currents sigtype=dev
save XTEST.msky130_fd_pr__pfet_01v8:int_b XTEST.msky130_fd_pr__pfet_01v8:dbnode XTEST.msky130_fd_pr__pfet_01v8:sbnode sigtype=node
acBoundary ac start=1000 stop=10000000 dec=10 prevoppoint=no skipdc=no force=none useprevic=no oppoint=rawfile
element info what=inst where=rawfile
outputParameter info what=output where=rawfile
'''
        path = folder / 'input.scs'
        path.write_text(text)
        manifest['cases'][name] = {'delta_D_minus_SB_V': delta, 'input_path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
    shutil.copyfile(ROOT.parent/'static_charge_v1/limited_model_metadata.py', ROOT/'limited_model_metadata.py')
    manifest['metadata_script_sha256'] = sha(ROOT/'limited_model_metadata.py')
    (ROOT/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('P1_AC_BOUNDARY_PREPARED_NOT_RUN')

if __name__ == '__main__':
    main()
