#!/usr/bin/env python3
"""DEPRECATED, unqualified B-source SAR harness; previous attempts were aborted.

Use the actual RTL/SPICE bridge under v2/integration for full conversion tests.
This historical experiment remains available only with an explicit flag.

The only digital decision threshold observes the REAL StrongARM output rails,
not an ideal comparison of the sampled analog input. Behavioral sources and
ideal memory switches implement testbench-only SAR timing and code retention.
This is NOT the synthesized RTL or fully transistor-level digital controller.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path

import numpy as np

from run_adc import HERE, RESULTS, LSB, deck, prepare, run_case, table, interp


def triple_switch(stem, bottom, target, weight=1):
    # Three nonoverlapping physical TG paths: VCM during acquisition, then
    # VREFP or VREFN. Clock drive itself is testbench ideal voltage control.
    wn = min(8, .84*weight**.5)
    wp = 2*wn
    return [f"B{stem}_bit {stem}_bit 0 V={target}",
            f"X{stem}_mux {bottom} {stem}_bit acq conv rp rn cm vdd 0 adc_ref_switch WN={wn:.8g} WP={wp:.8g}"]


def sar_deck(name, vin, source_r=350, ref_r=10, dsize=0):
    body = ["* Testbench digital sequencer is ideal; analog decision path is SKY130 MOS/MIM.",
            "VDD vdd 0 1.8", "VCM cm 0 .9", "VRP srp 0 1.1", "VRN srn 0 .7",
            f"RRP srp rp {ref_r}", f"RRN srn rn {ref_r}",
            f"VIP srcp 0 {.9+vin/2:.12g}", f"VIN srcn 0 {.9-vin/2:.12g}",
            f"RSP srcp ip {max(source_r,.001)}", f"RSN srcn inn {max(source_r,.001)}",
            "VEN en 0 PWL(0 1.8 2.49u 1.8 2.491u 0)",
            "VENB enb 0 PWL(0 0 2.49u 0 2.491u 1.8)",
            "VACQ acq 0 PWL(0 1.8 2.50u 1.8 2.501u 0)",
            "VCONV conv 0 PWL(0 0 2.52u 0 2.521u 1.8)",
            "XSP ip tp en enb vdd 0 adc_tgate", "XSN inn tn en enb vdd 0 adc_tgate",
            "RDC_P tp 0 1e15", "RDC_N tn 0 1e15",
            f"XCMP tp tn op on clk vdd 0 adc_latched_comparator ADC_PAIR_WIDTH_SKEW={dsize}",
            "CLOADP op 0 5f", "CLOADN on 0 5f",
            ".ic V(op)=0 V(on)=1.8",
            "BDEC decision 0 V=.9*(1+tanh((V(op)-V(on))/.02))",
            ".model MEMSW sw ron=1 roff=1e18 vt=.9 vh=.1"]
    clocks = ["0 0", "2.5u 0"]
    for k in range(12):
        b = 11-k
        start = 2.5e-6 + k*625e-9
        end = start + 625e-9
        eval_start = start + 315e-9
        clocks += [f"{eval_start:.12g} 0", f"{eval_start+1e-9:.12g} 1.8",
                   f"{end-4e-9:.12g} 1.8", f"{end-3e-9:.12g} 0"]
        # Capture after regeneration, 25 ns before next code update. At the
        # decision edge, trial bit is retained only if comparator says positive.
        body += [f"VSAVE{b} save{b} 0 PWL(0 0 {end-26e-9:.12g} 0 {end-25e-9:.12g} 1.8 {end-10e-9:.12g} 1.8 {end-9e-9:.12g} 0)",
                 f"SSAVE{b} decision mem{b} save{b} 0 MEMSW", f"CMEM{b} mem{b} 0 1p",
                 f"RMEM{b} mem{b} 0 1e15", f".ic V(mem{b})=0",
                 f"BBIT{b} bit{b} 0 V=(.5*(1+tanh((time-{start:.12g})/.5n)))*(1.8+(.5*(1+tanh((time-{end-8e-9:.12g})/.5n)))*(V(mem{b})-1.8))",
                 f"BNBIT{b} nbit{b} 0 V=1.8-V(bit{b})"]
        body += triple_switch(f"p{b}", f"bp{b}", f"V(nbit{b})",1<<b)
        body += triple_switch(f"n{b}", f"bn{b}", f"V(bit{b})",1<<b)
    body += ["VCLK clk 0 PWL(" + " ".join(clocks) + ")"]
    body += triple_switch("pdummy", "dp", "1.8")
    body += triple_switch("ndummy", "dn", "0")
    body += ["XCP tp " + " ".join(f"bp{b}" for b in reversed(range(12))) + " dp adc_cdac12",
             "XCN tn " + " ".join(f"bn{b}" for b in reversed(range(12))) + " dn adc_cdac12"]
    cols = "v(tp) v(tn) v(op) v(on) v(clk) v(rp) v(rn) i(vdd) i(vrp) i(vrn) " + " ".join(f"v(mem{b})" for b in reversed(range(12)))
    return deck(name,"\n".join(body),f"tran 2n 10.1u\nwrdata {RESULTS/(name+'.tsv')} {cols}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs",type=int,default=1)
    ap.add_argument("--suite",choices=["smoke","transfer"],default="transfer")
    ap.add_argument("--allow-deprecated-harness",action="store_true")
    args = ap.parse_args()
    if not args.allow_deprecated_harness:
        ap.error('This historical B-source harness had convergence/timeouts and is not an acceptance test. Use v2/integration actual RTL co-simulation; opt in explicitly only to investigate the archived failure.')
    prepare()
    inputs = [-.3,0,.3] if args.suite=="smoke" else list(np.linspace(-.39,.39,33))+[-.0002,-.0001,.0001,.0002]
    specs = [{"name":f"sar_{v:+.7f}","input_diff_v":float(v)} for v in inputs]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for name in pool.map(lambda spec: run_case(spec["name"],sar_deck(spec["name"],spec["input_diff_v"])),specs):
            print("simulated "+name,flush=True)
    rows=[]
    for spec in specs:
        d=table(spec["name"])
        bits = [int(interp(d,10.08e-6,col)>.9) for col in range(11,23)]
        code=sum(bit*(1<<(11-i)) for i,bit in enumerate(bits))
        ideal_code=int(np.clip(np.floor((spec["input_diff_v"]+.4)/LSB),0,4095))
        decisions=[]
        for k in range(12):
            t=2.5e-6+(k+1)*625e-9-20e-9
            od=interp(d,t,3)-interp(d,t,4)
            decisions.append({"bit":11-k,"held_bit":bits[k],"output_diff_v":od,
                              "resolved":bool(abs(od)>1.44),"input_residual_v":interp(d,t,1)-interp(d,t,2)})
        p_supply=float(np.trapezoid(-1.8*d[:,8],d[:,0])/d[-1,0])
        p_ref=float(np.trapezoid(-1.1*d[:,9]-.7*d[:,10],d[:,0])/d[-1,0])
        rows.append({**spec,"raw_code":code,"ideal_code":ideal_code,"code_error_lsb":code-ideal_code,
                     "decoded_midcode_v":(code+.5)*LSB-.4,"all_decisions_resolved":all(x["resolved"] for x in decisions),
                     "decisions":decisions,"analog_supply_power_w":p_supply,"net_reference_power_w":p_ref,
                     "vrefp_max_deviation_v":float(np.max(np.abs(d[:,6]-1.1))),
                     "vrefn_max_deviation_v":float(np.max(np.abs(d[:,7]-.7)))})
    summary={"evidence_level":"closed-loop real SKY130 analog ADC, ideal digital sequencer; deterministic nominal schematic",
             "sample_rate_sps":100000,"reference_source_ohm":10,"input_source_ohm_per_side":350,
             "samples":rows,"worst_absolute_code_error_lsb":max(abs(r["code_error_lsb"]) for r in rows),
             "all_decisions_resolved":all(r["all_decisions_resolved"] for r in rows),
             "not_qualified":["Full-code INL/DNL", "Noise-inclusive SNDR/ENOB", "PDK mismatch", "45-point PVT",
                              "Synthesized real digital logic integration", "Clock/control energy", "Layout/extraction", "AFE integration"]}
    (RESULTS/"sar_transistor_summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="samples"},indent=2))


if __name__=="__main__":
    main()
