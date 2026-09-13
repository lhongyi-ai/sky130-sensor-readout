#!/usr/bin/env python3
"""Quantify the real three-way reference switch on MSB acquisition/load bounds.

20.32128pF is the series-equivalent MSB load with a floating top and equal
remaining array; 40.64256pF is the MSB acquisition load with top clamped.
This isolated-block diagnostic cannot qualify full CDAC kickback or INL.
"""
import hashlib
import json
import argparse

from run_adc import HERE, RESULTS, LSB, deck, prepare, run_case, table, interp


def case(corner,vdd,temp,sign,unit_count,variant,scale,reference_mode='fixed'):
    name=f'ref_switch_{variant}_s{scale}_{corner}_{vdd}_{temp}_{sign}_c{unit_count}'
    if reference_mode!='fixed':name+='_'+reference_mode
    cm=vdd/2;target=cm+sign*.2
    rp,rn=(1.1,.7) if reference_mode=='fixed' else (cm+.2,cm-.2)
    reference=rp if sign<0 else rn
    cell='adc_ref_switch' if variant=='standard' else 'adc_ref_switch_lvt'
    body=f'''.include {HERE/'adc_reference_candidate.spice'}
VDD vdd 0 {vdd}
VSOURCE src 0 PWL(0 {cm} 20n {cm} 21n {target})
RS src sample 350
VRP srp 0 {rp}
VRN srn 0 {rn}
RRP srp rp 1
RRN srn rn 1
VACQ acq 0 PWL(0 {vdd} 2.476847754u {vdd} 2.477847754u 0)
VCONV conv 0 PWL(0 0 2.50u 0 2.501u {vdd})
VBIT bit 0 {vdd if sign<0 else 0}
XSW hold bit acq conv rp rn sample vdd 0 {cell} WN={.84*scale:.8g} WP={1.68*scale:.8g}
XC hold 0 adc_mim_bank COUNT={unit_count}
.ic v(hold)={cm}
'''
    return name,target,reference,deck(name,body,f'tran 2n 3.2u uic\nwrdata {RESULTS/(name+".tsv")} v(src) v(sample) v(hold) v(acq) v(conv) i(vdd)',corner,temp)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--actual-only',action='store_true')
    ap.add_argument('--candidate-scale',type=float,default=None)
    ap.add_argument('--corner',choices=['all','tt','ss','fs'],default='all')
    ap.add_argument('--reference-mode',choices=['fixed','tracking'],default='fixed')
    args=ap.parse_args()
    prepare();rows=[]
    conditions=[r for r in [('tt',1.8,27),('ss',1.62,-20),('fs',1.98,85)] if args.corner=='all' or r[0]==args.corner]
    for corner,vdd,temp in conditions:
        for sign in [-1,1]:
            for count in [1024,2048]:
                variants=[('standard',8/.84)] if args.actual_only else [('standard',8/.84),('standard',1),('lvt',1),('lvt',4),('lvt',16)]
                if args.candidate_scale is not None:variants=[('lvt',args.candidate_scale)]
                for variant,scale in variants:
                    name,target,ref,content=case(corner,vdd,temp,sign,count,variant,scale,args.reference_mode)
                    run_case(name,content,reuse_completed=True);d=table(name)
                    acquisition=interp(d,2.476e-6,3)-target
                    residual=interp(d,2.800e-6,3)-ref
                    rows.append(dict(name=name,corner=corner,vdd=vdd,temperature_c=temp,input_target_v=target,
                                     reference_target_v=ref,mim_units=count,capacitance_f=count*19.845e-15,
                                     reference_common_mode_rule=args.reference_mode,
                                     variant=variant,width_scale=scale,acquisition_error_v=acquisition,
                                     reference_error_after_300ns_v=residual,
                                     acquisition_quarter_lsb=abs(acquisition)<=LSB/4,
                                     reference_quarter_lsb=abs(residual)<=LSB/4))
                    print('simulated '+name,flush=True)
                    # An interrupted diagnostic still leaves the actual measured
                    # completed subset and planned coverage unambiguously visible.
                    summary=dict(evidence_level='Isolated actual reference decoder/TG/MIM MSB-load diagnostic; NOT full ADC',
                                 completed_cases=len(rows),planned_cases=len(conditions)*4*len(variants),cases=rows,
                                 source_sha256={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ['adc_blocks.spice','adc_reference_candidate.spice']},
                                 limitations=['Only three diagnostic corners','No charge-injection/noise/linearity qualification',
                                              '20pF/40pF load bounds do not replace an integrated floating CDAC test','Ideal finite-edge ACQ/CONV sources; actual phase-driver loading still required'])
                    suffix='_actual_msb' if args.actual_only else ''
                    if args.candidate_scale is not None:suffix+=f'_lvt{args.candidate_scale:g}'
                    if args.corner!='all':suffix+='_'+args.corner
                    if args.reference_mode!='fixed':suffix+='_'+args.reference_mode
                    (RESULTS/('reference_switch'+suffix+'_summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(completed_cases=len(rows),failed_cases=sum(not(r['acquisition_quarter_lsb'] and r['reference_quarter_lsb']) for r in rows)),indent=2))


if __name__=='__main__':main()
