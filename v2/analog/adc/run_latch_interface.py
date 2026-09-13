#!/usr/bin/env python3
"""Verify physical CMOS decision retention across comparator reset.

Interface contract: 5 fF receiver, resolve <=250ns after evaluate rising,
hold >=5ns after evaluate falls (corresponding to the controller capture edge).
"""
import concurrent.futures
import json

import numpy as np

from run_adc import RESULTS, LSB, deck, prepare, run_case, table, interp


def main():
    prepare()
    specs = []
    for corner,vdd,temp in [("tt",1.8,27),("ss",1.62,85),("ff",1.98,-20)]:
        for sign in [-1,1]:
            name=f"latch_{corner}_{vdd}_{temp}_{sign}"
            diff=sign*LSB/4
            body=f"""
VDD vdd 0 {vdd}
VIP sp 0 PWL(0 {vdd/2+diff/2:.12g} 600n {vdd/2+diff/2:.12g} 601n {vdd/2-diff/2:.12g})
VIN sn 0 PWL(0 {vdd/2-diff/2:.12g} 600n {vdd/2-diff/2:.12g} 601n {vdd/2+diff/2:.12g})
RP sp ip 350
RN sn inn 350
XCP ip 0 adc_mim_bank COUNT=4096
XCN inn 0 adc_mim_bank COUNT=4096
VCLK clk 0 PULSE(0 {vdd} 200n 1n 1n 250n 625n)
XCMP ip inn q qb clk vdd 0 adc_latched_comparator
CP q 0 5f
CN qb 0 5f
.ic V(q)=0 V(qb)={vdd}
"""
            control=f"tran 250p 1.4u\nwrdata {RESULTS/(name+'.tsv')} v(q) v(qb) v(xcmp.dpos) v(xcmp.dneg) v(clk) i(vclk) v(ip) v(inn)"
            specs.append(dict(name=name,corner=corner,vdd=vdd,temp=temp,sign=sign,deck=deck(name,body,control,corner,temp)))
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        for name in pool.map(lambda s:run_case(s['name'],s['deck']),specs):
            print("simulated "+name,flush=True)
    rows=[]
    for spec in specs:
        d=table(spec['name']); vd=spec['vdd']
        qd=d[:,1]-d[:,2]
        polarities=[spec['sign'],-spec['sign']]
        cycles=[]
        for k,start in enumerate([200e-9,825e-9]):
            ev=(d[:,0]>=start+1e-9)&(d[:,0]<=start+249e-9)
            resolved=ev&(qd*polarities[k]>.8*vd)
            delay=float(d[resolved,0][0]-start) if np.any(resolved) else None
            hold=(d[:,0]>=start+256e-9)&(d[:,0]<=start+590e-9)
            if k==1: hold=(d[:,0]>=start+256e-9)&(d[:,0]<=1.39e-6)
            hold_good=bool(np.all(qd[hold]*polarities[k]>.8*vd))
            edge=(d[:,0]>=start)&(d[:,0]<=start+5e-9)
            charge=float(np.trapezoid(np.abs(d[edge,6]),d[edge,0]))
            cycles.append(dict(cycle=k,resolution_delay_s=delay,resolve_250ns_pass=bool(delay is not None and delay<=250e-9),
                               reset_hold_5ns_and_beyond_pass=hold_good,evaluate_edge_charge_c=charge,equivalent_clock_load_f=charge/vd))
        rows.append({k:v for k,v in spec.items() if k!='deck'}|{'cycles':cycles})
    result={'evidence_level':'SKY130 transistor comparator plus static CMOS SR latch; deterministic schematic',
            'output_load_f':5e-15,'cases':rows,
            'all_pass':all(c['resolve_250ns_pass'] and c['reset_hold_5ns_and_beyond_pass'] for r in rows for c in r['cycles']),
            'max_clock_equivalent_cap_f':max(c['equivalent_clock_load_f'] for r in rows for c in r['cycles']),
            'max_resolution_delay_s':max(c['resolution_delay_s'] or 0 for r in rows for c in r['cycles'])}
    (RESULTS/'latch_interface_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))


if __name__=='__main__':main()
