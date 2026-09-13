#!/usr/bin/env python3
"""At most eight serial, frozen device-headroom/DC/step diagnoses; not signoff."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
FRONT = HERE.parent
BASE = FRONT/'repair_20260910/results/20260910T062811944809Z_cascoded_tail_g16/candidate.spice'
BASE_SHA = '564f4776c4c61872de63648816ef5aaf51555769edeca326042f287880ae1a3c'
sys.path.insert(0, str(FRONT))
from measurement_evidence import write_manifest, verify_manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Expected exactly one source marker: '+before)
    return source.replace(before, after)


def make_source(variant):
    if sha(BASE) != BASE_SHA:
        raise ValueError('Frozen baseline has changed')
    source = BASE.read_text()
    if variant != 'baseline':
        source = (HERE/'candidates'/f'{variant}.spice').read_text()
    return source


def device_vectors(source):
    model = 'nfet_01v8_lvt' if 'XP1 DP IP TAIL VSS sky130_fd_pr__nfet_01v8_lvt' in source else 'nfet_01v8'
    devices = {f'xerr{s}.{d}': model if d in ('xp1','xn1') else 'nfet_01v8'
               for s in ('p','n') for d in ('xp1','xn1','xt0','xtc0')}
    devices.update({d:'nfet_01v8' for d in ('xop','xon','xcmref','xcmsense','xcmt','xbn1','xbtd','xcasp','xcasn')})
    devices.update({d:'pfet_01v8' for d in ('xlp','xln','xpcasp','xpcasn','xip','xin','xbp1','xcasbp')})
    if 'XCASBP BCASC' not in source:
        devices.pop('xcasbp')
    fields = ('id','gm','gds','vds','vdsat','vgs','vth')
    return {f'{name}.{field}':f'@m.xpga.xamp.{name}.msky130_fd_pr__{mod}[{field}]'
            for name,mod in devices.items() for field in fields}


def build_deck(a, source, vectors):
    nodes = ['v(sp)','v(sn)','v(op)','v(on)','v(xpga.xamp.xp)','v(xpga.xamp.xn)',
             'v(xpga.xamp.npc)','v(xpga.xamp.nnc)','v(xpga.xamp.xerrp.tail)',
             'v(xpga.xamp.xerrn.tail)','v(xpga.xamp.xerrp.ts)','v(xpga.xamp.xerrn.ts)',
             'v(xpga.xamp.bn)','v(xpga.xamp.bt)','v(xpga.xamp.bcasc)',
             'v(xpga.xamp.cmctl)','i(vdd)','i(vcm)']
    waveform = nodes+list(vectors.values())
    text = f'''Frozen headroom diagnosis: full-range DC and optional capacitive-load step
.lib /foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice {a.corner}
.include frontend_pdk_snapshot.spice
.temp {a.temp}
.options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18 itl1=200 itl2=200 method=gear maxord=2
VDD VDD 0 {a.vdd}
VCM VCM 0 {a.vdd/2}
VIP SP 0 PWL(0 {a.vdd/2} 2u {a.vdd/2} 2.01u {a.vdd/2+.05} 5u {a.vdd/2+.05} 5.01u {a.vdd/2} 8u {a.vdd/2} 8.01u {a.vdd/2+.18/a.gain} 13u {a.vdd/2+.18/a.gain} 13.01u {a.vdd/2-.18/a.gain} 18u {a.vdd/2-.18/a.gain} 18.01u {a.vdd/2})
VCMS CMS 0 PWL(0 0 2u 0 2.01u .1 5u .1 5.01u 0)
BIN SN 0 v={a.vdd}-v(sp)+v(cms)
RSP SP IP 350
RSN SN IN 350
VSEL0 SEL0 0 {a.vdd if a.gain==4 else 0}
VSEL1 SEL1 0 {a.vdd if a.gain==16 else 0}
XPGA IP IN OP ON VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga
XRIP OP FP 0 frontend_r R=2600
XRIN ON FN 0 frontend_r R=2600
XCFP FP 0 frontend_c4p
XCFN FN 0 frontend_c4p
CLP FP 0 81.285p
CLN FN 0 81.285p
.save {' '.join(waveform)} v(fp) v(fn)
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
op
wrdata op.dat {' '.join(waveform)}
dc VIP {a.vdd/2-.2/a.gain:.14g} {a.vdd/2+.2/a.gain:.14g} {.005/a.gain:.14g}
wrdata dc.dat {' '.join(waveform)}
'''
    if not a.dc_only:
        text += f'tran 5n 25u 0 5n\nwrdata transient.dat {" ".join(waveform)} v(fp) v(fn)\n'
    text += 'quit\n.endc\n.end\n'
    return text, ['scale']+nodes+list(vectors)


def analyze(folder, a, columns):
    data = np.loadtxt(folder/'dc.dat', skiprows=1, ndmin=2)
    if data.shape != (81, len(columns)) or not np.isfinite(data).all():
        raise ValueError('Missing/invalid full 81-point data or device vectors')
    col={key:index for index,key in enumerate(columns)}
    target=(data[:,col['v(sp)']]-data[:,col['v(sn)']])*a.gain
    if not np.allclose(target,np.linspace(-.4,.4,81),atol=1e-10,rtol=0):
        raise ValueError('Incorrect full-range DC stimulus')
    od=data[:,col['v(op)']]-data[:,col['v(on)']]
    cm=(data[:,col['v(op)']]+data[:,col['v(on)']])/2
    result={'dc_complete_81_points':True,'max_output_cm_error_v':float(np.max(abs(cm-a.vdd/2))),
            'output_endpoints_v':[float(od[0]),float(od[-1])],
            'source_r_ohm_per_side':350,'dc_load_isolation_r_ohm_per_side':2600,
            'scope':'Frontend-only deterministic DC and optional static-capacitive-load step; not SAR sampling, sampled noise, SNDR, loop phase-margin or PEX.'}
    if a.calibration_from:
        cal=json.loads((folder/'calibration_source_summary.json').read_text())
        fit=np.asarray(cal['calibration_coefficients'])
        result['calibration_source']='frozen same-source/same-gain/same-corner nominal summary'
    elif (a.vdd,a.temp)==(1.8,27):
        fit=np.polyfit(od[[8,40,72]],target[[8,40,72]],1)
        result['calibration_source']='this corner/gain nominal 1.8 V, 27 C only'
    else:
        fit=None
        result['calibration_status']='NOT_QUALIFIED_NO_SAME_CANDIDATE_NOMINAL_COEFFICIENTS'
    if fit is not None:
        hold=np.ones(81,dtype=bool); hold[[8,40,72]]=False
        residual=(od*fit[0]+fit[1]-target)/(.8/4096)
        limit=1 if (a.vdd,a.temp)==(1.8,27) else 4
        result.update(calibration_coefficients=fit.tolist(),max_holdout_error_lsb=float(np.max(abs(residual[hold]))),
                      static_accuracy_limit_lsb=limit,static_accuracy_pass=bool(np.max(abs(residual[hold]))<=limit))
    regions={}
    for device in ('xerrp.xp1','xerrp.xn1','xerrn.xp1','xerrn.xn1',
                   'xerrp.xt0','xerrp.xtc0','xerrn.xt0','xerrn.xtc0','xcasp','xcasn','xop','xon','xcmt'):
        margin=data[:,col[device+'.vds']]-data[:,col[device+'.vdsat']]
        i=int(np.argmin(margin))
        regions[device]={'min_vds_minus_vdsat_v':float(margin[i]),'worst_target_v':float(target[i]),
                         'zero_vds_minus_vdsat_v':float(margin[40]),
                         'zero_id_a':float(data[40,col[device+'.id']]),
                         'zero_gm_s':float(data[40,col[device+'.gm']]),
                         'zero_gds_s':float(data[40,col[device+'.gds']]),
                         'zero_vgs_v':float(data[40,col[device+'.vgs']]),
                         'zero_vth_v':float(data[40,col[device+'.vth']])}
    result['dc_device_headroom']=regions
    power=-a.vdd*data[:,col['i(vdd)']]-(a.vdd/2)*data[:,col['i(vcm)']]
    result['frontend_vdd_and_vcm_power_w']={'zero':float(power[40]),'max_dc_sweep':float(np.max(power))}
    if not a.dc_only:
        tr=np.loadtxt(folder/'transient.dat',skiprows=1,ndmin=2)
        t=tr[:,0]
        if not np.isfinite(tr).all() or np.any(np.diff(t)<=0) or t[0]>1e-12 or abs(t[-1]-25e-6)>1e-12:
            raise ValueError('Incomplete/invalid transient waveform')
        cm=(tr[:,col['v(op)']]+tr[:,col['v(on)']])/2
        diff=tr[:,-2]-tr[:,-1]
        windows={}
        trap=np.trapezoid if hasattr(np,'trapezoid') else np.trapz
        for name,lo,hi in [('positive',12e-6,13e-6),('negative',17e-6,18e-6),('zero',23e-6,25e-6)]:
            m=(t>=lo)&(t<=hi)
            if np.sum(m)<2:
                raise ValueError('No complete diagnostic window')
            windows[name]={'differential_mean_v':float(trap(diff[m],t[m])/(t[m][-1]-t[m][0])),
                           'differential_peak_to_peak_v':float(np.ptp(diff[m])),
                           'common_mode_peak_to_peak_v':float(np.ptp(cm[m]))}
        result['step_windows']=windows
        result['step_max_output_cm_error_v']=float(np.max(abs(cm[t>=1e-6]-a.vdd/2)))
        result['preliminary_quiet_window_gate']=bool(result['step_max_output_cm_error_v']<=.05 and
            all(max(w['differential_peak_to_peak_v'],w['common_mode_peak_to_peak_v'])<4.8828125e-6 for w in windows.values()))
        result['preliminary_step_amplitude_gate']=bool(abs(windows['positive']['differential_mean_v']-.36)<.0036 and
            abs(windows['negative']['differential_mean_v']+.36)<.0036 and abs(windows['zero']['differential_mean_v'])<.0036)
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--variant',default='baseline')
    p.add_argument('--gain',type=int,choices=[1,4,16],required=True)
    p.add_argument('--corner',choices=['tt','ff','ss','fs','sf'],default='tt')
    p.add_argument('--vdd',type=float,default=1.8)
    p.add_argument('--temp',type=float,default=27)
    p.add_argument('--dc-only',action='store_true')
    p.add_argument('--timeout',type=float,default=90)
    p.add_argument('--calibration-from',type=Path)
    a=p.parse_args()
    if not 0<a.timeout<=120:
        p.error('Owned diagnostic timeout must be in (0,120] seconds')
    results=HERE/'diagnostics'; results.mkdir(exist_ok=True)
    count=sum(path.is_dir() for path in results.iterdir())
    if count>=8:
        raise ValueError('Eight-diagnostic budget exhausted; no automatic continuation')
    folder=results/f'{count+1:02d}_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}_{a.variant}_g{a.gain}_{a.corner}'
    folder.mkdir()
    source=make_source(a.variant)
    (folder/'frontend_pdk_snapshot.spice').write_text(source)
    (folder/'runner_snapshot.py').write_bytes(Path(__file__).read_bytes())
    (folder/'measurement_evidence_snapshot.py').write_bytes((FRONT/'measurement_evidence.py').read_bytes())
    config={**vars(a),'calibration_from':str(a.calibration_from) if a.calibration_from else None}
    save(folder/'experiment_config.json',config)
    if a.calibration_from:
        calibration_path=a.calibration_from.resolve()
        if not verify_manifest(calibration_path.parent):
            raise ValueError('Calibration source requires a verified immutable manifest')
        cal=json.loads(calibration_path.read_text())
        if (cal['gain'],cal['corner'],cal['vdd_v'],cal['temp_c'])!=(a.gain,a.corner,1.8,27):
            raise ValueError('Wrong fixed calibration gain/corner/nominal condition')
        if (calibration_path.parent/'frontend_pdk_snapshot.spice').read_text()!=source:
            raise ValueError('Fixed calibration must be from identical source')
        (folder/'calibration_source_summary.json').write_bytes(calibration_path.read_bytes())
        (folder/'calibration_source_core.spice').write_text(source)
        save(folder/'calibration_source_metadata.json',{'original_path':str(calibration_path),'sha256':sha(calibration_path)})
    vectors=device_vectors(source)
    deck,columns=build_deck(a,source,vectors)
    (folder/'bench.spice').write_text(deck)
    save(folder/'columns.json',columns)
    report={'status':'RUNNING','gain':a.gain,'corner':a.corner,'vdd_v':a.vdd,'temp_c':a.temp,
            'source_sha256':sha(folder/'frontend_pdk_snapshot.spice'),'baseline_sha256':BASE_SHA,
            'ordinal':count+1,'diagnostic_budget':8,'worker_count':1,'configuration':config,
            'full_frontend_qualified':False,'full_chip_qualified':False,'noise_included':False}
    env=dict(os.environ,SPICE_USERINIT_DIR='/foss/pdks/sky130A/libs.tech/ngspice',
             OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    started=time.monotonic()
    with (folder/'console.txt').open('x') as stream:
        proc=subprocess.Popen(['ngspice','-b','-o','simulator.log','bench.spice'],cwd=folder,env=env,
                              stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            proc.wait(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM)
            try: proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=2)
            report['status']='TIMEOUT_INCOMPLETE'
    report.update(elapsed_s=time.monotonic()-started,returncode=proc.returncode)
    log=(folder/'simulator.log').read_text(errors='replace') if (folder/'simulator.log').exists() else ''
    bad=any(s in log.lower() for s in ('error:','timestep too small','simulation(s) aborted','simulation interrupted'))
    if report['status']=='RUNNING' and (proc.returncode or bad or 'ngspice-47 done' not in log):
        report['status']='SIMULATOR_FAILURE'
    # DC can finish before transient solver failure; retain it as partial diagnostic evidence.
    if (folder/'dc.dat').exists():
        try:
            report.update(analyze(folder,a,columns))
            if report['status']=='RUNNING': report['status']='DIAGNOSTIC_COMPLETE'
        except (OSError,ValueError,KeyError) as error:
            report['analysis_error']=str(error)
            if report['status']=='RUNNING': report['status']='INVALID_OR_INCOMPLETE_DATA'
    save(folder/'summary.json',report)
    write_manifest(folder,['frontend_pdk_snapshot.spice','runner_snapshot.py','experiment_config.json','bench.spice','summary.json'],
                   [Path(__file__),FRONT/'measurement_evidence.py'])
    print(json.dumps({'summary_path':str(folder/'summary.json'),**report},indent=2),flush=True)


if __name__=='__main__':
    main()
