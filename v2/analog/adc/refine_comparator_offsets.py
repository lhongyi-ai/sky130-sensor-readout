#!/usr/bin/env python3
"""Refine the SAME 200 PDK comparator mismatch samples and freeze calibration.

The fixed seed and identical ordered statistical device inventory preserve each
sample across input sweeps and V/T. A 25-instance replay must first agree with
the preceding global-stimulus screen. Calibration is a scalar input-offset
estimate per comparator, not a claim of full ADC calibration.
"""
import concurrent.futures
import argparse
import hashlib
import json
import re

import numpy as np

from run_adc import HERE, RESULTS, LSB, deck, prepare, run_case


def run_batch(batch, levels_by_id, tag, vdd=1.8, temp=27, repetitions=1):
    name=f'cmp_refine_{tag}_batch_{batch}'
    body=[f'VDD vdd 0 {vdd}',f'VCLK clk 0 PULSE(0 {vdd} 200n 1n 1n 250n 625n)']
    measure=[]; count=len(levels_by_id[batch*25])
    for i in range(25):
        levels=np.repeat(levels_by_id[batch*25+i],repetitions).tolist();p=[];n=[]
        for k,diff in enumerate(levels):
            vp=vdd/2+diff/2;vn=vdd/2-diff/2
            if k==0:p.append(f'0 {vp:.14g}');n.append(f'0 {vn:.14g}')
            else:
                t=k*625e-9-100e-9
                p += [f'{t:.12g} {vdd/2+levels[k-1]/2:.14g}',f'{t+1e-9:.12g} {vp:.14g}']
                n += [f'{t:.12g} {vdd/2-levels[k-1]/2:.14g}',f'{t+1e-9:.12g} {vn:.14g}']
        body += [f'VIP{i} sp{i} 0 PWL('+' '.join(p)+')',f'VIN{i} sn{i} 0 PWL('+' '.join(n)+')',
                 f'RP{i} sp{i} ip{i} 350',f'RN{i} sn{i} inn{i} 350',
                 f'XCP{i} ip{i} 0 adc_mim_bank COUNT=4096',f'XCN{i} inn{i} 0 adc_mim_bank COUNT=4096',
                 f'XCMP{i} ip{i} inn{i} q{i} qb{i} clk vdd 0 adc_latched_comparator',
                 f'CQ{i} q{i} 0 5f',f'CQB{i} qb{i} 0 5f',f'.ic V(q{i})=0 V(qb{i})={vdd}']
        for k in range(count):
            t=((k+1)*repetitions-1)*625e-9+425e-9
            measure += [f'meas tran s{i}_k{k}_q find v(q{i}) at={t:.12g}',f'meas tran s{i}_k{k}_qb find v(qb{i}) at={t:.12g}']
    control=f'setseed {1309200+batch}\nreset\ntran 1n {(count*repetitions-1)*625e-9+550e-9:.12g}\n'+'\n'.join(measure)
    run_case(name,deck(name,'\n'.join(body),control,corner='tt_mm',temp=temp))
    log=(RESULTS/(name+'.log')).read_text()
    values={m.group(1):float(m.group(2)) for m in re.finditer(r'(?im)^\s*(s\d+_k\d+_q[b]?)\s*=\s*([-+0-9.eE]+)',log)}
    rows=[]
    for i in range(25):
        levels=levels_by_id[batch*25+i]
        diffs=[values[f's{i}_k{k}_q']-values[f's{i}_k{k}_qb'] for k in range(count)]
        decisions=[int(x>0) for x in diffs]
        monotonic=all(a<=b for a,b in zip(decisions,decisions[1:]))
        low=[d for d,q in zip(levels,decisions) if q==0];high=[d for d,q in zip(levels,decisions) if q==1]
        rows.append(dict(sample=batch*25+i,levels_v=levels,decisions=decisions,output_differential_v=diffs,
                         all_resolved=all(abs(x)>.8*vdd for x in diffs),monotonic=monotonic,
                         offset_bracket_v=[max(low),min(high)] if low and high and monotonic else None))
    print('simulated '+name,flush=True)
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--from-refinement-round',type=int,default=None,
                    help='Use a completed stable refinement round, explicitly retaining its finite uncertainty; do not invent finer thresholds.')
    ap.add_argument('--jobs',type=int,default=1)
    args=ap.parse_args()
    prepare()
    coarse=json.loads((RESULTS/'comparator_mismatch_summary.json').read_text())['samples']
    replay_levels=[r['input_levels_v'] for r in coarse]
    replay=run_batch(0,replay_levels,'replay')
    if any(r['decisions']!=coarse[r['sample']]['decisions'] for r in replay):
        raise RuntimeError('Statistical ensemble replay failed; fixed-calibration V/T test is invalid.')
    brackets=[]
    for r in coarse:
        b=r['offset_bracket_v']
        if b is None:b=[.003,.025] if r['decisions'][-1]==0 else [-.025,-.003]
        brackets.append([b[0]-100e-6,b[1]+100e-6])
    history=[]
    for round_id in ([] if args.from_refinement_round is not None else range(4)):
        levels=[np.linspace(lo,hi,7).tolist() for lo,hi in brackets]
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            batches=list(pool.map(lambda b:run_batch(b,levels,f'stable_r{round_id}',repetitions=2),range(8)))
        rows=[r for batch in batches for r in batch]
        bad=[r for r in rows if r['offset_bracket_v'] is None or not r['all_resolved'] or not r['monotonic']]
        history.append(rows)
        (RESULTS/f'comparator_offset_stable_refinement_r{round_id}.json').write_text(json.dumps(rows,indent=2)+'\n')
        if bad:
            (RESULTS/'comparator_offset_stable_refinement_blocker.json').write_text(json.dumps(bad,indent=2)+'\n')
            raise RuntimeError('Offset refinement found unbracketed/unresolved/nonmonotonic sample; not silently dropped.')
        # The first failed refinement exposed cycle-history dependence near the
        # threshold. Measure the second identical-input cycle and explicitly
        # retain a 5-uV guard on each bracket end rather than silently assert a
        # unique exact offset. The failed first-cycle evidence is preserved.
        brackets=[[r['offset_bracket_v'][0]-5e-6,r['offset_bracket_v'][1]+5e-6] for r in rows]
    if args.from_refinement_round is not None:
        rows=json.loads((RESULTS/f'comparator_offset_stable_refinement_r{args.from_refinement_round}.json').read_text())
        if len(rows)!=200 or any(r['offset_bracket_v'] is None or not r['all_resolved'] or not r['monotonic'] for r in rows):
            raise RuntimeError('Cannot calibrate from incomplete or invalid refinement round.')
        brackets=[[r['offset_bracket_v'][0]-5e-6,r['offset_bracket_v'][1]+5e-6] for r in rows]
    calibration=[sum(b)/2 for b in brackets]
    nominal=dict(sample_count=200,replay_pass=True,replayed_sample_count=25,nominal_vdd=1.8,nominal_temperature_c=27,
                 completed_refinement_round=args.from_refinement_round if args.from_refinement_round is not None else 3,
                 input_repetitions_per_level=2,measured_repetition=2,bracket_guard_each_end_v=5e-6,
                 source_sha256=hashlib.sha256((HERE/'adc_blocks.spice').read_bytes()).hexdigest(),
                 samples=[dict(sample=i,offset_bracket_v=b,calibration_offset_v=calibration[i],
                               estimate_uncertainty_v=(b[1]-b[0])/2) for i,b in enumerate(brackets)],
                 maximum_bracket_width_v=max(b[1]-b[0] for b in brackets),
                 offset_estimate_min_v=min(calibration),offset_estimate_max_v=max(calibration),
                 offset_estimate_mean_v=float(np.mean(calibration)),offset_estimate_sample_sigma_v=float(np.std(calibration,ddof=1)))
    (RESULTS/'comparator_offset_calibration.json').write_text(json.dumps(nominal,indent=2)+'\n')
    conditions=[]
    # Endpoints are independent holdout tests of the fixed calibration residual.
    # Do not force an arbitrary exact-threshold decision as an accuracy test.
    levels=[[c-4*LSB,c+4*LSB] for c in calibration]
    for vdd,temp in [(1.62,-20),(1.62,85),(1.98,-20),(1.98,85)]:
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            batches=list(pool.map(lambda b:run_batch(b,levels,f'stable_vt_{vdd}_{temp}',vdd,temp,repetitions=2),range(8)))
        rows=[r for batch in batches for r in batch]
        for row in rows:
            row['fixed_calibration_offset_v']=calibration[row['sample']]
            row['residual_within_4lsb']=bool(row['all_resolved'] and row['monotonic'] and row['decisions'][0]==0 and row['decisions'][-1]==1)
        conditions.append(dict(vdd=vdd,temperature_c=temp,samples=rows,
                               pass_count=sum(r['residual_within_4lsb'] for r in rows),fail_count=sum(not r['residual_within_4lsb'] for r in rows)))
        (RESULTS/f'comparator_fixed_calibration_{vdd}_{temp}.json').write_text(json.dumps(conditions[-1],indent=2)+'\n')
    summary=dict(evidence_level='PDK comparator-only mismatch offset calibration and four V/T extremes; NOT system calibration or yield',
                 sample_count=200,statistical_process_corner='tt_mm',replay_pass=True,replayed_sample_count=25,
                 nominal_calibration_file='comparator_offset_calibration.json',maximum_nominal_bracket_width_v=nominal['maximum_bracket_width_v'],
                 offset_min_v=min(calibration),offset_max_v=max(calibration),offset_sigma_v=nominal['offset_estimate_sample_sigma_v'],
                 conditions=[{k:v for k,v in c.items() if k!='samples'} for c in conditions],
                 fixed_per_instance=True,retuned_at_vt=False,
                 limitations=['No extracted parasitics','No stochastic transient noise','No process-corner transfer beyond tt_mm',
                              'Continuously driven comparator input, not floating switched CDAC','Does not include the newly added preamp candidate',
                              'Nominal estimates retain finite bracket uncertainty plus explicit 5-uV guards','No full ADC/system calibration claim'])
    (RESULTS/'comparator_calibration_vt_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
