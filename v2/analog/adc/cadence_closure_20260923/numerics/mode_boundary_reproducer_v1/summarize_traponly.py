import bisect, hashlib, json, os
from pathlib import Path
import review
ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'mode_boundary_matrix_review_v1'
NEW = ROOT.parent.parent / 'runs/task_20260924T072122103642Z/design/results/matched_strict_traponly'
OLD = next((ROOT.parent.parent / 'runs/task_20260924T071339938962Z/design/results').glob('matched_strict_*'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    single, tt, trows = review.analyze(NEW)
    pair = review.pair(OLD, NEW, allow_method_difference=True)
    _, grows = review.waveform(OLD)
    (OUT / 'matched_strict_traponly.json').write_text(json.dumps(single, indent=2) + '\n')
    (OUT / 'matched_same_strict_gear_vs_trap.json').write_text(json.dumps(pair, indent=2) + '\n')
    when = pair['signals'][review.P + 'g_$flow']['worst_time_s']
    times = [r['time'] for r in trows]
    i = bisect.bisect_left(times, when)
    chosen = trows[i - 4:i + 21]
    sig = review.P + 'g_$flow'
    d = [b[sig] - a[sig] for a, b in zip(chosen, chosen[1:])]
    alternate = sum((x * y < 0 for x, y in zip(d, d[1:])))
    r = {'status': 'METHOD_CONTROL_HAS_STEP_ALTERNATING_CURRENT_NOT_AN_ACCEPTED_FIX', 'input_sha256': sha(NEW / 'input.scs'), 'gear_input_sha256': sha(OLD / 'input.scs'), 'trap_exit': single['simulator_exit_code'], 'trap_warnings': single['warnings'], 'body_peak_difference_V': pair['signals'][review.P + 'int_b']['maximum_absolute_difference'], 'gate_total_current_peak_difference_A': pair['signals'][sig]['maximum_absolute_difference'], 'selected_consecutive_raw_points': [{n: x[n] for n in ['time', 'D', 'G', 'SB', review.P + 'int_b', review.P + 'reversed', sig]} for x in chosen], 'successive_current_increment_sign_changes': alternate, 'possible_sign_changes': len(d) - 1, 'interpretation': 'Persistent accepted-step alternating total gate current, absent from same-setting Gear reference, is consistent with trapezoidal numerical ringing. Small body-voltage difference and no warnings do not make this a validated fix. This is method sensitivity, not a same-method tightening test.', 'complete_ADC': False, 'full_ADC_accuracy_pass': False}
    (OUT / 'traponly_addendum.json').write_text(json.dumps(r, indent=2) + '\n')
    p = OUT / 'README.md'
    s = p.read_text().split('\n## Independent strict traponly method control')[0]
    s += '\n## Independent strict traponly method control\n\nThe later school run retained strict stimuli, PDK, tolerances and maxstep, changing only integration. It completed with zero errors/warnings, 8020 points and eight mode changes. Relative to strict gear2only, maximum int_b difference was 9.882 µV and gate total-current difference 117.549 µA.\n\nGate current alternates persistently at successive accepted points: approximately −294.461/−492.600/−294.587/−492.719 µA at 110.1773/110.1920/110.2067/110.2214 ps, including after reversal. This is consistent with trapezoidal numerical ringing and is not an accepted repair. No warning is not convergence evidence. Original neighbors remain in traponly_addendum.json and the ringing figure. This is a same-strict-profile method comparison, not a same-method precision-tightening test. The preceding eight controls are preserved.\n'
    p.write_text(s)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT.parent / 'private_runtime/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11.6, 5.8))
    fig.subplots_adjust(left=0.12, right=0.96, bottom=0.29, top=0.78)
    for rows, label, color in [(grows, 'strict gear2only', '#1769aa'), (trows, 'same strict traponly', '#ba3a34')]:
        rs = [x for x in rows if 1.099e-10 < x['time'] < 1.111e-10]
        ax.plot([x['time'] * 1000000000000.0 for x in rs], [x[sig] * 1000000.0 for x in rs], '.-', lw=1, ms=2.6, label=label, color=color)
    ax.set_xlabel('Original time (ps); no alignment')
    ax.set_ylabel('Total gate current (uA)')
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.text(0.12, 0.92, 'Zero warnings still conceal accepted-step current ringing', fontsize=16, weight='bold')
    fig.text(0.12, 0.84, 'Same native single-device fixture and strict settings; only the integration method changes.', fontsize=10.5, color='#536377')
    fig.text(0.12, 0.065, 'Observed alternating terminal-current response rejects traponly as an established repair.\nBody-voltage agreement alone does not establish current or loaded-circuit accuracy; ADC acceptance remains false.', fontsize=10.5, color='#536377', linespacing=1.5)
    for ext in ['png', 'svg']:
        fig.savefig(OUT / f'traponly_current_ringing.{ext}', dpi=170)
    plt.close(fig)
    print(json.dumps({k: v for k, v in r.items() if k != 'selected_consecutive_raw_points'}, indent=2))
if __name__ == '__main__':
    main()
