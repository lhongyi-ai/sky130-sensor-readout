#!/usr/bin/env python3
"""Strict reader for the real Spectre PSFASCII noise STRUCT format observed here.

Scalar out is V/sqrt(Hz); every STRUCT member is V^2/Hz. Device totals are
checked against member sums and against out squared, never counted twice.
"""
import re
import numpy as np


def parse_noise(text):
    types, remain = text.split('\nTYPE\n', 1)[1].split('\nSWEEP\n', 1)
    if not re.search(r'"V/sqrt\(Hz\)" FLOAT DOUBLE PROP\(\n"units" "V/sqrt\(Hz\)"', types):
        raise ValueError('Missing explicit ASD unit declaration')
    structures = {}
    for name, body in re.findall(r'"([^\"]+)" STRUCT\(\n(.*?)\n\) PROP\(', types, re.S):
        fields = re.findall(r'^"([^\"]+)" FLOAT DOUBLE PROP\(\n"units" "([^\"]+)"\n\)', body, re.M)
        if not fields or any(unit != 'V^2/Hz' for _, unit in fields):
            raise ValueError('Unsupported STRUCT units or fields: '+name)
        structures[name] = [field for field, _ in fields]
        if 'total' not in structures[name] or len(set(structures[name])) != len(structures[name]):
            raise ValueError('Missing/duplicate total field: '+name)
    traces, values = remain.split('\nTRACE\n', 1)[1].split('\nVALUE\n', 1)
    trace_types = dict(re.findall(r'^"([^\"]+)" "([^\"]+)"$', traces, re.M))
    if trace_types.pop('out', None) != 'V/sqrt(Hz)':
        raise ValueError('out must be V/sqrt(Hz)')
    if any(t not in structures for t in trace_types.values()):
        raise ValueError('Unsupported trace type')
    rows = {name: [] for name in trace_types}; out = []; frequencies = []
    blocks = re.split(r'^"freq" ', values, flags=re.M)[1:]
    for block in blocks:
        frequency, rest = block.split('\n', 1)
        frequencies.append(float(frequency))
        found = re.findall(r'^"([^\"]+)" \(\n(.*?)\n\)', rest, re.M | re.S)
        if len(found) != len(rows) or {x[0] for x in found} != set(rows):
            raise ValueError('Missing, duplicate or unexpected trace in frequency block')
        for name, body in found:
            vals = [float(v) for v in body.split()]
            if len(vals) != len(structures[trace_types[name]]):
                raise ValueError('STRUCT value count mismatch: '+name)
            rows[name].append(vals)
        scalar = re.findall(r'^"out" (\S+)$', rest, re.M)
        if len(scalar) != 1: raise ValueError('Missing/duplicate out value')
        out.append(float(scalar[0]))
    f = np.array(frequencies); output = np.array(out)
    if not len(f) or not np.all(np.diff(f)>0) or not np.all(np.isfinite(output)) or np.any(output<0):
        raise ValueError('Invalid frequency or output data')
    devices = {}; total = np.zeros_like(output)
    max_member_error = 0.
    for name, rows_for_device in rows.items():
        values = np.array(rows_for_device)
        if not np.all(np.isfinite(values)): raise ValueError('Nonfinite device PSD')
        fields = structures[trace_types[name]]
        device = {field: values[:, i] for i, field in enumerate(fields)}
        member_sum = sum(v for field,v in device.items() if field != 'total')
        error = float(np.max(abs(member_sum-device['total'])/np.maximum(abs(device['total']),1e-200)))
        if error > 1e-8: raise ValueError('Device PSD members disagree with total: '+name)
        max_member_error = max(error, max_member_error)
        devices[name] = device; total += device['total']
    closure_error = float(np.max(abs(total-output**2)/np.maximum(output**2,1e-200)))
    if closure_error > 1e-8: raise ValueError('Device total sum disagrees with out squared')
    return {'frequency': f, 'out_asd': output, 'devices': devices,
            'max_member_sum_relative_error': max_member_error,
            'max_all_devices_vs_out_squared_relative_error': closure_error}


def integrate_psd(f, psd, low, high):
    if not f[0] <= low < high <= f[-1]: raise ValueError('Band outside saved range')
    inside = (f>low)&(f<high)
    x = np.r_[low,f[inside],high]
    y = np.r_[np.interp(low,f,psd),psd[inside],np.interp(high,f,psd)]
    # This same linear PSD/frequency integration preserves contribution sums.
    return float(np.trapezoid(y,x))
