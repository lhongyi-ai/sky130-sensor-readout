#!/usr/bin/env python3
"""Strict school_r1 flat Spectre netlist audit; never simulates or edits input.

The expected JSON is a native object list, not a simulator result. A passed
audit means connectivity/parameters match that proposal, never M2 qualification.
Compatible with Python 3.6+; standard library only.
"""
import argparse
from collections import Counter
from fractions import Fraction
import ast
import hashlib
import json
from pathlib import Path
import re

SUFFIX = {'': 1, 'T': 10**12, 'G': 10**9, 'g': 10**9,
          'M': 10**6, 'meg': 10**6, 'Meg': 10**6, 'k': 1000, 'K': 1000,
          'm': Fraction(1, 1000), 'u': Fraction(1, 10**6),
          'n': Fraction(1, 10**9), 'p': Fraction(1, 10**12),
          'f': Fraction(1, 10**15), 'a': Fraction(1, 10**18)}
NUMBER = re.compile(r'(?<![\w.])((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(meg|Meg|[TGMgkKmunpfa])?(?![\w.])')
INSTANCE = re.compile(r'^([^\s()]+)\s*\(([^()]*)\)\s+([A-Za-z_][\w]*)\s*(.*)$')
ASSIGNMENT = re.compile(r'(?:^|\s)([A-Za-z_][\w]*)\s*=')


def affine(expression):
    """Return exact rational (constant, SW coefficient); reject other grammar."""
    expression = str(expression).strip()
    if len(expression) >= 2 and expression[0] == expression[-1] == '"':
        expression = expression[1:-1]
    if expression.startswith('{') and expression.endswith('}'):
        expression = expression[1:-1]
    numbers = {}

    def replace(match):
        name = 'N' + str(len(numbers))
        numbers[name] = Fraction(match.group(1)) * SUFFIX[match.group(2) or '']
        return name
    expression = NUMBER.sub(replace, expression)
    tree = ast.parse(expression, mode='eval')

    def rec(node):
        if isinstance(node, ast.Expression): return rec(node.body)
        if isinstance(node, ast.Name):
            if node.id == 'SW': return Fraction(0), Fraction(1)
            if node.id in numbers: return numbers[node.id], Fraction(0)
            raise ValueError('Unknown expression symbol: ' + node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            a, b = rec(node.operand)
            sign = -1 if isinstance(node.op, ast.USub) else 1
            return sign * a, sign * b
        if isinstance(node, ast.BinOp):
            a, b = rec(node.left); c, d = rec(node.right)
            if isinstance(node.op, ast.Add): return a + c, b + d
            if isinstance(node.op, ast.Sub): return a - c, b - d
            if isinstance(node.op, ast.Mult):
                if b and d: raise ValueError('Nonlinear SW expression')
                return a*c, a*d+b*c
            if isinstance(node.op, ast.Div):
                if d or not c: raise ValueError('Variable or zero denominator')
                return a/c, b/c
        raise ValueError('Unsupported expression grammar: ' + expression)
    return rec(tree)


def scalar(expression):
    constant, coefficient = affine(expression)
    if coefficient: raise ValueError('Expected constant, got SW expression')
    return constant


def close(a, b):
    # Serialization tolerance, much smaller than the 5nm geometry grid.
    return abs(a-b) <= max(abs(b), Fraction(1, 10**30)) * Fraction(1, 10**10)


def width_um(value):
    """Manifest W is an explicit positive decimal in micrometres, no units/code.

    Both source_parameters.W and mapped_parameters.W use the same contract.
    Native properties still use the existing unit-aware arithmetic parser.
    """
    text = str(value).strip()
    if not re.fullmatch(r'\+?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', text):
        raise ValueError('Manifest W must be a positive decimal micrometre value, without suffixes or expressions')
    number = Fraction(text)
    if number <= 0:
        raise ValueError('Manifest W must be greater than zero')
    return number


def logical_lines(text):
    pending = ''
    first = None
    for line_no, raw in enumerate(text.splitlines(), 1):
        # Frozen native body has no path strings; comments inside quoted values
        # are not expected. Reject ambiguous strings instead of dropping them.
        quoted = False; cut = len(raw)
        for i, c in enumerate(raw):
            if c == '"': quoted = not quoted
            if not quoted and raw[i:i+2] == '//': cut = i; break
        line = raw[:cut].strip()
        if not line: continue
        if first is None: first = line_no
        if line.endswith('\\'):
            pending += line[:-1] + ' '
            continue
        yield first, pending + line
        first = None; pending = ''
    if pending: raise ValueError('Trailing unfinished continuation')


def parameters(text):
    matches = list(ASSIGNMENT.finditer(text))
    if not matches:
        if text.strip(): raise ValueError('Unparsed instance text: ' + text)
        return {}
    if text[:matches[0].start()].strip(): raise ValueError('Unexpected parameter prefix')
    result = {}
    for i, m in enumerate(matches):
        key = m.group(1)
        value = text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
        if not value or key in result: raise ValueError('Empty/duplicate parameter: ' + key)
        result[key] = value
    return result


def parse(text):
    instances = {}
    headers = []
    for line_no, line in logical_lines(text):
        if re.fullmatch(r'(simulator\s+lang=spectre|global\s+0)', line):
            headers.append(line)
            continue
        if line.startswith('parameters '):
            values = parameters(line[len('parameters '):])
            if set(values) != {'SW'} or scalar(values['SW']) != 0:
                raise ValueError('Only the default SW=0 header is accepted; audit the native body separately from sweep decks.')
            headers.append(line)
            continue
        m = INSTANCE.match(line)
        if not m:
            raise ValueError('Unsupported native-body line {}: {}'.format(line_no, line[:160]))
        name, nodes, model, params = m.groups()
        if name in instances: raise ValueError('Duplicate instance: ' + name)
        instances[name] = {'name': name, 'nodes': nodes.split(), 'model': model,
                           'parameters': parameters(params), 'line': line_no}
    return instances, headers


def audit(objects, text):
    result = {'status': 'NATIVE_NETLIST_AUDIT_FAIL',
              'scope': 'Flat native connectivity and requested school_r1 parameters only; no simulator/performance/physical acceptance.',
              'errors': [], 'instances': [], 'cdf_r_usage': 'Recorded for traceability only; never used as actual model resistance or acceptance threshold.'}

    def error(kind, name, **detail):
        result['errors'].append(dict({'kind': kind, 'instance': name}, **detail))
    names = [x['name'] for x in objects]
    if len(names) != len(set(names)):
        error('DUPLICATE_MANIFEST_INSTANCE', '')
        return result
    try:
        actual, headers = parse(text)
    except (ValueError, SyntaxError, ZeroDivisionError, KeyError) as exc:
        result['status'] = 'NATIVE_NETLIST_PARSE_ERROR'
        error('PARSE_ERROR', '', message=str(exc))
        return result
    result['headers'] = headers
    result['expected_count'] = len(objects); result['actual_count'] = len(actual)
    for name in sorted(set(names) - set(actual)): error('MISSING_INSTANCE', name)
    for name in sorted(set(actual) - set(names)): error('UNEXPECTED_INSTANCE', name)

    def check_constant(got, key, expected, name, default=None):
        expression = got.get(key, default)
        if expression is None:
            error('MISSING_PARAMETER', name, parameter=key)
            return None
        try:
            value, want = scalar(expression), scalar(expected)
            if not close(value, want):
                error('PARAMETER_MISMATCH', name, parameter=key,
                      actual_expression=expression, expected_expression=expected,
                      actual_value=float(value), expected_value=float(want))
            return value
        except (ValueError, SyntaxError, ZeroDivisionError, KeyError) as exc:
            error('INVALID_PARAMETER', name, parameter=key, expression=expression, message=str(exc))
            return None

    for expected in objects:
        name = expected['name']
        if name not in actual: continue
        got = actual[name]; p = got['parameters']; props = expected['props']; kind = expected['kind']
        model = expected['cell']
        if kind == 'mos':
            order = ['D', 'G', 'S', 'B']; allowed = {'w', 'l', 'm', 'as', 'ad', 'ps', 'pd'}
        elif kind == 'resistor':
            order = ['PLUS', 'MINUS', 'B']; allowed = {'l', 'w', 'r', 'm'}
        elif kind == 'mim':
            model = 'cap_mim_m3_1'; order = ['PLUS', 'MINUS']; allowed = {'l', 'w', 'm'}
        elif kind == 'testbench_resistor':
            model = 'resistor'; order = ['PLUS', 'MINUS']; allowed = {'r', 'm'}
        elif kind == 'testbench_source':
            model = 'vsource'; order = ['PLUS', 'MINUS']; allowed = {'dc', 'mag', 'phase', 'type'}
        else:
            error('UNSUPPORTED_MANIFEST_KIND', name, actual=kind)
            continue
        want_nodes = [expected['nets'][pin] for pin in order]
        if got['nodes'] != want_nodes:
            error('CONNECTIVITY_MISMATCH', name, terminal_order=order,
                  actual=got['nodes'], expected=want_nodes)
        if got['model'] != model:
            error('MODEL_MISMATCH', name, actual=got['model'], expected=model)
        for key in sorted(set(p) - allowed):
            error('UNREVIEWED_PARAMETER', name, parameter=key, value=p[key])
        width_mapping = None
        if kind == 'mos':
            w = check_constant(p, 'w', props['fw'], name)
            check_constant(p, 'l', props['l'], name)
            m = check_constant(p, 'm', '({})*({})'.format(props['m'], props['fingers']), name)
            try:
                original_w = width_um(expected['source_parameters']['W'])
                mapped = expected.get('mapped_parameters', {})
                if not isinstance(mapped, dict):
                    raise ValueError('mapped_parameters must be an object when present')
                target_field = 'mapped_parameters.W' if 'W' in mapped else 'source_parameters.W'
                target_w = width_um(mapped['W']) if 'W' in mapped else original_w
                width_mapping = {'original_source_w_um': float(original_w),
                                 'target_w_um': float(target_w), 'target_field': target_field,
                                 'intentional_width_change': original_w != target_w,
                                 'target_over_original': float(target_w/original_w),
                                 'units': 'um; explicit design values, not a physical-equivalence claim'}
                if w is not None and m is not None:
                    total = target_w * Fraction(1, 10**6) * scalar(props['m'])
                    if not close(w*m, total):
                        error('TOTAL_MOS_WIDTH_MISMATCH', name, actual_m=float(w*m), expected_m=float(total),
                              target_field=target_field)
            except (ValueError, TypeError, KeyError, SyntaxError, ZeroDivisionError) as exc:
                error('INVALID_MOS_WIDTH_TARGET', name, message=str(exc))
            for key in ('as', 'ad', 'ps', 'pd'):
                if key in p:
                    try:
                        if scalar(p[key]) < 0: raise ValueError('Negative geometry')
                    except (ValueError, SyntaxError, ZeroDivisionError, KeyError) as exc:
                        error('INVALID_DIFFUSION_GEOMETRY', name, parameter=key, value=p[key], message=str(exc))
        elif kind == 'resistor':
            length = check_constant(p, 'l', props['segL'], name)
            check_constant(p, 'w', props['segW'], name)
            check_constant(p, 'm', '1', name, default='1')
            if length is not None:
                if not Fraction(5, 10**7) <= length <= Fraction(1, 10000):
                    error('ILLEGAL_RESISTOR_LENGTH_RANGE', name, actual_m=float(length))
                grid_steps = length / Fraction(5, 10**9)
                if not close(grid_steps, Fraction(round(grid_steps))):
                    error('RESISTOR_OFF_5NM_GRID', name, actual_m=float(length))
        elif kind == 'mim':
            w = check_constant(p, 'w', props['w'], name)
            length = check_constant(p, 'l', props['l'], name)
            check_constant(p, 'm', props['m'], name)
            if w is not None and length is not None and min(w, length) < Fraction(4, 10**6):
                error('MIM_BELOW_SCHOOL_MINIMUM', name, w_m=float(w), l_m=float(length))
        elif kind == 'testbench_resistor':
            check_constant(p, 'r', props['r'], name)
            check_constant(p, 'm', '1', name, default='1')
        elif kind == 'testbench_source':
            if p.get('type', '').strip('"') != 'dc':
                error('SOURCE_TYPE_MISMATCH', name, actual=p.get('type'), expected='dc')
            try:
                got_dc = affine(p['dc']); want_dc = affine(props['dc'])
                if not all(close(a, b) for a, b in zip(got_dc, want_dc)):
                    error('DC_STIMULUS_MISMATCH', name, actual=p['dc'], expected=props['dc'])
            except (ValueError, SyntaxError, KeyError, ZeroDivisionError) as exc:
                error('INVALID_DC_STIMULUS', name, actual=p.get('dc'), message=str(exc))
            check_constant(p, 'mag', props.get('acm', '0'), name, default='0')
            check_constant(p, 'phase', props.get('acp', '0'), name, default='0')
        record = {'name': name, 'originalpath': expected.get('originalpath'),
                  'kind': kind, 'line': got['line'], 'model': got['model'],
                  'terminal_order': order, 'nodes': got['nodes'], 'exported_parameters': p}
        if kind == 'mos': record['width_mapping'] = width_mapping
        result['instances'].append(record)
    result['expected_counts_by_kind'] = dict(Counter(x['kind'] for x in objects))
    result['native_net_count'] = len({n for x in actual.values() for n in x['nodes']})
    result['error_count'] = len(result['errors'])
    if not result['errors']: result['status'] = 'NATIVE_NETLIST_AUDIT_PASS'
    result['limitations'] = ['Source/drain geometry is recorded and required to be nonnegative when exported; physical equivalence is not established.',
                             'MIM multiplier matches requested netlist only; actual capacitance/statistical averaging requires simulation/model evidence.',
                             'No model loading, Spectre success, waveform, stability, noise, PVT, DRC/LVS or parasitic qualification is inferred.']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('netlist', type=Path)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).with_name('native_canary_school_r1_objects.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists(): raise SystemExit('Output already exists; choose a new audit filename to preserve evidence.')
    objects = json.loads(args.manifest.read_text())
    result = audit(objects, args.netlist.read_text())
    result['inputs'] = {str(p): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size_bytes': p.stat().st_size}
                        for p in (args.netlist, args.manifest)}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: result.get(k) for k in ('status', 'expected_count', 'actual_count', 'error_count')}))
    raise SystemExit(0 if result['status'] == 'NATIVE_NETLIST_AUDIT_PASS' else 2)


if __name__ == '__main__':
    main()
