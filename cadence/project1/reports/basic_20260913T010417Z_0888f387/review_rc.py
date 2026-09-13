"""Review returned RC data without altering original metrics or run statuses."""
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
RUN = ROOT / 'received/runs/rc_step/20260913T010221Z_e511fd36'
sys.path.insert(0, str(BASE / 'basic_design'))
from analyze import analyze, curve, crossing
from audit import check


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    state = read(RUN / 'status.json')
    job = state['job']
    assert (job['cell'], job['corner'], job['temp']) == ('p1b_tb_rc', 'tt', 27)
    names = ['status.json', 'metrics.json', 'native_netlist.scs', 'native_input.scs',
             'input.scs', 'spectre.out', 'VIN.csv', 'VOUT.csv', 'log_audit.json']
    fingerprints = {name: sha(RUN / name) for name in names}
    native = read(RUN / 'native_selection.json')
    checks = {
        'manifest_matches_run': sha(ROOT / 'received/package_manifest.json') == state['package_sha256'],
        'manifest_matches_delivered_runtime': sha(BASE / 'runtime_fixes/v1_0_4p1/payload/package_manifest.json') == state['package_sha256'],
        'native_body_hash_matches': fingerprints['native_netlist.scs'] == state['native_netlist_sha256'] == native['selected_body_sha256'],
        'native_input_hash_matches': fingerprints['native_input.scs'] == native['returned_input_sha256'],
        'simulation_input_hash_matches': fingerprints['input.scs'] == state['input_sha256'],
    }
    audit = check((RUN / 'native_netlist.scs').read_text(), read(BASE / 'basic_design/design.json'), job['cell'], job['params'])
    checks['native_connections_and_all_pulse_values_match'] = audit['status'] == 'PASS'
    original = read(RUN / 'metrics.json')
    recalculated = analyze(RUN, job)
    checks['original_metrics_reproduced'] = all(math.isclose(original[k], recalculated[k], rel_tol=1e-13) for k in ['tau_s', 'cdf_tau_s'])
    vin, vout = curve(RUN, 'VIN'), curve(RUN, 'VOUT')
    checks['waveform_axes_match'] = [t for t, _ in vin] == [t for t, _ in vout]
    checks['waveforms_are_real'] = all(v.imag == 0 for rows in (vin, vout) for _, v in rows)
    checks['covers_0_to_10ns'] = all(rows[0][0] == 0 and math.isclose(rows[-1][0], 1e-8, abs_tol=1e-18) for rows in (vin, vout))
    rise_start = crossing(vin, .05, 0, 2e-9, True)
    rise_end = crossing(vout, .1 * (1 - math.exp(-1)), rise_start, 4e-9, True)
    fall_start = crossing(vin, .05, 5e-9, 7e-9, False)
    fall_end = crossing(vout, .1 * math.exp(-1), fall_start, 9e-9, False)
    high = [abs(v.real - .1) for t, v in vout if 2e-9 <= t <= 5e-9]
    low = [abs(v.real) for t, v in vout if 7e-9 <= t <= 1e-8]
    text = (RUN / 'spectre.out').read_text()
    summary = re.search(r'spectre completes with (\d+) errors, (\d+) warnings, and (\d+) notices', text, re.I)
    assert summary
    simulator = dict(zip(['errors', 'warnings', 'notices'], map(int, summary.groups())))
    checks['spectre_normal_completion'] = simulator['errors'] == 0 and read(RUN / 'log_audit.json')['exit_code'] == 0
    checks['export_complete'] = (RUN / 'export_complete.txt').read_text().strip() == 'COMPLETE'
    repair = (ROOT / 'received/runs/p1_pulse_repair_v2.log').read_text()
    checks['both_pulse_sources_saved'] = all('CELL_SAVED ' + cell in repair for cell in ['p1b_tb_rc', 'p1b_tb_step']) and 'RESULT (t)' in repair
    previous = read(BASE / 'reports/basic_20260912T093350Z_ad8b13b5/review.json')
    old_res = ROOT / 'received/runs/res_dc' / previous['run_id']
    checks['prior_resistor_evidence_matches'] = all(sha(old_res / n) == h for n, h in previous['fingerprints'].items())
    assert all(checks.values()), checks
    mean_r = previous['original_comparison']['mean_resistance_ohm']
    rough_tau = mean_r * 34.6223e-15
    mim = [read(p) for p in sorted((ROOT / 'received/runs/mim_ac').glob('*/status.json'))]
    result = {
        'review_status': 'SIMULATION_VERIFIED_ACCEPTANCE_REVIEW_PENDING_MIM',
        'run_id': RUN.name,
        'original_status_preserved': {k: state[k] for k in ['status', 'performance_status']},
        'checks': checks, 'simulator_summary': simulator,
        'samples_per_waveform': len(vin),
        'spectre_accepted_tran_steps': int(re.search(r'Number of accepted tran steps\s*=\s*(\d+)', text)[1]),
        'waveform': {
            'rising_input_midpoint_s': rise_start, 'rising_output_63pct_s': rise_end,
            'rising_63pct_delay_ps': (rise_end - rise_start) * 1e12,
            'falling_37pct_delay_ps': (fall_end - fall_start) * 1e12,
            'input_min_V': min(v.real for _, v in vin), 'input_max_V': max(v.real for _, v in vin),
            'output_min_V': min(v.real for _, v in vout), 'output_max_V': max(v.real for _, v in vout),
            'high_plateau_max_error_V': max(high), 'low_plateau_max_error_V': max(low),
        },
        'failed_criterion': {
            'name': 'tau_within_10pct_of_CDF', 'old_target_ps': original['cdf_tau_s'] * 1e12,
            'measured_delay_ps': original['tau_s'] * 1e12,
            'relative_difference_percent': 100 * (original['tau_s'] / original['cdf_tau_s'] - 1),
        },
        'diagnostic_estimate_not_new_acceptance_threshold': {
            'prior_measured_mean_R_ohm': mean_r, 'CDF_C_fF_not_yet_measured': 34.6223,
            'mean_R_times_CDF_C_ps': rough_tau * 1e12,
            'delay_difference_from_rough_estimate_percent': 100 * (original['tau_s'] / rough_tau - 1),
            'interpretation': 'Old target uses CDF resistance already shown to differ from this model. Using measured R explains most of the delay shift; this estimate omits nonlinear trajectory and parasitic capacitance and is not a qualification.',
        },
        'mim_attempts': [{'status': s['status'], 'performance_status': s['performance_status'], 'error': s.get('error')} for s in mim],
        'limitations': [
            'OCEAN-exported CSV reviewed; preserved binary PSF not independently decoded.',
            'No successful MIM AC result in this report; RC full-model acceptance remains pending.',
            'Repair log confirms OTA step CDF save, not native OTA netlist or OTA simulation.',
            'Spectre has no warnings; OCEAN environment, log-lock and font warnings remain in the original logs.',
        ],
        'next_step': 'Run the existing mim_ac job with the school launcher, collect report; do not repeat rc_step unchanged.',
        'fingerprints': fingerprints,
        'report_sha256': sha(ROOT / 'project1_basic_report_20260913T010417Z_0888f387.zip'),
    }
    (ROOT / 'review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['review_status', 'simulator_summary', 'samples_per_waveform', 'waveform', 'failed_criterion', 'diagnostic_estimate_not_new_acceptance_threshold', 'mim_attempts']}, indent=2))


if __name__ == '__main__':
    main()
