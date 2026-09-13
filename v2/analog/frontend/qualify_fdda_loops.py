#!/usr/bin/env python3
"""FDDA DM/CM return-ratio diagnostics with operating-point-preserving injections.

This is a scalar voltage-return-ratio check, not a replacement for full
multi-loop stability qualification, extracted parasitics, or switched loading.
The opposite feedback loop remains connected. Every unity crossing is reported.
"""
import argparse
import hashlib
import json
import numpy as np
from run_frontend import HERE, header, run_deck

p=argparse.ArgumentParser()
p.add_argument('--core',default='frontend_fdda.spice')
p.add_argument('--gain',type=int,choices=[1,4,16],default=4)
p.add_argument('--corner',default='tt')
p.add_argument('--vdd',type=float,default=1.8)
p.add_argument('--temp',type=float,default=27)
p.add_argument('--isolation-r',type=float,default=2700)
p.add_argument('--out',required=True)
a=p.parse_args()
source=(HERE/a.core).read_text()
assert 'fdda_error_pair' in source
folder=HERE/a.out/f'loops_{a.corner}_{a.vdd:g}_{a.temp:g}_g{a.gain}'
folder.mkdir(parents=True,exist_ok=True)
snapshot=folder/'frontend_snapshot.spice'
if snapshot.exists() and snapshot.read_text()!=source:
    raise ValueError('Choose a new output directory for a new circuit revision')
snapshot.write_text(source)
results={}
for mode in ['dm','cm']:
    if mode=='dm':
        before='XAMP VINP VINN FBP FBN OUTP OUTN'
        after='''VTESTP IFBP FBP dc 0 ac 0.5
VTESTN IFBN FBN dc 0 ac -0.5
XAMP VINP VINN IFBP IFBN OUTP OUTN'''
        ratio='-(v(xpga.fbp)-v(xpga.fbn))/(v(xpga.ifbp)-v(xpga.ifbn))'
    else:
        before='XCMSENSE CMCTL CMSENSE CMSS VSS sky130_fd_pr__nfet_01v8'
        after='''VTESTCM ICMSENSE CMSENSE dc 0 ac 1
XCMSENSE CMCTL ICMSENSE CMSS VSS sky130_fd_pr__nfet_01v8'''
        ratio='-v(xpga.xamp.cmsense)/v(xpga.xamp.icmsense)'
    assert source.count(before)==1, mode
    measured=folder/f'measurement_{mode}.spice'
    measured.write_text(source.replace(before,after))
    deck=header(a.corner,a.vdd,a.temp,measured)+f'''
VIP SP 0 {a.vdd/2}
VIN SN 0 {a.vdd/2}
RSP SP IP 350
RSN SN IN 350
VSEL0 SEL0 0 {a.vdd if a.gain==4 else 0}
VSEL1 SEL1 0 {a.vdd if a.gain==16 else 0}
XPGA IP IN OP ON VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga
XRIP OP FP 0 frontend_r R={a.isolation_r}
XRIN ON FN 0 frontend_r R={a.isolation_r}
XCFP FP 0 frontend_c4p
XCFN FN 0 frontend_c4p
* Explicit static test load, no sampling-noise claim.
CLP FP 0 81.28512p
CLN FN 0 81.28512p
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
wrdata {mode}_op.dat all
ac dec 100 1 1g
let loop={ratio}
let lr=real(loop)
let li=imag(loop)
wrdata {mode}_ac.dat lr li
quit
.endc
.end
'''
    run_deck(mode,deck,folder)
    d=np.loadtxt(folder/f'{mode}_ac.dat',skiprows=1)
    f=d[:,0]; z=d[:,1]+1j*d[:,2]
    db=20*np.log10(abs(z))
    phase=np.unwrap(np.angle(z))*180/np.pi
    phase-=360*np.round(phase[0]/360)
    crossings=[]
    for j in np.where(db[:-1]*db[1:]<0)[0]:
        fraction=-db[j]/(db[j+1]-db[j])
        freq=10**(np.log10(f[j])+fraction*(np.log10(f[j+1])-np.log10(f[j])))
        angle=phase[j]+fraction*(phase[j+1]-phase[j])
        crossings.append({'frequency_hz':float(freq),'phase_deg':float(angle),
                          'scalar_phase_margin_deg':float(180+angle),
                          'direction':'down' if db[j]>0 else 'up'})
    results[mode]={'low_frequency_gain_db':float(db[0]),'low_frequency_phase_deg':float(phase[0]),
                   'unity_crossings':crossings,
                   'scalar_downcrossings_meet_60deg':bool(crossings and all(c['scalar_phase_margin_deg']>=60 for c in crossings if c['direction']=='down'))}
report={'test':'FDDA scalar voltage-return-ratio diagnostic','gain':a.gain,
        'corner':a.corner,'vdd_v':a.vdd,'temp_c':a.temp,
        'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'loops':results,
        'formal_multiloop_stability_signoff':False,
        'limitations':['Static 81.28512 pF/side test load after physical isolation network.',
                      'Opposite loop remains connected; no independent open-loop RHP pole count.',
                      'Scalar injection assumes useful unidirectional return-ratio separation; all unity crossings retained.',
                      'Switched-load transient, layout parasitics, and full PVT are separate evidence.']}
(folder/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
