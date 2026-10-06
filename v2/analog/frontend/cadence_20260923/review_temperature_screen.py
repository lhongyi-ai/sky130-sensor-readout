"""Fixed nominal calibration, three real TT temperatures, no remote work."""
from pathlib import Path
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
from review_three_gain import MOS, span
ROOT = REPO / 'v2/cadence/linuxlab_20260923/runs'
RUNS = {-20: ROOT / 'spectre_three_gain_20260923T105727131772Z', 27: ROOT / 'spectre_three_gain_20260923T104459162350Z', 85: ROOT / 'spectre_three_gain_20260923T105736108259Z'}
HASHES = {}

def track(path):
    HASHES[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path.read_text()

def read(path):
    track(path)
    r = parse_spectre_psf_ascii(path)
    assert r.status.value == 'success'
    return r.data

def cj(z):
    return {'real': float(z.real), 'imag': float(z.imag)}

def decompose(data, g):
    a = {k: v[0] if isinstance(v, list) else v for k, v in data.items()}
    assert a['freq'] == 1
    pre = 'XPGA_XFP{}_XSW'.format(g)
    fb_current = -(a[pre + '_XN.msky130_fd_pr__nfet_01v8:d'] + a[pre + '_XP.msky130_fd_pr__pfet_01v8:d'])
    mid = a['XPGA_XFP{}_N'.format(g)]
    ri = (a['IP'] - a['XPGA_SUMPOS']) / a['RSP:1']
    rf = (a['ON'] - mid) / fb_current
    ron = (mid - a['XPGA_SUMPOS']) / fb_current
    A = (a['OP'] - a['ON']) / (a['XPGA_SUMPOS'] - a['XPGA_SUMNEG'])
    K = (rf + ron) / (ri + 350)
    factors = {'resistor_ratio': abs(rf / ri), 'switch_factor': abs(1 + ron / rf), 'source350_factor': abs(1 / (1 + 350 / ri)), 'finite_A_factor': abs(1 / (1 + (1 + K) / A))}
    predicted = K / (1 + (1 + K) / A)
    actual = (a['FP'] - a['FN']) / (a['VINP'] - a['VINN'])
    assert abs(predicted / actual - 1) < 2e-05
    assert abs(np.prod(list(factors.values())) / abs(predicted) - 1) < 1e-12
    return {'frequency_hz': 1, 'Rin_ohm': cj(ri), 'Rfb_ohm': cj(rf), 'Ron_ohm': cj(ron), 'A_core': cj(A), 'factors': factors, 'predicted_gain_abs': abs(predicted), 'actual_gain_abs': abs(actual), 'decomposition_relative_complex_error': abs(predicted / actual - 1)}

def gain_model(ri, rf, ron, A):
    K = (rf + ron) / (ri + 350)
    return K / (1 + (1 + K) / A)

def main():
    output = HERE / 'temperature_screen_r3_independent_review.json'
    if output.exists():
        raise SystemExit('Output exists; preserve evidence and choose a new version.')
    track(Path(__file__))
    spec = json.loads(track(REPO / 'v2/config/spec.json'))
    LSB = spec['spec']['full_scale_vpp'] / 2 ** spec['spec']['bits']
    limit = spec['qualification']['corner_calibration_residual_lsb']
    hold = np.ones(81, dtype=bool)
    hold[[8, 40, 72]] = False
    coeffs = {}
    for g in [1, 4, 16]:
        nom = read(RUNS[27] / 'input.raw' / 'g{}_dc.dc'.format(g))
        target = np.array(nom['SW']) * g / 4
        measured = np.array(nom['FP']) - np.array(nom['FN'])
        coeffs[g] = np.polyfit(measured[[8, 40, 72]], target[[8, 40, 72]], 1)
    temps = {}
    native_sha = None
    normalized_deck = None
    for temp, directory in RUNS.items():
        deck = track(directory / 'input.scs')
        assert re.search('options temp=' + re.escape(str(temp)) + '(?:\\.0)? ', deck)
        normal = re.sub('options temp=[^ ]+', 'options temp=FIXED', deck)
        if normalized_deck is None:
            normalized_deck = normal
        else:
            assert normal == normalized_deck, 'Other simulation inputs differ'
        native = track(directory / 'native_netlist')
        sha = hashlib.sha256(native.encode()).hexdigest()
        if native_sha is None:
            native_sha = sha
        else:
            assert sha == native_sha
        info = read(directory / 'input.raw/dcOpInfo.info')
        d = {'gains': {}, 'rin_bulk_model_res_ohm_at_initial_g4_op': info['XPGA_XRINP_XR.rhrpoly_0p35:res']}
        log = track(directory / 'spectre.out')
        d['errors_warnings_notices'] = re.search('spectre completes with (\\d+) errors?, (\\d+) warnings?, and (\\d+) notices?\\.', log).groups()
        assert d['errors_warnings_notices'][0] == '0'
        d['warning_lines'] = [l.strip() for l in log.splitlines() if 'WARNING (' in l]
        for g in [1, 4, 16]:
            dc = read(directory / 'input.raw' / 'g{}_dc.dc'.format(g))
            ac = read(directory / 'input.raw' / 'g{}_ac.ac'.format(g))
            x = np.array(dc['SW']) * g / 4
            yp = np.array(dc['FP'])
            yn = np.array(dc['FN'])
            y = yp - yn
            assert len(x) == 81 and np.allclose(x, np.linspace(-0.4, 0.4, 81), atol=1e-12, rtol=0)
            assert np.all(np.isfinite(y))
            residual = (coeffs[g][0] * y + coeffs[g][1] - x) / LSB
            i = int(np.flatnonzero(hold)[np.argmax(abs(residual[hold]))])
            devices = {}
            for dev in MOS:
                model = 'pfet_01v8' if dev in ['XMLN', 'XMLP', 'XMSN', 'XMSP'] else 'nfet_01v8'
                pre = 'XPGA_XOTA_' + dev + '.msky130_fd_pr__' + model
                vectors = {k: np.array(dc[pre + ':' + k]) for k in ['vds', 'vdsat', 'id', 'region']}
                for v in vectors.values():
                    assert v.shape == (81,) and np.all(np.isfinite(v))
                margin = abs(vectors['vds']) - abs(vectors['vdsat'])
                j = int(np.argmin(margin))
                regions, counts = np.unique(vectors['region'], return_counts=True)
                devices[dev] = {'min_abs_vds_minus_abs_vdsat_v': float(margin[j]), 'worst_target_v': float(x[j]), 'regions': {str(int(k)): int(n) for k, n in zip(regions, counts)}, 'id_a': span(vectors['id']), 'distinct_vds_values': len(np.unique(vectors['vds']))}
                if dev != 'XBIAS_XDBN':
                    assert devices[dev]['distinct_vds_values'] > 1
            d['gains'][str(g)] = {'max_78_independent_error_lsb': float(abs(residual[i])), 'worst_target_v': float(x[i]), 'fixed27_coefficients': coeffs[g].tolist(), 'meets_4lsb_fixed_calibration_screen': bool(max(abs(residual[hold])) <= limit), 'measured_diff_v': span(y), 'common_mode_v': span((yp + yn) / 2), 'adc_range_exceeded_count': int(np.count_nonzero(abs(y) > 0.4)), 'power_vdd_plus_vcm_dc_w': span(-np.array(dc['VDD']) * np.array(dc['VDD_SRC:p']) - np.array(dc['VCM']) * np.array(dc['VCM:p'])), 'core_mos': devices, 'all_13_region2_all81points': all((v['regions'] == {'2': 81} for v in devices.values())), 'ac_1hz_decomposition': decompose(ac, g), 'all_residuals_lsb': residual.tolist(), 'scope': 'Analog static proxy with fixed acquisition; no ADC codes/noise/quantization or actual ADC bottom-plate switching.'}
        temps[str(temp)] = d
    for temp in [-20, 27, 85]:
        for g in [1, 4, 16]:
            now = temps[str(temp)]['gains'][str(g)]['ac_1hz_decomposition']
            nom = temps['27']['gains'][str(g)]['ac_1hz_decomposition']
            contributions = {k: float(100 * np.log(v / nom['factors'][k])) for k, v in now['factors'].items()}
            now['log_gain_drift_contributions_percent'] = contributions
            now['sum_log_contributions_percent'] = sum(contributions.values())
            now['actual_log_gain_drift_percent'] = float(100 * np.log(now['actual_gain_abs'] / nom['actual_gain_abs']))
    predictions = {}
    for variant, g in [('r4_G1_feedback_TG_times16', 1), ('r5_G16_feedback_TG_half', 16)]:
        values = {}
        for temp in [-20, 27, 85]:
            a = temps[str(temp)]['gains'][str(g)]['ac_1hz_decomposition']
            ri, rf, ron, A = [a[k]['real'] for k in ['Rin_ohm', 'Rfb_ohm', 'Ron_ohm', 'A_core']]
            if g == 1:
                slope = (ri - rf) / (9.105 - 8.895)
                new_rf = rf + slope * (9.4 - 8.895)
                new_ron = ron / 16
            else:
                slope = temps[str(temp)]['rin_bulk_model_res_ohm_at_initial_g4_op'] / 9.105
                new_rf = rf - 2 * 0.24 * slope
                new_ron = 2 * ron
            values[str(temp)] = {'predicted_gain': float(gain_model(ri, new_rf, new_ron, A)), 'model_Rfb_ohm': new_rf, 'model_Ron_ohm': new_ron, 'estimated_bulk_slope_ohm_per_um': slope}
        for temp in [-20, 27, 85]:
            values[str(temp)]['predicted_endpoint_gain_drift_lsb_after_new_nominal_calibration'] = 2048 * (values[str(temp)]['predicted_gain'] / values['27']['predicted_gain'] - 1)
        predictions[variant] = {'status': 'SENSITIVITY_PREDICTION_NOT_A_SIMULATION', 'temperatures': values, 'assumptions': ['Ron inversely proportional to total width across changed geometry and temperatures', 'Core A and Rin unchanged', 'Length sensitivity inferred from existing actual model observations; not CDF r', 'No change in leakage, off branches, noise or parasitic dynamics', 'Only linear gain drift term; no new 81-point curvature, voltage/PVT, mismatch or sampling validation'], 'phase_margin_or_system_pass': False}
    result = {'status': 'TT_THREE_TEMPERATURE_STATIC_SCREEN_FAILED_NOT_FULL_PVT', 'same_native_sha256': native_sha, 'only_deck_temperature_changed': True, 'nominal_calibration_temperature_c': 27, 'calibration_refit_at_other_temperatures': False, 'lsb_v': LSB, 'independent_points_per_gain_temperature': 78, 'temperatures': temps, 'bounded_revision_predictions': predictions, 'decomposition_definition': 'G≈(Rfb/Rin)*(1+Ron/Rfb)/(1+350/Rin)/(1+(1+K)/A), K=(Rfb+Ron)/(Rin+350); reported factor magnitudes and additive 100*ln(T/27) contributions. Algebraic decomposition, not four independent causal interventions.', 'source_resistor_scope': '350ohm is fixed; its contribution changes through Rin(T), not a simulated source resistor temperature coefficient.', 'qualification_45_pvt': False, 'actual_adc_sampling_tg_change_recommended': False, 'hashes': HASHES}
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for temp in [-20, 85]:
        for g in [1, 4, 16]:
            a = temps[str(temp)]['gains'][str(g)]
            print(temp, g, a['max_78_independent_error_lsb'], a['ac_1hz_decomposition']['log_gain_drift_contributions_percent'])
if __name__ == '__main__':
    main()
