#!/usr/bin/env python3
"""Freeze the actual ADC/phase graph and explicit school_r1 mapping proposal.

No Cadence or simulation calls. Only arithmetic source expressions are accepted.
Every topological/geometry change is recorded; no original files are modified.
"""
import ast
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP, getcontext
import hashlib
import json
from pathlib import Path
import re

getcontext().prec = 42
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN = ROOT / 'v2/analog/adc/qualification_20260913/snapshot/frozen'
EXPECTED = {
    'adc_blocks.spice': '255fe052f96de8e784bc337ac5b696e88294639c6817fd45e989d865d9ec3591',
    'adc_preamp.spice': 'c0ed1e17434f4a85d7bf174f9ab01f80a414d2d411338db771a4d7969d909782',
    'adc_reference_candidate.spice': '5813ab5f1c959f5b0d6ac44473d929259c45d534dff785263e667be963283442',
    'adc_tgate_dual_lvt_dummy.spice': '389d182342b2d1e88ba31530c6cc98d0e75756d8009126746d7d73b40d98d734',
    'sensor_adc_candidate.spice': '94c047a1f664ffa001c1588c5cfefe85fc5d09f42dd2705a7dade21f332acf6d',
    'sensor_phases.spice': 'be8e84861058a1aba7e4219efe3fdec5ef9d4f47b44e6c5207eda709cddaa462',
    'sar_controller.v': '5e65a4cff94ae8507d5830cd7c0c669be50ea6e1730b8d20b0893afc39e4dadf',
}
MODELS = {
    **{'sky130_fd_pr__' + n: ('mos', ('D', 'G', 'S', 'B')) for n in
       ('nfet_01v8', 'pfet_01v8', 'nfet_01v8_lvt', 'pfet_01v8_lvt')},
    **{'sky130_fd_pr__' + n: ('resistor', ('A', 'B', 'SUB')) for n in
       ('res_high_po_5p73', 'res_high_po_1p41')},
    'sky130_fd_pr__cap_mim_m3_1': ('mim', ('TOP', 'BOTTOM')),
}
TOKEN = re.compile(r'[^\s{}]+?=\{[^}]+\}|\S+')
GRID = Decimal('.005')
REND = Decimal('72.75744875')
ROHM_PER_UM = Decimal('56.642069825')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ds(value):
    return format(value.normalize(), 'f')


def um(value):
    return ds(value) + 'u'


def quantize(value):
    return (value / GRID).to_integral_value(rounding=ROUND_HALF_UP) * GRID


def write(name, content):
    (HERE / name).write_text(json.dumps(content, indent=2, default=ds, allow_nan=False) + '\n')


def evaluate(expression, parameters):
    expression = expression.strip('{}')
    tree = ast.parse(expression, mode='eval')

    def rec(node):
        if isinstance(node, ast.Expression):
            return rec(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (float, int):
            return Decimal(ast.get_source_segment(expression, node))
        if isinstance(node, ast.Name):
            return parameters[node.id.upper()]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return (-1 if isinstance(node.op, ast.USub) else 1) * rec(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = rec(node.left), rec(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b
        raise ValueError('Unsupported source expression: ' + expression)
    return rec(tree)


def definitions():
    result, current = {}, None
    for name, expected in EXPECTED.items():
        path = FROZEN / name
        assert sha(path) == expected, 'Frozen source changed: ' + name
        if not name.endswith('.spice'): continue
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith('*'): continue
            tokens = TOKEN.findall(line)
            if tokens[0].lower() == '.subckt':
                assert current is None and tokens[1].lower() not in result
                current = {'name': tokens[1].lower(), 'ports': [], 'defaults': {}, 'body': []}
                for token in tokens[2:]:
                    if token.lower() == 'params:': continue
                    if '=' in token:
                        key, value = token.split('=', 1)
                        current['defaults'][key.upper()] = evaluate(value, current['defaults'])
                    else:
                        current['ports'].append(token.upper())
                result[current['name']] = current
            elif tokens[0].lower() == '.ends':
                assert current is not None
                if len(tokens) > 1: assert tokens[1].lower() == current['name']
                current = None
            else:
                assert current is not None and tokens[0][0].upper() == 'X', line
                current['body'].append({'file': name, 'line': number, 'text': line})
    assert current is None
    return result


def flatten(defs, top, prefix):
    primitives, hierarchy = [], []

    def expand(model, scope, ports, values):
        d = defs[model]
        hierarchy.append({'path': scope, 'subcircuit': model, 'ports': ports, 'parameters': values})
        for record in d['body']:
            t = TOKEN.findall(record['text'])
            first_param = next((i for i, tok in enumerate(t) if '=' in tok), len(t))
            child = t[first_param - 1].lower()
            name = scope + '/' + t[0].upper()
            def net(n):
                n = n.upper()
                return '0' if n == '0' else ports.get(n, scope + '/' + n)
            nets = [net(n) for n in t[1:first_param - 1]]
            overrides = {}
            for token in t[first_param:]:
                key, value = token.split('=', 1)
                assert key.upper() not in overrides
                overrides[key.upper()] = evaluate(value, values)
            if child in MODELS:
                kind, terms = MODELS[child]
                assert len(nets) == len(terms)
                primitives.append({'path': name, 'kind': kind, 'model': child,
                                   'nets': dict(zip(terms, nets)), 'parameters': overrides,
                                   'context_parameters': deepcopy(values), 'source': record})
            else:
                c = defs[child]
                assert len(nets) == len(c['ports'])
                assert set(overrides) <= set(c['defaults']), (child, overrides)
                expand(child, name, dict(zip(c['ports'], nets)), dict(c['defaults'], **overrides))

    expand(top, prefix, {p: p for p in defs[top]['ports']}, defs[top]['defaults'])
    assert len({p['path'] for p in primitives}) == len(primitives)
    uses = defaultdict(list)
    for p in primitives:
        for terminal, node in p['nets'].items(): uses[node].append(p['path'] + '.' + terminal)
        if p['kind'] == 'mos':
            assert p['nets']['B'] == ('VDD' if 'pfet' in p['model'] else 'VSS')
            assert p['parameters'].get('NF', 1) == p['parameters'].get('MULT', 1) == 1
        if p['kind'] == 'resistor': assert p['nets']['SUB'] == 'VSS'
    singles = {n: p for n, p in uses.items() if len(p) == 1 and n not in defs[top]['ports']}
    assert not singles, singles
    return {'top': top, 'port_order': defs[top]['ports'], 'primitives': primitives,
            'hierarchy': hierarchy, 'primitive_count': len(primitives),
            'counts_by_kind': dict(Counter(p['kind'] for p in primitives)),
            'counts_by_model': dict(Counter(p['model'] for p in primitives)),
            'internal_single_terminal_nets': singles}


def mapping(source):
    objects, changes, names, originalnets = [], [], {}, set()
    def identifier(n):
        out = n.replace('/', '_')
        assert names.setdefault(out, n) == n, 'Flattened identifier collision'
        return out
    for p in source['primitives']:
        for n in p['nets'].values(): originalnets.add(identifier(n))
    for p in source['primitives']:
        params, cell = p['parameters'], p['model'].removeprefix('sky130_fd_pr__')
        obj = {'name': identifier(p['path']), 'originalpath': p['path'],
               'kind': p['kind'], 'library': 'sky130_fd_pr_main', 'cell': cell, 'view': 'symbol',
               'source_parameters': deepcopy(params), 'original_model': p['model'],
               'source_location': p['source'], 'mapping_notes': []}
        if p['kind'] == 'mos':
            w, length = quantize(params['W']), quantize(params['L'])
            assert Decimal('.42') <= w <= 50 and length == params['L']
            obj['props'] = {'w': um(w), 'fw': um(w), 'l': um(length), 'fingers': '1', 'm': '1'}
            obj['mapped_parameters'] = {'W': w, 'L': length, 'NF': 1, 'M': 1}
            obj['nets'] = {k: identifier(v) for k, v in p['nets'].items()}
            if w != params['W']:
                changes.append({'path': p['path'], 'kind': 'mos_width_grid',
                                'source_W_um': params['W'], 'requested_W_um': w,
                                'delta_um': w - params['W'], 'fraction': w / params['W'] - 1})
                obj['mapping_notes'].append('New school_r1: width explicitly rounded to nearest 5nm; original width preserved above. Requires CDF and performance requalification.')
            objects.append(obj)
        elif p['kind'] == 'mim':
            count = params.get('M', Decimal(1))
            assert params.get('MULT', count) == count and count == int(count)
            w, length = max(params['W'], Decimal(4)), max(params['L'], Decimal(4))
            assert quantize(w) == w and quantize(length) == length
            obj['cell'] = 'cap_mim_m3__base'
            obj['props'] = {'w': um(w), 'l': um(length), 'm': ds(count)}
            obj['mapped_parameters'] = {'W': w, 'L': length, 'M': count}
            obj['nets'] = {'PLUS': identifier(p['nets']['TOP']), 'MINUS': identifier(p['nets']['BOTTOM'])}
            obj['mapping_notes'].append('Source m and mult represent one nominal COUNT; school m=COUNT only. Statistical averaging and spatial mismatch are not qualified.')
            if w != params['W'] or length != params['L']:
                changes.append({'path': p['path'], 'kind': 'mim_minimum_geometry',
                                'source_W_L_um': [params['W'], params['L']],
                                'requested_W_L_um': [w, length], 'physical_unit_count': count})
                obj['mapping_notes'].append('New school_r1: 3x3um unit becomes 4x4um. Applies to CDAC, comparator ballast and preamp loads. Old timing/noise/PEX results do not transfer.')
            objects.append(obj)
        elif p['kind'] == 'resistor':
            if cell == 'res_high_po_5p73':
                width, target = Decimal('5.73'), p['context_parameters']['R']
                assert abs(REND + ROHM_PER_UM * params['L'] - target) < Decimal('1e-30')
                count = 1
                while (target / count - REND) / ROHM_PER_UM > 100: count += 1
                raw_length = (target / count - REND) / ROHM_PER_UM
                length = quantize(raw_length)
                predicted_total = count * (REND + ROHM_PER_UM * length)
            else:
                assert cell == 'res_high_po_1p41'
                width, target, count = Decimal('1.41'), None, 1
                raw_length, length = params['L'], quantize(params['L'])
                predicted_total = None
            assert Decimal('.5') <= length <= 100
            intermediate = [obj['name'] + '_SERIES_' + str(i) for i in range(1, count)]
            assert not originalnets.intersection(intermediate)
            nodes = [identifier(p['nets']['A'])] + intermediate + [identifier(p['nets']['B'])]
            segments = []
            for i in range(count):
                part = deepcopy(obj)
                if count > 1: part['name'] += '_SEG_' + str(i + 1)
                segments.append(part['name'])
                part['props'] = {'segL': um(length), 'segW': um(width), 'segments': 1, 'connection': 'Series'}
                part['mapped_parameters'] = {'L': length, 'W': width, 'SEGMENTS': 1}
                part['nets'] = {'PLUS': nodes[i], 'MINUS': nodes[i + 1], 'B': identifier(p['nets']['SUB'])}
                part['mapping_segment_index'], part['mapping_segment_count'] = i + 1, count
                part['mapping_notes'] = ['Source 5p73 end-resistance model used for allocation; never equate CDF r with actual resistance. All lengths explicitly rounded to nearest 5nm; additional end parasitics unqualified.']
                objects.append(part)
            changes.append({'path': p['path'], 'kind': 'resistor_segments_and_grid',
                            'cell': cell, 'source_L_um': params['L'], 'target_R_ohm': target,
                            'source_end_ohm': REND if target is not None else None,
                            'source_ohm_per_um': ROHM_PER_UM if target is not None else None,
                            'raw_segment_L_um': raw_length, 'segment_L_um': length,
                            'segment_count': count, 'segment_names': segments,
                            'internal_nodes': intermediate, 'predicted_total_R_ohm': predicted_total,
                            'predicted_delta_R_ohm': None if target is None else predicted_total - target,
                            'scope': 'Nominal source-model arithmetic estimate only. School bias, end effects and extracted parasitics require simulation.'})
        else: raise ValueError(p['kind'])
    uses = defaultdict(list)
    for obj in objects:
        for term, node in obj['nets'].items(): uses[node].append(obj['name'] + '.' + term)
    assert len(objects) == len({o['name'] for o in objects})
    for change in changes:
        for node in change.get('internal_nodes', []): assert len(uses[node]) == 2
    bypath = defaultdict(list)
    for obj in objects: bypath[obj['originalpath']].append(obj)
    for p in source['primitives']:
        mapped = bypath[p['path']]
        if p['kind'] == 'resistor':
            assert mapped[0]['nets']['PLUS'] == identifier(p['nets']['A'])
            assert mapped[-1]['nets']['MINUS'] == identifier(p['nets']['B'])
            assert all(a['nets']['MINUS'] == b['nets']['PLUS'] for a, b in zip(mapped, mapped[1:]))
            assert all(o['nets']['B'] == 'VSS' for o in mapped)
        else:
            remap = {'TOP': 'PLUS', 'BOTTOM': 'MINUS'} if p['kind'] == 'mim' else {k: k for k in p['nets']}
            assert len(mapped) == 1
            assert all(mapped[0]['nets'][remap[k]] == identifier(v) for k, v in p['nets'].items())
    return objects, changes


def main():
    defs = definitions()
    result = {'status': 'LOCAL_SOURCE_AND_MAPPING_AUDIT_PASS__NATIVE_NOT_CREATED',
              'source_hashes': {str((FROZEN / n).relative_to(ROOT)): h for n, h in EXPECTED.items()},
              'proposal_variant': 'adc_school_r1', 'school_executed': False,
              'geometry': {'grid_um': GRID, 'rounding': 'ROUND_HALF_UP nearest 5nm',
                           'maximum_finger_width_um': 50, 'minimum_mim_side_um': 4,
                           'maximum_resistor_segment_length_um': 100},
              'topologies': {}, 'changes': {}, 'source_contains_B_E_A_devices': False,
              'ADC_PAIR_WIDTH_SKEW': 0,
              'scope': 'Nominal source geometry resolved exactly; deliberate new school proposal. Not native export, model validation, performance or physical acceptance.'}
    for name, prefix, output in [('sensor_adc_candidate', 'XADC', 'adc'), ('sensor_phases', 'XPHASE', 'phase')]:
        source = flatten(defs, name, prefix)
        objs, changes = mapping(source)
        write(output + '_source_connectivity.json', source)
        write(output + '_school_r1_objects.json', objs)
        result['topologies'][output] = {k: source[k] for k in ('top', 'port_order', 'primitive_count', 'counts_by_kind', 'counts_by_model', 'internal_single_terminal_nets')}
        result['topologies'][output]['native_proposal_count'] = len(objs)
        result['topologies'][output]['native_counts_by_kind'] = dict(Counter(o['kind'] for o in objs))
        result['topologies'][output]['maximum_source_MOS_W_um'] = max(p['parameters']['W'] for p in source['primitives'] if p['kind'] == 'mos')
        result['changes'][output] = changes
        if output == 'adc':
            bypath = {p['path']: p for p in source['primitives']}
            assert bypath['XADC/XPRE/XIP']['nets']['G'] == 'XADC/TN'
            assert bypath['XADC/XPRE/XIN']['nets']['G'] == 'XADC/TP'
            assert bypath['XADC/XSP/XND']['nets']['D'] == bypath['XADC/XSP/XND']['nets']['S'] == 'XADC/TP'
            for side, bottom in [('P', 'BP'), ('N', 'BN')]:
                for i in range(12):
                    cap = bypath['XADC/XC' + side + '/XC' + str(i) + '/XC']
                    assert cap['parameters']['M'] == cap['parameters']['MULT'] == 2 ** i
                    assert cap['nets'] == {'TOP': 'XADC/T' + side, 'BOTTOM': 'XADC/' + bottom + str(i)}
                dummy = bypath['XADC/XC' + side + '/XD/XC']
                assert dummy['parameters']['M'] == 1
                assert sum(p['parameters']['M'] for p in source['primitives'] if p['path'].startswith('XADC/XC' + side + '/')) == 4096
            result['binary_array'] = {'bits': 12, 'weights_LSB_to_MSB': [2**i for i in range(12)],
                                      'dummy_units_per_side': 1, 'total_units_per_side': 4096,
                                      'source_unit_W_L_um': [3, 3], 'school_unit_W_L_um': [4, 4],
                                      'source_nominal_unit_fF': '19.845',
                                      'school_CDF_unit_fF_not_measurement': '34.6223',
                                      'source_nominal_per_side_pF': '81.28512',
                                      'school_CDF_per_side_pF_not_measurement': '141.8129408',
                                      'count_and_topology_preserved': True,
                                      'school_nominal_and_mismatch_model_qualification': 'PENDING'}
    result['change_counts'] = {top: dict(Counter(c['kind'] for c in rows)) for top, rows in result['changes'].items()}
    result['pending'] = [
        'Native CDF and termOrder readback for res_high_po_5p73 and res_high_po_1p41; exact model entry.',
        'Confirm proposed rounded reference-switch widths with CDF readback; no silent callback change.',
        'Export real native ADC and phase netlists and compare every instance, body, port and geometry.',
        'Native two-frame actual-comparator AMS run, then 12-frame convergence qualification.',
        'School 4um MIM nominal/multiplier/noise/statistical-model qualification; 3um PEX does not map.',
        'School 5p73 segmented resistor DC/noise/RC comparison at actual bias; CDF r is not acceptance.',
        'All full-code, 16384-record dynamics with device noise, 200 mismatch samples, 45 PVT and physical gates remain.'
    ]
    write('mapping_report.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'topologies', 'change_counts', 'binary_array')}, indent=2, default=ds))


if __name__ == '__main__':
    main()
