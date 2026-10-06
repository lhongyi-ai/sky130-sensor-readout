#!/usr/bin/env python3
"""Independent local review of the fixed first school_r1 STB export.

Reads the exported native body, never invokes Cadence or changes a design.
Probe equivalence here is topological contraction, not behavioral validation.
"""
import hashlib
import json
from pathlib import Path

from audit_native_netlist import parse, audit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROOT = REPO / 'v2/cadence/linuxlab_20260923'
RUN = ROOT / 'runs/p2fe_c06_stb_school_r1_20260923T101912237473Z'
ATTEMPT = ROOT / 'runs/spectre_stb_20260923T102213876307Z'
POLES = ROOT / 'runs/spectre_poles_20260923T101120120043Z'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    before = json.loads((ROOT / 'native_canary_school_r1_design.json').read_text())
    after = json.loads((ROOT / 'native_stb_school_r1_design.json').read_text())
    b = {o[0]: o for o in before}
    a = {o[0]: o for o in after}
    assert len(b) == len(before) == 133
    assert len(a) == len(after) == 136
    changes = {
        'XPGA_XOTA_XMIP': ('XPGA_SUMPOS', 'DM_INP'),
        'XPGA_XOTA_XMIN': ('XPGA_SUMNEG', 'DM_INN'),
        'XPGA_XOTA_XMLP': ('XPGA_XOTA_NCM', 'CM1_GATE'),
        'XPGA_XOTA_XMLN': ('XPGA_XOTA_NCM', 'CM1_GATE'),
        'XPGA_XOTA_XMOP': ('XPGA_XOTA_CMG', 'CM2_GATE'),
        'XPGA_XOTA_XMON': ('XPGA_XOTA_CMG', 'CM2_GATE'),
    }
    for name, old in b.items():
        new = a[name]
        assert old[:3] == new[:3] and old[4:] == new[4:], name
        expected = dict(old[3])
        if name in changes:
            original, inserted = changes[name]
            assert expected['G'] == original
            expected['G'] = inserted
        assert expected == dict(new[3]), name

    got, headers = parse((RUN / 'netlist').read_text())
    probes = {
        'DM_PROBE': ('diffstbprobe', ['XPGA_SUMPOS', 'XPGA_SUMNEG', 'DM_INP', 'DM_INN']),
        'CM1_PROBE': ('iprobe', ['XPGA_XOTA_NCM', 'CM1_GATE']),
        'CM2_PROBE': ('iprobe', ['XPGA_XOTA_CMG', 'CM2_GATE']),
    }
    assert len(got) == 136
    for name, (model, nodes) in probes.items():
        obj = got.pop(name)
        assert obj['model'] == model and obj['nodes'] == nodes and not obj['parameters']
    contractions = {'DM_INP': 'XPGA_SUMPOS', 'DM_INN': 'XPGA_SUMNEG',
                    'CM1_GATE': 'XPGA_XOTA_NCM', 'CM2_GATE': 'XPGA_XOTA_CMG'}
    lines = list(headers)
    for obj in got.values():
        nodes = [contractions.get(n, n) for n in obj['nodes']]
        params = ' '.join(k + '=' + v for k, v in obj['parameters'].items())
        lines.append('{} ({}) {} {}'.format(obj['name'], ' '.join(nodes), obj['model'], params))
    manifest = json.loads((HERE / 'native_canary_school_r1_objects.json').read_text())
    checked = audit(manifest, '\n'.join(lines))
    assert checked['status'] == 'NATIVE_NETLIST_AUDIT_PASS', checked['errors']
    pz = json.loads((POLES / 'pole_diagnostic.json').read_text())
    log = (ATTEMPT / 'spectre.out').read_text()
    assert 'undefined model or subcircuit' in log and '`diffstbprobe\'' in log
    files = [ROOT / 'build_stb_cell.py', ROOT / 'native_canary_school_r1_design.json',
             ROOT / 'native_stb_school_r1_design.json', RUN / 'netlist',
             ATTEMPT / 'input.scs', ATTEMPT / 'spectre.out', POLES / 'input.scs',
             POLES / 'spectre.out', POLES / 'input.raw/allPoles.pz',
             HERE / 'native_canary_school_r1_objects.json']
    result = {
        'scope': 'Offline fixed-input topology and interpretation review; no remote execution',
        'status': 'TOPOLOGY_CONTRACTION_PASS_STB_RUN_FAILED',
        'original_objects': 133, 'probe_objects': 3,
        'gate_nodes_changed': changes,
        'unchanged_core_device_parameters': True,
        'contracted_native_audit': {'status': checked['status'], 'errors': checked['errors'],
                                    'expected_count': checked['expected_count'], 'actual_count': checked['actual_count']},
        'probe_behavior_equivalence': 'NOT_VERIFIED: missing diffstbprobe definition in this fixed attempt',
        'stb_numeric_results': 'NOT_RUN',
        'pz_inspected': {k: pz[k] for k in ['scope', 'pole_count', 'rhp_count', 'max_real_Hz', 'limitation']},
        'pz_other_frequency_and_gmin_runs': 'Parent reported 1MHz and gmin=10f checks; not in the fixed files audited here',
        'formal_multiloop_stability': 'UNQUALIFIED',
        'missing_independent_probe_readout': 'input common mode at the paired input cut',
        'source_hashes': {str(p.relative_to(REPO)): sha(p) for p in files},
    }
    (HERE / 'stb_topology_independent_review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(result['status'])
    print('133 original objects and all core parameters preserved; contracted actual native body audited PASS.')
    print('Fixed STB attempt failed at circuit read-in; no numerical margin accepted.')


if __name__ == '__main__':
    main()
