#!/usr/bin/env python3
"""One serial simulation: two uncoupled, DC-preserving scalar loop probes."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import numpy as np
from run_diagnostic import HERE,FRONT,make_source,replace_once,save,sha
sys.path.insert(0,str(FRONT))
from measurement_evidence import write_manifest


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--variant',required=True)
    p.add_argument('--gain',type=int,choices=[1,4,16],required=True)
    a=p.parse_args()
    results=HERE/'diagnostics';results.mkdir(exist_ok=True)
    count=sum(path.is_dir() for path in results.iterdir())
    if count>=8:raise ValueError('Eight-diagnostic budget exhausted')
    folder=results/f'{count+1:02d}_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}_{a.variant}_g{a.gain}_loops'
    folder.mkdir()
    source=make_source(a.variant)
    (folder/'frontend_pdk_snapshot.spice').write_text(source)
    (folder/'runner_snapshot.py').write_bytes(Path(__file__).read_bytes())
    (folder/'helper_snapshot.py').write_bytes((HERE/'run_diagnostic.py').read_bytes())
    s=replace_once(source,'.subckt sky130_v2_fdda INP INN FBP FBN OUTP OUTN VDD VSS VCM BYP BYPB',
                   '.subckt sky130_v2_fdda INP INN FBP FBN OUTP OUTN VDD VSS VCM BYP BYPB params: CMAC=0')
    s=replace_once(s,'XCMSENSE CMCTL CMSENSE CMSS VSS sky130_fd_pr__nfet_01v8',
                   'VTESTCM ICMSENSE CMSENSE dc 0 ac {CMAC}\nXCMSENSE CMCTL ICMSENSE CMSS VSS sky130_fd_pr__nfet_01v8')
    s=replace_once(s,'.subckt sky130_v2_switchable_pga VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1',
                   '.subckt sky130_v2_switchable_pga VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1 params: CMAC=0 DMAC=0')
    s=replace_once(s,'XAMP VINP VINN FBP FBN OUTP OUTN VDD VSS VCM E1 E1B sky130_v2_fdda',
                   'VTESTP IFBP FBP dc 0 ac {DMAC*.5}\nVTESTN IFBN FBN dc 0 ac {-DMAC*.5}\n'
                   'XAMP VINP VINN IFBP IFBN OUTP OUTN VDD VSS VCM E1 E1B sky130_v2_fdda CMAC={CMAC}')
    (folder/'measurement_injections.spice').write_text(s)
    deck='''Two uncoupled scalar loop probes, NOT two-chip circuit implementation
.lib /foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice tt
.include measurement_injections.spice
.temp 27
.options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18
VDD VDD 0 1.8
VCM VCM 0 .9
VIP SP 0 .9
VIN SN 0 .9
'''
    deck+=f'VSEL0 SEL0 0 {1.8 if a.gain==4 else 0}\nVSEL1 SEL1 0 {1.8 if a.gain==16 else 0}\n'
    for mode in ('cm','dm'):
        deck+=f'''RSP_{mode} SP IP_{mode} 350
RSN_{mode} SN IN_{mode} 350
XPGA_{mode} IP_{mode} IN_{mode} OP_{mode} ON_{mode} VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga CMAC={int(mode=='cm')} DMAC={int(mode=='dm')}
XRIP_{mode} OP_{mode} FP_{mode} 0 frontend_r R=2600
XRIN_{mode} ON_{mode} FN_{mode} 0 frontend_r R=2600
XCFP_{mode} FP_{mode} 0 frontend_c4p
XCFN_{mode} FN_{mode} 0 frontend_c4p
CLP_{mode} FP_{mode} 0 81.285p
CLN_{mode} FN_{mode} 0 81.285p
'''
    deck+='''.control
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
op
wrdata op.dat v(op_cm) v(on_cm) v(op_dm) v(on_dm)
ac dec 100 1 1g
let cm_loop=-v(xpga_cm.xamp.cmsense)/v(xpga_cm.xamp.icmsense)
let dm_loop=-(v(xpga_dm.fbp)-v(xpga_dm.fbn))/(v(xpga_dm.ifbp)-v(xpga_dm.ifbn))
let cmr=real(cm_loop)
let cmi=imag(cm_loop)
let dmr=real(dm_loop)
let dmi=imag(dm_loop)
wrdata loops.dat cmr cmi dmr dmi
quit
.endc
.end
'''
    (folder/'bench.spice').write_text(deck)
    save(folder/'experiment_config.json',vars(a))
    report={'status':'RUNNING','ordinal':count+1,'diagnostic_budget':8,'gain':a.gain,
            'source_sha256':sha(folder/'frontend_pdk_snapshot.spice'),
            'scope':'One AC solve of two isolated copies of the same physical core, one with differential injection and one with common-mode injection; ideal test sources preserve DC operating points.',
            'full_frontend_qualified':False,'full_chip_qualified':False,'formal_multiloop_stability_signoff':False}
    started=time.monotonic()
    env=dict(os.environ,SPICE_USERINIT_DIR='/foss/pdks/sky130A/libs.tech/ngspice',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with (folder/'console.txt').open('x') as stream:
        proc=subprocess.Popen(['ngspice','-b','-o','simulator.log','bench.spice'],cwd=folder,env=env,
                              stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=2)
            report['status']='TIMEOUT_INCOMPLETE'
    report.update(returncode=proc.returncode,elapsed_s=time.monotonic()-started)
    log=(folder/'simulator.log').read_text(errors='replace')
    if report['status']=='RUNNING' and (proc.returncode or 'error:' in log.lower() or 'ngspice-47 done' not in log):report['status']='SIMULATION_FAILED'
    if report['status']=='RUNNING':
        data=np.loadtxt(folder/'loops.dat',skiprows=1)
        if not np.isfinite(data).all() or data[0,0]!=1 or abs(data[-1,0]-1e9)>1:
            report['status']='INVALID_OR_INCOMPLETE_DATA'
        else:
            report['status']='DIAGNOSTIC_COMPLETE';report['loops']={}
            for mode,j in [('cm',1),('dm',3)]:
                f=data[:,0];z=data[:,j]+1j*data[:,j+1]
                db=20*np.log10(abs(z));phase=np.unwrap(np.angle(z))*180/np.pi
                phase-=360*np.round(phase[0]/360)
                crossings=[]
                for k in np.flatnonzero(db[:-1]*db[1:]<0):
                    frac=-db[k]/(db[k+1]-db[k]);angle=phase[k]+frac*(phase[k+1]-phase[k])
                    crossings.append({'frequency_hz':float(10**(np.log10(f[k])+frac*np.log10(f[k+1]/f[k]))),
                                      'phase_deg':float(angle),'scalar_phase_margin_deg':float(180+angle),
                                      'direction':'down' if db[k]>0 else 'up'})
                report['loops'][mode]={'low_frequency_gain_db':float(db[0]),'low_frequency_phase_deg':float(phase[0]),
                    'unity_crossings':crossings,'scalar_downcrossings_meet_60deg':bool(crossings and any(c['direction']=='down' for c in crossings) and
                      all(c['scalar_phase_margin_deg']>=60 for c in crossings if c['direction']=='down'))}
    report['limitations']=['Opposite loop remains connected; no independent open-loop RHP pole count.',
                          'Scalar voltage injection needs a useful unidirectional partition; this is diagnostic, not full loop or PEX qualification.',
                          'No switching, noise, mismatch or PVT signoff.']
    save(folder/'summary.json',report)
    write_manifest(folder,['frontend_pdk_snapshot.spice','measurement_injections.spice','bench.spice','summary.json'],[Path(__file__),HERE/'run_diagnostic.py'])
    print(json.dumps({'summary_path':str(folder/'summary.json'),**report},indent=2),flush=True)


if __name__=='__main__':main()
