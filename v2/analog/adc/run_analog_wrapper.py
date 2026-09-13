#!/usr/bin/env python3
"""Single-trial analog-wrapper checks without any behavioral SAR register.

Real top TGs, reference switch CMOS decode, CDAC and retained comparator are
driven by finite-edge external phase/code sources. These are NOT full SAR codes.
"""
import concurrent.futures
import json
import argparse

from run_adc import HERE, RESULTS, LSB, deck, prepare, run_case, table, interp


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--architecture',choices=['top','bottom','bottom_preamp'],default='top')
    ap.add_argument('--reference-ohm',type=float,default=10)
    ap.add_argument('--external-reference-cap-f',type=float,default=0)
    args=ap.parse_args()
    cell={'top':'adc_analog12','bottom':'adc_analog12_bottomsample','bottom_preamp':'adc_analog12_bottom_preamp'}[args.architecture]
    prepare()
    specs=[]
    for code in [1024,2048,3072]:
        for sign in [-1,1]:
            suffix='' if args.reference_ohm==10 and args.external_reference_cap_f==0 else f'_r{args.reference_ohm:g}_c{args.external_reference_cap_f:g}'
            name=f"wrapper_{args.architecture}{suffix}_trial_{code}_{sign}"
            vin=code*LSB-.4+sign*LSB/4
            body=[f".include {HERE/(cell+'.spice')}", "VDD vdd 0 1.8", "VCM cm 0 .9",
                  "VRP srp 0 1.1", "VRN srn 0 .7", f"RRP srp rp {args.reference_ohm}", f"RRN srn rn {args.reference_ohm}",
                  f"VIP sp 0 {.9+vin/2:.12g}", f"VIN sn 0 {.9-vin/2:.12g}",
                  "RSP sp ip 350", "RSN sn inn 350",
                  "VSAMP sample 0 PWL(0 1.8 2.49u 1.8 2.491u 0)",
                  "VSAMPB sampleb 0 PWL(0 0 2.49u 0 2.491u 1.8)",
                  "VACQ acq 0 PWL(0 1.8 2.50u 1.8 2.501u 0)",
                  "VCONV conv 0 PWL(0 0 2.52u 0 2.521u 1.8)",
                  "VEVAL ev 0 PULSE(0 1.8 2.825u 1n 1n 250n 625n)"]
            if args.architecture=='bottom_preamp':body.insert(0,f'.include {HERE/"adc_preamp.spice"}')
            for b in range(12):
                body.append(f"VB{b} b{b} 0 {1.8 if (code>>b)&1 else 0}")
            if args.external_reference_cap_f:
                body += [f'CEXTP rp 0 {args.external_reference_cap_f}', f'CEXTN rn 0 {args.external_reference_cap_f}']
            body += ["XADC ip inn q qb sample sampleb acq conv ev "+" ".join(f"b{b}" for b in reversed(range(12)))+f" rp rn cm vdd 0 {cell}",
                     "CQ q 0 5f", "CQB qb 0 5f", ".ic V(q)=0 V(qb)=1.8"]
            inputs='v(xadc.tp) v(xadc.tn)' if args.architecture=='top' else 'v(xadc.tn) v(xadc.tp)'
            control=f"tran 2n 3.2u\nwrdata {RESULTS/(name+'.tsv')} {inputs} v(q) v(qb) v(ev) v(rp) v(rn)"
            specs.append(dict(name=name,code=code,sign=sign,input_diff_v=vin,deck=deck(name,'\n'.join(body),control)))
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        for name in pool.map(lambda s:run_case(s['name'],s['deck']),specs):
            print('simulated '+name,flush=True)
    rows=[]
    for spec in specs:
        d=table(spec['name'])
        residual=interp(d,2.81e-6,1)-interp(d,2.81e-6,2)
        out=interp(d,3.02e-6,3)-interp(d,3.02e-6,4)
        rows.append({k:v for k,v in spec.items() if k!='deck'}|dict(residual_before_evaluate_v=residual,
                   residual_error_lsb=(residual-spec['sign']*LSB/4)/LSB,output_diff_v=out,
                   expected_comparison_pass=bool(out*spec['sign']>1.44),
                   reset_retained=bool((interp(d,3.15e-6,3)-interp(d,3.15e-6,4))*out>1.44**2)))
    summary=dict(evidence_level="single-trial full analog-wrapper transistor checks, ideal external phases/codes; NOT full SAR conversion",
                 cases=rows,pass_count=sum(r['expected_comparison_pass'] for r in rows),
                 fail_count=sum(not r['expected_comparison_pass'] for r in rows))
    summary['architecture']=args.architecture
    summary['external_reference_resistance_ohm']=args.reference_ohm
    summary['external_reference_capacitance_f']=args.external_reference_cap_f
    (RESULTS/f'analog_wrapper_{args.architecture}{suffix}_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
