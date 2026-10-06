"""Independent local audit of all saved R5 conditional STB crossings; never simulates."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, re
import numpy as np
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
METHOD = REPO / 'v2/analog/frontend/cadence_20260923/review_stb_results.py'
spec = importlib.util.spec_from_file_location('prior_stb_review', METHOD)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
SOURCES = {}

def track(p):
    p = Path(p).resolve()
    assert REPO in p.parents
    SOURCES[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p.read_text()

def read(p):
    track(p)
    r = prior.parse_spectre_psf_ascii(p)
    assert r.status.value == 'success', str(p)
    return r.data

def crossing_events(f, y):
    """All sign changes plus exact grid zeros, including zero plateaus/tangencies."""
    f = np.asarray(f)
    y = np.asarray(y)
    assert np.all(np.diff(f) > 0) and np.all(f > 0)
    assert np.isfinite(y).all()
    events = []
    i = 0
    while i < len(y):
        if y[i] == 0:
            j = i
            while j + 1 < len(y) and y[j + 1] == 0:
                j += 1
            before = float(np.sign(y[i - 1])) if i > 0 else None
            after = float(np.sign(y[j + 1])) if j + 1 < len(y) else None
            direction = 'descending' if before == 1 and after == -1 else 'ascending' if before == -1 and after == 1 else 'tangent_or_zero_plateau' if before is not None and after is not None else 'endpoint_zero'
            events.append(dict(i=i, j=j, t=0.0, frequency_hz=float(f[i]) if i == j else None, frequency_interval_hz=[float(f[i]), float(f[j])], event='exact_grid_zero' if i == j else 'exact_zero_interval', direction=direction))
            i = j + 1
            continue
        if i + 1 < len(y) and y[i + 1] != 0 and (np.signbit(y[i]) != np.signbit(y[i + 1])):
            t = float(-y[i] / (y[i + 1] - y[i]))
            events.append(dict(i=i, j=i + 1, t=t, frequency_hz=float(np.exp(np.log(f[i]) + t * np.log(f[i + 1] / f[i]))), frequency_interval_hz=[float(f[i]), float(f[i + 1])], event='bracketed_sign_change', direction='descending' if y[i] > 0 else 'ascending'))
        i += 1
    return events

def margin(p):
    body = track(p).split('\nVALUE\n')[1]
    out = {}
    for key in ('gainMargin', 'gainMarginFreq', 'phaseMargin', 'phaseMarginFreq'):
        m = re.search('^"' + key + '" "[^"]+" (\\S+)', body, re.M)
        assert m, (p, key)
        value = float(m[1])
        out[key] = value if math.isfinite(value) else None
    state = re.search('^"stb_state" "stbstate" "([^"]*)"', body, re.M)
    assert state
    out['state_verbatim'] = state[1]
    return out

def cj(x):
    return {'real': float(np.real(x)), 'imag': float(np.imag(x))}

def finite(x):
    return float(x) if math.isfinite(float(x)) else None

def loop_metrics(f, L, native):
    f = np.asarray(f, float)
    L = np.asarray(L, complex)
    assert len(f) == len(L) >= 3 and np.isfinite(L).all()
    assert np.all(np.diff(f) > 0) and np.all(f > 0)
    mag = np.abs(L)
    phase = np.unwrap(np.angle(L)) * 180 / np.pi
    db = np.full(len(f), -np.inf)
    nz = mag > 0
    db[nz] = 20 * np.log10(mag[nz])
    u = []
    for e in crossing_events(f, mag - 1):
        i, j = (e['i'], e['j'])
        t = e['t']
        method = 'exact_sample_or_interval'
        if e['event'] == 'bracketed_sign_change':
            if np.isfinite(db[i]) and np.isfinite(db[j]):
                t = float(-db[i] / (db[j] - db[i]))
                method = 'linear_dB_vs_log_frequency'
            else:
                method = 'linear_magnitude_vs_log_frequency_zero_endpoint'
            e['frequency_hz'] = float(np.exp(np.log(f[i]) + t * np.log(f[j] / f[i])))
            e['t'] = t
        angle = float(phase[i] + t * (phase[j] - phase[i]))
        principal = float((angle + 180) % 360 - 180)
        e.update(interpolation=method, phase_L_unwrapped_deg=angle, phase_L_principal_deg=principal, phase_interval_endpoint_deg=[float(phase[i]), float(phase[j])])
        u.append(e)
    axes = []
    for e in crossing_events(f, L.imag):
        i, j = (e['i'], e['j'])
        t = e['t']
        real = float(L.real[i] + t * (L.real[j] - L.real[i]))
        interval = e['event'] == 'exact_zero_interval'
        range_real = [float(min(L.real[i:j + 1])), float(max(L.real[i:j + 1]))]
        axis = 'positive' if range_real[0] > 0 else 'negative' if range_real[1] < 0 else 'origin_or_axis_sign_change' if interval else 'positive' if real > 0 else 'negative' if real < 0 else 'origin'
        e.update(L_real=real, axis=axis, real_range=range_real, inverse_magnitude_db=finite(-20 * np.log10(abs(real))) if real else None)
        axes.append(e)
    checks = {}
    issues = []

    def match(key, fkey, candidates, valuekey):
        value = native[key]
        freq = native[fkey]
        if value is None or freq is None:
            checks[key] = {'native_available': False, 'observed_candidate_count': len(candidates)}
            if candidates:
                issues.append(key + '_UNAVAILABLE_DESPITE_SAVED_CROSSING')
            if value is not None or freq is not None:
                issues.append(key + '_PARTIAL_NATIVE_RECORD')
            return
        positive = [(k, e) for k, e in enumerate(candidates) if e['frequency_hz'] is not None and e['frequency_hz'] > 0]
        if not positive:
            checks[key] = {'native_available': True, 'match': False}
            issues.append(key + '_NO_OBSERVED_CROSSING')
            return
        k, e = min(positive, key=lambda ke: abs(math.log(ke[1]['frequency_hz'] / freq)))
        delta = e[valuekey] - value if e[valuekey] is not None else None
        if key == 'phaseMargin' and delta is not None:
            delta = (delta + 180) % 360 - 180
        ferr = e['frequency_hz'] / freq - 1
        good = delta is not None and abs(delta) < 0.05 and (abs(ferr) < 0.0005)
        checks[key] = {'native_available': True, 'matched_candidate_index': k, 'native_frequency_hz': freq, 'interpolated_frequency_hz': e['frequency_hz'], 'frequency_relative_difference': ferr, 'value_difference': delta, 'match': good, 'all_candidate_count': len(candidates)}
        if not good:
            issues.append(key + '_NATIVE_INTERPOLATION_DISAGREEMENT')
    match('phaseMargin', 'phaseMarginFreq', u, 'phase_L_principal_deg')
    match('gainMargin', 'gainMarginFreq', [e for e in axes if e['axis'] == 'positive'], 'inverse_magnitude_db')
    point = int(np.argmin(abs(L - 1)))
    best = (float(abs(L[point] - 1)), float(f[point]))
    for i in range(len(L) - 1):
        v = L[i + 1] - L[i]
        if v == 0:
            continue
        t = float(np.clip(np.real((1 - L[i]) * np.conj(v)) / abs(v) ** 2, 0, 1))
        d = float(abs(L[i] + t * v - 1))
        if d < best[0]:
            best = (d, float(np.exp(np.log(f[i]) + t * np.log(f[i + 1] / f[i]))))
    endpoint = {'low': {'f_hz': float(f[0]), 'raw_L': cj(L[0]), 'gain_db': finite(db[0])}, 'high': {'f_hz': float(f[-1]), 'raw_L': cj(L[-1]), 'gain_db': finite(db[-1])}}
    if len(u) > 1:
        issues.append('MULTIPLE_UNITY_CROSSINGS_REQUIRE_REVIEW')
    if any((e['event'] != 'bracketed_sign_change' for e in u)):
        issues.append('EXACT_GRID_UNITY_OR_TANGENCY_PRESENT')
    pm = native['phaseMargin']
    pm_status = 'NOT_AVAILABLE' if pm is None else 'MEETS_NATIVE_CONDITIONAL_PM_TARGET' if pm >= 60 else 'BELOW_NATIVE_CONDITIONAL_PM_TARGET'
    return dict(samples=len(f), range_hz=[float(f[0]), float(f[-1])], maximum_gain_db=finite(max(db)), minimum_gain_db=finite(min(db)), raw_L_endpoints=endpoint, all_observed_unity_crossings=u, all_observed_real_axis_crossings=axes, native_margins=native, native_crosschecks=checks, native_conditional_pm_60deg_status=pm_status, review_flags=issues, zero_magnitude_samples=int(sum(mag == 0)), maximum_saved_phase_increment_deg=float(max(abs(np.diff(phase)))), max_adjacent_frequency_ratio=float(max(f[1:] / f[:-1])), nearest_saved_point_to_raw_critical_plus_one={'distance': float(abs(L[point] - 1)), 'frequency_hz': float(f[point])}, nearest_polyline_chord_to_raw_critical_plus_one={'distance': best[0], 'frequency_hz_approx': best[1]}, crossing_coverage='Every sign change and exact zero on the saved grid is included; unresolved between-point tangent/double crossings and finite-frequency endpoints remain possible.', sign_policy='Exported Spectre L is unchanged. Raw critical point +1; native PM checked against arg(L) at a matching unity crossing, native GM against positive-real crossing. Negative-real crossings also recorded. No ad hoc sign flips.', full_multiloop_stability_pass=False)

def numeric_dict(d):
    out = {}
    skip = {}
    for k, v in d.items():
        a = np.asarray(v)
        if a.dtype.kind in 'iufc':
            assert np.isfinite(a).all(), k
            out[k] = a
        else:
            skip[k] = v
    return (out, skip)

def equivalence(stb, base, gain):
    result = {}
    allok = True
    for mode, ext in [('op', 'dc'), ('ac', 'ac')]:
        filename = f'g{gain}_{mode}.{ext}'
        a, skip_a = numeric_dict(read(base / 'input.raw' / filename))
        b, skip_b = numeric_dict(read(stb / 'input.raw' / filename))
        shared = set(a) & set(b)
        missing = sorted(set(a) - set(b))
        expected_unsaved = [x for x in missing if re.search('\\.msky130_fd_pr__(?:nfet|pfet)_01v8:(?:id|vds|vdsat|region)$', x)]
        assert set(missing) == set(expected_unsaved), (filename, 'Missing unexpected nodes or branch signals', missing)
        assert skip_a == skip_b, (filename, 'metadata mismatch')
        diffs = []
        for key in sorted(shared - {'freq'}):
            assert a[key].shape == b[key].shape, (filename, key)
            diffs.append((float(np.max(abs(a[key] - b[key]))), key))
        nodes = sorted((x for x in diffs if ':' not in x[1]), reverse=True)
        currents = sorted((x for x in diffs if ':' in x[1]), reverse=True)
        assert nodes and currents
        r = {'shared_nodes': len(nodes), 'shared_currents': len(currents), 'baseline_device_op_fields_not_saved_in_stb': expected_unsaved, 'missing_field_policy': 'Explicitly not compared; baseline has additional saved MOS internal operating-point fields. All ordinary baseline nodes and branch signals must still be present.', 'extra_probe_signals': sorted(set(b) - set(a)), 'max_node_abs_difference': {'value': nodes[0][0], 'signal': nodes[0][1]}, 'max_current_abs_difference': {'value': currents[0][0], 'signal': currents[0][1]}, 'excluded_equal_metadata': skip_a}
        if mode == 'op':
            aliases = {'DM_INP': 'XPGA_SUMPOS', 'DM_INN': 'XPGA_SUMNEG', 'CM1_GATE': 'XPGA_XOTA_NCM', 'CM2_GATE': 'XPGA_XOTA_CMG'}
            r['probe_zero_dc_drop_v'] = {k: float(b[k] - b[v]) for k, v in aliases.items()}
            r['selected_nodes'] = {k: {'without_probe_v': float(a[k]), 'with_probe_v': float(b[k]), 'difference_v': float(b[k] - a[k])} for k in ['FP', 'FN', 'OP', 'ON', 'XPGA_XOTA_NCM', 'XPGA_XOTA_CMG', 'XPGA_XOTA_BN']}
            ok = nodes[0][0] < 1e-08 and currents[0][0] < 1e-12 and (max((abs(v) for v in r['probe_zero_dc_drop_v'].values())) < 1e-10)
        else:
            assert a['freq'].shape == b['freq'].shape and np.allclose(a['freq'], b['freq'], rtol=1e-12, atol=0), 'Different AC grids'
            ga = (a['FP'] - a['FN']) / (a['VINP'] - a['VINN'])
            gb = (b['FP'] - b['FN']) / (b['VINP'] - b['VINN'])
            r['diff_gain_max_abs_difference'] = float(max(abs(gb - ga)))
            r['diff_gain_max_relative_difference'] = float(max(abs(gb - ga) / np.maximum(abs(ga), 1e-30)))
            r['samples'] = len(a['freq'])
            r['frequency_range_hz'] = [float(a['freq'][0]), float(a['freq'][-1])]
            ok = r['diff_gain_max_relative_difference'] < 1e-06
        r['status'] = 'PASS_WITHIN_TOLERANCES' if ok else 'FAIL'
        allok &= ok
        result[mode] = r
    return {'status': 'NUMERICAL_EQUIVALENCE_WITHIN_TOLERANCES' if allok else 'FAIL', 'gain': gain, 'results': result, 'limits': {'op_node_v': 1e-08, 'op_current_a': 1e-12, 'probe_zero_dc_drop_v': 1e-10, 'diff_ac_gain_relative': 1e-06}, 'scope': 'Zero-differential DC nodes/branch signals and saved differential AC input only. Baseline-only MOS internal OP fields are explicitly unverified. No independent common-mode excitation or large-signal equivalence inferred.'}

def write_markdown(report, path):
    lines = ['# school_r5_noise three-gain conditional STB review', '', 'Only saved linearized single-probe conditional return ratios are reviewed. **Complete coupled-loop stability has not passed.** Exported L signs and all observed crossings are retained.', '', '| Gain | Channel | All observed unity crossings (Hz) | Native PM (°) | Native GM (dB) | Native status |', '|---:|---|---|---:|---:|---|']
    for gain in (1, 4, 16):
        for name in ('dm', 'input_cm', 'cm1', 'cm2'):
            l = report['loops'][f'g{gain}_{name}']
            n = l['native_margins']
            freqs = ', '.join((f'{e['frequency_hz']:.7g}' if e['frequency_hz'] else str(e['frequency_interval_hz']) for e in l['all_observed_unity_crossings'])) or 'no observed crossing'
            lines.append(f'| {gain} | {name} | {freqs} | {n['phaseMargin']} | {n['gainMargin']} | {n['state_verbatim']} |')
    lines += ['', '## Probe-free control', '']
    for gain in (1, 4, 16):
        eq = report['probe_equivalence'][str(gain)]
        r = eq['results']
        lines.append(f'- Gain {gain}：{eq['status']}; maximum DC node difference {r['op']['max_node_abs_difference']['value']:.3g} V; current difference {r['op']['max_current_abs_difference']['value']:.3g} A; maximum differential AC relative difference {r['ac']['diff_gain_max_relative_difference']:.3g}。')
    lines += ['', '## Scope and incomplete qualification', '', 'The exported L critical point is +1. Positive/negative real-axis crossings are recorded separately; native GM matches the positive axis. All crossings, original brackets, grid spacing and native comparison differences remain in JSON.', '', 'All means observed sign changes, exact zeros/tangencies/zero intervals on the saved grid. A finite scan cannot exclude paired crossings or tangencies between points, and its Nyquist endpoints are not closed. Reference-system RHP modes and full multiport return difference remain unresolved. A single native stable result/PM is not a general coupled-loop proof.', '', 'OP/AC equivalence covers the common saved zero-differential nodes/branches and existing differential AC stimulus for three gains. The probe-free control additionally saved 52 MOS OP fields on 13 devices; STB did not, so internal MOS OP equality is not claimed. PVT, dynamic noise, actual switched load, full coupled return difference and top-level PEX remain outside this report.', '', 'Original failures, warnings, audits and input hashes are preserved. JSON is the primary numeric record.']
    path.write_text('\n'.join(lines) + '\n')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stb-run', type=Path, required=True)
    p.add_argument('--baseline-run', type=Path, required=True)
    p.add_argument('--core-audit', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    assert not a.output.exists(), 'Preserve earlier review'
    SOURCES[str(METHOD.relative_to(REPO))] = hashlib.sha256(METHOD.read_bytes()).hexdigest()
    stb = a.stb_run.resolve()
    base = a.baseline_run.resolve()
    loops = {}
    logs = {}
    for run in (stb, base):
        for n in ('input.scs', 'native_netlist', 'provenance.json', 'completion.json'):
            track(run / n)
        log = track(run / 'spectre.out')
        m = re.findall('spectre completes with (\\d+) errors?, (\\d+) warnings?, and (\\d+) notices?\\.', log, re.I)
        assert m and m[-1][0] == '0'
        logs[run.name] = {'errors': int(m[-1][0]), 'warnings': int(m[-1][1]), 'notices': int(m[-1][2]), 'warning_lines': [l for l in log.splitlines() if re.match('\\s*(?:WARNING\\b|Warning from\\b)', l, re.I)]}
    for gain in (1, 4, 16):
        for name in ('dm', 'input_cm', 'cm1', 'cm2'):
            tag = f'g{gain}_{name}'
            d = read(stb / 'input.raw' / f'{tag}.stb')
            loops[tag] = loop_metrics(d['freq'], d['loopGain'], margin(stb / 'input.raw' / f'{tag}.margin.stb'))
    eq = {str(g): equivalence(stb, base, g) for g in (1, 4, 16)}
    audit = json.loads(track(a.core_audit.resolve())) if a.core_audit else None
    report = dict(status='REAL_THREE_GAIN_FOUR_CONDITIONAL_STB_REVIEW_NOT_MULTILOOP_PASS', scope='school_r5_noise TT/1.8V/27C; fixed acquisition state, zero differential input; gains1/4/16', stb_run=str(stb.relative_to(REPO)), baseline_run=str(base.relative_to(REPO)), loops=loops, probe_equivalence=eq, native_core_audit=audit, spectre_logs=logs, source_sha256=SOURCES, full_multiloop_stability_pass=False, pvt_pass=False, dynamic_noise_pass=False, pex_pass=False)
    a.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    write_markdown(report, a.output.with_suffix('.md'))
    for tag, l in loops.items():
        print(tag, 'crossings', len(l['all_observed_unity_crossings']), 'PM', l['native_margins']['phaseMargin'], 'GM', l['native_margins']['gainMargin'], 'flags', l['review_flags'])
    print('equivalence', {g: e['status'] for g, e in eq.items()})
if __name__ == '__main__':
    main()
