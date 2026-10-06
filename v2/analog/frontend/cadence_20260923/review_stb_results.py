"""Offline audit of four fixed real Spectre STB outputs and probe equivalence."""
from pathlib import Path
import hashlib
import json
import math
import re
import sys
import numpy as np
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BRIDGE = Path('/path/to/virtuoso-bridge-lite')
sys.path.insert(0, str(BRIDGE / 'src'))
from virtuoso_bridge.spectre.parsers import parse_spectre_psf_ascii
ROOT = REPO / 'v2/cadence/linuxlab_20260923/runs'
BASE = ROOT / 'spectre_canary_20260923T100631141401Z'
STB = ROOT / 'spectre_stb_20260923T102355388855Z'
ICM = ROOT / 'spectre_stb_input_cm_20260923T102452043895Z'
SOURCES = {}

def track(path):
    SOURCES[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path.read_text()

def read(path):
    track(path)
    data = parse_spectre_psf_ascii(path)
    assert data.status.value == 'success', str(path)
    return data.data

def cj(v):
    return {'real': float(np.real(v)), 'imag': float(np.imag(v))}

def margin(path):
    body = track(path).split('\nVALUE\n')[1]
    out = {}
    for key in ['gainMargin', 'gainMarginFreq', 'phaseMargin', 'phaseMarginFreq']:
        m = re.search('^"' + key + '" "[^"]+" (\\S+)', body, re.M)
        assert m, (path, key)
        value = float(m.group(1))
        out[key] = value if math.isfinite(value) else None
    out['state_verbatim_from_simulator'] = re.search('^"stb_state" "stbstate" "([^"]*)"', body, re.M).group(1)
    return out

def interpolate_frequency(f, i, t):
    return float(np.exp(np.log(f[i]) + t * np.log(f[i + 1] / f[i])))

def analyze_loop(directory, name):
    a = read(directory / 'input.raw' / ('stb_' + name + '.stb'))
    f, L = (np.array(a['freq']), np.array(a['loopGain']))
    assert len(f) == 1401 and f[0] == 0.01 and (abs(f[-1] / 1000000000000.0 - 1) < 1e-10)
    assert np.all(np.diff(f) > 0) and np.all(np.isfinite(L))
    dB = 20 * np.log10(abs(L))
    phase = np.unwrap(np.angle(L)) * 180 / np.pi
    assert not np.any(dB == 0), 'Exact grid unity needs a separate edge rule'
    assert not np.any(L.imag == 0), 'Exact grid real-axis crossing needs a separate edge rule'
    crosses = []
    for i in np.flatnonzero(dB[:-1] * dB[1:] < 0):
        t = -dB[i] / (dB[i + 1] - dB[i])
        angle = float(phase[i] + t * (phase[i + 1] - phase[i]))
        crosses.append({'frequency_hz': interpolate_frequency(f, i, t), 'phase_L_unwrapped_deg': angle, 'phase_L_principal_deg': (angle + 180) % 360 - 180, 'direction': 'descending' if dB[i + 1] < dB[i] else 'ascending', 'bracket_hz': [float(f[i]), float(f[i + 1])]})
    real_crosses = []
    for i in np.flatnonzero(L.imag[:-1] * L.imag[1:] < 0):
        t = -L.imag[i] / (L.imag[i + 1] - L.imag[i])
        real = float(L.real[i] + t * (L.real[i + 1] - L.real[i]))
        real_crosses.append({'frequency_hz': interpolate_frequency(f, i, t), 'L_real': real, 'axis': 'positive' if real > 0 else 'negative', 'inverse_magnitude_db': float(-20 * np.log10(abs(real))), 'bracket_hz': [float(f[i]), float(f[i + 1])]})
    native = margin(directory / 'input.raw' / ('stb_' + name + '.margin.stb'))
    checks = {}
    if native['phaseMargin'] is not None:
        assert len(crosses) == 1
        checks['pm_difference_deg'] = crosses[0]['phase_L_principal_deg'] - native['phaseMargin']
        checks['pm_frequency_relative_difference'] = crosses[0]['frequency_hz'] / native['phaseMarginFreq'] - 1
        assert abs(checks['pm_difference_deg']) < 0.002
        assert abs(checks['pm_frequency_relative_difference']) < 1e-05
    else:
        assert not crosses and np.max(dB) < 0
    if native['gainMargin'] is not None:
        nearest = min(real_crosses, key=lambda x: abs(math.log(x['frequency_hz'] / native['gainMarginFreq'])))
        assert nearest['axis'] == 'positive'
        checks['gm_difference_db'] = nearest['inverse_magnitude_db'] - native['gainMargin']
        checks['gm_frequency_relative_difference'] = nearest['frequency_hz'] / native['gainMarginFreq'] - 1
        assert abs(checks['gm_difference_db']) < 0.002
        assert abs(checks['gm_frequency_relative_difference']) < 0.0001
    return {'samples': len(f), 'range_hz': [float(f[0]), float(f[-1])], 'raw_loop_gain_first': cj(L[0]), 'raw_loop_gain_last': cj(L[-1]), 'maximum_gain_db': float(max(dB)), 'minimum_gain_db': float(min(dB)), 'all_observed_unity_crossings': crosses, 'all_observed_real_axis_crossings': real_crosses, 'native_margins': native, 'native_interpolation_crosschecks': checks, 'sampling_limitation': 'All sign-changing crossings on the saved 100 points/decade grid; does not certify absence of an unsampled tangent or pair of crossings.', 'formal_multiloop_pass': False}

def equivalence(directory, baseline):
    values = {}
    for fname in ['dcOp.dc', 'ac.ac']:
        a = baseline[fname]
        b = read(directory / 'input.raw' / fname)
        shared = set(a) & set(b)
        if fname == 'ac.ac':
            assert a['freq'] == b['freq'] and len(a['freq']) == 161
        errors = []
        skipped_metadata = {}
        for key in shared - {'freq'}:
            av, bv = (np.asarray(a[key]), np.asarray(b[key]))
            if av.dtype.kind not in 'iufc' or bv.dtype.kind not in 'iufc':
                assert key == 'units' and a[key] == b[key]
                skipped_metadata[key] = a[key]
                continue
            assert av.shape == bv.shape
            assert np.all(np.isfinite(av)) and np.all(np.isfinite(bv))
            delta = float(np.max(abs(av - bv)))
            errors.append((delta, key))
        nodes = sorted([x for x in errors if ':' not in x[1]], reverse=True)
        currents = sorted([x for x in errors if ':' in x[1]], reverse=True)
        assert nodes and currents
        entry = {'shared_node_voltage_count': len(nodes), 'shared_current_count': len(currents), 'excluded_parser_metadata': skipped_metadata, 'max_node_voltage_difference': {'abs': nodes[0][0], 'signal': nodes[0][1]}, 'max_current_difference': {'abs': currents[0][0], 'signal': currents[0][1]}}
        if fname == 'dcOp.dc':
            entry['selected_nodes'] = {k: {'baseline_v': a[k], 'with_probe_v': b[k], 'difference_v': b[k] - a[k]} for k in ['FP', 'FN', 'XPGA_XOTA_NCM', 'XPGA_XOTA_CMG', 'XPGA_XOTA_BN']}
            assert nodes[0][0] < 1e-08 and currents[0][0] < 1e-12
            aliases = {'DM_INP': 'XPGA_SUMPOS', 'DM_INN': 'XPGA_SUMNEG', 'CM1_GATE': 'XPGA_XOTA_NCM', 'CM2_GATE': 'XPGA_XOTA_CMG'}
            entry['probe_zero_dc_drop_v'] = {k: b[k] - b[v] for k, v in aliases.items()}
            assert max((abs(v) for v in entry['probe_zero_dc_drop_v'].values())) < 1e-10
        else:
            ga = (np.array(a['FP']) - np.array(a['FN'])) / (np.array(a['VINP']) - np.array(a['VINN']))
            gb = (np.array(b['FP']) - np.array(b['FN'])) / (np.array(b['VINP']) - np.array(b['VINN']))
            entry['diff_gain_max_abs_difference'] = float(max(abs(gb - ga)))
            entry['diff_gain_max_relative_difference'] = float(max(abs(gb - ga) / abs(ga)))
            entry['frequency_range_hz'] = [a['freq'][0], a['freq'][-1]]
            assert entry['diff_gain_max_relative_difference'] < 1e-06
            entry['limitation'] = 'Saved complex AC values are rounded to about six significant digits; this check does not demand bitwise identical underlying solutions.'
        values[fname] = entry
    return {'status': 'NUMERICAL_EQUIVALENCE_WITHIN_REPORTED_TOLERANCES', 'results': values, 'limits': {'op_node_abs_v': 1e-08, 'op_current_abs_a': 1e-12, 'diff_ac_gain_relative': 1e-06}, 'scope': 'Zero differential OP and original differential AC excitation only; no independent common-mode AC excitation or large-signal equivalence claimed.'}

def main():
    baseline = {name: read(BASE / 'input.raw' / name) for name in ['dcOp.dc', 'ac.ac']}
    eq = {d.name: equivalence(d, baseline) for d in [STB, ICM]}
    loops = {n: analyze_loop(STB, n) for n in ['dm', 'cm1', 'cm2']}
    loops['input_cm'] = analyze_loop(ICM, 'input_cm')
    logs = {}
    for d in [BASE, STB, ICM]:
        for name in ['input.scs', 'native_netlist', 'provenance.json']:
            track(d / name)
        raw = track(d / 'spectre.out')
        logs[d.name] = re.search('spectre completes with (\\d+) errors?, (\\d+) warnings?, and (\\d+) notices?\\.', raw).groups()
        assert logs[d.name][0] == '0'
    result = {'status': 'REAL_SPECTRE_FOUR_CONDITIONAL_LOOPS_REVIEWED_NOT_M2_PASS', 'data_policy': 'Each named raw PSF analysis separately read; margin nan parsed as null, never as a passing value.', 'scope': 'School_r1 TT 1.8V 27C gain4 zero input fixed acquisition; new physical MIM bank geometry', 'sign_convention': 'Raw exported L retained. Native PM matches arg(L) at these three unity crossings; native GM matches positive-real L crossing. Equivalent T=-L puts the critical point at T=-1, but no per-loop ad hoc sign flip is allowed.', 'loops': loops, 'probe_equivalence': eq, 'spectre_errors_warnings_notices': logs, 'formal_multiloop_stability_pass': False, 'sampled_noise_pass': False, 'pvt_45_pass': False, 'source_sha256': SOURCES}
    dest = HERE / 'stb_results_independent_review.json'
    dest.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for name, loop in loops.items():
        print(name, 'unity_crossings=' + str(len(loop['all_observed_unity_crossings'])), 'native_pm=' + str(loop['native_margins']['phaseMargin']), 'native_gm=' + str(loop['native_margins']['gainMargin']))
    print(result['status'])
if __name__ == '__main__':
    main()
