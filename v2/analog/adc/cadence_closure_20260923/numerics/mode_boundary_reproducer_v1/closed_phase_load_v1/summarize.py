from pathlib import Path
import hashlib, json, os
import analyze
ROOT = Path(__file__).resolve().parent
CLOSURE = ROOT.parents[2]
OUT = ROOT.parents[1] / 'closed_phase_load_review_v1'
RUN = CLOSURE / 'runs/task_20260924T073403971296Z/design'
BASE = RUN / 'results/baseline_20260924T073407Z_2387831'
STRICT = RUN / 'results/strict_20260924T073433Z_2388411'
FULL = CLOSURE / 'runs/task_20260924T060914240241Z/design'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    j = json.loads((OUT / 'review.json').read_text())
    m = json.loads((ROOT / 'manifest.json').read_text())
    proof = {'frozen_local_manifest_sha256': sha(ROOT / 'manifest.json'), 'actual_run_manifest_sha256': {str(r): sha(r / 'package_manifest.json') for r in [BASE, STRICT]}, 'actual_native_sha256': {str(r): sha(r / 'native_closed.scs') for r in [BASE, STRICT]}, 'frozen_native_sha256': sha(ROOT / 'native_closed.scs'), 'original_native_still_matches': sha(Path(m['source_native'])) == m['source_native_sha256'], 'every_retained_native_record_count': len(m['records']), 'direct_CONV_gate_load_count': len(m['fanout']['CONV']), 'analysis_sha256': {n: sha(ROOT / n) for n in ['analyze.py', 'psf_stream.py', 'summarize.py']}, 'tool_model_note': 'Both logs useSpectre21.1.0.132 and samePDKinclude. Thisrunner does notcontain a separatebefore/afterPDKfilehash capture; frozen native and input hashes verified. NoPDKbody copied/edited.'}
    assert all((v == proof['frozen_local_manifest_sha256'] for v in proof['actual_run_manifest_sha256'].values()))
    assert all((v == proof['frozen_native_sha256'] for v in proof['actual_native_sha256'].values()))
    (OUT / 'provenance.json').write_text(json.dumps(proof, indent=2) + '\n')
    b = j['baseline']
    s = j['strict']
    p = j['pair']['signals']
    full = j['original_full_probe_comparison']['comparison']['signals']
    text = '# Reduced native closed phase/load diagnosis: not repaired\n\nTwo profiles used 654 native devices and 104 direct CONV gate loads, preserving frozen input/native hashes. Effective reltol was 1e−6/1e−7, absolute tolerances tenfold tighter and maxstep 2/1 ns, with gear2only/sigglobal. Complete ADC PASS remains false.\n\n| Result | baseline | strict |\n|---|---:|---:|\n| Spectre exit | 0 | 0 |\n| Saved points | 4572 | 7958 |\n| Record end | 4.1 µs | 4.1 µs |\n| Warnings | 1 | 5 |\n| Accepted points inside 1 ns source rise | {bn} | {sn} |\n\nThe original CONV PFET warning was not reproduced: the reduced baseline warning names XLOAD.XADC_XDP_NL, while the original complete probe names CONV PFET int_b. Similar response does not prove the same warning. Full contexts remain in review.json.\n\nStrict reaches Newton recovery at 4.0625 µs, shrinks to about 2e−19 s and skips the 4.0635 µs breakpoint with LTE ignored. Raw points jump 4.0625→4.064500000000001 µs across the full 1 ns rise. Exact source values at saved points do not prove that the edge was resolved.\n\n| Full union maximum difference | Value |\n|---|---:|\n| Command including missing-edge interpolation | 0.9 V |\n| CONV | 1.012019 V |\n| TP−TN | 193.630 mV |\n| RP | 14.5548 µV |\n| RN | 5.1778 µV |\n| VCM | 0 |\n\nThese retained failures are not reliable physical/convergence error estimates from a resolved edge. No alignment, edge deletion or threshold change is used. Omitting 87 preamp/comparator devices changes baseline TP−TN by 23.089 mV from the complete probe, so the reduction is not full ADC equivalence.\n\nAn independent half-sine control tests source-shape sensitivity while keeping free output and actual loads. It changes the stimulus and cannot be called an original-circuit repair. Full ADC/original RTL two-frame/reset qualification remains mandatory. Exact inputs, original points and logs are in review.json/provenance.json.\n'.format(bn=b['active_command_accepted_point_count'], sn=s['active_command_accepted_point_count'])
    (OUT / 'README.md').write_text(text)
    plot()
    print('REPORT_READY', OUT)

def plot():
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT.parents[1] / 'private_runtime/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 10})
    _, b = analyze.read(analyze.raw(BASE))
    _, s = analyze.read(analyze.raw(STRICT))
    fp = list((FULL / 'amsdControl.raw').glob('*.tran'))[0]
    _, f = analyze.read(fp)
    fig, ax = plt.subplots(3, 1, figsize=(11.7, 10))
    fig.subplots_adjust(left=0.12, right=0.96, top=0.85, bottom=0.17, hspace=0.5)
    for rows, name, color, ls in [(b, 'closed baseline', '#1671ac', '-'), (s, 'closed strict', '#bc4437', '--')]:
        local = [r for r in rows if 4.0623e-06 <= r['time'] <= 4.0648e-06]
        x = [(r['time'] - 4.0625e-06) * 1000000000.0 for r in local]
        ax[0].plot(x, [r['SAMPLE_CMD'] for r in local], '.' + ls, ms=3, label=name, color=color)
        ax[1].plot(x, [r['CONV'] for r in local], '.' + ls, ms=3, label=name, color=color)
        local = [r for r in rows if 4.0623e-06 <= r['time'] <= 4.09e-06]
        ax[2].plot([(r['time'] - 4.0625e-06) * 1000000000.0 for r in local], [r['XLOAD.XADC_TP'] - r['XLOAD.XADC_TN'] for r in local], ls, lw=1.2, color=color)
    ax[0].plot([-0.2, 0, 1, 2.3], [0, 0, 1.8, 1.8], ':', color='#222', lw=1.5, label='defined command')
    ff = [r for r in f if 4.0623e-06 <= r['time'] <= 4.0648e-06]
    ax[1].plot([(r['time'] - 4.0625e-06) * 1000000000.0 for r in ff], [r['p2_ams_reset1.conv_e'] for r in ff], ':', color='#222', lw=1, label='original full ADC probe')
    for a, label, title in zip(ax, ['Command (V)', 'CONV (V)', 'TP - TN (V)'], ['Strict recovery skips the entire 1 ns command edge', 'Similar baseline CONV does not reproduce the same warning node', 'Changed loading and failed strict integration prohibit ADC accuracy claims']):
        a.set_ylabel(label)
        a.set_xlabel('Original time relative to 4.0625 us (ns); no alignment')
        a.set_title(title, loc='left', fontsize=10.5)
        a.grid(alpha=0.2)
    ax[0].legend(frameon=False, fontsize=9)
    ax[1].legend(frameon=False, fontsize=9)
    fig.text(0.12, 0.95, 'A completed run can still miss the stimulus edge', fontsize=17, weight='bold')
    fig.text(0.12, 0.9, 'Real school runs; 654 unchanged native instances with a free CONV output and all 104 original gate loads.', fontsize=10, color='#596879')
    fig.text(0.12, 0.095, 'Dashed strict segments cross actual unsampled recovery gaps; they are not a resolved physical waveform.', fontsize=10.7, weight='bold')
    fig.text(0.12, 0.047, 'Baseline LTE warning: switch-control node XADC_XDP_NL, not the original CONV PFET.\nAll-interval comparison and every accepted point are retained. Reduced diagnostic only; full ADC acceptance remains false.', fontsize=10, color='#596879', linespacing=1.6)
    for ext in ['png', 'svg']:
        fig.savefig(OUT / f'closed_phase_source_gap.{ext}', dpi=165)
    plt.close(fig)
if __name__ == '__main__':
    main()
