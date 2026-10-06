#!/usr/bin/env python3
"""Same-input prefix determinism only; never a precision/convergence PASS."""
import argparse
import itertools
import json
from pathlib import Path
from psf_stream import Trace
from compare_full_adc_stream import digest


def check(partial,complete):
    files=["amsdControl.scs","reset1_native_bound.scs","sar_controller.v","p1_interfaces.vams","p2_ams_reset1.vams","p2_sequence.sv","profile.vh"]
    hashes={f:{"partial":digest(partial/f),"complete":digest(complete/f)} for f in files}
    if any(h["partial"]!=h["complete"] for h in hashes.values()):raise ValueError("Same-input repeat required")
    rel="amsdControl.raw/adc_closure_tran.tran.tran"
    traces=[Trace(partial/rel),Trace(complete/rel)]
    rows=[0,0];ends=[None,None];equal_prefix=0;first_difference=None;grid_mismatches=0;value_mismatches=0
    for a,b in itertools.zip_longest(*(t.rows() for t in traces)):
        for i,r in enumerate([a,b]):
            if r is not None:rows[i]+=1;ends[i]=r["time"]
        if a is None or b is None:continue
        if a==b:
            if first_difference is None:equal_prefix+=1
        else:
            if a["time"]!=b["time"]:grid_mismatches+=1
            else:value_mismatches+=1
            if first_difference is None:
                first_difference={"row":rows[0],"time_partial_s":a["time"],"time_complete_s":b["time"],"different_channels":[k for k in a if a[k]!=b.get(k)]}
    return {"scope":"SAME_INPUT_REPEAT_PREFIX_DIAGNOSTIC_NOT_NUMERICAL_QUALIFICATION","source_identity":hashes,"raw_sha256":{"partial":digest(partial/rel),"complete":digest(complete/rel)},"row_counts":rows,"end_times_s":ends,"trace_count":len(traces[0].names),"identical_prefix_rows":equal_prefix,"first_differing_shared_row":first_difference,"shared_row_time_mismatches":grid_mismatches,"same_time_row_value_mismatches":value_mismatches,"entire_shorter_trace_exactly_reproduced":equal_prefix==min(rows),"limitations":["The interrupted run remains incomplete; shared-prefix identity does not grant any convergence or waveform-accuracy PASS.","Both runs use the same tolerances; only a separately tightened physical full-ADC comparison can test numerical convergence.","Same printed warnings are retained and require independent investigation."]}


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("partial",type=Path);p.add_argument("complete",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    result=check(a.partial,a.complete);a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ["source_identity","raw_sha256"]},indent=2))
