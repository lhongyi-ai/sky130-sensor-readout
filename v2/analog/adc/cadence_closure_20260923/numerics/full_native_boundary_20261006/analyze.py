#!/usr/bin/env python3
"""Retain complete-domain failures and test native versus original boundaries."""
import argparse
import bisect
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from psf_stream import Trace
from build import STOP, ramp

LIMIT = 9.765625e-6
MAP = {'CONV': 'conv_e', 'SAMPLE_CMD': 'sample_cmd_e', 'RST_N': 'rst_n_e',
       'EVAL': 'eval_e', 'TOP': 'top_e', 'TOPB': 'topb_e', 'ACQ': 'acq_e',
       'VDD': 'vdd', 'RP': 'rp', 'RN': 'rn', 'VCM': 'vcm', 'Q': 'q_e', 'QB': 'qb_e',
       'XADC.XADC_TP': 'adc.XADC_TP', 'XADC.XADC_TN': 'adc.XADC_TN',
       'XADC.XADC_PREP': 'adc.XADC_PREP', 'XADC.XADC_PREN': 'adc.XADC_PREN'}
MAP = {k: 'p2_ams_reset1.' + v for k, v in MAP.items()}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def compare(first, second, names):
    a = [r['time'] for r in first]
    b = [r['time'] for r in second]
    lo, hi = max(a[0], b[0]), min(a[-1], b[-1])
    if hi < lo:
        raise ValueError('No common domain')
    ts = sorted(set(t for t in a + b if lo <= t <= hi))

    def sample(rows, times, t, n):
        i = bisect.bisect_right(times, t) - 1
        if i < 0 or t > times[-1]:
            raise ValueError('Extrapolation forbidden')
        if t == times[i] or i == len(times) - 1:
            return rows[i][n]
        fraction = (t - times[i]) / (times[i + 1] - times[i])
        return rows[i][n] + fraction * (rows[i + 1][n] - rows[i][n])

    differences = {}
    for n in names:
        value, when = max((abs(sample(second, b, t, n) - sample(first, a, t, n)), t) for t in ts)
        differences[n] = {'max_abs_difference_V': value, 'worst_time_s': when}
    complete = lo == 0 and abs(hi - STOP) < 1e-17
    within = all(differences[n]['max_abs_difference_V'] <= LIMIT for n in ['TP_minus_TN', 'RP', 'RN', 'VCM'])
    return {'common_domain_s': [lo, hi], 'complete_0_to_4p1us': complete,
            'union_points': len(ts), 'signals': differences,
            'short_numeric_control_pass': complete and within,
            'method': 'Every union accepted time; linear interpolation, no alignment, edge removal or extrapolation.'}


def load(run):
    manifest = json.loads((run / 'package_manifest.json').read_text())
    profile = (run / 'profile.txt').read_text().strip()
    if sha(run / 'input.scs') != manifest['profiles'][profile]['sha256'] or sha(run / 'native_full.scs') != manifest['native_sha256']:
        raise ValueError('Retained input differs from prepared manifest')
    tr = Trace(run / 'trace.tran.gz', wanted=set(MAP))
    rows = list(tr.rows())
    if not rows:
        raise ValueError('Empty trace')
    for row in rows:
        row['TP_minus_TN'] = row['XADC.XADC_TP'] - row['XADC.XADC_TN']
    log = (run / 'spectre.out').read_text(errors='replace')
    edge_checks = {}
    for n, start in [('RST_N', 1.885e-6), ('SAMPLE_CMD', 4.0625e-6)]:
        quarters = [sum(start + i * .25e-9 < r['time'] < start + (i + 1) * .25e-9 for r in rows) for i in range(4)]
        edge_checks[n] = {'accepted_points_per_edge_quarter': quarters,
                          'every_quarter_resolved': all(quarters),
                          'max_source_error_at_saved_points_V': max(abs(r[n] - ramp(r['time'], start)) for r in rows)}
    complete = rows[0]['time'] == 0 and abs(rows[-1]['time'] - STOP) < 1e-17
    exit_code = int((run / 'exit_code.txt').read_text())
    warning_lines = [line.strip() for line in log.splitlines() if 'WARNING (' in line or 'Warning from spectre' in line]
    review = {'profile': profile, 'input_sha256': sha(run / 'input.scs'),
              'raw_sha256': sha(run / 'trace.tran.gz'), 'exit_code': exit_code,
              'domain_s': [rows[0]['time'], rows[-1]['time']], 'points': len(rows),
              'complete_domain': complete, 'actual_solver_header': tr.header,
              'source_edge_checks': edge_checks, 'warning_lines': warning_lines,
              'completion_summary': re.findall(r'spectre completes with [^\n]+', log),
              'diagnostic_integrity_pass': complete and exit_code == 0 and all(x['every_quarter_resolved'] and x['max_source_error_at_saved_points_V'] < 5e-12 for x in edge_checks.values())}
    return review, rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--strict', type=Path, required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Review already exists; preserve it')
    br, baseline = load(a.baseline)
    sr, strict = load(a.strict)
    original = list(Trace(a.reference, wanted=set(MAP.values())).rows())
    reference = [{'time': row['time'], **{n: row[o] for n, o in MAP.items()},
                  'TP_minus_TN': row[MAP['XADC.XADC_TP']] - row[MAP['XADC.XADC_TN']]} for row in original]
    names = [*MAP, 'TP_minus_TN']
    convergence = compare(baseline, strict, names)
    equivalence = compare(reference, baseline, names)
    report = {'scope': 'FULL_NATIVE_FIRST_EDGE_DIAGNOSIS_ONLY',
              'baseline': br, 'strict': sr,
              'baseline_vs_original_AMS': equivalence,
              'strict_vs_baseline': convergence,
              'original_reference_sha256': sha(a.reference),
              'diagnostic_success': br['diagnostic_integrity_pass'] and sr['diagnostic_integrity_pass'] and equivalence['short_numeric_control_pass'] and convergence['short_numeric_control_pass'],
              'numeric_limit_V': LIMIT, 'completed_frames': 0,
              'original_RTL_simulated': False, 'full_ADC_numeric_qualified': False,
              'formal_ADC_PEX_allowed': False}
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['scope', 'diagnostic_success', 'full_ADC_numeric_qualified']}))


if __name__ == '__main__':
    main()
