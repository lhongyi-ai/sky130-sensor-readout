#!/usr/bin/env python3
"""Full accepted-time union comparison, bounded memory, no excluded edges.

Designed for actual school AMS run directories, not synthetic waveform claims.
It never promotes an interrupted run or warning-bearing run to qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from psf_stream import Trace
from measurement_domain import contract

PREFIX = "p2_ams_reset1."
CHANNELS = {
    "CDAC_TP_minus_TN": (PREFIX+"adc.XADC_TP", PREFIX+"adc.XADC_TN"),
    "RP": (PREFIX+"rp",), "RN": (PREFIX+"rn",), "VCM": (PREFIX+"vcm",),
}
LIMIT = .05*.8/4096


def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()


def fixed_configuration(text):
    """Only numerical tolerance and maxstep may differ in a precision pair."""
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    for name in ["reltol", "vabstol", "iabstol", "maxstep"]:
        text = re.sub(r"\b"+name+r"=\S+", name+"=<PRECISION_SETTING>", text)
    return " ".join(text.split())


def union_compare(rows_a, rows_b, channels, domain_end=None):
    """Compare piecewise-linear signals at all accepted times in shared interval.

    Missing tails are reported, never extrapolated. Callers cannot mark such a
    comparison fully qualified. Both iterators are drained for provenance.
    """
    ia,ib=iter(rows_a),iter(rows_b)
    a0,b0=next(ia),next(ib)
    if a0["time"]!=b0["time"]:raise ValueError("Different initial times")
    start=a0["time"];a1=next(ia,None);b1=next(ib,None)
    result={k:{"max_abs_V":0.,"worst_time_s":start,"signed_difference_V":0.} for k in channels}
    domain_result={k:dict(v) for k,v in result.items()}
    tail_result={k:dict(v) for k,v in result.items()}
    domain_count=0;tail_count=0
    count=0;end=start
    def value(lo,hi,t,ns):
        q=0. if hi is None else (t-lo["time"])/(hi["time"]-lo["time"])
        return sum((1 if i==0 else -1)*(lo[n]+q*((hi[n] if hi else lo[n])-lo[n])) for i,n in enumerate(ns))
    def observe(t):
        nonlocal count,end,domain_count,tail_count
        count+=1;end=t
        if domain_end is not None:
            if t<=domain_end:domain_count+=1
            if t>=domain_end:tail_count+=1
        for name,ns in channels.items():
            d=value(b0,b1,t,ns)-value(a0,a1,t,ns)
            entry={"max_abs_V":abs(d),"worst_time_s":t,"signed_difference_V":d,
                    "baseline_interpolated_V":value(a0,a1,t,ns),"strict_interpolated_V":value(b0,b1,t,ns),
                    "baseline_actual_bracket":[{k:r[k] for k in ("time",)+ns} for r in [a0,a1] if r is not None],
                    "strict_actual_bracket":[{k:r[k] for k in ("time",)+ns} for r in [b0,b1] if r is not None]}
            if abs(d)>result[name]["max_abs_V"]:result[name]=entry
            if domain_end is not None and t<=domain_end and abs(d)>domain_result[name]["max_abs_V"]:domain_result[name]=entry
            if domain_end is not None and t>=domain_end and abs(d)>tail_result[name]["max_abs_V"]:tail_result[name]=entry
    observe(start)
    while a1 is not None and b1 is not None:
        t=min(a1["time"],b1["time"])
        if domain_end is not None and end<domain_end<t:observe(domain_end)
        observe(t)
        if a1["time"]==t:a0,a1=a1,next(ia,None)
        if b1["time"]==t:b0,b1=b1,next(ib,None)
    lasta=a0["time"];lastb=b0["time"]
    if a1 is not None:
        lasta=a1["time"]
        for row in ia:lasta=row["time"]
    if b1 is not None:
        lastb=b1["time"]
        for row in ib:lastb=row["time"]
    output={"shared_interval_s":[start,end],"actual_end_times_s":[lasta,lastb],"full_intervals_equal":lasta==lastb,"union_point_count":count,"channels":result}
    if domain_end is not None:
        output['planned_measurement_domain']={'interval_s':[start,domain_end],'fully_covered':start==0 and end>=domain_end,'observed_until_s':min(end,domain_end),'union_points_including_endpoints':domain_count,'channels':domain_result}
        output['outside_planned_domain_audit']={'comparison_interval_s':[domain_end,end] if end>=domain_end else None,'each_saved_tail_interval_s':[[domain_end,x] if x>domain_end else None for x in [lasta,lastb]],'common_tail_union_points':tail_count,'common_tail_channels':tail_result,'unpaired_tail_present':lasta!=lastb,'scope':'All raw samples retained and read; unmatched tail cannot be compared or silently treated as zero difference.'}
    return output


def compare_runs(baseline,strict):
    names=set(n for ns in CHANNELS.values() for n in ns)
    def path(run):
        matches=list((run/"amsdControl.raw").glob("adc_closure_tran.tran.tran"))
        if len(matches)!=1:raise ValueError("Expected one physical AMS transient trace")
        return matches[0]
    pa,pb=path(baseline),path(strict);ta,tb=Trace(pa,names),Trace(pb,names)
    identities={}
    for name in ["reset1_native_bound.scs","sar_controller.v","p1_interfaces.vams","p2_ams_reset1.vams","p2_sequence.sv","profile.vh"]:
        identities[name]={"baseline":digest(baseline/name),"strict":digest(strict/name)}
        if len(set(identities[name].values()))!=1:raise ValueError("Circuit/stimulus identity mismatch: "+name)
    configuration_identity = fixed_configuration((baseline/"amsdControl.scs").read_text()) == fixed_configuration((strict/"amsdControl.scs").read_text())
    if not configuration_identity:raise ValueError("Non-precision AMS configuration mismatch")
    domain=contract(baseline)
    if domain!=contract(strict):raise ValueError('Testbench domain contracts differ')
    result=union_compare(ta.rows(),tb.rows(),CHANNELS,domain_end=domain['finish_s'])
    headers={"baseline":ta.header,"strict":tb.header}
    tightened=all(tb.header[k] <= ta.header[k]*.10000001 for k in ["reltol","abstol(V)","abstol(I)"]) and tb.header["maxstep"]<=ta.header["maxstep"]*.50000001
    same_solver = all(ta.header.get(k) is not None and ta.header[k]==tb.header.get(k) for k in ["version","temp","tnom","method","relref","errpreset","lteratio","cmin","gmin","ic","skipdc"])
    runs={}
    for label,run in [("baseline",baseline),("strict",strict)]:
        try:exitcode=int((run/"simulator_exit_code.txt").read_text().strip())
        except (FileNotFoundError,ValueError):exitcode=None
        log=(run/"xrun.log").read_text(errors="replace")
        marker=re.findall(r"P2_HANDSHAKE_PASS frames=(\d+) accepted=(\d+) aborted=(\d+) checks=(\d+) ignored_busy=(\d+) reserved=(\d+)",log)
        loss_codes={c:len(re.findall(r"WARNING \("+c+r"\)",log)) for c in ["SPECTRE-16266","SPECTRE-16578","SPECTRE-16780"]}
        review_path=run.parent/"review.json"
        review=json.loads(review_path.read_text()) if review_path.exists() else {}
        functional_pass=review.get("functional_pass") is True
        finish=re.findall(r'Simulation complete via \$finish\(1\) at time (\d+) PS \+ 0',log)
        finish_matches=len(finish)==1 and int(finish[0])==domain['finish_ps']
        runs[label]={"simulator_exit_code":exitcode,"handshake_pass_markers":marker,"LTE_failure_warning_counts":loss_codes,"no_known_LTE_loss":not any(loss_codes.values()),"integration_review_functional_pass":functional_pass,"logged_finish_ps":finish,"finish_matches_frozen_schedule":finish_matches,"completed":exitcode==0 and len(marker)==1 and functional_pass and finish_matches}
    domain_channels=result['planned_measurement_domain']['channels']
    for collection in [result['channels'],domain_channels,result['outside_planned_domain_audit']['common_tail_channels']]:
        for item in collection.values():
            item["max_abs_LSB"]=item["max_abs_V"]/(.8/4096)
            item["le_0_05_LSB"]=item["max_abs_V"]<=LIMIT
    waveform_pass=result['planned_measurement_domain']['fully_covered'] and all(v["le_0_05_LSB"] for v in domain_channels.values())
    result['scope_status']='COMPLETE_PAIR_REVIEW' if all(v['completed'] for v in runs.values()) else 'PARTIAL_DIAGNOSTIC_NOT_QUALIFIED'
    result['analyzer_sha256']={name:digest(Path(__file__).parent/name) for name in ['compare_full_adc_stream.py','psf_stream.py','measurement_domain.py']}
    result.update({"measurement_domain_contract":domain,"raw_sha256":{"baseline":digest(pa),"strict":digest(pb)},"circuit_stimulus_hash_identity":identities,"fixed_AMS_configuration_identity":configuration_identity,"same_actual_solver_method_and_environment":same_solver,"profiles":headers,"actual_tightening_verified":tightened,"runs":runs,"absolute_limit_V":LIMIT,"waveform_gate_pass":waveform_pass,"eligible_for_numeric_review":waveform_pass and tightened and same_solver and all(v["completed"] and v["no_known_LTE_loss"] for v in runs.values()),"formal_numeric_acceptance":"REQUIRES_REVIEW_OF_ALL_WARNINGS_AND_EVIDENCE","limitations":["Top-level channels summarize the entire shared raw interval; planned_measurement_domain channels summarize the complete predeclared test interval. Neither discards any switching edge inside that interval.","Same code/handshake alone cannot override voltage differences or LTE warnings.","The union retains every accepted point and switching edge; no alignment, cropping to matching frames, or extrapolation.","Waveform accuracy comparison is separate from full-code, noise, mismatch, power, and PEX acceptance.","This helper checks physical CDAC differential and RP/RN/VCM only; detailed digital and reset checks remain the integration analyzer's responsibility.","Three known LTE warning codes are checked automatically; other warnings, include/model provenance, and suppressed messages still require log review."]})
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("baseline",type=Path);p.add_argument("strict",type=Path);p.add_argument("output",type=Path);a=p.parse_args()
    result=compare_runs(a.baseline,a.strict);a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ["channels","full_intervals_equal","actual_tightening_verified","eligible_for_numeric_review"]},indent=2))
