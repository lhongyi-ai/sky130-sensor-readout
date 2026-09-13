#!/usr/bin/env python3
"""Frozen, bounded common-mode repair experiments; NOT frontend signoff."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
FRONT = HERE.parent
sys.path.insert(0, str(FRONT))
from measurement_evidence import write_manifest
BASE = FRONT / 'frontend_fdda.spice'
PDK = Path('/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice')


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Expected exactly one frozen topology marker: '+before)
    return source.replace(before, after)


def candidate(source, kind):
    marker = 'XT TAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=480'
    if kind == 'long_tail':
        source = replace_once(source, marker, '\n'.join(
            f'XT{n} TAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=4 W=640' for n in range(3)))
    elif kind.startswith('cascoded_tail'):
        source = replace_once(source, marker, '''* Real wide-swing tail cascode; fixed bias generated inside each error pair.
XT0 TS BN VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=480
XT1 TS BN VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=480
XTC0 TAIL BT TS VSS sky130_fd_pr__nfet_01v8 L=1 W=800
XTC1 TAIL BT TS VSS sky130_fd_pr__nfet_01v8 L=1 W=800''')
        source = replace_once(source, '.subckt fdda_error_pair IP IM DP DM BN VSS',
                              '.subckt fdda_error_pair IP IM DP DM BN BT VSS')
        source = replace_once(source, 'XERRP INP FBP NPC NNC BN VSS fdda_error_pair',
            'XBTBIAS BT BP VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=10\n'
            'XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=1\n'
            'XERRP INP FBP NPC NNC BN BT VSS fdda_error_pair')
        source = replace_once(source, 'XERRN INN FBN NNC NPC BN VSS fdda_error_pair',
                              'XERRN INN FBN NNC NPC BN BT VSS fdda_error_pair')
        if kind.endswith('_cm4p'):
            source = replace_once(source, 'XCCM CMCTL VSS frontend_c1p',
                                  'XCCM CMCTL VSS frontend_c4p')
    elif kind != 'baseline':
        raise ValueError(kind)
    return source


def simulate(kind, source, gain, corner, vdd, temp, method, step_ns, timeout, generation_metadata=None):
    folder = HERE/'results'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_'+kind+f'_g{gain}')
    folder.mkdir(parents=True)
    (folder/'candidate.spice').write_text(source)
    arguments = dict(kind=kind,gain=gain,corner=corner,vdd=vdd,temp=temp,method=method,step_ns=step_ns)
    report = dict(status='RUNNING',arguments=arguments,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                  base_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scope='Static-capacitive-load common-mode/differential step diagnostic only',
                  full_frontend_qualified=False)
    report['generation_metadata'] = generation_metadata or {}
    report['generation_metadata_interpretation'] = 'Applied generation arguments; defaults may be no-ops on an existing source. The full candidate snapshot/hash, not argument defaults, defines actual devices.'
    output = folder/'summary.json'
    output.write_text(json.dumps(report,indent=2)+'\n')
    extra_nodes = ['v(xpga.xamp.xerrn.tail)']
    if 'XT0 TS BN' in source:
        extra_nodes += ['v(xpga.xamp.bt)', 'v(xpga.xamp.xerrp.ts)', 'v(xpga.xamp.xerrn.ts)']
        for side in ('p','n'):
            for device in ('xt0','xtc0'):
                for field in ('id','vds','vdsat'):
                    extra_nodes.append(f'@m.xpga.xamp.xerr{side}.{device}.msky130_fd_pr__nfet_01v8[{field}]')
    input_columns={}
    input_model='nfet_01v8_lvt' if 'XP1 DP IP TAIL VSS sky130_fd_pr__nfet_01v8_lvt' in source else 'nfet_01v8'
    for side in ('p','n'):
        for device in ('xp1','xn1'):
            input_columns[side+'.'+device]=13+len(extra_nodes)
            for field in ('id','vds','vdsat'):
                extra_nodes.append(f'@m.xpga.xamp.xerr{side}.{device}.msky130_fd_pr__{input_model}[{field}]')
    extra_text = ' '.join(extra_nodes)
    report['extra_waveform_columns'] = {str(13+i): name for i,name in enumerate(extra_nodes)}
    deck = f'''SKY130 frozen common-mode repair diagnostic
.lib {PDK} {corner}
.include candidate.spice
.temp {temp}
.options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18 itl1=200 itl2=200 method={method} maxord=2
VDD VDD 0 {vdd}
VCM VCM 0 {vdd/2}
VCMS CMS 0 PWL(0 0 2u 0 2.01u .05 6u .05 6.01u 0)
VDIFF DIFF 0 PWL(0 0 7u 0 7.01u {0.36/gain} 12u {0.36/gain} 12.01u {-0.36/gain} 18u {-0.36/gain} 18.01u 0)
BIP SP 0 v={vdd/2}+v(cms)+v(diff)/2
BIN SN 0 v={vdd/2}+v(cms)-v(diff)/2
RSP SP IP 350
RSN SN IN 350
VSEL0 SEL0 0 {vdd if gain==4 else 0}
VSEL1 SEL1 0 {vdd if gain==16 else 0}
XPGA IP IN OP ON VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga
XRIP OP FP 0 frontend_r R=2800
XRIN ON FN 0 frontend_r R=2800
XCFP FP 0 frontend_c4p
XCFN FN 0 frontend_c4p
CLP FP 0 81.28512p
CLN FN 0 81.28512p
.save v(op) v(on) v(fp) v(fn) v(sp) v(sn) i(vdd) i(vcm) v(xpga.xamp.cmctl) v(xpga.xamp.xerrp.tail) v(xpga.xamp.xp) v(xpga.xamp.xn) {extra_text}
.control
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
op
wrdata op.dat v(op) v(on) v(xpga.xamp.cmctl) v(xpga.xamp.xerrp.tail) v(xpga.xamp.xp) v(xpga.xamp.xn) i(vdd)
tran {step_ns}n 25u 0 {step_ns}n
wrdata transient.dat v(op) v(on) v(fp) v(fn) v(sp) v(sn) i(vdd) i(vcm) v(xpga.xamp.cmctl) v(xpga.xamp.xerrp.tail) v(xpga.xamp.xp) v(xpga.xamp.xn) {extra_text}
quit
.endc
.end
'''
    (folder/'bench.spice').write_text(deck)
    env = dict(os.environ,SPICE_USERINIT_DIR='/foss/pdks/sky130A/libs.tech/ngspice')
    start = time.monotonic()
    with (folder/'console.txt').open('w') as console:
        proc = subprocess.Popen(['ngspice','-b','-o','simulator.log','bench.spice'],cwd=folder,env=env,
                                stdout=console,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM)
            proc.wait()
            report['status']='TIMEOUT_INCOMPLETE'
    report['elapsed_s']=time.monotonic()-start
    report['returncode']=proc.returncode
    log=(folder/'simulator.log').read_text(errors='replace')
    failures=any(s in log.lower() for s in ('error:','timestep too small','simulation(s) aborted','simulation interrupted'))
    if report['status']=='RUNNING' and (proc.returncode or failures or 'ngspice-47 done' not in log):
        report['status']='SIMULATOR_FAILURE'
    if report['status']=='RUNNING':
        data=np.loadtxt(folder/'transient.dat',skiprows=1,ndmin=2)
        t=data[:,0]
        if not np.isfinite(data).all() or len(t)<2 or np.any(np.diff(t)<=0) or t[-1]<25e-6-1e-12:
            report['status']='INCOMPLETE_OR_INVALID_WAVEFORM'
        else:
            cm=(data[:,1]+data[:,2])/2
            od=data[:,3]-data[:,4]
            late=(t>=23e-6)&(t<=25e-6)
            use=t>=1e-6
            power=-vdd*data[:,7]-(vdd/2)*data[:,8]
            windows={}
            for name,lo,hi in [('positive',11e-6,12e-6),('negative',17e-6,18e-6),('zero',23e-6,25e-6)]:
                sel=(t>=lo)&(t<=hi)
                windows[name]={'output_mean_v':float(np.trapezoid(od[sel],t[sel])/(t[sel][-1]-t[sel][0])),
                               'output_peak_to_peak_v':float(np.ptp(od[sel])),
                               'common_mode_peak_to_peak_v':float(np.ptp(cm[sel]))}
                windows[name]['input_pair_min_vds_minus_vdsat_v']={
                    key:float(np.min(data[sel,col+1]-data[sel,col+2])) for key,col in input_columns.items()}
                if 'XT0 TS BN' in source:
                    windows[name]['tail_stack'] = {}
                    for side,offset in [('p',17),('n',23)]:
                        windows[name]['tail_stack'][side] = {
                            'bottom_min_vds_minus_vdsat_v':float(np.min(data[sel,offset+1]-data[sel,offset+2])),
                            'upper_min_vds_minus_vdsat_v':float(np.min(data[sel,offset+4]-data[sel,offset+5])),
                            'one_bottom_mean_id_a':float(np.mean(data[sel,offset]))}
            report.update(status='DIAGNOSTIC_COMPLETED',
                common_mode_max_error_v=float(np.max(abs(cm[use]-vdd/2))),
                late_common_mode_peak_to_peak_v=float(np.ptp(cm[late])),
                late_differential_peak_to_peak_v=float(np.ptp(od[late])),
                mean_vdd_and_vcm_power_w=float(np.trapezoid(power[use],t[use])/(t[use][-1]-t[use][0])),
                windows=windows)
            report['diagnostic_stability_gate']=bool(report['common_mode_max_error_v']<=.05 and
                all(max(row['output_peak_to_peak_v'],row['common_mode_peak_to_peak_v'])<4.8828125e-6 for row in windows.values()))
            report['diagnostic_polarity_and_amplitude_gate']=bool(
                abs(windows['positive']['output_mean_v']-.36)<.0036 and
                abs(windows['negative']['output_mean_v']+.36)<.0036 and
                abs(windows['zero']['output_mean_v'])<.0036)
            report['acquisition_window_settling_qualified']=False
    report['artifact_integrity_status']='NEW_IMMUTABLE_MANIFEST'
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    write_manifest(folder, ['candidate.spice','bench.spice','summary.json','simulator.log'],
                   [Path(__file__), FRONT/'measurement_evidence.py'])
    print(json.dumps({'path':str(output.relative_to(FRONT)),**{k:v for k,v in report.items() if k not in ('source_sha256','base_sha256','script_sha256')}},indent=2),flush=True)
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--variant',choices=['baseline','long_tail','cascoded_tail','cascoded_tail_cm4p'],required=True)
    p.add_argument('--source',type=Path)
    p.add_argument('--gain',type=int,choices=[1,4,16],default=16)
    p.add_argument('--corner',choices=['tt','ff','ss','fs','sf'],default='tt')
    p.add_argument('--vdd',type=float,default=1.8)
    p.add_argument('--temperature',type=float,default=27)
    p.add_argument('--method',choices=['gear','trap'],default='gear')
    p.add_argument('--step-ns',type=float,default=2)
    p.add_argument('--timeout',type=float,default=180)
    p.add_argument('--tail-scale',type=float,default=1)
    p.add_argument('--bt-diode-width',type=float,default=1,help='lower physical cascode bias by increasing its diode width')
    p.add_argument('--miller-cap-pf',type=int,choices=[16,24,32,48,64],default=16)
    p.add_argument('--miller-zero-r',type=float,default=3600)
    p.add_argument('--input-lvt',action='store_true',help='use actual PDK low-threshold error-pair devices to recover input headroom')
    p.add_argument('--output-n-width',type=float,default=105,help='reduce output NMOS width to raise first-stage DC output voltage at the same bias current')
    p.add_argument('--cm-tail-width',type=float,default=192)
    p.add_argument('--cm-degeneration-ohm',type=float,default=2000)
    p.add_argument('--cm-cap-count',type=int,default=0,help='replace CM capacitor with N actual24pF MIM banks')
    p.add_argument('--cm-sense-r',type=float,default=100000)
    p.add_argument('--cm-sense-cap',type=int,choices=[0,1,4],default=0)
    a=p.parse_args()
    source=a.source.read_text() if a.source else candidate(BASE.read_text(),a.variant)
    parent_source_path=a.source.resolve() if a.source else BASE
    metadata={**vars(a),'source':str(parent_source_path),
              'parent_source_sha256':hashlib.sha256(parent_source_path.read_bytes()).hexdigest()}
    if a.input_lvt:
        source,n=re.subn(r'^(X[PN][1-6] D[PM] I[PM] TAIL VSS )sky130_fd_pr__nfet_01v8( L=2 W=800)$',
            r'\1sky130_fd_pr__nfet_01v8_lvt\2',source,flags=re.MULTILINE)
        if n != 12:
            raise ValueError(f'Expected exactly 12 error-pair input instances, found {n}')
    if a.output_n_width != 105:
        for side in ('P','N'):
            source=replace_once(source,f'XO{side} OUT{side} X{side} VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=105',
                f'XO{side} OUT{side} X{side} VSS VSS sky130_fd_pr__nfet_01v8 L=2 W={a.output_n_width:g}')
    if a.bt_diode_width != 1:
        source=replace_once(source,'XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=1',
            f'XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8 L=1 W={a.bt_diode_width:g}')
    if a.miller_cap_pf != 16:
        before='.subckt frontend_c16p A B\n'+''.join(f'XC{n} A B frontend_c4p\n' for n in range(4))+'.ends frontend_c16p'
        after='.subckt frontend_c16p A B\n'+''.join(f'XC{n} A B frontend_c4p\n' for n in range(a.miller_cap_pf//4))+'.ends frontend_c16p'
        source=replace_once(source,before,after)
    if a.miller_zero_r != 3600:
        for side in ('P','N'):
            source=replace_once(source,f'XRZ{side} X{side} CZ{side} VSS frontend_r R=3600',
                f'XRZ{side} X{side} CZ{side} VSS frontend_r R={a.miller_zero_r:g}')
    if a.tail_scale != 1:
        source,n=re.subn(r'^(XT\d* (?:TS|TAIL) BN VSS VSS sky130_fd_pr__nfet_01v8 L=[\d.]+ W=)([\d.]+)$',
                       lambda m:m[1]+f'{float(m[2])*a.tail_scale:g}',source,flags=re.MULTILINE)
        if n<1:
            raise ValueError('No current-setting tail devices found')
    if a.cm_tail_width!=192:
        source=replace_once(source,'XCMT CMTAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=192',
            f'XCMT CMTAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=1 W={a.cm_tail_width:g}')
    if a.cm_degeneration_ohm!=2000:
        for side in ('R','S'):
            source=replace_once(source,f'XRCM{side} CMS{side} CMTAIL VSS frontend_r R=2000',
                f'XRCM{side} CMS{side} CMTAIL VSS frontend_r R={a.cm_degeneration_ohm:g}')
    if a.cm_cap_count:
        source=replace_once(source,'XCCM CMCTL VSS frontend_c1p','\n'.join(
            f'XCCM{n} CMCTL VSS frontend_c24p' for n in range(a.cm_cap_count)))
    if a.cm_sense_r!=100000:
        for side in ('P','N'):
            source=replace_once(source,f'XRCM{side} OUT{side} CMSENSE VSS frontend_r100k',
                f'XRCM{side} OUT{side} CMSENSE VSS frontend_r R={a.cm_sense_r:g}')
    if a.cm_sense_cap:
        source=replace_once(source,'XCMREF CMD VCM CMSR VSS',
            '\n'.join(f'XFF{side} OUT{side} CMSENSE frontend_c{a.cm_sense_cap}p' for side in ('P','N'))+'\nXCMREF CMD VCM CMSR VSS')
    if not a.source:
        source+=f'\n* Repair experiment tail_scale={a.tail_scale:g}, cm_tail_width={a.cm_tail_width:g}, cm_degeneration_ohm={a.cm_degeneration_ohm:g}, cm_cap_count={a.cm_cap_count}, cm_sense_r={a.cm_sense_r:g}, cm_sense_cap={a.cm_sense_cap}\n'
    simulate(a.variant,source,a.gain,a.corner,a.vdd,a.temperature,a.method,a.step_ns,a.timeout,metadata)


if __name__=='__main__':
    main()
