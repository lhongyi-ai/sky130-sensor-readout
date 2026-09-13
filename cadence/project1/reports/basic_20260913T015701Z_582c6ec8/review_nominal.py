"""Review returned Cadence evidence; never launch a simulator or modify received files."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
RECEIVED = HERE / 'received'
REPORT_SHA = '1145038acb946f06e97a5995308f9316bdc49217f6674bbf2f41e11436ec9eb4'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def same_calculation(a, b):
    """Allow only cross-platform floating-point roundoff in local reanalysis."""
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(same_calculation(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(same_calculation(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-20)
    return type(a) == type(b) and a == b


def main():
    archive = HERE / 'project1_basic_report_20260913T015701Z_582c6ec8.zip'
    assert sha(archive) == REPORT_SHA
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not item.is_dir():
                assert (RECEIVED / item.filename).read_bytes() == z.read(item)
    with tempfile.TemporaryDirectory(prefix='p1_nominal_review_') as temp:
        temp = Path(temp)
        with zipfile.ZipFile(BASE / 'releases/project1_basic_design_v1.0.4.zip') as z:
            z.extractall(temp)
        root = temp / 'project1_handoff/basic_design_v1_0_4'
        for version in ['v1_0_4p1', 'v1_0_4p2', 'v1_0_4p3']:
            for p in (BASE / 'runtime_fixes' / version / 'payload').iterdir():
                if p.is_file():
                    shutil.copy2(p, root / p.name)
        assert sha(root / 'package_manifest.json') == sha(RECEIVED / 'package_manifest.json')
        sys.path.insert(0, str(root))
        import run
        import analyze
        from passive_review import review_passives
        run.verify()
        jobs = {j['id']: j for j in read(root / 'jobs.json')}
        cfg = read(RECEIVED / 'site.json')
        design = read(root / 'design.json')
        records = {}
        folders = {}
        for ident in ['P01_op', 'P01_ac', 'P01_loop', 'P01_step']:
            folder = sorted((RECEIVED / 'runs' / ident).glob('*/status.json'))[-1].parent
            folders[ident] = folder
            state = read(folder / 'status.json')
            job = jobs[ident]
            assert state['job'] == job and state['site'] == cfg
            assert state['package_sha256'] == sha(root / 'package_manifest.json')
            assert state['status'] == state['performance_status'] == 'PASS'
            assert state['simulation_status'] == state['export_status'] == 'PASS'
            native = (folder / 'native_netlist.scs').read_text()
            assert run.check(native, design, job['cell'], job['params']) == read(folder / 'netlist_audit.json')
            assert run.deck(job, run.netlist_body(native), cfg) == (folder / 'input.scs').read_text()
            for name, field in [('native_netlist.scs', 'native_netlist_sha256'), ('input.scs', 'input_sha256')]:
                assert sha(folder / name) == state[field]
            selection = read(folder / 'native_selection.json')
            assert sha(folder / 'native_input.scs') == selection['returned_input_sha256']
            assert sha(folder / 'native_netlist.scs') == selection['selected_body_sha256']
            log = (folder / 'spectre.out').read_text()
            logcheck = read(folder / 'log_audit.json')
            assert run.log_audit(log, logcheck['exit_code']) == logcheck
            assert logcheck['status'] == 'PASS'
            completion = re.search(r'spectre completes with (\d+) errors, (\d+) warnings, and (\d+) notices', log, re.I)
            assert completion and completion.group(1, 2) == ('0', '0')
            # The runner records successful export completion but no separate numeric
            # OCEAN exit-code file; validate content and logs without inventing one.
            run.validate_export(folder, job, 0)
            metrics = analyze.analyze(folder, job)
            saved_metrics = read(folder / 'metrics.json')
            assert same_calculation(metrics, saved_metrics) and metrics['status'] == 'PASS'
            row_counts = {}
            for p in folder.glob('*.csv'):
                with p.open() as f:
                    row_counts[p.name] = sum(1 for _ in csv.DictReader(f))
            assert row_counts['op_devices.csv'] == row_counts['op_instance_map.csv'] == 13
            if job['analysis'] == 'ac':
                curves = [analyze.curve(folder, name) for name in ['VINP', 'VINN', 'VOUT']]
                axis = [x for x, _ in curves[0]]
                assert len(axis) == 1081 and all([x for x, _ in c] == axis for c in curves)
                assert all(abs(math.log10(x) - i / 120) < 1e-10 for i, x in enumerate(axis))
            if job['analysis'] == 'step':
                vi, vo = [analyze.curve(folder, name) for name in ['VINP', 'VOUT']]
                assert [x for x, _ in vi] == [x for x, _ in vo]
                assert vi[0][0] == 0 and abs(vi[-1][0] - 5e-6) < 1e-15
                assert max(b[0] - a[0] for a, b in zip(vi, vi[1:])) <= 0.5e-9 * (1 + 1e-8)
                assert min(v.real for _, v in vi) >= .8 - 1e-12
                assert max(v.real for _, v in vi) <= 1.2 + 1e-12
            records[ident] = dict(attempt=folder.name, metrics=metrics, csv_rows=row_counts,
                model_entry_sha256=state['model_entry_sha256'],
                spectre_errors=0, spectre_warnings=0, spectre_notices=int(completion.group(3)),
                dc_iterations=int(re.search(r'Convergence achieved in (\d+) iterations', log).group(1)),
                bad_pivot_notice='Bad pivoting' in log,
                simulation_origin=state.get('simulation_origin', 'NEW_SPECTRE_EXECUTION'),
                evidence_sha256={p.name: sha(p) for p in folder.iterdir() if p.is_file()})
        assert len({r['model_entry_sha256'] for r in records.values()}) == 1
        recovered = folders['P01_op']
        recovery = read(recovered / 'recovery_source.json')
        source = RECEIVED / 'runs/P01_op' / recovery['source_attempt']
        assert recovery['new_spectre_execution'] is False
        assert read(source / 'status.json') == recovery['source_status']
        for name, digest in recovery['source_files_sha256'].items():
            assert sha(source / name) == digest
            if name.startswith('psf/'):
                assert sha(recovered / name) == digest
        # Reuse verified passive records with no access to the school PDK locally.
        shutil.copytree(RECEIVED / 'runs', root / 'runs')
        passive = review_passives(root, cfg, run.deck, run.netlist_body, run.log_audit, check_model=False)
        school = read(RECEIVED / 'runs/passive_reviews/20260913T015510Z_c3bf46cf/review.json')
        assert passive['status'] == school['status'] == 'PASS'
        assert same_calculation(passive['records'], school['records'])
        assert school['current_site_model_checked'] is True
        assert school['package_sha256'] == sha(root / 'package_manifest.json')
        assert school['model_entry_sha256'] == records['P01_op']['model_entry_sha256']

        historical = []
        with (root / 'reference/P01_transient.tsv').open() as f:
            next(f)
            for line in f:
                columns = line.split()
                historical.append(tuple(float(x) for x in columns[:3]))
        old_step = analyze.step_metrics([(t, complex(v)) for t, v, _ in historical],
                                        [(t, complex(v)) for t, _, v in historical])
        old_summary = next(csv.DictReader((root / 'reference/pvt_summary.csv').open()))
        assert old_summary['point_id'] == 'P01'
        pvt_jobs = [j for j in jobs.values() if j['group'] == 'pvt']
        review = dict(status='PASS_RETURNED_NOMINAL_DATA_REVIEW', source_report_sha256=REPORT_SHA,
            package_sha256=sha(root / 'package_manifest.json'), records=records,
            passive_review='PASS_REPRODUCED_FROM_RETURNED_DATA',
            recovery_source_hashes_verified=True, local_simulator_execution=False,
            local_recalculation_comparison_tolerance=dict(relative=1e-8, absolute=1e-20,
                scope='Floating point arithmetic comparison only; no simulation acceptance limits changed'),
            historical_step_reanalysis=old_step, remaining_pvt_jobs=len(pvt_jobs),
            remaining_pvt_points=[j for j in pvt_jobs if j['analysis'] == 'op'],
            limitations=[
                'Legacy OTA TT / 1.8 V / 27 C / 5 pF || 100 kohm only; not full PVT or frontend/ADC qualification.',
                'School width rounding and M7 parallel split differ from the frozen ngspice implementation.',
                'The local machine does not access school PDK, native OA database or licenses.',
                'Bad-pivot notices are retained; all four returned Spectre runs converged with zero errors and warnings.',
                'OCEAN environment warnings (locks, library redefinition, fonts and debugger) remain; export contains complete finite data.',
                'Step settling uses the old 1% of 0.4 V criterion (4 mV), not the newer 0.25 LSB criterion.',
                'Step overshoot is reported; the frozen Day 4 criteria have no separate overshoot limit.',
                'Steady-state device saturation does not certify saturation throughout the transient.',
                'Model dependency files are not independently hash-certified; only the entry-file hash is recorded.'
            ])
        (HERE / 'review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')

        os.environ['MPLCONFIGDIR'] = str(temp / 'matplotlib')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 2, figsize=(12, 7.3), constrained_layout=True)
        vo = analyze.curve(folders['P01_loop'], 'VOUT')
        vn = analyze.curve(folders['P01_loop'], 'VINN')
        loop = analyze.ratio([(f, -v) for f, v in vo], vn)
        histloop = []
        with (root / 'reference/P01_loop.tsv').open() as f:
            next(f)
            for line in f:
                c = line.split(); histloop.append((float(c[0]), complex(float(c[1]), float(c[2]))))
        for data, label, color, style in [(loop, 'Cadence / mapped widths', '#136f9a', '-'),
                                         (histloop, 'Frozen ngspice baseline', '#d07524', '--')]:
            phase = []
            for _, value in data:
                angle = math.degrees(math.atan2(value.imag, value.real))
                if phase: angle += 360 * round((phase[-1] - angle) / 360)
                phase.append(angle)
            ax[0, 0].semilogx([f for f, _ in data], [20 * math.log10(abs(v)) for _, v in data], style, color=color, label=label)
            ax[0, 1].semilogx([f for f, _ in data], phase, style, color=color)
        ax[0, 0].axhline(0, color='.5', linewidth=.7)
        ax[0, 0].set(title='Legacy single-loop return ratio', xlabel='Frequency (Hz)', ylabel='Magnitude (dB)')
        ax[0, 0].legend(fontsize=9)
        ax[0, 1].set(title='Cadence PM: 68.79 degrees at 16.733 MHz', xlabel='Frequency (Hz)', ylabel='Unwrapped phase (degrees)')
        vi, vo = [analyze.curve(folders['P01_step'], name) for name in ['VINP', 'VOUT']]
        for axis, edge, lower, upper, title in [(ax[1, 0], 1e-6, .98e-6, 1.17e-6, 'Rising step: 74.10 mV overshoot'),
                                              (ax[1, 1], 3.02e-6, 3e-6, 3.19e-6, 'Falling step: 40.92 ns settling (1%)')]:
            for data, label, color, style in [(vi, 'Input', '.5', ':'), (vo, 'Cadence', '#136f9a', '-')]:
                selected = [(t, v.real) for t, v in data if lower <= t <= upper]
                axis.plot([(t - edge) * 1e9 for t, _ in selected], [v for _, v in selected], style, color=color, label=label)
            selected = [(t, v) for t, _, v in historical if lower <= t <= upper]
            axis.plot([(t-edge)*1e9 for t,_ in selected], [v for _,v in selected], '--', color='#d07524', label='ngspice')
            axis.set(title=title, xlabel='Time from input edge start (ns)', ylabel='Voltage (V)')
            axis.legend(fontsize=8)
        for axis in ax.flat: axis.grid(True, alpha=.2)
        fig.suptitle('Legacy OTA: returned simulation evidence | TT, 1.8 V, 27 C, 5 pF || 100 kohm', fontsize=13)
        fig.savefig(HERE / 'nominal_comparison.png', dpi=170)
        fig.savefig(HERE / 'nominal_comparison.pdf')
        plt.close(fig)
        print(json.dumps(dict(status=review['status'], remaining_pvt_jobs=len(pvt_jobs),
            rows={k: r['csv_rows'] for k, r in records.items()}, historical_step=old_step), indent=2))


if __name__ == '__main__':
    main()
