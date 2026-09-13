#!/usr/bin/env python3
"""Characterize the independent real-device ADC preamp candidate.

Stationary .noise applies ONLY to the continuously biased preamp. It does not
verify StrongARM transient device noise, sampled noise folding or system SNDR.
"""
import concurrent.futures
import argparse
import hashlib
import json

import numpy as np

from run_adc import HERE, RESULTS, LSB, deck, prepare, run_case, table, interp


def case(corner, vdd, temp):
    name=f'preamp_{corner}_{vdd}_{temp}'
    body=f'''.include {HERE/'adc_preamp.spice'}
VDD vdd 0 {vdd}
VDDCMP cmpdd 0 {vdd}
VCM cm 0 {vdd/2}
VDIFF diff 0 DC 0 AC 1
EIP ip cm diff 0 .5
EIN inn cm diff 0 -.5
XPRE ip inn op on vdd 0 adc_preamp
XCMP op on q qb 0 cmpdd 0 adc_latched_comparator
CQ q 0 5f
CQB qb 0 5f
.nodeset v(q)=0 v(qb)={vdd}
'''
    control=f'''op
wrdata {RESULTS/(name+'_op.tsv')} v(op) v(on) v(xpre.bn) v(xpre.bp) i(vdd)
ac dec 30 1 1g
let dg=v(op)-v(on)
wrdata {RESULTS/(name+'_ac.tsv')} real(dg) imag(dg)
'''
    if corner=='tt' and vdd==1.8 and temp==27:
        body+='\n.options sparse\n'
        control+=f'''noise v(op,on) VDIFF dec 40 1 100meg
setplot noise1
wrdata {RESULTS/(name+'_noise.tsv')} onoise_spectrum inoise_spectrum
'''
    return name,deck(name,body,control,corner,temp)


def transient_case():
    name='preamp_overload_recovery'
    levels=[.4,-.2,.1,-.05,.025,-.0125,.00625,-.003125,.0015625,-.00078125,LSB/4,-LSB/4,LSB/2,-LSB/2]
    points=[f'0 {levels[0]}']
    for k,x in enumerate(levels[1:],1):
        t=2.52e-6+k*625e-9
        points += [f'{t:.12g} {levels[k-1]}',f'{t+1e-9:.12g} {x}']
    body=f'''.include {HERE/'adc_preamp.spice'}
VDD vdd 0 1.8
VCM cm 0 .9
VDIFF diff 0 PWL({' '.join(points)})
EIP sp cm diff 0 .5
EIN sn cm diff 0 -.5
RSP sp ip 350
RSN sn inn 350
XCP ip 0 adc_mim_bank COUNT=4096
XCN inn 0 adc_mim_bank COUNT=4096
XPRE ip inn op on vdd 0 adc_preamp
VEVAL ev 0 PULSE(0 1.8 2.825u 1n 1n 250n 625n)
XCMP op on q qb ev vdd 0 adc_latched_comparator
CQ q 0 5f
CQB qb 0 5f
'''
    stop=2.52e-6+len(levels)*625e-9
    return name,levels,deck(name,body,f'tran 1n {stop:.12g}\nwrdata {RESULTS/(name+".tsv")} v(ip) v(inn) v(op) v(on) v(q) v(qb) v(ev) i(vdd)')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--jobs',type=int,default=1)
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    prepare()
    specs=[(c,v,t) for c in ['tt','ff','ss','fs','sf'] for v in [1.62,1.8,1.98] for t in [-20,27,85]]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for n in pool.map(lambda x:run_case(*case(*x),reuse_completed=args.resume),specs):print('simulated '+n,flush=True)
    rows=[]
    for c,v,t in specs:
        n=f'preamp_{c}_{v}_{t}'
        op=table(n+'_op')[0]; ac=table(n+'_ac'); gain=np.hypot(ac[:,1],ac[:,2])
        f3=ac[np.where(gain<=gain[0]/np.sqrt(2))[0][0],0] if np.any(gain<=gain[0]/np.sqrt(2)) else None
        rows.append(dict(corner=c,vdd=v,temperature_c=t,output_cm_v=float((op[1]+op[2])/2),
                         bias_bn_v=float(op[3]),bias_bp_v=float(op[4]),power_w=float(-v*op[5]),
                         low_frequency_gain_vv=float(gain[0]),f3db_hz=float(f3) if f3 else None,
                         operating_point_nonsaturated=bool(.15<(op[1]+op[2])/2<v-.15)))
    name,levels,content=transient_case();run_case(name,content,reuse_completed=args.resume);d=table(name)
    checks=[]
    for k,x in enumerate(levels):
        te=2.825e-6+k*625e-9
        out=interp(d,te+225e-9,5)-interp(d,te+225e-9,6)
        checks.append(dict(cycle=k,input_target_v=x,input_at_evaluate_v=interp(d,te,1)-interp(d,te,2),
                           preamp_output_diff_at_evaluate_v=interp(d,te,3)-interp(d,te,4),
                           q_diff_v=out,decision_pass=bool(out*x>0 and abs(out)>1.44)))
    noise=table('preamp_tt_1.8_27_noise')
    bands=[]
    nominal_gain=next(r['low_frequency_gain_vv'] for r in rows if r['corner']=='tt' and r['vdd']==1.8 and r['temperature_c']==27)
    for upper in [5e3,50e3,1e8]:
        mask=noise[:,0]<=upper
        bands.append(dict(lower_hz=1,upper_hz=upper,
                           integrated_input_noise_spectrum_rms_v=float(np.sqrt(np.trapezoid(noise[mask,2]**2,noise[mask,0]))),
                           integrated_output_noise_referred_to_dc_input_rms_v=float(np.sqrt(np.trapezoid(noise[mask,1]**2,noise[mask,0]))/nominal_gain)))
    result=dict(status='COMPLETE_BLOCK_CHARACTERIZATION_NOT_ADC_QUALIFICATION',
                power_measurement_scope='Preamp-only separate supply; static SR-latch operating-point current excluded from OP power. Dynamic total comparator/ADC power needs integrated transient measurement.',
                evidence_level='Independent self-biased PDK preamp candidate: stationary OP/AC/noise and driven-input overload recovery, NOT ADC SNDR',
                source_sha256=hashlib.sha256((HERE/'adc_preamp.spice').read_bytes()).hexdigest(),
                pvt_conditions=rows,condition_count=len(rows),noise_bands=bands,
                overload_recovery_checks=checks,overload_recovery_pass_count=sum(x['decision_pass'] for x in checks),
                overload_recovery_fail_count=sum(not x['decision_pass'] for x in checks),
                limitations=['Not floating-CDAC decision noise','No sampled-noise folding','No extracted layout',
                             'PVT OP/AC does not qualify PVT dynamic comparator decisions','No preamp mismatch calibration yet'])
    (RESULTS/'preamp_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='pvt_conditions'},indent=2))


if __name__=='__main__':main()
