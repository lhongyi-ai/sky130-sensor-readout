#!/usr/bin/env python3
"""90 floating-CDAC near-zero trial checks of the preamp candidate.

This holds the sensor input constant from the initial operating point: it tests
reference redistribution and decision across PVT, NOT worst acquisition steps.
"""
import concurrent.futures
import argparse
import hashlib
import json

from run_adc import HERE, RESULTS, LSB, deck, prepare, run_case, table, interp


def case(corner,vdd,temp,sign):
    name=f'preamp_float_{corner}_{vdd}_{temp}_{sign}'
    diff=sign*LSB/4;cm=vdd/2
    body=[f'.include {HERE/"adc_preamp.spice"}',f'.include {HERE/"adc_analog12_bottom_preamp.spice"}',
          f'VDD vdd 0 {vdd}',f'VCM cm 0 {cm}',
          'VRP srp 0 1.1','VRN srn 0 .7','RRP srp rp 1','RRN srn rn 1',
          'CEXTP rp 0 10n','CEXTN rn 0 10n',
          f'VIP sp 0 {cm+diff/2:.14g}',f'VIN sn 0 {cm-diff/2:.14g}',
          'RSP sp ip 350','RSN sn inn 350',
          f'VSAMP sample 0 PWL(0 {vdd} 2.49u {vdd} 2.491u 0)',
          f'VSAMPB sampleb 0 PWL(0 0 2.49u 0 2.491u {vdd})',
          f'VACQ acq 0 PWL(0 {vdd} 2.5u {vdd} 2.501u 0)',
          f'VCONV conv 0 PWL(0 0 2.52u 0 2.521u {vdd})',
          f'VEVAL ev 0 PULSE(0 {vdd} 2.825u 1n 1n 250n 625n)',
          'XADC ip inn q qb sample sampleb acq conv ev vdd '+('0 '*11)+'rp rn cm vdd 0 adc_analog12_bottom_preamp',
          'CQ q 0 5f','CQB qb 0 5f',f'.ic V(q)=0 V(qb)={vdd}']
    return name,deck(name,'\n'.join(body),f'tran 2n 3.2u\nwrdata {RESULTS/(name+".tsv")} v(xadc.tn) v(xadc.tp) v(xadc.prep) v(xadc.pren) v(q) v(qb) v(ev) i(vdd)',corner,temp)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--jobs',type=int,default=1)
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    prepare()
    specs=[(c,v,t,s) for c in ['tt','ff','ss','fs','sf'] for v in [1.62,1.8,1.98] for t in [-20,27,85] for s in [-1,1]]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for n in pool.map(lambda x:run_case(*case(*x),reuse_completed=args.resume),specs):print('simulated '+n,flush=True)
    rows=[]
    for c,v,t,s in specs:
        n=f'preamp_float_{c}_{v}_{t}_{s}';d=table(n)
        residual=interp(d,2.81e-6,1)-interp(d,2.81e-6,2)
        out=interp(d,3.02e-6,5)-interp(d,3.02e-6,6)
        held=interp(d,3.15e-6,5)-interp(d,3.15e-6,6)
        rows.append(dict(name=n,corner=c,vdd=v,temperature_c=t,input_diff_v=s*LSB/4,
                         residual_before_eval_v=residual,residual_error_lsb=(residual-s*LSB/4)/LSB,
                         output_diff_v=out,decision_pass=bool(out*s>.8*v),retained=bool(held*s>.8*v)))
    result=dict(evidence_level='90 schematic floating-CDAC/preamp/comparator single-trial checks, NOT full SAR conversion',
                source_sha256={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ['adc_blocks.spice','adc_preamp.spice','adc_analog12_bottom_preamp.spice']},
                condition_count=45,case_count=90,pass_count=sum(r['decision_pass'] and r['retained'] for r in rows),
                fail_count=sum(not(r['decision_pass'] and r['retained']) for r in rows),cases=rows,
                ideal_fixtures=['External finite-edge phase and fixed trial-code sources','External VREFP=1.1 V and VREFN=0.7 V through 1 ohm plus 10 nF each','Constant input from initial operating point'],
                limitations=['No worst-case input acquisition step','Only central code 2048 +/- 0.25 LSB','No transient stochastic device noise','No mismatch','No extracted parasitics'])
    (RESULTS/'preamp_floating_pvt_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))


if __name__=='__main__':main()
