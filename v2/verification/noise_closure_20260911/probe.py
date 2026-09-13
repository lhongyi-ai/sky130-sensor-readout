#!/usr/bin/env python3
"""Four bounded native-ngspice runs, one worker; no injected circuit noise.

The RC noise flags test native resistor and Verilog-A white_noise in .noise
versus .tran. notrnoise is a documented TRNOISE-source switch, NOT an intrinsic
MOS-noise enable. Its scope is deliberately recorded; no TRNOISE source exists.
The real SKY130 NFET and all its PDK parameters are unchanged in every case.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PDK = Path('/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice')
DEVICE = 'm.xm.msky130_fd_pr__nfet_01v8'
CASES = [('off_seed11', 11, False), ('on_seed11', 11, True),
         ('replay_seed11', 11, True), ('on_seed29', 29, True)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounded(cmd, folder, name, timeout):
    start = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=folder, capture_output=True, text=True,
                           timeout=timeout)
        result = dict(returncode=p.returncode, timeout=False)
        output = p.stdout + p.stderr
    except subprocess.TimeoutExpired as exc:
        result = dict(returncode=None, timeout=True)
        def decoded(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else (value or '')
        output = decoded(exc.stdout) + decoded(exc.stderr)
    (folder / (name+'.log')).write_text(output)
    result['elapsed_s'] = time.monotonic() - start
    return result


def worker(folder, module, seed, enable):
    import ngspyce as ns
    import numpy as np
    folder.mkdir(exist_ok=True)
    original = f'''Intrinsic noise capability: native RC, OSDI RC, unchanged SKY130 NFET
.lib {PDK} tt
.param mc_mm_switch=0 mc_pr_switch=0
VDD vdd 0 1.8
VG gate 0 DC .7 AC 1
RLOAD vdd out 20k
CLOAD out 0 1p
XM out gate 0 0 sky130_fd_pr__nfet_01v8 W=2 L=1
VRC in 0 DC 0 AC 1
RRC in rc_native 10k noisy={int(enable)}
CRC rc_native 0 1n
NRC in rc_osdi thermal
CVA rc_osdi 0 1n
.model thermal closure_thermal_resistor r=10000 noisy={int(enable)}
.temp 27
.end
'''
    source = folder/'control.spice'
    source.write_text(original)
    interface_messages = list(ns.cmd('osdi '+str(module)))
    ns.cmd('setseed '+str(seed))
    ns.cmd(('unset' if enable else 'set')+' notrnoise')
    ns.source(str(source))
    ns.cmd('set numdgt=17')
    ns.operating_point()
    model_lines = list(ns.cmd('showmod '+DEVICE))
    result = {
        'rc_noise_enabled':enable, 'seed':seed,
        'notrnoise_switch_scope':'independent TRNOISE sources only; none present',
        'mos_intrinsic_transient_enable_available':False,
        'no_external_noise_source':True,
        'original_model_implementation':model_lines[0],
        'original_model_version':next(l.split()[1] for l in model_lines if l.split()[0]=='version'),
        'original_selected_bin':next(l.split()[1] for l in model_lines if l.split()[0]=='model'),
        'op':{k:float(ns.vector(k)[0]) for k in ['out','vdd#branch','rc_native','rc_osdi']},
        'osdi_load_messages':interface_messages,
        'pdk_sha256':sha(PDK), 'pdk_resolved_path':str(PDK.resolve()),
        'input_sha256':sha(source), 'noise':{},
    }
    # A small DC sweep verifies the original NFET conducts; it is not a PVT sweep.
    ns.cmd('dc vg .6 .8 .02')
    np.savez(folder/'dc.npz',gate=np.real(ns.vector('v-sweep')).copy(),
             output=np.real(ns.vector('out')).copy(),current=np.real(ns.vector('vdd#branch')).copy())
    ns.cmd('ac dec 100 1 100meg')
    np.savez(folder/'ac.npz',frequency=np.real(ns.vector('frequency')).copy(),
             out=ns.vector('out').copy(),rc_native=ns.vector('rc_native').copy(),
             rc_osdi=ns.vector('rc_osdi').copy())
    for i,(node,source_name) in enumerate([('out','vg'),('rc_native','vrc'),('rc_osdi','vrc')]):
        ns.cmd(f'noise v({node}) {source_name} dec 100 1 100meg')
        ns.cmd(f'setplot noise{2*i+1}')
        frequency=np.real(ns.vector('frequency')).copy()
        spectrum=np.real(ns.vector('onoise_spectrum')).copy()
        np.savez(folder/(node+'_noise.npz'),frequency=frequency,amplitude_spectrum=spectrum)
        result['noise'][node]={'known_band_hz':[float(frequency[0]),float(frequency[-1])],
            'rms_v':float(np.sqrt(np.trapezoid(spectrum**2,frequency)))}
    ns.cmd('tran 100n 2m 0 100n')
    t=np.real(ns.vector('time')).copy()
    arrays={'time':t}
    result['transient']={}
    uniform=np.arange(100e-6,2e-3,100e-9)
    for node in ['out','rc_native','rc_osdi']:
        v=np.real(ns.vector(node)).copy(); arrays[node]=v
        sampled=np.interp(uniform,t,v)
        result['transient'][node]={'std_v':float(np.std(sampled)),
            'peak_to_peak_v':float(np.ptp(sampled)),
            'uniform_sample_sha256':hashlib.sha256(sampled.tobytes()).hexdigest()}
    np.savez_compressed(folder/'tran.npz',**arrays)
    result['transient_end_s']=float(t[-1])
    # Seed positive control is a disconnected software vector, never wired into
    # any circuit. This only verifies setseed, not physical noise generation.
    ns.cmd('setseed '+str(seed))
    ns.cmd('let rng_control = sgauss(vector(16))')
    rng=ns.vector('rng_control').copy()
    result['disconnected_rng_control']={
        'sha256':hashlib.sha256(rng.tobytes()).hexdigest(),
        'values':rng.tolist(), 'not_a_circuit_noise_source':True}
    # Test the requested command spelling without claiming an undocumented option.
    result['noisetran_command_response']=list(ns.cmd('noisetran 100n 1u'))
    result['status']='CONTROL_RUN_COMPLETE_NOT_INTRINSIC_TRANSIENT_NOISE_QUALIFIED'
    (folder/'summary.json').write_text(json.dumps(result,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',type=Path)
    parser.add_argument('--module',type=Path)
    parser.add_argument('--seed',type=int)
    parser.add_argument('--enabled',type=int)
    args=parser.parse_args()
    for name in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
        os.environ[name]='1'
    if args.worker:
        worker(args.worker,args.module,args.seed,bool(args.enabled));return
    tag=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
    out=HERE/'results'/tag;out.mkdir(parents=True)
    runtime=Path(tempfile.mkdtemp(prefix='sky130_noise_closure_osdi_'))
    module=runtime/'thermal.osdi'
    compile_result=bounded(['openvaf',str(HERE/'thermal_resistor.va'),'-o',str(module)],out,'compile',60)
    report={'created_utc':tag,'compile':compile_result,'runs':[],
        'script_sha256':sha(__file__),'va_source_sha256':sha(HERE/'thermal_resistor.va'),
        'run_count_limit':4,'per_run_timeout_s':180,'worker_limit':1,
        'adc_noise_qualified':False,'full_chain_sndr_qualified':False}
    if compile_result['returncode']==0:
        report['compiled_module_runtime_path']=str(module)
        report['compiled_module_sha256']=sha(module)
        for name,seed,enable in CASES:
            folder=out/name;folder.mkdir()
            status=bounded([sys.executable,__file__,'--worker',str(folder),
                            '--module',str(module),'--seed',str(seed),
                            '--enabled',str(int(enable))],folder,'worker',180)
            report['runs'].append({'case':name,'run':status})
            # No blind retry, and no wasted later runs after a fixture failure.
            if status['returncode']!=0:break
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
