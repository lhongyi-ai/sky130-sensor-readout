#!/usr/bin/env python3
"""Resolve frozen canary connectivity, never rewriting or simulating it.

This is a deliberately narrow parser of the frozen X-subcircuit syntax. All
parameters are evaluated by an arithmetic-only AST; primitive dimensions retain
the source model's micrometre convention. Native CDF mapping is NOT inferred.
"""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'qualification_20260913'
BENCH = SOURCE / 'runs/20260913T062412790986Z_noise_g4_acquire/bench.spice'
MODELS = {
    'sky130_fd_pr__nfet_01v8': ('mos', ['D', 'G', 'S', 'B']),
    'sky130_fd_pr__pfet_01v8': ('mos', ['D', 'G', 'S', 'B']),
    'sky130_fd_pr__nfet_01v8_lvt': ('mos', ['D', 'G', 'S', 'B']),
    'sky130_fd_pr__pfet_01v8_lvt': ('mos', ['D', 'G', 'S', 'B']),
    'sky130_fd_pr__res_high_po_0p35': ('resistor', ['A', 'B', 'SUB']),
    'sky130_fd_pr__res_high_po_0p69': ('resistor', ['A', 'B', 'SUB']),
    'sky130_fd_pr__cap_mim_m3_1': ('mim', ['TOP', 'BOTTOM']),
}
TOKEN = re.compile(r'[^\s{}]+?=\{[^}]+\}|\S+')


def number(expr, params):
    expr = expr.strip('{}')
    tree = ast.parse(expr, mode='eval')

    def val(n):
        if isinstance(n, ast.Expression):
            return val(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (float, int)):
            return n.value
        if isinstance(n, ast.Name):
            return params[n.id.upper()]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            return val(n.operand) * (-1 if isinstance(n.op, ast.USub) else 1)
        if isinstance(n, ast.BinOp):
            a, b = val(n.left), val(n.right)
            if isinstance(n.op, ast.Add): return a + b
            if isinstance(n.op, ast.Sub): return a - b
            if isinstance(n.op, ast.Mult): return a * b
            if isinstance(n.op, ast.Div): return a / b
        raise ValueError('Unsupported arithmetic: ' + expr)
    return val(tree)


def split_tokens(line):
    return TOKEN.findall(line)


def read_subcircuits(paths):
    definitions = {}
    current = None
    for path in paths:
        for lineno, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith('*'): continue
            if line.lower().startswith('.subckt '):
                t = split_tokens(line)
                if current is not None or t[1].lower() in definitions:
                    raise ValueError('Nested or duplicate definition')
                defaults = {}
                ports = []
                for token in t[2:]:
                    if token.lower() == 'params:': continue
                    if '=' in token:
                        k, v = token.split('=', 1)
                        defaults[k.upper()] = number(v, defaults)
                    else: ports.append(token.upper())
                current = {'name': t[1].lower(), 'ports': ports,
                           'defaults': defaults, 'lines': []}
                definitions[current['name']] = current
            elif line.lower().startswith('.ends'):
                current = None
            elif current is not None:
                current['lines'].append((line, path.name, lineno))
    if current is not None: raise ValueError('Unclosed subcircuit')
    return definitions


def main():
    paths = [SOURCE / n for n in ('candidate_06.spice', 'sampling_switch.spice', 'adc_blocks.spice')]
    definitions = read_subcircuits(paths)
    primitives, ideal_resistors, stimuli = [], [], []

    def expand(line, scope, ports, params, source, lineno):
        t = split_tokens(line)
        name = (scope + '/' + t[0]).strip('/')

        def net(n):
            n = n.upper()
            return '0' if n == '0' else ports.get(n, scope + '/' + n if scope else n)

        if t[0][0].upper() != 'X':
            if scope: raise ValueError('Unexpected non-X inside source hierarchy: ' + line)
            record = {'path': name, 'source_line': line, 'source_file': source,
                      'line': lineno, 'nets': [net(t[1]), net(t[2])]}
            (ideal_resistors if t[0].upper().startswith('R') else stimuli).append(record)
            return
        first = next((i for i, x in enumerate(t) if '=' in x), len(t))
        model = t[first - 1].lower()
        nodes = [net(x) for x in t[1:first - 1]]
        overrides = {k.upper(): number(v, params) for k, v in
                     (token.split('=', 1) for token in t[first:])}
        if model in MODELS:
            kind, terminals = MODELS[model]
            if len(terminals) != len(nodes): raise ValueError('Port count mismatch')
            primitives.append({'path': name, 'kind': kind, 'model': model,
                               'nets': dict(zip(terminals, nodes)), 'parameters': overrides,
                               'source_file': source, 'line': lineno,
                               'local_expression': line, 'context_parameters': params})
        else:
            definition = definitions[model]
            if len(nodes) != len(definition['ports']): raise ValueError('Subcircuit port count mismatch')
            child = dict(definition['defaults'], **overrides)
            mapping = dict(zip(definition['ports'], nodes))
            for inner, file, row in definition['lines']:
                expand(inner, name, mapping, child, file, row)

    for lineno, raw in enumerate(BENCH.read_text().splitlines(), 1):
        line = raw.strip()
        if line.lower() == '.control': break
        if not line or line[0] in '*.': continue
        expand(line, '', {}, {}, str(BENCH.relative_to(SOURCE)), lineno)
    resistors = []
    for x in primitives:
        if x['kind'] == 'resistor':
            resistors.append({'path': x['path'], 'model': x['model'],
                              'L_um': x['parameters']['L'],
                              'target_R_ohm': x['context_parameters']['R'], 'nets': x['nets']})
    result = {
        'status': 'SOURCE_CONNECTIVITY_RESOLVED__NATIVE_CDF_MAPPING_UNVERIFIED',
        'source_files': {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in paths + [BENCH]},
        'units': {'W': 'um in the frozen ngspice subcircuit interface',
                  'L': 'um in the frozen ngspice subcircuit interface'},
        'multiplicity_note': 'PDK primitive entries count parameterized source instances, not physical unit capacitors. The two CDAC bank entries each specify m=4096,mult=4096 under the source model semantics. Do not multiply them together or infer Cadence CDF semantics.',
        'primitive_entry_count': len(primitives),
        'primitive_counts_by_kind': dict(Counter(x['kind'] for x in primitives)),
        'primitive_counts_by_model': dict(Counter(x['model'] for x in primitives)),
        'ideal_testbench_resistors': ideal_resistors, 'testbench_stimuli': stimuli,
        'resistor_dimension_inventory': resistors, 'primitives': primitives,
    }
    # Independent source anchors prevent interpreting an incorrect split as a valid manifest.
    byname = {x['path']: x for x in primitives}
    assert byname['XPGA/XOTA/XMIP']['parameters'] == {'L': 1, 'W': 80}
    assert byname['XPGA/XOTA/XMIP']['nets']['G'] == 'XPGA/SUMPOS'
    assert byname['XPGA/XFP4/XR/XR']['nets']['A'] == 'ON'
    assert byname['XPGA/XFN4/XR/XR']['nets']['A'] == 'OP'
    assert byname['XCP/XC']['parameters'] == {'W': 3, 'L': 3, 'M': 4096, 'MULT': 4096}
    assert byname['XTGP/XND']['nets']['D'] == byname['XTGP/XND']['nets']['S'] == 'HP'
    output = HERE / 'canary_connectivity.json'
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'primitive_entry_count',
                                           'primitive_counts_by_kind', 'primitive_counts_by_model')}, indent=2))


if __name__ == '__main__':
    main()
