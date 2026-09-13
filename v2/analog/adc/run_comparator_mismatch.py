#!/usr/bin/env python3
"""Real dynamic-comparator mismatch screening, with finite offset brackets.

Eight decks each contain 25 independent PDK tt_mm comparator instances.
Each instance is tested at seven input levels, preserving its mismatch through
all cycles. This is comparator-only statistical characterization, not ADC yield.
"""
import concurrent.futures
import hashlib
import json
import re

import numpy as np

from run_adc import HERE, RESULTS, deck, prepare, run_case

LEVELS=[-.003,-.001,-.00025,0,.00025,.001,.003]


def batch_deck(batch):
    name=f'comparator_mc_batch_{batch}'
    p=[]; n=[]
    for k,diff in enumerate(LEVELS):
        vplus=.9+diff/2; vminus=.9-diff/2
        if k==0:
            p.append(f'0 {vplus:.12g}');n.append(f'0 {vminus:.12g}')
        else:
            t=k*625e-9-100e-9
            p += [f'{t:.12g} {.9+LEVELS[k-1]/2:.12g}',f'{t+1e-9:.12g} {vplus:.12g}']
            n += [f'{t:.12g} {.9-LEVELS[k-1]/2:.12g}',f'{t+1e-9:.12g} {vminus:.12g}']
    body=['VDD vdd 0 1.8','VIP sp 0 PWL('+' '.join(p)+')','VIN sn 0 PWL('+' '.join(n)+')',
          'VCLK clk 0 PULSE(0 1.8 200n 1n 1n 250n 625n)']
    measure=[]
    for i in range(25):
        body += [f'RP{i} sp ip{i} 350',f'RN{i} sn inn{i} 350',
                 f'XCP{i} ip{i} 0 adc_mim_bank COUNT=4096',f'XCN{i} inn{i} 0 adc_mim_bank COUNT=4096',
                 f'XCMP{i} ip{i} inn{i} q{i} qb{i} clk vdd 0 adc_latched_comparator',
                 f'CQ{i} q{i} 0 5f',f'CQB{i} qb{i} 0 5f',f'.ic V(q{i})=0 V(qb{i})=1.8']
        for k in range(len(LEVELS)):
            t=k*625e-9+425e-9
            measure += [f'meas tran s{i}_k{k}_q find v(q{i}) at={t:.12g}',
                        f'meas tran s{i}_k{k}_qb find v(qb{i}) at={t:.12g}']
    control=f'setseed {1309200+batch}\nreset\ntran 1n 4.3u\n'+'\n'.join(measure)
    control+=f'\nwrdata {RESULTS/(name+".tsv")} v(sp) v(sn) v(q0) v(qb0) v(q24) v(qb24)'
    return name,deck(name,'\n'.join(body),control,corner='tt_mm')


def main():
    prepare()
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        for name in pool.map(lambda b:run_case(*batch_deck(b)),range(8)):
            print('simulated '+name,flush=True)
    rows=[]
    for batch in range(8):
        log=(RESULTS/f'comparator_mc_batch_{batch}.log').read_text()
        values={m.group(1):float(m.group(2)) for m in re.finditer(r'(?im)^\s*(s\d+_k\d+_q[b]?)\s*=\s*([-+0-9.eE]+)',log)}
        for i in range(25):
            diffs=[values[f's{i}_k{k}_q']-values[f's{i}_k{k}_qb'] for k in range(len(LEVELS))]
            resolved=[abs(x)>1.44 for x in diffs]
            decisions=[int(x>0) for x in diffs]
            monotonic=all(a<=b for a,b in zip(decisions,decisions[1:]))
            low=[d for d,q in zip(LEVELS,decisions) if q==0]
            high=[d for d,q in zip(LEVELS,decisions) if q==1]
            bracket=[max(low),min(high)] if low and high and monotonic else None
            rows.append(dict(sample=batch*25+i,batch=batch,instance=i,seed=1309200+batch,
                             input_levels_v=LEVELS,decisions=decisions,output_differential_v=diffs,
                             all_resolved=all(resolved),monotonic=monotonic,offset_bracket_v=bracket,
                             bracket_midpoint_estimate_v=sum(bracket)/2 if bracket else None,
                             bracket_width_v=bracket[1]-bracket[0] if bracket else None,
                             within_tested_range=bool(bracket is not None)))
    result=dict(evidence_level='200 actual PDK tt_mm dynamic-comparator instances; finite staircase input-offset brackets, NOT whole ADC MC',
                nominal_vdd=1.8,nominal_temperature_c=27,sample_count=len(rows),comparisons=len(rows)*len(LEVELS),
                source_resistance_ohm=350,input_capacitance_f=81.28512e-12,output_load_f=5e-15,
                resolved_sample_count=sum(r['all_resolved'] for r in rows),monotonic_sample_count=sum(r['monotonic'] for r in rows),
                bracketed_sample_count=sum(r['within_tested_range'] for r in rows),
                smallest_bracket_v=min(r['bracket_width_v'] for r in rows if r['bracket_width_v'] is not None),
                largest_bracket_v=max(r['bracket_width_v'] for r in rows if r['bracket_width_v'] is not None),
                samples=rows,limitations=['Offset midpoint is a bounded estimate, not a high-resolution measurement',
                   'No stochastic transient device noise; mismatch is not noise',
                   'No whole-ADC yield or calibration pass assertion','Only nominal VDD/temperature in this screen'],
                source_sha256=hashlib.sha256((HERE/'adc_blocks.spice').read_bytes()).hexdigest())
    (RESULTS/'comparator_mismatch_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='samples'},indent=2))


if __name__=='__main__':main()
