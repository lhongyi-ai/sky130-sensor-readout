"""Audit returned extra tests. No simulator launch or edits to received evidence."""
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
import struct
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
RECEIVED = HERE / 'received'
PREVIOUS = BASE / 'reports/basic_20260913T023544Z_5cc09eef'
REPORT_SHA = '413e1edf9477d189f043045c2c49c17ef7900432de9b4e5962b545ee78822c27'
spec = importlib.util.spec_from_file_location('prior', BASE / 'reports/basic_20260913T015701Z_582c6ec8/review_nominal.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, read, same = prior.sha, prior.read, prior.same_calculation


def table(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def write_table(name, rows):
    with (HERE / name).open('w') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def noise_units(path):
    """Check this report's explicit binary PSF type/trace metadata, not data guesses.

    Bounded assertions for the observed file only; not a general PSF parser.
    A type record names V/sqrt(Hz), and both in/out trace records reference it.
    """
    data = path.read_bytes()
    u32 = lambda n: struct.pack('>I', n)
    name = lambda s: u32(len(s)) + s.encode() + b'\0' * (-len(s) % 4)
    type_prefix = u32(16) + u32(0xf1) + name('V/sqrt(Hz)')
    assert data.count(type_prefix) == 1
    pos = data.index(type_prefix)
    assert name('units') + name('V/sqrt(Hz)') in data[pos:pos+150]
    trace_offsets = {}
    for signal, ident in [('out', 0x172), ('in', 0x173)]:
        record = u32(16) + u32(ident) + name(signal) + u32(0xf1)
        assert data.count(record) == 1
        trace_offsets[signal] = data.index(record)
    return dict(units='V/sqrt(Hz)', type_id=0xf1, type_offset=pos,
                trace_offsets=trace_offsets, psf_sha256=sha(path))


def main():
    archive = HERE / 'project1_basic_report_20260913T062632Z_d7dc1ae6.zip'
    assert sha(archive) == REPORT_SHA
    with zipfile.ZipFile(archive) as z:
        for n in z.namelist():
            if not n.endswith('/'):
                assert (RECEIVED / n).read_bytes() == z.read(n)
    with zipfile.ZipFile(PREVIOUS / 'project1_basic_report_20260913T023544Z_5cc09eef.zip') as z:
        preserved = [n for n in z.namelist() if n.startswith('runs/') and not n.endswith('/')]
        assert all((RECEIVED / n).read_bytes() == z.read(n) for n in preserved)
    history = HERE / 'historical_context'
    for n, item in read(history / 'source_manifest.json').items():
        assert sha(history / n) == item['sha256']
    manifest = read(history / 'day4_manifest.json')
    for p in history.glob('*.csv'):
        assert all(r['manifest_sha256'] == manifest['manifest_sha256'] for r in table(p))

    with tempfile.TemporaryDirectory(prefix='p1_extra_review_') as temp:
        temp = Path(temp)
        with zipfile.ZipFile(BASE / 'releases/project1_basic_design_v1.0.4.zip') as z:
            z.extractall(temp)
        root = temp / 'project1_handoff/basic_design_v1_0_4'
        for ver in ['v1_0_4p1', 'v1_0_4p2', 'v1_0_4p3']:
            for p in (BASE / 'runtime_fixes' / ver / 'payload').iterdir():
                if p.is_file(): shutil.copy2(p, root / p.name)
        assert sha(root / 'package_manifest.json') == sha(RECEIVED / 'package_manifest.json')
        assert read(root / 'reference/day4_manifest.json') == manifest
        sys.path.insert(0, str(root))
        import run
        import analyze
        run.verify()
        cfg, design = read(RECEIVED / 'site.json'), read(root / 'design.json')
        jobs = {j['id']:j for j in read(root / 'jobs.json')}
        selected = [j for j in jobs.values() if j['group'] == 'extra']
        assert len(selected) == 32
        records, folders, curves, cores = {}, {}, {}, set()
        for job in selected:
            ident = job['id']
            attempts = list((RECEIVED / 'runs' / ident).glob('*/status.json'))
            assert len(attempts) == 1
            folder = attempts[0].parent
            folders[ident] = folder
            state = read(folder / 'status.json')
            assert state['job'] == job and state['site'] == cfg
            assert state['package_sha256'] == sha(root / 'package_manifest.json')
            assert state['status'] == state['simulation_status'] == state['export_status'] == 'PASS'
            native = (folder / 'native_netlist.scs').read_text()
            assert run.check(native, design, job['cell'], job['params']) == read(folder / 'netlist_audit.json')
            body = run.netlist_body(native)
            core = re.search(r'subckt p1b_ota_legacy_r4\b.*?ends p1b_ota_legacy_r4', body, re.S).group()
            cores.add(hashlib.sha256(core.encode()).hexdigest())
            assert run.deck(job, body, cfg) == (folder / 'input.scs').read_text()
            assert sha(folder / 'native_netlist.scs') == state['native_netlist_sha256']
            assert sha(folder / 'input.scs') == state['input_sha256']
            selection = read(folder / 'native_selection.json')
            assert sha(folder / 'native_input.scs') == selection['returned_input_sha256']
            assert sha(folder / 'native_netlist.scs') == selection['selected_body_sha256']
            log = (folder / 'spectre.out').read_text()
            audit = read(folder / 'log_audit.json')
            assert run.log_audit(log, audit['exit_code']) == audit and audit['status'] == 'PASS'
            ending = re.search(r'completes with (\d+) errors, (\d+) warnings, and (\d+) notices', log, re.I)
            assert ending and ending.group(1,2) == ('0','0')
            # Numeric OCEAN exit was not separately saved. Check recorded success,
            # marker, error log scan, and exported content, without inventing one.
            run.validate_export(folder, job, 0)
            metrics = analyze.analyze(folder, job)
            assert same(metrics, read(folder / 'metrics.json'))
            assert state['performance_status'] == metrics['status']
            signals = {'ac':['VINP','VINN','VOUT','VSS','VDD'], 'step':['VINP','VOUT'],
                       'swing':['VINP','VOUT'], 'noise':['in','out']}[job['analysis']]
            waves = {s:analyze.curve(folder,s) for s in signals}
            curves[ident] = waves
            axis = [x for x,_ in waves[signals[0]]]
            assert all([x for x,_ in c] == axis for c in waves.values())
            if job['analysis'] in ['ac','noise']:
                count, start_log, per_dec = (1081,0,120) if job['analysis']=='ac' else (501,1,100)
                assert len(axis) == count
                assert all(abs(math.log10(x)-start_log-i/per_dec)<1e-10 for i,x in enumerate(axis))
            elif job['analysis'] == 'step':
                assert axis[0] == 0 and abs(axis[-1]-5e-6)<1e-15
                assert max(b-a for a,b in zip(axis,axis[1:])) <= .5e-9*(1+1e-8)
            else:
                assert len(axis)==181 and all(abs(x-i*.01)<1e-12 for i,x in enumerate(axis))
            records[ident] = dict(job=job, attempt=folder.name, metrics=metrics,
                status=state['status'],performance_status=metrics['status'],samples=len(axis),
                errors=0,warnings=0,notices=int(ending.group(3)),
                suppressed_notices=[int(n) for n in re.findall(r'(\d+) notices suppressed',log)],
                gmin_notice='GminDC' in log,bad_pivot_notice='Bad pivoting' in log,
                model_entry_sha256=state['model_entry_sha256'],
                evidence_sha256={p.name:sha(p) for p in folder.iterdir() if p.is_file()})
        previous = read(PREVIOUS / 'review.json')
        assert cores == {previous['identical_core_netlist_sha256']}
        assert {r['model_entry_sha256'] for r in records.values()} == {previous['records']['P01_op']['model_entry_sha256']}

        # Preserve the package's labels; independently apply original Day 4 ICMR
        # rules to existing points. A 100-mV grid cannot locate 10-mV endpoints.
        nominal_gain = records['icmr_09']['metrics']['gain_dB']
        icmr = []
        for i in range(19):
            ident = 'icmr_%02d' % i
            r = records[ident]; m = r['metrics']; vcm = r['job']['params']['VCM']
            vp, vn = curves[ident]['VINP'][0][1], curves[ident]['VINN'][0][1]
            criteria = dict(gain_within_minus_3dB=m['gain_dB']>=nominal_gain-3,
                actual_differential_stimulus=math.isclose(abs(vp-vn),1,rel_tol=1e-6,abs_tol=1e-6),
                devices_saturated=m['min_saturation_margin_V']>=0,
                output_guard=.05<m['dc_nodes']['VOUT']<1.75,
                tracking_10mV=abs(m['dc_nodes']['VOUT']-vcm)<=.01)
            icmr.append(dict(VCM_V=vcm, package_status=m['status'],
                historical_criteria_at_sample='PASS' if all(criteria.values()) else 'FAIL',
                gain_dB=m['gain_dB'],gain_delta_dB=m['gain_dB']-nominal_gain,
                VOUT_V=m['dc_nodes']['VOUT'],min_saturation_margin_V=m['min_saturation_margin_V'],
                failed_historical_criteria=';'.join(k for k,v in criteria.items() if not v),
                nonsaturated_devices=';'.join(k for k,v in m['device_saturation_margin_V'].items() if v<=0)))
        assert [round(r['VCM_V'],10) for r in icmr if r['historical_criteria_at_sample']=='PASS'] == [.8,.9,1.,1.1,1.2]

        loads=[]
        old_load={float(r['CL_pF']):r for r in table(history/'day4_load_stability.csv')}
        for cl in [1,2,5,10,20]:
            loop = previous['records']['P01_loop']['metrics'] if cl==5 else records['load_%dp_loop'%cl]['metrics']
            step = previous['records']['P01_step']['metrics'] if cl==5 else records['load_%dp_step'%cl]['metrics']
            loads.append(dict(CL_pF=cl,pm_deg=loop['pm_deg'],ugb_MHz=loop['ugb_MHz'],loop_status=loop['status'],
                step_status=step['status'],settling_ns=step['worst_settling_us']*1000,
                rise_overshoot_mV=step['rise_overshoot_mV'],fall_overshoot_mV=step['fall_overshoot_mV'],
                historical_pm_deg=float(old_load[cl]['pm_deg']) if cl in old_load else None))

        units = noise_units(folders['nom_noise']/'psf/noise.noise')
        noise = dict(metadata=units,measurement_scope='Stationary small-signal; VINP-referred, VINN AC-grounded; not switched ADC noise')
        for sig,wave in curves['nom_noise'].items():
            assert all(v.imag==0 and v.real>=0 for _,v in wave)
            noise[sig+'_at_1k_V_per_sqrtHz'] = wave[200][1].real
            area = math.fsum((a.real**2+b.real**2)/2*(y-x) for (x,a),(y,b) in zip(wave,wave[1:]))
            noise[sig+'_10Hz_1MHz_Vrms'] = math.sqrt(area)
        old_noise = table(history/'day4_noise_curve.csv')
        old_1k = min(old_noise,key=lambda r:abs(math.log10(float(r['frequency_hz'])/1000)))
        noise['historical_input_at_1k_V_per_sqrtHz'] = float(old_1k['input_noise_density_V_per_sqrtHz'])
        noise['numeric_acceptance'] = 'REPORT_ONLY_NO_FROZEN_NOISE_LIMIT'

        # The existing rejection tests do not share the P01 differential DC OP.
        # Do not label ratios using P01 gain as CMRR/PSRR measurements.
        rejection=dict(status='METHOD_INCOMPLETE', differential_VOUT_V=previous['records']['P01_ac']['metrics']['dc_nodes']['VOUT'],
            common_VOUT_V=records['nom_cm']['metrics']['dc_nodes']['VOUT'],
            raw_transfer_1k_dB={j:records[j]['metrics']['transfer_1k_dB'] for j in ['nom_cm','nom_psrrp','nom_psrrm']},
            required='Matched-OP differential measurement and explicit PSRR-minus reference/stimulus definition',
            psrr_minus_scope='VINP/VINN sources and load follow VSS; VDD held at absolute AC ground; exported VOUT is absolute-ground referenced',
            historical_psrr_minus_scope='Inputs and VDD held at absolute AC ground; not the same stimulus')
        swing=dict(status='METHOD_INCOMPLETE',points=181,
            output_min_V=records['nom_swing']['metrics']['output_min_V'],output_max_V=records['nom_swing']['metrics']['output_max_V'],
            scope='Forward unity-follower DC transfer with moving input common mode',
            missing='Original fixed-common-mode inverting test (equal 10-Mohm feedback/input resistors), reverse sweep and per-point M6/M7 operating points',
            caveat='Low-input GminDC notices and 207 suppressed notices; output extrema are not qualified output swing')
        counts=dict(collections.Counter(r['performance_status'] for r in records.values()))
        assert counts=={'REVIEW_REQUIRED':5,'PASS':13,'FAIL':14}
        jobs_executed=[]
        for ident in jobs:
            states=[read(p) for p in (RECEIVED/'runs'/ident).glob('*/status.json')]
            assert any(s['status']=='PASS' for s in states)
            jobs_executed.append(ident)
        assert len(jobs_executed)==87
        summary=dict(source_report_sha256=REPORT_SHA,data_integrity_status='PASS',new_jobs=32,
            execution_pass=32,returned_performance_counts=counts,package_sha256=sha(root/'package_manifest.json'),
            previous_run_files_preserved=len(preserved),all_87_entrypoints_executed=True,
            original_acceptance_complete=False,core_netlist_sha256=next(iter(cores)),
            icmr=icmr,load_comparison=loads,noise=noise,rejection=rejection,swing=swing,records=records,
            retained_pvt_failures=previous['failed_jobs'],local_simulator_execution=False,
            limitations=['School native OA database and PDK dependencies were not accessed locally.',
                'No received labels, thresholds, design source, released package or runtime were changed.',
                'Extra ICMR automatic labels use a 50-dB floor, not original minus-3-dB range qualification.',
                'No original ICMR fine-grid endpoints, full output-swing or matched-OP rejection acceptance yet.',
                'No frontend/ADC, statistical, layout or 45-condition final-system qualification.'])
        (HERE/'review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        write_table('load_comparison.csv',loads)
        write_table('icmr_criteria_comparison.csv',icmr)
        write_table('extra_results.csv',[dict(job=j,execution=r['status'],performance=r['performance_status'],
            samples=r['samples'],errors=r['errors'],warnings=r['warnings'],notices=r['notices'],
            failed_criteria=';'.join(k for k,v in r['metrics']['criteria'].items() if not v)) for j,r in records.items()])

        os.environ['MPLCONFIGDIR']=str(temp/'matplotlib')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axs=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
        ax=axs[0,0]
        ax.plot([r['CL_pF'] for r in loads],[r['pm_deg'] for r in loads],'o-',color='#156887',label='Cadence')
        ax.plot([1,2,5],[float(old_load[x]['pm_deg']) for x in [1,2,5]],'x',color='#cf8820',label='Historical ngspice')
        ax.axhline(55,color='#bc4141',linestyle='--',label='Old OTA limit: 55 deg')
        ax.set(xlabel='Load capacitance (pF)',ylabel='Phase margin (deg)',title='10 pF and 20 pF fail the margin limit',xticks=[1,2,5,10,20])
        ax.legend(fontsize=8)
        ax=axs[0,1]
        for cl in [1,2,10,20]:
            wave=curves['load_%dp_step'%cl]['VOUT']
            ax.plot([t*1e6 for t,_ in wave],[v.real for _,v in wave],label=f'{cl} pF')
        vi=curves['load_1p_step']['VINP']
        ax.plot([t*1e6 for t,_ in vi],[v.real for _,v in vi],'k--',linewidth=1,label='Input')
        ax.set(xlim=(.98,1.45),ylim=(.77,1.34),xlabel='Time (us)',ylabel='Voltage (V)',title='All four steps settle; margin is a separate requirement')
        ax.legend(fontsize=8,ncol=3)
        ax=axs[1,0]
        ax.plot([r['VCM_V'] for r in icmr],[r['gain_dB'] for r in icmr],'.-',label='Cadence 0.1-V grid')
        old_icmr=table(history/'day4_icmr_sweep.csv')
        ax.plot([float(r['vcm_V']) for r in old_icmr],[float(r['gain_dB']) for r in old_icmr],'--',color='#cf8820',linewidth=1,label='Historical 0.01-V grid')
        ax.axhline(50,color='.5',linestyle=':',label='Package screen: 50 dB')
        ax.axhline(nominal_gain-3,color='#bc4141',linestyle='--',label='Original: nominal minus 3 dB')
        valid=[r for r in icmr if r['historical_criteria_at_sample']=='PASS']
        ax.scatter([r['VCM_V'] for r in valid],[r['gain_dB'] for r in valid],color='#238858',s=45,label='Pass original rules at sampled point',zorder=4)
        ax.set(xlabel='Input common-mode voltage (V)',ylabel='Low-frequency gain (dB)',title='Original rules pass sampled points 0.8 to 1.2 V')
        ax.legend(fontsize=7,loc='lower center')
        ax=axs[1,1]
        wave=curves['nom_noise']['in']
        ax.loglog([f for f,_ in wave],[v.real*1e9 for _,v in wave],label='Cadence')
        ax.loglog([float(r['frequency_hz']) for r in old_noise],[float(r['input_noise_density_V_per_sqrtHz'])*1e9 for r in old_noise],'--',color='#cf8820',label='Historical ngspice')
        ax.set(xlabel='Frequency (Hz)',ylabel='Input noise density (nV / sqrt(Hz))',title='Stationary noise: 401.15 nV/sqrt(Hz) at 1 kHz')
        ax.legend(fontsize=8)
        for ax in axs.flat:ax.grid(True,alpha=.2)
        fig.suptitle('Legacy OTA extra characterization | TT / 1.8 V / 27 C\nReturned data reviewed; full original acceptance remains incomplete',fontsize=13)
        fig.savefig(HERE/'extra_characterization.png',dpi=170)
        fig.savefig(HERE/'extra_characterization.pdf')
        plt.close(fig)
        print(json.dumps({k:summary[k] for k in ['data_integrity_status','new_jobs','execution_pass','returned_performance_counts','previous_run_files_preserved','all_87_entrypoints_executed','original_acceptance_complete']},indent=2))
        print(json.dumps(noise,indent=2))


if __name__=='__main__':main()
