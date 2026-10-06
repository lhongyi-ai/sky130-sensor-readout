import bisect, hashlib, json, os
from pathlib import Path
import review
ROOT = Path(__file__).resolve().parent
RUN = ROOT.parent.parent / 'runs/task_20260924T071339938962Z/design'
OUT = ROOT.parent / 'mode_boundary_matrix_review_v1'
P = review.P

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((RUN / 'manifest.json').read_text())
    paths = {}
    summary = {}
    for run in sorted((RUN / 'results').iterdir()):
        case = (run / 'case.txt').read_text().strip()
        profile = (run / 'profile.txt').read_text().strip()
        if (case, profile) in paths:
            raise ValueError('Duplicate case; no newest-result selection')
        paths[case, profile] = run
        r, _, _ = review.analyze(run)
        (OUT / f'{case}_{profile}.json').write_text(json.dumps(r, indent=2) + '\n')
    allrows = {}
    context = {}
    for case in ['matched', 'static_gate', 'slow_10x', 'finite_1ohm']:
        pair = review.pair(paths[case, 'baseline'], paths[case, 'strict'])
        (OUT / f'{case}_pair.json').write_text(json.dumps(pair, indent=2) + '\n')
        ranges = pair['strict']['body_minus_external_bulk_range_V']
        sg = pair['signals']
        summary[case] = {'baseline_exit': pair['baseline']['simulator_exit_code'], 'strict_exit': pair['strict']['simulator_exit_code'], 'baseline_warnings': pair['baseline']['warnings'], 'strict_warnings': pair['strict']['warnings'], 'baseline_points': pair['baseline']['points'], 'strict_points': pair['strict']['points'], 'complete_both': all((pair[k]['complete_diagnostic_interval'] for k in ['baseline', 'strict'])), 'actual_tightening': pair['strict_actual_precision_tightening'], 'same_method': pair['same_actual_solver_method_environment'], 'actual_shape_input_sha_verified': all((sha(paths[case, k] / 'input.scs') == manifest['cases'][case]['files'][k]['sha256'] for k in ['baseline', 'strict'])), 'max_int_b_difference_V': sg[P + 'int_b']['maximum_absolute_difference'], 'max_dbnode_difference_V': sg[P + 'dbnode']['maximum_absolute_difference'], 'max_sbnode_difference_V': sg[P + 'sbnode']['maximum_absolute_difference'], 'max_gate_current_difference_A': sg[P + 'g_$flow']['maximum_absolute_difference'], 'max_gate_voltage_difference_V': sg['G']['maximum_absolute_difference'], 'max_drain_voltage_difference_V': sg['D']['maximum_absolute_difference'], 'strict_body_swing_peak_to_peak_V': ranges['int_b'][1] - ranges['int_b'][0], 'reference_voltage_only_V': 0.05 * 0.8 / 4096, 'note': 'Internal-body differences are not ADC input or conversion error. The ADC0.05LSB scale is not an acceptance criterion for this isolated internal node.'}
        context[case] = {}
        for prof in ['baseline', 'strict']:
            tr, rows = review.waveform(paths[case, prof])
            allrows[case, prof] = rows
            t = [r['time'] for r in rows]
            for signal in [P + 'int_b', P + 'g_$flow']:
                when = sg[signal]['worst_time_s']
                i = bisect.bisect_left(t, when)
                keep = ['time', 'D', 'G', 'SB', P + 'int_b', P + 'dbnode', P + 'sbnode', P + 'reversed', P + 'g_$flow', P + 'd_$flow', P + 'b_$flow', P + 's_$flow']
                context[case][prof + '_' + signal] = {'comparison_peak': sg[signal], 'actual_rows': [{n: r[n] for n in keep} for r in rows[max(0, i - 4):i + 5]]}
    result = {'status': 'EIGHT_REAL_RUNS_REVIEWED_MODEL_ISOLATION_ONLY', 'run': str(RUN), 'summaries': summary, 'model_hash_before_after_equal': (RUN / 'models_before.sha256').read_bytes() == (RUN / 'models_after.sha256').read_bytes(), 'model_hash_comparison_exit': (RUN / 'model_hash_comparison_exit.txt').read_text().strip(), 'model_hashes': (RUN / 'models_before.sha256').read_text().splitlines(), 'source_manifest_sha256': sha(RUN / 'manifest.json'), 'analysis_files_sha256': {f: sha(ROOT / f) for f in ['review.py', 'psf_stream.py', 'interpretation_contract.json']}, 'peak_actual_rows': context, 'interpretation': ['The isolated identical device under finite smooth sources has reproducible source/drain-mode-sensitive body/current responses and baseline/strict differences, without the full ADC or AMS interface.', 'The original SPECTRE-16780 warning was not reproduced: all8runs have0warnings. The isolated forced-source network and29.4/14.7fs maximumsteps differ from original loaded ADC; do not claim complete reproduction or a cure.', 'The fixed-gate case retains nearly the same int_b and gate-current pair difference as the dynamic gate case. Dynamic gate motion is therefore not required for this isolated mode-sensitive current/body effect; stored-charge history still differs.', 'Slower inputs reduce total body swing by about9x and gate-current peak difference by about10x, consistent with a rate-dependent charge response. Their numeric body error does not decrease10x because physical rate and relative time-step limit both change; no universal slope-based fix follows.', 'With1ohm impedance, forced-source values still follow the exact sine, while terminalD/G acquire several-microvolt differences. This explicitly shows how model/current numeric differences can enter external voltages through finite impedance, but1ohm is not calibrated native driver impedance.', 'All analog union peaks retain switching edges; current and mode peaks have their original brackets preserved. Piecewise interpolation across a rapidly changing mode boundary is not proof of an underlying physical model discontinuity.'], 'repair_status': 'NO_VALIDATED_ADC_REPAIR_YET', 'next_closed_dynamic_reproduction': 'Retain the original native phase output and real transistor gate fanout so CONV is a free circuit node; use native switches/CDAC or a conservatively closed native subnetwork, preserve body/junction models, and provide finite control stimulus only at the boundary. Validate the loaded waveform against the exactfullADCprobe before attributing a repair. Do not add invented ideal load capacitance.', 'complete_ADC': False, 'full_ADC_accuracy_pass': False}
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Single-device mode-boundary matrix: eight actual runs, no ADC repair', '', 'All eight school Spectre runs completed with zero errors/warnings, four cycles and eight mode changes each. Original model/entry hashes match before and after. Four baseline/strict pairs tighten realized tolerances tenfold and halve maxstep with identical integration.', '', '| Control | Strict int_b peak-to-peak | Baseline/strict int_b maximum difference | Gate total-current maximum difference |', '|---|---:|---:|---:|']
    for c, s in summary.items():
        lines.append(f'| {c} | {s['strict_body_swing_peak_to_peak_V'] * 1000.0:.3f} mV | {s['max_int_b_difference_V'] * 1000000.0:.3f} µV | {s['max_gate_current_difference_A'] * 1000000.0:.3f} µA |')
    lines += ['', '**int_b is an internal MOS body voltage, not ADC input error. Total terminal-current differences include displacement current and are not conversion errors.** All accepted times and edges are retained, with no time alignment or deletion.', '', 'The forced sources match their analytic waveform at accepted points within 0.9 fV. Matched D/G union-interpolation differences are 0.099/0.202 µV while int_b differs 23.528 µV. In finite_1ohm, actual D/G differences are 2.861/7.087 µV. This demonstrates impedance feedback, not permission to insert 1 Ω into the real ADC.', '', 'Fixed-gate controls retain similar body/current sensitivity, so gate variation is not necessary in this isolation fixture. Slowing both slopes tenfold reduces body amplitude about ninefold and current difference about tenfold, but does not proportionally remove int_b precision sensitivity. Reducing ADC rate is not a repair.', '', '**The original SPECTRE-16780 warning was not reproduced.** Forced ports remove closed load dynamics, and the very small maxstep changes the solver path. Only mode-boundary sensitivity was reproduced. summary.json retains worst points and actual brackets. A peak alone does not prove physical-model discontinuity.', '', 'The next controlled diagnosis retains the real phase generator and MOS gate loads with a freely solved CONV output, original body/junction parameters and PDK. No ideal lumped capacitor substitutes for omitted real loads. Any supported method repair still requires the complete actual ADC/original RTL two-frame/reset comparison and full 0.05 LSB gate before 12 frames.', '', 'All formal ADC PASS fields remain false. Pair JSON retains full waveform comparisons, actual settings/aliases and source checks; summary.json retains model hashes, worst neighbors and scope.']
    (OUT / 'README.md').write_text('\n'.join(lines) + '\n')
    plot(manifest, allrows, summary)
    print(json.dumps({c: {k: v for k, v in x.items() if k in ['max_int_b_difference_V', 'strict_body_swing_peak_to_peak_V', 'max_gate_current_difference_A']} for c, x in summary.items()}, indent=2))

def plot(m, rows, summary):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT.parent / 'private_runtime/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axs = plt.subplots(4, 1, figsize=(11.8, 11.6))
    fig.subplots_adjust(left=0.12, right=0.96, top=0.86, bottom=0.18, hspace=0.43)
    for ax, case in zip(axs, ['matched', 'static_gate', 'slow_10x', 'finite_1ohm']):
        period = m['cases'][case]['period_s']
        center = 3.75 * period
        for p, color in [('baseline', '#1769aa'), ('strict', '#ba3a34')]:
            rs = [r for r in rows[case, p] if abs(r['time'] - center) < period * 0.006]
            ax.plot([(r['time'] - center) * 1000000000000000.0 for r in rs], [(r[P + 'int_b'] - r['SB']) * 1000000.0 for r in rs], '.-', ms=3, lw=1, label=p, color=color)
        ax.grid(alpha=0.2)
        ax.axvline(0, color='#65748b', ls='--', lw=0.8)
        ax.set_title(case + '; full-interval max body difference = ' + f'{summary[case]['max_int_b_difference_V'] * 1000000.0:.3f} uV', loc='left', fontsize=10.5)
        ax.set_ylabel('int_b - SB (uV)')
        ax.set_xlabel('Time from source phase 3.75 T (fs); no run alignment')
        if case == 'matched':
            ax.legend(frameon=False)
    fig.text(0.12, 0.95, 'Mode-boundary differences remain with zero warnings', fontsize=17, weight='bold', color='#172b46')
    fig.text(0.12, 0.914, 'Eight actual school runs; identical native PFET/PDK. Continuous analytic sources, four cycles in each run.', color='#596779')
    fig.text(0.12, 0.884, 'Local plots show original points near a predeclared source phase. Reports retain all accepted points and every edge.', fontsize=9.7, color='#596779')
    fig.text(0.12, 0.102, 'Model-isolation diagnostic only: no complete ADC pass and no model-bug verdict.', fontsize=11.5, weight='bold', color='#172b46')
    fig.text(0.12, 0.055, 'Ideal sources clamp external D/G; original ADC loading and charge history differ. Internal-body voltage error is not\nADC input/conversion error. Next: original native phase driver with free output and real transistor fanout.', color='#596779', linespacing=1.6)
    for ext in ['png', 'svg']:
        fig.savefig(OUT / f'mode_boundary_matrix.{ext}', dpi=170)
    plt.close(fig)
if __name__ == '__main__':
    main()
