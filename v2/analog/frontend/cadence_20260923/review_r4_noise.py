"""Independent static-noise budget and retained r4 temperature/range evidence."""
from pathlib import Path
import hashlib
import json
import re
import sys
import numpy as np
from parse_noise_psf import parse_noise, integrate_psd
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BRIDGE = Path('/path/to/virtuoso-bridge-lite')
sys.path.insert(0, str(BRIDGE / 'src'))
from virtuoso_bridge.spectre.parsers import parse_spectre_psf_ascii
ROOT = REPO / 'v2/cadence/linuxlab_20260923/runs'
NOISE = ROOT / 'spectre_noise_screen_20260923T110907590483Z'
STATIC = {27: ROOT / 'spectre_three_gain_20260923T110840899589Z', -20: ROOT / 'spectre_three_gain_20260923T110850521882Z', 85: ROOT / 'spectre_three_gain_20260923T110859261509Z'}
BANDS = {'1Hz_50kHz': (1.0, 50000.0), 'one_fft_bin_50kHz': (100000 / 16384, 50000.0), '1Hz_100MHz': (1.0, 100000000.0)}
HASHES = {}

def track(p):
    HASHES[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p.read_text()

def read(p):
    track(p)
    r = parse_spectre_psf_ascii(p)
    assert r.status.value == 'success'
    return r.data

def main():
    output = HERE / 'r4_noise_and_temperature_independent_review.json'
    if output.exists():
        raise SystemExit('Output exists; preserve earlier evidence.')
    for p in [Path(__file__), HERE / 'parse_noise_psf.py', HERE / 'test_noise_psf.py']:
        track(p.resolve())
    spec = json.loads(track(REPO / 'v2/config/spec.json'))
    lsb = spec['spec']['full_scale_vpp'] / 2 ** spec['spec']['bits']
    srms = spec['spec']['full_scale_vpp'] / 2 * 10 ** (-1 / 20) / np.sqrt(2)
    budget = srms / 10 ** (spec['qualification']['nominal_sndr_db'] / 20)
    results = {}
    for gain in [1, 4, 16]:
        for stage in ['front', 'track']:
            p = NOISE / 'input.raw' / 'g{}_{}.noise'.format(gain, stage)
            d = parse_noise(track(p))
            f = d['frequency']
            outpsd = d['out_asd'] ** 2
            assert len(f) == 401 and f[0] == 1 and (f[-1] == 100000000.0)
            bands = {}
            for label, (low, high) in BANDS.items():
                I = lambda v: integrate_psd(f, v, low, high)
                total = I(outpsd)
                all_sources = {n: I(v['total']) for n, v in d['devices'].items()}
                assert abs(sum(all_sources.values()) / total - 1) < 1e-10
                mechanisms = {}
                for n, z in d['devices'].items():
                    for key, v in z.items():
                        if key != 'total':
                            mechanisms[key] = mechanisms.get(key, 0) + I(v)
                top = [{'source': n, 'output_variance_v2': v, 'percent_total_variance': 100 * v / total, 'individual_output_rms_v': np.sqrt(max(0, v))} for n, v in sorted(all_sources.items(), key=lambda a: a[1], reverse=True)[:20]]
                input_fn = sum((I(z['fn']) for n, z in d['devices'].items() if any((n.startswith('XPGA_XOTA_' + k + '.') for k in ['XMIP', 'XMIN']))))
                load_fn = sum((I(z['fn']) for n, z in d['devices'].items() if any((n.startswith('XPGA_XOTA_' + k + '.') for k in ['XMLP', 'XMLN']))))
                other = total - input_fn - load_fn
                scaled = other + input_fn / 16 + load_fn / 4
                bands[label] = {'low_hz': low, 'high_hz': high, 'output_variance_v2': total, 'output_rms_v': np.sqrt(total), 'top20_sources': top, 'mechanism_variance_v2': mechanisms, 'mechanism_percent_total_variance': {k: 100 * v / total for k, v in mechanisms.items()}, 'noise_only_sine_to_rms_ratio_db_not_SNDR': 20 * np.log10(srms / np.sqrt(total)), 'r5_area_sensitivity_NOT_SIMULATED': {'input_pair_fn_variance_v2': input_fn, 'pmos_load_pair_fn_variance_v2': load_fn, 'other_variance_frozen_v2': other, 'conditional_floor_if_only_these_four_fn_removed_rms_v': np.sqrt(other), 'conditional_area16_input_area4_load_estimated_rms_v': np.sqrt(scaled), 'conditional_remaining_total_noise_error_budget_rms_v': np.sqrt(max(0, budget ** 2 - scaled)), 'assumptions': 'All transfer functions, bias, thermal/other components unchanged; selected flicker PSD scales inversely with area. Not a true bound for a changed circuit.'}}
            results['g{}_{}'.format(gain, stage)] = {'output': 'FP-FN' if stage == 'front' else 'HP-HN', 'state': 'DC-fixed acquisition ON proxy', 'sample_count': len(f), 'output_units': 'V/sqrt(Hz)', 'struct_contribution_units': 'V^2/Hz', 'max_device_member_sum_error': d['max_member_sum_relative_error'], 'max_total_contribution_vs_out_squared_relative_error': d['max_all_devices_vs_out_squared_relative_error'], 'bands': bands}
    static = {}
    mask = np.ones(81, dtype=bool)
    mask[[8, 40, 72]] = False
    for gain in [1, 4, 16]:
        nom = read(STATIC[27] / 'input.raw' / 'g{}_dc.dc'.format(gain))
        target = np.array(nom['SW']) * gain / 4
        cf = np.polyfit((np.array(nom['FP']) - np.array(nom['FN']))[[8, 40, 72]], target[[8, 40, 72]], 1)
        static[str(gain)] = {'fixed27_coefficients': cf.tolist(), 'temperature': {}}
        for temp, p in STATIC.items():
            dc = read(p / 'input.raw' / 'g{}_dc.dc'.format(gain))
            x = np.array(dc['SW']) * gain / 4
            y = np.array(dc['FP']) - np.array(dc['FN'])
            assert np.allclose(x, target, atol=1e-12, rtol=0) and len(x) == 81
            residual = (cf[0] * y + cf[1] - x) / lsb
            static[str(gain)]['temperature'][str(temp)] = {'max78_error_lsb': float(max(abs(residual[mask]))), 'output_diff_endpoints_v': [float(y[0]), float(y[-1])], 'adc_range_exceeded_count': int(sum(abs(y) > 0.4)), 'temperature_4lsb_numeric_screen_met': bool(max(abs(residual[mask])) <= 4), 'overall_pass': False}
    logs = {}
    noise_native = track(NOISE / 'native_netlist')
    for p in [NOISE] + list(STATIC.values()):
        native = track(p / 'native_netlist')
        assert native == noise_native
        track(p / 'input.scs')
        track(p / 'provenance.json')
        log = track(p / 'spectre.out')
        counts = re.search('spectre completes with (\\d+) errors?, (\\d+) warnings?, and (\\d+) notices?\\.', log).groups()
        assert counts[0] == '0'
        logs[p.name] = {'errors_warnings_notices': counts, 'bad_pivoting_notice_present': 'Bad pivoting' in log, 'gmin_notice_present': 'GminDC' in log}
    report = {'status': 'REAL_R4_STATIC_NOISE_DIAGNOSTIC_NOT_DYNAMIC_SNDR_OR_M2_PASS', 'noise_analysis': results, 'static_temperature': static, 'logs': logs, 'integration_method': 'Trapezoid integration of PSD over linear frequency, linearly interpolating band edges; square out ASD exactly once. Same weights for device contributions preserve variance closure.', 'noise_signal_reference': {'sine_dbfs': -1, 'signal_rms_v': srms, 'sndr_target_db': 65, 'total_allowed_noise_and_distortion_rms_v': budget, 'note': 'Whole-chain allowance; all of it cannot be assigned to the front end.'}, 'finite_record_scope': '100k/16384=6.103515625Hz lower band is a sensitivity study, not the exact weighting/window of a sampled noisy FFT; lower-frequency fluctuations cannot simply be discarded for acceptance.', 'sampling_scope': 'Fixed conduction proxy only. Actual ADC bottom-plate network, time-varying noise transfer/folding and quantitative control tests remain required.', 'parser_validation': {'tests': 5, 'final_failures': 0, 'initial_fixture_issue': 'First test fixture omitted SWEEP content; fixture corrected and all five tests rerun successfully.'}, 'hashes': HASHES}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    for g in [1, 4, 16]:
        print(g, {k: v['output_rms_v'] * 1000000.0 for k, v in results['g{}_track'.format(g)]['bands'].items()}, static[str(g)]['temperature'])
if __name__ == '__main__':
    main()
