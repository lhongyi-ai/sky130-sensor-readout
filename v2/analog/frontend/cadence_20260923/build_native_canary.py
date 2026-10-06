#!/usr/bin/env python3
"""Generate a proposed flat native mapping from frozen resolved connectivity.

CDF callbacks, geometry readback, parasitics and native netlist equivalence must
be validated by the remote executor. Nothing here calls Cadence or claims that
the mapping has been accepted by the PDK.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'canary_connectivity.json'


def decimal(value):
    return str(int(value)) if int(value) == value else repr(value)


def dim(value):
    return decimal(value) + 'u'


def identifier(source):
    return source.replace('/', '_')


def main():
    source = json.loads(SOURCE.read_text())
    objects = []
    mappings = []
    net_identity = {}

    def net(value):
        mapped = identifier(value)
        prior = net_identity.setdefault(mapped, value)
        if prior != value:
            raise ValueError('Identifier collision: ' + mapped)
        return mapped

    for p in source['primitives']:
        params = p['parameters']
        cell = p['model'].removeprefix('sky130_fd_pr__')
        notes = []
        if p['kind'] == 'mos':
            total = params['W']
            fingers = {80: 2, 64: 2, 180: 4}.get(total, 1)
            fw = total / fingers
            if fw > 50: raise ValueError('Unmapped over-width MOS')
            if params.get('NF', 1) != 1 or params.get('MULT', 1) != 1:
                raise ValueError('Unexpected source MOS multiplicity')
            props = {'w': dim(total), 'fw': dim(fw), 'l': dim(params['L']),
                     'fingers': str(fingers), 'm': '1'}
            nets = {pin: net(node) for pin, node in p['nets'].items()}
            assert nets['B'] == ('VDD' if cell.startswith('pfet') else '0')
            assert float(fw) * fingers == total
            if fingers != 1:
                notes.append('Requested total W preserved via fingers; school simW=fw,simM=m*fingers. Source/drain area, perimeter and other native geometry effects still require audit.')
                mappings.append({'original_path': p['path'], 'source_W_um': total,
                                 'native_fw_um': fw, 'fingers': fingers, 'm': 1})
        elif p['kind'] == 'resistor':
            width = {'res_high_po_0p35': .35, 'res_high_po_0p69': .69}[cell]
            props = {'segL': dim(params['L']), 'effL': dim(params['L']),
                     'segW': dim(width), 'effW': dim(width),
                     'segments': 1, 'connection': 'Series'}
            nets = {'PLUS': net(p['nets']['A']), 'MINUS': net(p['nets']['B']),
                    'B': net(p['nets']['SUB'])}
            assert nets['B'] == '0'
            notes.append('Requested dimensions retained without rounding; legal grid/range and segment callback readback unverified.')
        elif p['kind'] == 'mim':
            cell = 'cap_mim_m3__base'
            count = params.get('M', 1)
            if params.get('MULT', count) != count:
                raise ValueError('Unexpected source MIM mult semantics')
            props = {'w': dim(params['W']), 'l': dim(params['L']), 'm': decimal(count)}
            nets = {'PLUS': net(p['nets']['TOP']), 'MINUS': net(p['nets']['BOTTOM'])}
            if count != 1:
                notes.append('School m=4096 is a nominal mapping proposal; source m=mult=4096 must not be multiplied together. Native unit/bank AC verification and statistical-model semantics remain unverified.')
        else:
            raise ValueError(p['kind'])
        objects.append({'name': identifier(p['path']), 'originalpath': p['path'],
                        'library': 'sky130_fd_pr_main', 'cell': cell,
                        'view': 'symbol', 'kind': p['kind'], 'props': props,
                        'nets': nets, 'original_model': p['model'],
                        'source_parameters': params, 'mapping_notes': notes})

    for p in source['ideal_testbench_resistors']:
        resistance = '350' if p['path'] in ('RSP', 'RSN') else '1G'
        objects.append({'name': p['path'], 'originalpath': p['path'],
                        'library': 'analogLib', 'cell': 'res', 'view': 'symbol',
                        'kind': 'testbench_resistor', 'props': {'r': resistance},
                        'nets': dict(zip(('PLUS', 'MINUS'), map(net, p['nets'])))})

    supply_values = {'VDD': '1.8', 'VCM': '0.9', 'VACQ': '1.8',
                     'VACQB': '0', 'VSEL0': '1.8', 'VSEL1': '0'}
    stimulus_by_path = {x['path']: x for x in source['testbench_stimuli']}
    for path, value in supply_values.items():
        p = stimulus_by_path[path]
        objects.append({'name': path, 'originalpath': path, 'library': 'analogLib',
                        'cell': 'vdc', 'view': 'symbol', 'kind': 'testbench_source',
                        'props': {'dc': value},
                        'nets': dict(zip(('PLUS', 'MINUS'), map(net, p['nets'])))})
    for original, name, dc, phase in [('BSP', 'VINP', '0.9+SW/8', '0'),
                                      ('BSN', 'VINN', '0.9-SW/8', '180')]:
        p = stimulus_by_path[original]
        objects.append({'name': name, 'originalpath': original,
                        'library': 'analogLib', 'cell': 'vdc', 'view': 'symbol',
                        'kind': 'testbench_source',
                        'props': {'dc': dc, 'acm': '.125', 'acp': phase},
                        'nets': dict(zip(('PLUS', 'MINUS'), map(net, p['nets']))),
                        'mapping_notes': ['VSW and dependent-source testbench replaced by exact DC expression and AC stimulus; SW is a design variable with default 0.']})

    names = [x['name'] for x in objects]
    assert len(names) == len(set(names))
    assert len(objects) == 119
    assert Counter(x['kind'] for x in objects) == {
        'mos': 55, 'resistor': 22, 'mim': 30,
        'testbench_resistor': 4, 'testbench_source': 8}
    terminal_uses = defaultdict(list)
    for x in objects:
        for pin, node in x['nets'].items():
            terminal_uses[node].append(x['name'] + '.' + pin)
    single = {n: p for n, p in terminal_uses.items() if len(p) == 1}
    assert single == {'XPGA_XOTA_BP': ['XPGA_XOTA_XBIAS_XRBP_XR.PLUS']}, single
    assert 'SW' not in terminal_uses
    # Check that every original primitive terminal survives the native renaming.
    bypath = {x['originalpath']: x for x in objects}
    for p in source['primitives']:
        pins = ({'A': 'PLUS', 'B': 'MINUS', 'SUB': 'B'} if p['kind'] == 'resistor'
                else {'TOP': 'PLUS', 'BOTTOM': 'MINUS'} if p['kind'] == 'mim'
                else {s: s for s in ('D', 'G', 'S', 'B')})
        for pin, node in p['nets'].items():
            assert bypath[p['path']]['nets'][pins[pin]] == identifier(node)

    (HERE / 'native_canary_objects.json').write_text(json.dumps(objects, indent=2) + '\n')
    review = {
        'status': 'NATIVE_MAPPING_PROPOSAL__CDF_READBACK_AND_SIMULATION_REQUIRED',
        'source_manifest_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'objects_sha256': hashlib.sha256((HERE / 'native_canary_objects.json').read_bytes()).hexdigest(),
        'object_count': len(objects), 'counts': dict(Counter(x['kind'] for x in objects)),
        'unique_instance_names': True, 'primitive_connectivity_preserved': True,
        'mos_bodies_checked': 55, 'resistor_bodies_checked': 22,
        'design_variables': {'SW': 0}, 'ground_net': '0',
        'net_name_map': net_identity, 'single_terminal_nets': single,
        'single_terminal_note': 'BP is the pre-existing unused compatibility node at the far end of the 1 MOhm bias resistor. Preserve and report it; do not add an invented connection. All other nets have at least two terminals.',
        'mos_width_mapping': mappings,
        'unverified': ['CDF callback acceptance and legal grids/ranges',
                       'Native exported netlist connectivity and instance parameters',
                       'MOS source/drain geometry and parasitics after finger mapping',
                       'MIM m=4096 nominal AC capacitance and statistical-model semantics',
                       'Any actual Cadence execution or frontend qualification'],
    }
    (HERE / 'native_canary_mapping_review.json').write_text(json.dumps(review, indent=2) + '\n')
    print(json.dumps({k: review[k] for k in ('status', 'object_count', 'counts', 'single_terminal_nets')}, indent=2))


if __name__ == '__main__':
    main()
