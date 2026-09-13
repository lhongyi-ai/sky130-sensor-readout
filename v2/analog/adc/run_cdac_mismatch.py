#!/usr/bin/env python3
"""200 PDK capacitor-array samples, not 200 whole-ADC Monte Carlo samples.

Each sample has independent statistical binary MIM banks and a dummy on both
sides. AC currents measure actual instantiated capacitances; charge-conservation
then predicts ideal-switch, ideal-comparator CDAC static thresholds. No synthetic
random perturbation is added, and no silicon-yield statement is made.
"""
import hashlib
import json
import math

import numpy as np

from run_adc import HERE, RESULTS, LSB, deck, prepare, run_case


def main():
    prepare()
    body=[]; writes=[]
    samples=200
    for s in range(samples):
        currents=[]
        for side in ["p","n"]:
            for bank in range(13):
                weight=(1<<bank) if bank<12 else 1
                tag=f"s{s}_{side}_{bank}"
                body += [f"V{tag} {tag} 0 DC 0 AC 1",f"X{tag} {tag} 0 adc_mim_bank COUNT={weight}"]
                currents.append(f"imag(i(v{tag}))")
        writes.append(f"wrdata {RESULTS / ('cdac_mc_'+str(s)+'.tsv')} " + " ".join(currents))
    controls="setseed 1309026\nreset\nac lin 1 1000 1000\n"+"\n".join(writes)
    name="cdac_mismatch_200"
    run_case(name,deck(name,"\n".join(body),controls,corner="tt_mm"))
    codes=np.arange(4096)
    bits=((codes[:,None]>>np.arange(12)[None,:])&1)
    rows=[]
    for s in range(samples):
        raw=np.loadtxt(RESULTS/f"cdac_mc_{s}.tsv",skiprows=1)
        caps=np.abs(raw[1:])/(2*math.pi*1000)
        p,n=caps[:13],caps[13:]
        normalized=p[:12]/p.sum()+n[:12]/n.sum()
        thresholds=-.4+.4*(bits@normalized)
        all_boundaries=np.r_[thresholds,.4]
        dnl=np.diff(all_boundaries)/LSB-1
        interior=thresholds[1:]
        slope=(interior[-1]-interior[0])/4094
        endpoint=interior[0]+np.arange(4095)*slope
        inl=(interior-endpoint)/slope
        good=bool(np.all(np.diff(all_boundaries)>0) and np.max(np.abs(inl))<=1.5 and dnl.min()>=-.9 and dnl.max()<=1.5)
        rows.append(dict(sample=s,capacitances_f=caps.tolist(),cap_p_f=float(p.sum()),cap_n_f=float(n.sum()),
                         max_abs_endpoint_inl_lsb=float(np.max(np.abs(inl))),min_dnl_lsb=float(dnl.min()),
                         max_dnl_lsb=float(dnl.max()),monotonic=bool(np.all(np.diff(all_boundaries)>0)),
                         static_cdac_only_pass=good))
    summary=dict(evidence_level="PDK MIM mismatch -> charge-conservation CDAC-only static prediction; NOT full ADC MC",
                 corner="tt_mm",seed=1309026,independent_array_samples=samples,banks_per_array_pair=26,
                 matched_units_per_bank="m=COUNT mult=COUNT; independently qualified root semantics",
                 pass_count=sum(r['static_cdac_only_pass'] for r in rows),fail_count=sum(not r['static_cdac_only_pass'] for r in rows),
                 worst_inl_lsb=max(r['max_abs_endpoint_inl_lsb'] for r in rows),
                 worst_min_dnl_lsb=min(r['min_dnl_lsb'] for r in rows),worst_max_dnl_lsb=max(r['max_dnl_lsb'] for r in rows),
                 samples=rows,exclusions=["Comparator mismatch/noise", "Switch mismatch/charge injection", "Reference driver",
                                         "Spatial gradients", "Extracted parasitics", "PGA mismatch", "Whole-chip yield"],
                 source_sha256=hashlib.sha256((HERE/'adc_blocks.spice').read_bytes()).hexdigest())
    (RESULTS/'cdac_mismatch_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='samples'},indent=2))


if __name__=='__main__':main()
