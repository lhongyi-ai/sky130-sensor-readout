from pathlib import Path
import bisect, hashlib, json, os, math
import analyze
ROOT = Path(__file__).resolve().parent
CLOSURE = ROOT.parents[2]
OUT = ROOT.parents[1] / 'closed_phase_load_halfsine_review_v1'
RUN = CLOSURE / 'runs/task_20260924T074135693318Z/design'
BASE = RUN / 'results/baseline_20260924T074138Z_2394497'
STRICT = RUN / 'results/strict_20260924T074204Z_2395083'
OLD = CLOSURE / 'runs/task_20260924T073403971296Z/design/results/baseline_20260924T073407Z_2387831'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    j = json.loads((OUT / 'review.json').read_text())
    m = json.loads((ROOT / 'manifest.json').read_text())
    bt, b = analyze.read(analyze.raw(BASE))
    st, s = analyze.read(analyze.raw(STRICT))
    ot, o = analyze.read(analyze.raw(OLD))
    for rs in [b, s, o]:
        for r in rs:
            r['TP_minus_TN'] = r['XLOAD.XADC_TP'] - r['XLOAD.XADC_TN']
    types = dict(bt.types)
    types['TP_minus_TN'] = 'V'
    oldcompare = analyze.compare(o, b, types)
    oldcompare.update(kind='CHANGED_SOURCE_SHAPE_COMPARISON_NOT_CONVERGENCE', note='Both usebaselineprecision. PWLlinear→halfsine changes derivative corners, intermediatevoltage, peak slope and resulting timing; cannot isolate aunique cause or claim originalADC equivalence.')
    (OUT / 'linear_to_halfsine_baseline.json').write_text(json.dumps(oldcompare, indent=2) + '\n')
    peaks = {}
    for n in ['TP_minus_TN', 'CONV', 'SAMPLE_CMD', analyze.P + 'int_b', analyze.P + 'g']:
        e = j['pair']['signals'][n]
        peaks[n] = {'comparison_peak': e}
        for name, rows in [('baseline', b), ('strict', s)]:
            i = bisect.bisect_left([r['time'] for r in rows], e['worst_time_s'])
            names = ['time', 'SAMPLE_CMD', 'CONV', 'ACQ', 'TOP', 'TOPB', 'XLOAD.XADC_TP', 'XLOAD.XADC_TN', 'TP_minus_TN', 'XPHASE.XPHASE_XBCONV_B', *[analyze.P + k for k in ['int_b', 'dbnode', 'sbnode', 'vds', 'reversed', 'g', 'd', 's', 'b']]]
            peaks[n][name + '_actual_neighbors'] = [{k: r[k] for k in names} for r in rows[max(0, i - 3):i + 4]]
    proof = {'local_manifest_sha256': sha(ROOT / 'manifest.json'), 'actual_manifest_hashes': [sha(x / 'package_manifest.json') for x in [BASE, STRICT]], 'native_local_sha256': sha(ROOT / 'native_closed.scs'), 'native_run_hashes': [sha(x / 'native_closed.scs') for x in [BASE, STRICT]], 'native_matches_linear_parent': sha(ROOT / 'native_closed.scs') == sha(OLD / 'native_closed.scs'), 'retained_instances': len(m['records']), 'CONV_gate_fanout': len(m['fanout']['CONV']), 'analysis_sha256': {n: sha(ROOT / n) for n in ['analyze.py', 'psf_stream.py', 'summarize.py']}, 'peak_context': peaks, 'full_ADC_accuracy_pass': False, 'complete_ADC': False}
    assert all((h == proof['local_manifest_sha256'] for h in proof['actual_manifest_hashes']))
    assert all((h == proof['native_local_sha256'] for h in proof['native_run_hashes']))
    (OUT / 'provenance_and_peak_context.json').write_text(json.dumps(proof, indent=2) + '\n')
    peak = j['pair']['signals']['TP_minus_TN']
    sourced = j['pair']['signals']['SAMPLE_CMD']
    budget = 0.05 * 0.8 / 4096
    text = f'# Half-sine input-edge control: gap removed, numerical gate still fails\n\nBoth actual pure-Spectre profiles retain the frozen 654-device circuit and 104 CONV loads. Only VCMD changes to edgetype=halfsine transitionreference=100, retaining 4.0625 µs start, 1 ns duration and 0/1.8 V endpoints. Effective precision tightens tenfold with the same integration.\n\nActual rising-edge records have 926/2353 points and match 0.9[1−cos(πu)] within 3.13 pV. Difference from the old linear edge is 0.189462 V, so the stimulus change is explicit.\n\n| Result | baseline | strict |\n|---|---:|---:|\n| Complete 0–4.1 µs exit | 0 | 0 |\n| Accepted points | 4586 | 10288 |\n| LTE-relaxation warnings | 0 | 4 |\n| Breakpoint skip/LTE ignore | 0 | 0 |\n\nThe former skipped-edge gap disappears, but half-sine also changes midpoint voltage, threshold times and peak slew 1.8→2.827 V/ns. Four strict warnings name other body nodes at 4.06326/4.06327/4.06333/4.07506 µs; exact contexts remain in review.json. They are not the original CONV PFET warning.\n\n| Full accepted-time union difference | Value |\n|---|---:|\n| TP−TN | 1.127887 mV |\n| RP | 3.2727 nV |\n| RN | 2.4411 nV |\n| VCM | 0 |\n| CONV | 304.202 µV |\n\nTP−TN peaks at 4.075067258260984 µs, approximately {peak['max_abs_difference'] / budget:.2f} times the original 9.765625 µV gate. Original neighbors and all edges remain; no complete ADC/original RTL qualification follows.\n\nBoth source values are exact at their own accepted points, but union interpolation produces approximately {sourced['max_abs_difference'] * 1000000.0:.3f} µV command difference. This is not a real source error or a reason to delete the TP−TN peak, which occurs about 11.57 ns after the input edge ends. Peaks alone do not prove a physical-model bug/discontinuity.\n\nThis is an informative source-shape control retaining free output and real loads. Internal-body LTE and full voltage accuracy remain unresolved. A smoother-input candidate must explicitly requalify complete ADC timing, conversions and convergence; it is not an equivalent repair by this reduced result alone. review.json, linear_to_halfsine_baseline.json and provenance_and_peak_context.json retain exact evidence.\n'
    (OUT / 'README.md').write_text(text)
    plot(b, s, o, peak)
    print('REPORT_READY', OUT)

def plot(b, s, o, peak):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT.parents[1] / 'private_runtime/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 10})
    fig, ax = plt.subplots(3, 1, figsize=(11.7, 10))
    fig.subplots_adjust(left=0.12, right=0.96, top=0.85, bottom=0.17, hspace=0.52)
    for rows, name, color in [(b, 'half-sine baseline', '#1771ab'), (s, 'half-sine strict', '#bb4135')]:
        r = [r for r in rows if 4.06245e-06 <= r['time'] <= 4.06355e-06]
        ax[0].plot([(x['time'] - 4.0625e-06) * 1000000000.0 for x in r], [x['SAMPLE_CMD'] for x in r], '.-', ms=2, lw=1, label=name, color=color)
        r = [r for r in rows if 4.0749e-06 <= r['time'] <= 4.0753e-06]
        ax[1].plot([(x['time'] - 4.075e-06) * 1000000000000.0 for x in r], [x['TP_minus_TN'] * 1000.0 for x in r], '.-', ms=2, lw=1, label=name, color=color)
        for a in [ax[0], ax[1]]:
            a.grid(alpha=0.2)
    ax[0].plot([0, 1], [0, 1.8], '--', lw=1, color='#444', label='original linear shape')
    ax[0].set_ylabel('Command (V)')
    ax[0].set_xlabel('Original time from 4.0625 us (ns)')
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].set_title('Source shape actually verified: all four edge quarters have accepted points', loc='left', fontsize=10.5)
    ax[1].set_ylabel('TP - TN (mV)')
    ax[1].set_xlabel('Original time from 4.075 us (ps); no alignment')
    ax[1].set_title('Local view of the retained full-interval worst difference', loc='left', fontsize=10.5)
    ts = sorted(set((r['time'] for r in b + s if 4.0749e-06 <= r['time'] <= 4.0753e-06)))

    def at(rs, t):
        times = [r['time'] for r in rs]
        i = bisect.bisect_right(times, t) - 1
        q = (t - times[i]) / (times[i + 1] - times[i]) if i + 1 < len(rs) else 0
        return rs[i]['TP_minus_TN'] + q * (rs[min(i + 1, len(rs) - 1)]['TP_minus_TN'] - rs[i]['TP_minus_TN'])
    ax[2].plot([(t - 4.075e-06) * 1000000000000.0 for t in ts], [(at(s, t) - at(b, t)) * 1000000.0 for t in ts], color='#894494', lw=1.2)
    for y in [-9.765625, 9.765625]:
        ax[2].axhline(y, color='#777', ls='--', lw=0.8)
    ax[2].grid(alpha=0.2)
    ax[2].set_ylabel('Strict - baseline (uV)')
    ax[2].set_xlabel('Original time from 4.075 us (ps); all local union points')
    ax[2].set_title('1.128 mV retained peak exceeds the unchanged 9.766 uV numeric scale', loc='left', fontsize=10.5)
    fig.text(0.12, 0.95, 'A smoother source removes one failure mode, not every error', fontsize=16.7, weight='bold')
    fig.text(0.12, 0.9, 'Same 654-device closed subnetwork; source edge shape is deliberately changed. Four strict LTE warnings remain.', fontsize=10, color='#596879')
    fig.text(0.12, 0.095, 'Changed stimulus, reduced circuit: no complete ADC pass and no model-bug verdict.', fontsize=11.2, weight='bold')
    fig.text(0.12, 0.047, 'No time alignment or omitted edges. Reports retain the complete 0–4.1 us records and exact warning nodes.\nFour source quarters are resolved; zero warning in the baseline does not establish strict convergence.', fontsize=10.3, color='#596879', linespacing=1.6)
    for ext in ['png', 'svg']:
        fig.savefig(OUT / f'halfsine_residual.{ext}', dpi=165)
    plt.close(fig)
if __name__ == '__main__':
    main()
