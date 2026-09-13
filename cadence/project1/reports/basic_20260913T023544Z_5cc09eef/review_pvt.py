"""Review retained PVT data without running Cadence or changing original evidence."""
import collections
import csv
import hashlib
import importlib.util
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
REPORT_SHA = '9730a427a344b5161dc5faf99dd3c573ed76f68c86a9de8893601e1079c6a3d3'
PREVIOUS = BASE / 'reports/basic_20260913T015701Z_582c6ec8'
spec = importlib.util.spec_from_file_location('prior_review', PREVIOUS / 'review_nominal.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, read, same = prior.sha, prior.read, prior.same_calculation


def plateau(rows, lo, hi, target):
    points = [v.real for t, v in rows if lo <= t <= hi]
    assert len(points) >= 10
    average = math.fsum(points) / len(points)
    return dict(mean_V=average, error_mV=(average-target)*1000,
                peak_to_peak_mV=(max(points)-min(points))*1000, points=len(points))


def main():
    archive = HERE / 'project1_basic_report_20260913T023544Z_5cc09eef.zip'
    assert sha(archive) == REPORT_SHA
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not name.endswith('/'):
                assert (RECEIVED/name).read_bytes() == z.read(name)
    with zipfile.ZipFile(PREVIOUS/'project1_basic_report_20260913T015701Z_582c6ec8.zip') as z:
        preserved = [n for n in z.namelist() if n.startswith('runs/') and not n.endswith('/')]
        assert all((RECEIVED/n).read_bytes() == z.read(n) for n in preserved)

    with tempfile.TemporaryDirectory(prefix='p1_pvt_review_') as temp:
        temp = Path(temp)
        with zipfile.ZipFile(BASE/'releases/project1_basic_design_v1.0.4.zip') as z:
            z.extractall(temp)
        root = temp/'project1_handoff/basic_design_v1_0_4'
        for version in ['v1_0_4p1', 'v1_0_4p2', 'v1_0_4p3']:
            for p in (BASE/'runtime_fixes'/version/'payload').iterdir():
                if p.is_file(): shutil.copy2(p, root/p.name)
        assert sha(root/'package_manifest.json') == sha(RECEIVED/'package_manifest.json')
        sys.path.insert(0, str(root))
        import run
        import analyze
        run.verify()
        cfg = read(RECEIVED/'site.json')
        design = read(root/'design.json')
        jobs = {j['id']:j for j in read(root/'jobs.json')}
        selected = [j for j in jobs.values() if j['group'] in ['nominal','pvt']]
        assert len(selected) == 52
        records, waveforms, core_hashes = {}, {}, set()
        for job in selected:
            ident = job['id']
            folder = sorted((RECEIVED/'runs'/ident).glob('*/status.json'))[-1].parent
            state = read(folder/'status.json')
            assert state['job'] == job and state['site'] == cfg
            assert state['package_sha256'] == sha(root/'package_manifest.json')
            assert state['status'] == state['simulation_status'] == state['export_status'] == 'PASS'
            native = (folder/'native_netlist.scs').read_text()
            assert run.check(native, design, job['cell'], job['params']) == read(folder/'netlist_audit.json')
            body = run.netlist_body(native)
            core = re.search(r'subckt p1b_ota_legacy_r4\b.*?ends p1b_ota_legacy_r4', body, re.S).group()
            core_hashes.add(hashlib.sha256(core.encode()).hexdigest())
            assert run.deck(job, body, cfg) == (folder/'input.scs').read_text()
            assert sha(folder/'native_netlist.scs') == state['native_netlist_sha256']
            assert sha(folder/'input.scs') == state['input_sha256']
            selection = read(folder/'native_selection.json')
            assert sha(folder/'native_input.scs') == selection['returned_input_sha256']
            assert sha(folder/'native_netlist.scs') == selection['selected_body_sha256']
            log = (folder/'spectre.out').read_text()
            audit = read(folder/'log_audit.json')
            assert run.log_audit(log, audit['exit_code']) == audit and audit['status'] == 'PASS'
            ending = re.search(r'completes with (\d+) errors, (\d+) warnings, and (\d+) notices', log, re.I)
            assert ending and ending.group(1,2) == ('0','0')
            # Numeric OCEAN exit codes were not separately saved; inspect recorded
            # success, completion marker, logs and full export contents.
            run.validate_export(folder, job, 0)
            metrics = analyze.analyze(folder, job)
            assert same(metrics, read(folder/'metrics.json'))
            assert state['performance_status'] == metrics['status']
            samples = {}
            if job['analysis'] == 'ac':
                curves = [analyze.curve(folder,n) for n in ['VINP','VINN','VOUT']]
                axis = [f for f,_ in curves[0]]
                assert len(axis) == 1081 and all([f for f,_ in c] == axis for c in curves)
                assert all(abs(math.log10(f)-i/120) < 1e-10 for i,f in enumerate(axis))
                samples['ac_points'] = len(axis)
            if job['analysis'] == 'step':
                vi, vo = [analyze.curve(folder,n) for n in ['VINP','VOUT']]
                assert [t for t,_ in vi] == [t for t,_ in vo]
                assert vi[0][0] == 0 and abs(vi[-1][0]-5e-6) < 1e-15
                assert max(b[0]-a[0] for a,b in zip(vi,vi[1:])) <= .5e-9*(1+1e-8)
                assert min(v.real for _,v in vi) >= .8-1e-12 and max(v.real for _,v in vi) <= 1.2+1e-12
                samples['transient_points'] = len(vi)
                samples['high_plateau'] = plateau(vo,2.5e-6,3e-6,1.2)
                samples['low_plateau'] = plateau(vo,4.5e-6,5e-6,.8)
                waveforms[job['point']] = (vi,vo)
            records[ident] = dict(job=job, attempt=folder.name, status=state['status'],
                performance_status=metrics['status'], metrics=metrics, samples=samples,
                model_entry_sha256=state['model_entry_sha256'],
                errors=0,warnings=0,notices=int(ending.group(3)),
                bad_pivot_notice='Bad pivoting' in log,
                evidence_sha256={p.name:sha(p) for p in folder.iterdir() if p.is_file()})
        assert len(core_hashes) == 1
        assert len({r['model_entry_sha256'] for r in records.values()}) == 1

        with (root/'reference/pvt_summary.csv').open() as f:
            references = {r['point_id']:r for r in csv.DictReader(f)}
        matrix, old_waveforms, comparisons = [], {}, []
        for point in references:
            op, ac, loop, step = [records[point+'_'+name] for name in ['op','ac','loop','step']]
            ref = references[point]
            old = []
            with (root/'reference/pvt_raw'/(point+'_transient.tsv')).open() as f:
                next(f)
                for line in f: old.append(tuple(float(v) for v in line.split()[:3]))
            oldvi = [(t,complex(v)) for t,v,_ in old]
            oldvo = [(t,complex(v)) for t,_,v in old]
            old_waveforms[point] = (oldvi,oldvo)
            oldmetrics = analyze.step_metrics(oldvi,oldvo)
            assert (oldmetrics['worst_settling_us'] is None) == (ref['worst_settling_us'] == '')
            for metric in ['sr_pos_V_per_us','sr_neg_V_per_us','worst_settling_us']:
                if ref[metric]: assert math.isclose(oldmetrics[metric],float(ref[metric]),rel_tol=1e-8,abs_tol=1e-12)
            historical_settling = 'PASS' if oldmetrics['worst_settling_us'] is not None and oldmetrics['worst_settling_us'] <= 1.5 else 'FAIL'
            row = dict(point=point,corner=op['job']['corner'],voltage_V=op['job']['params']['VDD'],temp_C=op['job']['temp'],
                op=op['performance_status'],ac=ac['performance_status'],loop=loop['performance_status'],step=step['performance_status'],
                point_status='PASS' if all(r['performance_status']=='PASS' for r in [op,ac,loop,step]) else 'FAIL',
                gain_dB=ac['metrics']['gain_dB'],ugb_MHz=loop['metrics']['ugb_MHz'],pm_deg=loop['metrics']['pm_deg'],
                power_uW=op['metrics']['power_uW'],sr_pos_V_per_us=step['metrics']['sr_pos_V_per_us'],
                sr_neg_V_per_us=step['metrics']['sr_neg_V_per_us'],worst_settling_us=step['metrics']['worst_settling_us'],
                high_error_mV=step['samples']['high_plateau']['error_mV'],low_error_mV=step['samples']['low_plateau']['error_mV'],
                historical_aggregate_label=ref['pass_fail'],historical_settling_label=ref['settling_status'],
                historical_waveform_settling_review=historical_settling)
            matrix.append(row)
            if historical_settling == 'FAIL' or row['step'] == 'FAIL':
                comparisons.append(dict(point=point,cadence=step['samples'],historical=dict(
                    high_plateau=plateau(oldvo,2.5e-6,3e-6,1.2),low_plateau=plateau(oldvo,4.5e-6,5e-6,.8),
                    metrics=oldmetrics,aggregate_label=ref['pass_fail'],settling_label=ref['settling_status'])))
        new = [r for r in records.values() if r['job']['group']=='pvt']
        failed = [r['job']['id'] for r in records.values() if r['performance_status']=='FAIL']
        assert failed == ['P06_step','P07_step','P13_step']
        summary = dict(data_integrity_status='PASS',performance_status='FAIL',scope='Legacy 13-point PVT including nominal',
            source_report_sha256=REPORT_SHA,package_sha256=sha(root/'package_manifest.json'),
            identical_core_netlist_sha256=next(iter(core_hashes)),new_jobs=len(new),
            new_pass=sum(r['performance_status']=='PASS' for r in new),new_fail=sum(r['performance_status']=='FAIL' for r in new),
            total_jobs=len(records),total_pass=len(records)-len(failed),total_fail=len(failed),
            passed_points=sum(r['point_status']=='PASS' for r in matrix),failed_jobs=failed,
            previous_run_files_preserved=len(preserved),local_simulator_execution=False,
            matrix=matrix,failed_waveform_comparisons=comparisons,records=records,
            limitations=[
                'Historical aggregate PASS excludes settling; use explicit settling fields and waveform review.',
                'The three failures are stable output tracking offsets outside +/-4 mV, not failed Spectre execution.',
                'No circuit tuning, simulator-option changes, acceptance-limit changes or report overwrites were made.',
                'Local review cannot inspect installed school PDK dependencies, licenses or native OA database.',
                'OCEAN numeric exit codes are not separately saved; export success is checked against logs, markers and finite data.',
                'Width mapping and M7 split differ from the original ngspice circuit; differences are retained.',
                'No full frontend/ADC, layout, statistical, dynamic noise or 45-condition qualification.'
            ])
        (HERE/'review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        with (HERE/'pvt_comparison.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(matrix[0]));writer.writeheader();writer.writerows(matrix)

        os.environ['MPLCONFIGDIR']=str(temp/'matplotlib')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,sharey=True,constrained_layout=True)
        for axis,point in zip(axes,['P06','P07','P13']):
            row=next(r for r in matrix if r['point']==point)
            axis.axhspan(-4,4,color='#d7ecdf',alpha=.85,label='Allowed error: +/-4 mV')
            for (vi,vo),label,color,style in [(waveforms[point],'Cadence','#14668b','-'),
                                            (old_waveforms[point],'Frozen ngspice','#d18122','--')]:
                assert [t for t,_ in vi] == [t for t,_ in vo]
                axis.plot([t*1e6 for t,_ in vo],[(out.real-inp.real)*1000 for (_,out),(_,inp) in zip(vo,vi)],
                          style,color=color,label=label,linewidth=1.7)
            for t in [1,3.02]: axis.axvline(t,color='.65',linewidth=.7,linestyle=':')
            axis.set(ylim=(-12,12),xlim=(0,5),ylabel='VOUT - VINP (mV)',
                     title=f"{point} | TT, {row['voltage_V']:.2f} V, {row['temp_C']} C | high {row['high_error_mV']:+.3f} mV, low {row['low_error_mV']:+.3f} mV")
            axis.grid(True,alpha=.2)
        axes[0].legend(loc='lower center',ncol=3,fontsize=9)
        axes[-1].set_xlabel('Time (us)')
        fig.suptitle('Three settling failures: stable tracking offsets outside the allowed band\nError zoomed to +/-12 mV; large edge transients are clipped',fontsize=13)
        fig.savefig(HERE/'pvt_settling_failures.png',dpi=170)
        fig.savefig(HERE/'pvt_settling_failures.pdf')
        plt.close(fig)
        print(json.dumps({k:summary[k] for k in ['data_integrity_status','performance_status','new_jobs','new_pass','new_fail','total_jobs','total_pass','failed_jobs','passed_points']},indent=2))
        print(json.dumps(matrix,indent=2))


if __name__=='__main__':main()
