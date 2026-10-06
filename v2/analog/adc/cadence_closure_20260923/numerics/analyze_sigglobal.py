#!/usr/bin/env python3
"""Review a genuine comparator run using frozen checks and all-point comparisons."""
import importlib.util
import json
from pathlib import Path
import numpy as np
from audit_saved_comparator import SOURCE, REPO, HERE, sha, absolute_compare, bracket
from audit_diagnose_log import audit


def main():
    spec = importlib.util.spec_from_file_location("oldcompare", SOURCE / "reset1/compare_numerics.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    run = HERE.parent / "runs/task_20260924T021925324213Z"
    reference = SOURCE / "private_runtime/reset1_comparator_strict_001"
    raw = HERE / "private_runtime/sigglobal.tran"
    bh, bn, b = old.parse(reference / "reset_decide.tran.tran")
    ch, cn, c = old.parse(raw)
    assert set(bn) == set(cn)
    c = c[:, [0] + [cn.index(n) + 1 for n in bn]]
    assert sha(run / "comparator_native_bound.scs") == sha(reference / "comparator_native_bound.scs")
    before = (reference / "input.scs").read_text()
    after = (run / "input.scs").read_text()
    expected = before.replace("iabstol=1e-14", "iabstol=1e-14 maxwarns=1000 maxwarnstologfile=1000 maxnotes=1000 maxnotestologfile=1000").replace("errpreset=conservative", "errpreset=conservative relref=sigglobal")
    assert expected == after, "Unexpected circuit, model, or stimulus change"
    idx = {n: i + 1 for i, n in enumerate(bn)}
    t, u = b[:, 0], c[:, 0]
    previous = json.loads((SOURCE / "reset1/comparator_fixture/run_strict_001_review.json").read_text())
    checks = []
    for entry in previous["checks"]:
        at = entry["time_s"]
        v = {n: float(np.interp(at, u, c[:, idx[n]])) for n in entry["voltages"] if n != "time"}
        observed = {n: 1 if v[n] >= .7*v["VDD"] else 0 if v[n] <= .3*v["VDD"] else None for n in entry["expected"]}
        active = None
        if entry["kind"] == "decision":
            control = "XCMP.XADC_XCMP_S_BAR" if entry["expected"]["Q"] else "XCMP.XADC_XCMP_R_BAR"
            active = v[control] <= .3*v["VDD"]
        checks.append({"time_s": at, "kind": entry["kind"], "expected": entry["expected"], "observed": observed, "voltages": v, "actual_SR_asserted": active, "pass": observed == entry["expected"] and active is not False})
    precharges = []
    for entry in previous["precharge_checks"]:
        at = entry["time_s"]
        values = {n: float(np.interp(at, u, c[:, idx[n]])) for n in ["VDD", "XCMP.XADC_XCMP_DPOS", "XCMP.XADC_XCMP_DNEG"]}
        precharges.append({"time_s": at, "values": values, "pass": min(values["XCMP.XADC_XCMP_DPOS"], values["XCMP.XADC_XCMP_DNEG"]) >= .7*values["VDD"]})
    eval_pre = old.crossing(t, b[:, idx["EVAL"]], .18, "rising") - 1e-9
    captures = (5 + np.arange(7)*.625 + .3115)*1e-6
    grids = {"union_accepted": np.union1d(t, u), "common_1ns": np.arange(9201)*1e-9, "pre_EVAL": eval_pre, "pre_capture": captures}
    channels = {n: [n] for n in bn}
    channels["preamp_differential"] = ["XCMP.XADC_PREP", "XCMP.XADC_PREN"]
    channels["ideal_input_differential_not_CDAC"] = ["TN", "TP"]
    compared = {}
    for channel, nodes in channels.items():
        y = sum((1 if i == 0 else -1)*b[:, idx[n]] for i, n in enumerate(nodes))
        z = sum((1 if i == 0 else -1)*c[:, idx[n]] for i, n in enumerate(nodes))
        output = {}
        for grid_name, g in grids.items():
            delta = np.interp(g, u, z) - np.interp(g, t, y)
            i = int(np.argmax(abs(delta)))
            output[grid_name] = {"max_abs_v": float(abs(delta[i])), "time_s": float(g[i]), "diagnostic_0_05lsb_pass": bool(abs(delta[i]) <= .05*.8/4096)}
        compared[channel] = output
    edges = {}
    for n, threshold, direction in [("Q", 1.26, "rising"), ("Q", .54, "falling"), ("XCMP.XADC_XCMP_S_BAR", .54, "falling"), ("XCMP.XADC_XCMP_R_BAR", .54, "falling")]:
        a = old.crossing(t, b[:, idx[n]], threshold, direction)
        d = old.crossing(u, c[:, idx[n]], threshold, direction)
        same = len(a) == len(d)
        edges[n + "/" + direction] = {"old_alllocal_s": a.tolist(), "sigglobal_s": d.tolist(), "same_count": same, "max_abs_delta_s": float(max(abs(d-a))) if same and len(a) else None}
    result = {
        "status": "FUNCTIONAL_DIAGNOSTIC_NOT_NUMERICALLY_QUALIFIED",
        "scope": "87-device comparator fixture; physical CDAC/reference ADC gate absent",
        "model_and_stimulus_identity_checked": True,
        "profiles": {"old_strict_alllocal": bh, "sigglobal": ch},
        "functional_checks_pass": all(x["pass"] for x in checks + precharges),
        "real_decision_count": sum(x["kind"] == "decision" for x in checks),
        "checks": checks, "precharge_checks": precharges,
        "log_audit": audit(run / "spectre.out"),
        "comparisons_to_old_alllocal": compared,
        "edges": edges,
        "raw_sha256": {"sigglobal": sha(raw), "old_alllocal": sha(reference / "reset_decide.tran.tran")},
        "limitations": ["No shifted/aligned/excluded switching edges.", "This compares different relative-error reference methods, not an identical-method tightening experiment.", "One remaining LTE relaxation prevents calling the run clean.", "The same sigglobal method still needs a tighter comparison before inference about convergence."]
    }
    target = HERE / "sigglobal_waveform_review.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"functional_checks_pass": result["functional_checks_pass"], "real_decisions": result["real_decision_count"], "preamp": compared["preamp_differential"], "edges": edges}, indent=2))


if __name__ == "__main__":
    main()
