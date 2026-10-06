"""Review an explicit real three-gain run against an explicit native manifest."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import numpy as np
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BRIDGE = Path('/path/to/virtuoso-bridge-lite')
sys.path.insert(0, str(BRIDGE / 'src'))
from virtuoso_bridge.spectre.parsers import parse_spectre_psf_ascii
from audit_native_netlist import parse, audit
RUNS = REPO / 'v2/cadence/linuxlab_20260923/runs'
RUN = RUNS / 'spectre_three_gain_20260923T103824323219Z'
BASE = RUNS / 'spectre_canary_20260923T100631141401Z'
SOURCES = {}
MOS = ['XBIAS_XDBN', 'XCMR', 'XCMS', 'XCMT', 'XMIN', 'XMIP', 'XMLN', 'XMLP', 'XMON', 'XMOP', 'XMSN', 'XMSP', 'XMTAIL']

def track(path):
    SOURCES[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path.read_text()

def read(path):
    track(path)
    result = parse_spectre_psf_ascii(path)
    assert result.status.value == 'success'
    return result.data

def span(x):
    return {'min': float(np.min(x)), 'max': float(np.max(x))}

def feedback_switches(dc, gain, target):
    """Use actual DC terminal currents, not the CDF resistance annotation.

    This V/I is a large-signal effective resistance at each operating point,
    not small-signal ron. Ignore divisions below 1nA and retain their indices.
    """
    results = {}
    arrays = {}
    for leg, summing, output, sensor, input_r in [('P', 'XPGA_SUMPOS', 'ON', 'IP', 'RSP:1'), ('N', 'XPGA_SUMNEG', 'OP', 'IN', 'RSN:1')]:
        prefix = 'XPGA_XF{}{}_XSW'.format(leg, gain)
        keys = [prefix + '_XN.msky130_fd_pr__nfet_01v8:d', prefix + '_XP.msky130_fd_pr__pfet_01v8:d']
        i = -sum((np.array(dc[k]) for k in keys))
        valid = abs(i) >= 1e-09
        mid = np.array(dc['XPGA_XF{}{}_N'.format(leg, gain)])
        drop = mid - np.array(dc[summing])
        ron = np.divide(drop, i, out=np.zeros_like(i), where=valid)
        rfb = np.divide(np.array(dc[output]) - mid, i, out=np.zeros_like(i), where=valid)
        assert np.all(ron[valid] > 0) and np.all(rfb[valid] > 0)
        arrays[leg] = (ron, valid)
        selected = []
        for j in [0, 8, 20, 40, 60, 72, 80]:
            selected.append({'target_v': float(target[j]), 'feedback_current_a': float(i[j]), 'ron_ohm': float(ron[j]) if valid[j] else None, 'actual_feedback_resistor_v_over_i_ohm': float(rfb[j]) if valid[j] else None})
        zero_rin = (dc[sensor][40] - dc[summing][40]) / dc[input_r][40]
        results[leg] = {'method': '(intermediate minus summing voltage) / negative sum of actual NMOS and PMOS drain currents', 'feedback_current_a': span(i), 'ron_dc_ohm': span(ron[valid]), 'feedback_resistor_dc_ohm': span(rfb[valid]), 'excluded_abs_current_below_1na_indices': np.flatnonzero(~valid).tolist(), 'selected_points': selected, 'zero_input_rin_dc_ohm': float(zero_rin), 'zero_input_ron_fraction_of_feedback_path': float(ron[40] / (ron[40] + rfb[40])) if valid[40] else None}
    valid_pair = arrays['P'][1] & arrays['N'][1]
    mean_ron = (arrays['P'][0] + arrays['N'][0]) / 2
    results['paired_mean_ron_dc_ohm'] = span(mean_ron[valid_pair])
    results['paired_zero_ron_dc_ohm'] = float(mean_ron[40]) if valid_pair[40] else None
    results['paired_endpoint_ron_dc_ohm'] = [float(mean_ron[0]), float(mean_ron[-1])]
    results['interpretation'] = 'Opposite leg trends cancel part of the first-order signal dependence. Correlation with residual curvature is not exclusive causal attribution; resistors and amplifier operating points also vary. No PVT was run.'
    return results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    global RUN
    RUN = args.run.resolve()
    args.manifest = args.manifest.resolve()
    args.output = args.output.resolve()
    if args.output.exists():
        raise SystemExit('Output exists; select a new file to retain evidence.')
    SOURCES[str(Path(__file__).resolve().relative_to(REPO))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = json.loads(track(args.manifest))
    native_audit = audit(manifest, track(RUN / 'native_netlist'))
    assert native_audit['status'] == 'NATIVE_NETLIST_AUDIT_PASS', native_audit['errors']
    spec = json.loads(track(REPO / 'v2/config/spec.json'))
    fs = spec['spec']['full_scale_vpp']
    bits = spec['spec']['bits']
    lsb = fs / 2 ** bits
    limit = spec['qualification']['nominal_calibration_residual_lsb']
    native, _ = parse(track(RUN / 'native_netlist'))
    original, _ = parse(track(BASE / 'native_netlist'))
    assert set(native) == set(original) and len(native) == 133
    changes = {}
    for name in original:
        for field in ['nodes', 'model', 'parameters']:
            if native[name][field] != original[name][field]:
                changes.setdefault(name, {})[field] = {'before': original[name][field], 'after': native[name][field]}
    base_op = read(BASE / 'input.raw/dcOp.dc')
    inp = track(RUN / 'input.scs')
    report = {}
    for gain in [1, 4, 16]:
        dc = read(RUN / 'input.raw' / 'g{}_dc.dc'.format(gain))
        op = read(RUN / 'input.raw' / 'g{}_op.dc'.format(gain))
        ac = read(RUN / 'input.raw' / 'g{}_ac.ac'.format(gain))
        x = np.array(dc['SW']) * gain / 4
        assert len(x) == 81 and np.allclose(x, np.linspace(-fs / 2, fs / 2, 81), atol=1e-12, rtol=0)
        assert np.all(np.diff(x) > 0)
        yp, yn = (np.array(dc['FP']), np.array(dc['FN']))
        hp, hn = (np.array(dc['HP']), np.array(dc['HN']))
        y = yp - yn
        cm = (yp + yn) / 2
        assert np.allclose((np.array(dc['VINP']) - np.array(dc['VINN'])) * gain, x, atol=1e-12, rtol=0)
        for v in [yp, yn, hp, hn]:
            assert np.all(np.isfinite(v))
        fit_idx = np.array([8, 40, 72])
        hold = np.ones(81, dtype=bool)
        hold[fit_idx] = False
        assert np.allclose(x[fit_idx], [-0.32, 0, 0.32], atol=1e-12, rtol=0)
        coeff = np.polyfit(y[fit_idx], x[fit_idx], 1)
        residual = (coeff[0] * y + coeff[1] - x) / lsb
        worst = int(np.flatnonzero(hold)[np.argmax(abs(residual[hold]))])
        outside = np.flatnonzero(abs(y) > fs / 2)
        slope = np.diff(y) / np.diff(x)
        devices = {}
        for dev in MOS:
            model = 'pfet_01v8' if dev in ['XMLN', 'XMLP', 'XMSN', 'XMSP'] else 'nfet_01v8'
            prefix = 'XPGA_XOTA_' + dev + '.msky130_fd_pr__' + model
            vectors = {}
            for name in ['id', 'vds', 'vdsat', 'region']:
                key = prefix + ':' + name
                assert key in inp, 'Missing explicit saved device vector: ' + key
                vectors[name] = np.array(dc[key])
                assert vectors[name].shape == (81,) and np.all(np.isfinite(vectors[name]))
            margin = abs(vectors['vds']) - abs(vectors['vdsat'])
            idx = int(np.argmin(margin))
            reg, counts = np.unique(vectors['region'], return_counts=True)
            distinct = {k: len(np.unique(v)) for k, v in vectors.items()}
            if dev != 'XBIAS_XDBN':
                assert distinct['vds'] > 1
            devices[dev] = {'min_abs_vds_minus_abs_vdsat_v': float(margin[idx]), 'worst_target_v': float(x[idx]), 'zero_input_margin_v': float(margin[40]), 'region_counts': {str(int(r)): int(n) for r, n in zip(reg, counts)}, 'id_a': span(vectors['id']), 'vds_v': span(vectors['vds']), 'vdsat_v': span(vectors['vdsat']), 'distinct_values': distinct, 'bias_diode': dev == 'XBIAS_XDBN'}
        supply = {}
        for inst, node in [('VDD_SRC', 'VDD'), ('VCM', 'VCM'), ('VSEL0', 'SEL0'), ('VSEL1', 'SEL1'), ('VACQ', 'ACQ'), ('VACQB', 'ACQB'), ('VINP', 'VINP'), ('VINN', 'VINN')]:
            supply[inst] = -np.array(dc[node]) * np.array(dc[inst + ':p'])
        frontend = supply['VDD_SRC'] + supply['VCM']
        positive_frontend = np.maximum(supply['VDD_SRC'], 0) + np.maximum(supply['VCM'], 0)
        source_gain = (np.array(ac['FP']) - np.array(ac['FN'])) / (np.array(ac['VINP']) - np.array(ac['VINN']))
        ac_selected = {}
        for f in [1.0, 1000.0]:
            i = int(np.argmin(abs(np.array(ac['freq']) - f)))
            assert abs(ac['freq'][i] / f - 1) < 1e-10
            ac_selected[str(int(f))] = {'gain_abs': float(abs(source_gain[i])), 'gain_real': float(source_gain[i].real), 'gain_imag': float(source_gain[i].imag)}
        report[str(gain)] = {'samples': 81, 'calibration_samples': 3, 'independent_samples': 78, 'sensor_input_differential_range_v': span(x / gain), 'target_adc_referred_range_v': span(x), 'calibration': {'model': 'target_v = a * measured_frontend_differential_v + b', 'fit_indices': fit_idx.tolist(), 'fit_target_v': x[fit_idx].tolist(), 'coefficients_a_b': coeff.tolist(), 'max_independent_residual_lsb': float(abs(residual[worst])), 'worst_target_v': float(x[worst]), 'worst_measured_v': float(y[worst]), 'nominal_analog_residual_le_1lsb': bool(max(abs(residual[hold])) <= limit), 'scope': 'No ADC codes, noise, averaging or quantization. This is analog DC curvature diagnosis only, not full-chain calibration acceptance.'}, 'output_differential_v': span(y), 'output_common_mode_v': span(cm), 'FP_v': span(yp), 'FN_v': span(yn), 'HP_minus_HN_v': span(hp - hn), 'adc_differential_range_exceeded': {'count': len(outside), 'points': [{'index': int(i), 'target_v': float(x[i]), 'measured_v': float(y[i])} for i in outside], 'consequence': 'Actual ADC clipping cannot be undone by linear calibration; no ADC conversion is simulated here.'}, 'minimum_normalized_static_slope': float(min(slope)), 'maximum_normalized_static_slope': float(max(slope)), 'monotonic_analog_dc': bool(np.all(np.diff(y) > 0)), 'core_mos': devices, 'all_13_mos_saturated_region2_at_81_points': all((v['region_counts'] == {'2': 81} for v in devices.values())), 'power': {'frontend_vdd_plus_vcm_signed_w': span(frontend), 'frontend_positive_delivered_without_credit_for_absorption_w': span(positive_frontend), 'each_ideal_voltage_source_delivered_w': {k: span(v) for k, v in supply.items()}, 'scope': 'DC front end only, including VCM net supply. Control/source stimulus power reported separately; no ADC, periodic switching or complete chip-core power claim.'}, 'ac_gain': ac_selected, 'feedback_switch_static_diagnosis': feedback_switches(dc, gain, x), 'zero_input_op': {k: op[k] for k in ['FP', 'FN', 'XPGA_XOTA_BN', 'XPGA_XOTA_CMG', 'XPGA_XOTA_CTAIL']}, 'pointwise': {'target_v': x.tolist(), 'frontend_diff_v': y.tolist(), 'frontend_cm_v': cm.tolist(), 'calibrated_residual_lsb': residual.tolist(), 'independent_mask': hold.tolist()}}
    base_cm = (base_op['FP'] + base_op['FN']) / 2
    new_cm = (report['4']['zero_input_op']['FP'] + report['4']['zero_input_op']['FN']) / 2
    mapped_cmt = next((o for o in manifest if o['name'] == 'XPGA_XOTA_XCMT'))
    mapped_w = float(mapped_cmt.get('mapped_parameters', mapped_cmt['source_parameters'])['W'])
    derivative = (new_cm - base_cm) / (mapped_w - 8) if mapped_w != 8 else None
    secant_w = 8 + (0.9 - base_cm) / derivative if derivative else None
    only_cmt = set(changes) == {'XPGA_XOTA_XCMT'}
    log = track(RUN / 'spectre.out')
    track(RUN / 'completion.json')
    track(RUN / 'provenance.json')
    status = re.search('spectre completes with (\\d+) errors?, (\\d+) warnings?, and (\\d+) notices?\\.', log).groups()
    assert status[0] == '0'
    result = {'status': 'REAL_THREE_GAIN_DC_ANALYZED_NOT_M2_PASS', 'scope': args.label + ', TT 1.8V 27C fixed acquisition, 350ohm per sensor leg', 'lsb_v': lsb, 'spec_unchanged': True, 'gains': report, 'r1_to_current_native_changes': changes, 'native_audit': {'status': native_audit['status'], 'expected_count': native_audit['expected_count'], 'actual_count': native_audit['actual_count'], 'errors': native_audit['errors']}, 'causal_diagnostic': {'only_cmt_changed': only_cmt, 'width_um': [8, mapped_w], 'associated_diffusion_geometry_also_changed': True, 'g4_cm_v': [base_cm, new_cm], 'apparent_secant_cm_change_v_per_um': derivative, 'secant_width_for_cm_0p9v_um_only_if_one_changed_instance': secant_w if only_cmt else None, 'interpretation': 'Single-CMT geometry change supports a controlled nominal comparison only when only_cmt_changed=true; if other feedback devices changed, the observed CM change has multiple changed inputs and is not an isolated CMT causal measurement.'}, 'spectre_errors_warnings_notices': status, 'formal_stability_pass': False, 'system_calibration_pass': False, 'sampled_noise_pass': False, 'pvt_45_pass': False, 'source_sha256': SOURCES}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for gain, value in report.items():
        print('gain', gain, 'holdout_lsb', value['calibration']['max_independent_residual_lsb'], 'outside_adc_range', value['adc_differential_range_exceeded']['count'], '13_mos_region2', value['all_13_mos_saturated_region2_at_81_points'])
    print('Isolated CM-width secant estimate um', secant_w if only_cmt else 'N/A: other devices changed')
if __name__ == '__main__':
    main()
