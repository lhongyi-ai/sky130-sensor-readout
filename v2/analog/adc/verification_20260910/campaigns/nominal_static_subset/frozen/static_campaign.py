#!/usr/bin/env python3
"""Resumable real-SAR static campaign. Never qualifies noise or the full chip.

Each point is converted by the unchanged SAR RTL reading the real comparator.
No ideal input expression selects the bits. A fine ramp, not code centres,
provides transition brackets for static INL/DNL. Batches restart the analog
circuit and replay the previous point before retained measurements; this finite
history is an explicit test condition, not a continuous infinite-history ramp.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

import numpy as np

HERE = Path(__file__).resolve().parent
V2 = HERE.parents[2]
LSB = .8 / 4096
CANDIDATE = V2 / "integration/candidates/20260908T045601001817Z"
PDK = Path("/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice")
PROFILES = {
    "baseline": {"reltol": "1e-5", "abstol": "1e-13", "vntol": "1e-8", "maxstep_ns": 2},
    "strict": {"reltol": "1e-6", "abstol": "1e-14", "vntol": "1e-9", "maxstep_ns": 1},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def grid(stage, steps=32, inputs=None):
    if stage == "smoke":
        result = list(inputs or [.123])
    elif stage == "centres":
        result = [-.4 + (i + .5) * LSB for i in range(4096)]
    elif stage == "ramp":
        if steps < 16:
            raise ValueError("ramp needs at least 16 steps per nominal LSB")
        result = [-.4 + i * LSB / steps for i in range(4096 * steps + 1)]
    else:
        raise ValueError("unknown stage")
    if not result or any(not math.isfinite(x) or not -.4 <= x <= .4 for x in result):
        raise ValueError("all differential inputs must be finite within +/-0.4 V")
    return result


def make_plan(args):
    out = args.campaign.resolve()
    if out.exists():
        raise ValueError("campaign already exists; immutable plan will not be overwritten")
    points = grid(args.stage, args.steps_per_lsb, args.inputs)
    out.mkdir(parents=True)
    frozen = out / "frozen"
    frozen.mkdir()
    files = [CANDIDATE / name for name in (
        "sensor_adc_candidate.spice", "adc_blocks.spice", "adc_preamp.spice",
        "adc_reference_candidate.spice", "adc_tgate_dual_lvt_dummy.spice")]
    files += [V2 / "integration" / name for name in (
        "cosim_controller.v", "qualify_cosim.py", "sensor_phases.spice")]
    files += [V2 / "rtl/sar_controller.v", Path(__file__)]
    sources = {}
    for source in files:
        target = frozen / source.name
        target.write_bytes(source.read_bytes())
        sources[source.name] = {"source": str(source.relative_to(V2)), "sha256": sha(target)}
    bridge_path = V2 / f"integration/results/bridge_{args.vdd:g}v_qualification.json"
    bridge = json.loads(bridge_path.read_text())
    if bridge.get("status") != "LIVE_RTL_SPICE_BRIDGE_PASS" or bridge.get("vdd_v") != args.vdd:
        raise ValueError("matching bridge qualification absent")
    for name in ("integration/cosim_controller.v", "integration/qualify_cosim.py", "rtl/sar_controller.v"):
        if bridge["source_sha256"].get(name) != sha(V2 / name):
            raise ValueError("bridge source no longer matches: " + name)
    write_json(frozen / "bridge_qualification.json", bridge)
    sources["bridge_qualification.json"] = {"source": str(bridge_path.relative_to(V2)), "sha256": sha(frozen / "bridge_qualification.json")}
    plan = {
        "schema": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
        "stage": args.stage, "steps_per_lsb": args.steps_per_lsb,
        "input_v": points, "required_points": len(points), "batch_size": args.batch_size,
        "warmup_conversions": args.warmup, "corner": args.corner, "vdd_v": args.vdd,
        "temperature_c": args.temperature, "source_ohm_per_leg": 350,
        "reference_ohm": 1, "reference_external_cap_nf": 10,
        "reference_cm_mode": args.reference_cm_mode, "input_cm_offset_mv": 0,
        "numeric_profile": args.numeric_profile, "numeric": PROFILES[args.numeric_profile],
        "sources": sources, "candidate": "20260908T045601001817Z composite LVT references + four-MOS dummy top clamps + preamp",
        "signal_bandwidth_scope": "static DC; input steps are testbench settling/history stimuli, not a dynamic SNDR test",
        "complete_adc_qualified": False,
    }
    plan["plan_sha256"] = digest(plan)
    write_json(out / "plan.json", plan)
    print(json.dumps({"campaign": str(out), "points": len(points), "status": "PLANNED_NOT_RUN"}, indent=2))


def read_plan(campaign):
    plan = json.loads((campaign / "plan.json").read_text())
    expected = plan.pop("plan_sha256")
    if digest(plan) != expected:
        raise ValueError("plan was changed")
    plan["plan_sha256"] = expected
    for name, item in plan["sources"].items():
        if sha(campaign / "frozen" / name) != item["sha256"]:
            raise ValueError("frozen source changed: " + name)
    return plan


def runtime_identity():
    # Combined model directory includes the active library's corner includes.
    # Hash every file, not merely the top-level .lib header. No PDK is copied.
    model_files = {str(p.relative_to(PDK.parent)): sha(p) for p in sorted(PDK.parent.rglob("*")) if p.is_file()}
    tools = {}
    for name, command in (("ngspice", ["ngspice", "--version"]), ("verilator", ["verilator", "--version"])):
        proc = subprocess.run(command, capture_output=True, text=True, timeout=20)
        if proc.returncode:
            raise ValueError("tool identity failed: " + name)
        tools[name] = proc.stdout.strip()
    return {"pdk_library_resolved": str(PDK.resolve()), "combined_model_sha256": model_files, "tools": tools}


def sequence_for_batch(plan, start):
    ids = list(range(start, min(start + plan["batch_size"], plan["required_points"])))
    # Explicit reset boundary: replay preceding point once, not an unreported
    # assumption that physical state carries across simulator processes.
    sequence = []
    if start:
        sequence.append({"point_id": None, "input_v": plan["input_v"][start - 1], "kind": "history_replay"})
    for index in ids:
        for _ in range(plan["warmup_conversions"]):
            sequence.append({"point_id": None, "input_v": plan["input_v"][index], "kind": "warmup"})
        sequence.append({"point_id": index, "input_v": plan["input_v"][index], "kind": "retained"})
    return sequence


def pwl_input(sequence, cm, sign):
    value = cm + sign * sequence[0]["input_v"] / 2
    pairs = [f"0 {value:.16g}"]
    for index, row in enumerate(sequence[1:], 1):
        # Input changes 10 ns AFTER prior conversion's data_valid edge and
        # before the next 2.5 us acquisition ends. It never changes a held
        # residue just before its LSB decision. All changes take 1 ns.
        change = 11.014 + (index - 1) * 10
        pairs.append(f"{change:.9f}u {value:.16g}")
        value = cm + sign * row["input_v"] / 2
        pairs.append(f"{change + .001:.9f}u {value:.16g}")
    return "PWL(" + " ".join(pairs) + ")"


def make_deck(campaign, plan, sequence, binary):
    frozen = campaign / "frozen"
    module_spec = importlib.util.spec_from_file_location("frozen_bridge", frozen / "qualify_cosim.py")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    vdd = plan["vdd_v"]
    cm = vdd / 2
    rcm = cm if plan["reference_cm_mode"] == "tracking" else .9
    numeric = plan["numeric"]
    include = [f".include {frozen / name}" for name in (
        "adc_blocks.spice", "sensor_adc_candidate.spice", "adc_preamp.spice",
        "adc_reference_candidate.spice", "adc_tgate_dual_lvt_dummy.spice", "sensor_phases.spice")]
    # Saving the actual output bit vector provides an independent cross-check
    # of the Verilator log, whose $realtime may be zero in this bridge.
    signals = ["v(valid)", "v(inp)", "v(inn)"] + [f"v(data{i})" for i in range(11, -1, -1)]
    duration = 12 + 10 * (len(sequence) - 1)
    return "\n".join([
        "Frozen composite SKY130 ADC / live unchanged SAR RTL / static campaign",
        f".lib {PDK} {plan['corner']}", *include,
        f".temp {plan['temperature_c']}",
        ".options sparse method=gear " + " ".join(f"{k}={numeric[k]}" for k in ("reltol", "abstol", "vntol")),
        f"VDD vdd 0 {vdd}", f"VVCM cv 0 {cm}", f"VRP pr 0 {rcm + .2}", f"VRN nr 0 {rcm - .2}",
        "RRP pr rp 1", "RRN nr rn 1", "RCM cv vcm 1", "CRP rp 0 10n", "CRN rn 0 10n", "CCM vcm 0 10n",
        "VIP sp 0 " + pwl_input(sequence, cm, 1), "VIN sn 0 " + pwl_input(sequence, cm, -1),
        "RSP sp inp 350", "RSN sn inn 350",
        f"Vclk clk 0 PULSE(0 {vdd} 1u 1n 1n 311.5n 625n)",
        f"Vrst rst 0 PWL(0 0 200n 0 201n {vdd})", f"Vstart start 0 PWL(0 0 800n 0 801n {vdd})",
        "VG1 gain_sel1 0 0", "VG0 gain_sel0 0 0", *module.controller_elements(binary, "verilator", vdd),
        "XPHASE sample top_sample top_sample_b acq conv vdd 0 sensor_phases",
        "XADC inp inn decision decision_b top_sample top_sample_b acq conv evaluate " +
        " ".join(f"trial{i}" for i in range(11, -1, -1)) + " rp rn vcm vdd 0 sensor_adc_candidate",
        "CQ decision 0 5f", "CQB decision_b 0 5f", ".save " + " ".join(signals),
        ".control", "set num_threads=1", "set wr_singlescale", "set wr_vecnames", "set numdgt=12",
        f"tran {numeric['maxstep_ns']}n {duration}u 0 {numeric['maxstep_ns']}n",
        "wrdata waveform.dat " + " ".join(signals), "quit", ".endc", ".end", "",
    ])


def analyse_batch(directory, plan, sequence, returncode):
    log = (directory / "simulation.log").read_text(errors="replace")
    codes = [int(x) for x in re.findall(r"COSIM_RESULT time_ns=[\d.]+ code=(\d+) gain_code=0", log)]
    result = {"status": "INCOMPLETE", "returncode": returncode, "plan_sha256": plan["plan_sha256"],
              "sequence": sequence, "raw_codes": codes, "rows": [], "complete_adc_qualified": False}
    path = directory / "waveform.dat"
    if returncode != 0 or not path.exists():
        result["reason"] = "timeout, simulator failure, or missing completed waveform; partial log codes are not retained measurements"
        return result
    values = np.loadtxt(path, skiprows=1)
    if values.ndim != 2 or values.shape[1] != 16 or not np.isfinite(values).all():
        result["reason"] = "invalid waveform"
        return result
    times, valid = values[:, 0], values[:, 1]
    crossings = np.flatnonzero((valid[:-1] < plan["vdd_v"] / 2) & (valid[1:] >= plan["vdd_v"] / 2))
    if len(codes) != len(sequence) or len(crossings) != len(sequence):
        result["reason"] = "conversion / data_valid count does not equal every scheduled warmup and retained frame"
        return result
    duration = (12 + 10 * (len(sequence) - 1)) * 1e-6
    if times[-1] < duration - 1e-12:
        result["reason"] = "waveform ends before requested stop time"
        return result
    for index, (row, edge, code) in enumerate(zip(sequence, crossings, codes)):
        t0, t1 = times[edge:edge + 2]
        level0, level1 = valid[edge:edge + 2]
        time_s = float(t0 + (t1 - t0) * (plan["vdd_v"] / 2 - level0) / (level1 - level0))
        if abs(time_s - (11.0035 + index * 10) * 1e-6) > 5e-9:
            result["reason"] = "data_valid not at expected real SPICE conversion time"
            return result
        sample_at = time_s + 10e-9
        bit_volts = np.array([np.interp(sample_at, times, values[:, col]) for col in range(4, 16)])
        if np.any((bit_volts > .1 * plan["vdd_v"]) & (bit_volts < .9 * plan["vdd_v"])):
            result["reason"] = "output data not settled to a logic level"
            return result
        bus = sum(int(v > plan["vdd_v"] / 2) << (11 - i) for i, v in enumerate(bit_volts))
        if bus != code:
            result["reason"] = "actual SPICE output bus disagrees with RTL log"
            return result
        if row["point_id"] is not None:
            result["rows"].append({"point_id": row["point_id"], "input_v": row["input_v"],
                                   "raw_code": code, "valid_time_s": time_s, "bus_code": bus})
    result["status"] = "BATCH_COMPLETE_NOT_ADC_QUALIFIED"
    return result


def run(campaign, max_batches, timeout, retry):
    plan = read_plan(campaign)
    # Exclusive lock prevents accidental multi-worker runs against this plan.
    lock = campaign / "worker.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        identity = runtime_identity()
        runtime_path = campaign / "runtime.json"
        if runtime_path.exists() and json.loads(runtime_path.read_text()) != identity:
            raise ValueError("PDK or tool identity changed; start a new campaign")
        if not runtime_path.exists():
            write_json(runtime_path, identity)
        frozen = campaign / "frozen"
        build_dir = campaign / "build"
        build_dir.mkdir(exist_ok=True)
        binary = build_dir / "cosim_controller.so"
        build_manifest = build_dir / "binary.json"
        if binary.exists():
            if not build_manifest.exists() or json.loads(build_manifest.read_text())["sha256"] != sha(binary):
                raise ValueError("compiled RTL binary changed")
        else:
            compiled = subprocess.run(["ngspice", "vlnggen", "--", "-Wno-fatal", "--top-module", "cosim_controller",
                str(frozen / "cosim_controller.v"), str(frozen / "sar_controller.v")], cwd=build_dir, capture_output=True, text=True, timeout=180)
            (build_dir / "build.log").write_text(compiled.stdout + compiled.stderr)
            if compiled.returncode or not binary.exists():
                raise ValueError("unchanged RTL build failed")
            write_json(build_manifest, {"sha256": sha(binary), "plan_sha256": plan["plan_sha256"]})
        performed = 0
        for start in range(0, plan["required_points"], plan["batch_size"]):
            group = campaign / "batches" / f"{start:06d}"
            previous = sorted(group.glob("attempt_*/summary.json"))
            if previous:
                latest = json.loads(previous[-1].read_text())
                if latest.get("status") == "BATCH_COMPLETE_NOT_ADC_QUALIFIED" or not retry:
                    continue
            if performed >= max_batches:
                break
            read_plan(campaign)
            sequence = sequence_for_batch(plan, start)
            directory = group / f"attempt_{len(previous) + 1:03d}"
            directory.mkdir(parents=True)
            source = directory / "adc.spice"
            source.write_text(make_deck(campaign, plan, sequence, binary))
            init = directory / ".spiceinit"
            init.write_text("set ngbehavior=hsa\nset skywaterpdk\nset ng_nomodcheck\nset num_threads=1\n")
            write_json(directory / "summary.json", {"status": "RUNNING", "plan_sha256": plan["plan_sha256"], "sequence": sequence})
            began = time.monotonic()
            try:
                proc = subprocess.run(["ngspice", "-b", "-o", "native.log", "adc.spice"], cwd=directory,
                    env=dict(os.environ, SPICE_USERINIT_DIR=str(directory)), capture_output=True, text=True, timeout=timeout)
                returncode, log = proc.returncode, proc.stdout + proc.stderr
            except subprocess.TimeoutExpired as error:
                returncode = None
                log = f"TIMEOUT after {timeout} seconds\n" + (error.stdout or b"").decode(errors="replace") + (error.stderr or b"").decode(errors="replace")
            if (directory / "native.log").exists():
                log += (directory / "native.log").read_text(errors="replace")
            (directory / "simulation.log").write_text(log)
            result = analyse_batch(directory, plan, sequence, returncode)
            result.update({"wall_seconds": time.monotonic() - began, "deck_sha256": sha(source),
                           "runtime_sha256": sha(runtime_path), "binary_sha256": sha(binary)})
            result["artifact_sha256"] = {p.name: sha(p) for p in directory.iterdir() if p.is_file() and p.name != "summary.json"}
            write_json(directory / "summary.json", result)
            print(json.dumps({"batch_start": start, "status": result["status"], "raw_codes": result["raw_codes"], "seconds": result["wall_seconds"]}), flush=True)
            performed += 1
    finally:
        lock.unlink()


def static_metrics(xs, codes):
    """Conservative grid brackets, endpoint INL, nominal-LSB DNL intervals.

    Endpoint INL uses T1 and T4095; not affine calibration of ADC codes.
    Saturating first/last code widths use specified +/-0.4 V external bounds.
    Values close enough to a limit that grid uncertainty overlaps it are
    INCONCLUSIVE, never rounded into a pass.
    """
    x, c = np.asarray(xs), np.asarray(codes)
    if len(x) != len(c) or len(x) < 2 or np.any(np.diff(x) <= 0):
        raise ValueError("strictly increasing ramp required")
    if np.any((c < 0) | (c > 4095)) or np.any(np.diff(c) < 0):
        return {"status": "FAIL_NONMONOTONIC_OR_INVALID_CODE"}
    absent = sorted(set(range(4096)) - set(int(v) for v in c))
    if absent:
        return {"status": "FAIL_UNOBSERVED_CODES", "unobserved_codes": absent}
    edges = np.searchsorted(c, np.arange(1, 4096))
    lo, hi = x[edges - 1], x[edges]
    lower = np.r_[-.4, lo, .4]
    upper = np.r_[-.4, hi, .4]
    dnl_lo = (lower[1:] - upper[:-1]) / LSB - 1
    dnl_hi = (upper[1:] - lower[:-1]) / LSB - 1
    # Every endpoint/transition bracket combination is bounded by monotonic
    # fractional-linear expressions; explicit corner evaluation is safe.
    k = np.arange(4095)
    inl_corners = []
    for first in (lo[0], hi[0]):
        for last in (lo[-1], hi[-1]):
            for transition in (lo, hi):
                inl_corners.append((transition - first) / ((last - first) / 4094) - k)
    bounds = np.asarray(inl_corners)
    inl_lo, inl_hi = bounds.min(axis=0), bounds.max(axis=0)
    inl_lo[[0, -1]], inl_hi[[0, -1]] = 0, 0
    passed = bool(np.all(dnl_lo >= -.9) and np.all(dnl_hi <= 1.5) and np.all(inl_lo >= -1.5) and np.all(inl_hi <= 1.5))
    definite_fail = bool(np.any(dnl_hi < -.9) or np.any(dnl_lo > 1.5) or np.any(inl_hi < -1.5) or np.any(inl_lo > 1.5))
    return {"status": "GRID_STATIC_LIMITS_PASS" if passed else "STATIC_LIMIT_FAIL" if definite_fail else "GRID_RESOLUTION_INCONCLUSIVE",
            "max_transition_bracket_lsb": float(np.max((hi - lo) / LSB)),
            "dnl_envelope_lsb": [float(dnl_lo.min()), float(dnl_hi.max())],
            "endpoint_inl_envelope_lsb": [float(inl_lo.min()), float(inl_hi.max())],
            "transitions": [{"code": int(i + 1), "lower_v": float(a), "upper_v": float(b)} for i, (a, b) in enumerate(zip(lo, hi))]}


def collect(campaign):
    plan = read_plan(campaign)
    rows, missing_batches, incomplete_batches, errors = {}, [], [], []
    for start in range(0, plan["required_points"], plan["batch_size"]):
        files = sorted((campaign / "batches" / f"{start:06d}").glob("attempt_*/summary.json"))
        if not files:
            missing_batches.append(start)
            continue
        report = json.loads(files[-1].read_text())
        if report.get("status") != "BATCH_COMPLETE_NOT_ADC_QUALIFIED":
            incomplete_batches.append(start)
            continue
        directory = files[-1].parent
        if report.get("plan_sha256") != plan["plan_sha256"]:
            errors.append(f"batch {start}: source/plan mismatch")
            continue
        artifacts = report.get("artifact_sha256", {})
        required = {"adc.spice", ".spiceinit", "simulation.log", "native.log", "waveform.dat"}
        if not required <= set(artifacts) or any(not (directory / name).is_file() or sha(directory / name) != value for name, value in artifacts.items()):
            errors.append(f"batch {start}: missing or modified raw evidence")
            continue
        sequence = sequence_for_batch(plan, start)
        reanalysed = analyse_batch(directory, plan, sequence, report.get("returncode"))
        if reanalysed["status"] != "BATCH_COMPLETE_NOT_ADC_QUALIFIED" or reanalysed["rows"] != report.get("rows"):
            errors.append(f"batch {start}: raw waveform reanalysis disagrees")
            continue
        for row in report["rows"]:
            index = row["point_id"]
            if index in rows or not 0 <= index < plan["required_points"] or row["input_v"] != plan["input_v"][index]:
                errors.append(f"batch {start}: duplicate, extra or wrong stimulus")
            else:
                rows[index] = row
    complete = not (errors or missing_batches or incomplete_batches) and len(rows) == plan["required_points"]
    result = {"status": "INCOMPLETE_COVERAGE", "stage": plan["stage"], "plan_sha256": plan["plan_sha256"],
              "required_points": plan["required_points"], "completed_points": len(rows),
              "missing_batches": missing_batches, "incomplete_batches": incomplete_batches, "errors": errors,
              "complete_adc_qualified": False, "full_chip_qualified": False,
              "limitations": ["Deterministic transistor static test; no device-noise SNDR or mismatch claim.",
                  "Ideal logic-voltage bridges; unchanged RTL, not routed digital power or delay.",
                  "Schematic composite ADC; no whole-ADC extracted layout.",
                  "Each batch starts from OP/reset and replays one preceding point; history protocol is finite.",
                  "A single numerical profile is not a convergence study or final static signoff."]}
    if complete:
        result["status"] = "SMOKE_POINTS_COMPLETE_NOT_LINEARITY" if plan["stage"] == "smoke" else "CENTRE_GRID_COMPLETE_NOT_LINEARITY"
        ordered = [rows[i] for i in range(plan["required_points"])]
        result["observed_unique_codes"] = len(set(row["raw_code"] for row in ordered))
        if plan["stage"] == "ramp":
            result["static_grid"] = static_metrics(plan["input_v"], [r["raw_code"] for r in ordered])
            result["status"] = result["static_grid"]["status"] + "_NUMERICAL_CONVERGENCE_PENDING"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    write_json(campaign / ("coverage_" + stamp + ".json"), result)
    print(json.dumps({k: v for k, v in result.items() if k != "static_grid"}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("campaign", type=Path)
    p.add_argument("--stage", choices=("smoke", "centres", "ramp"), default="smoke")
    p.add_argument("--inputs", type=float, nargs="+")
    p.add_argument("--steps-per-lsb", type=int, default=32)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--corner", choices=("tt", "ff", "ss", "fs", "sf"), default="tt")
    p.add_argument("--vdd", type=float, choices=(1.62, 1.8, 1.98), default=1.8)
    p.add_argument("--temperature", type=float, choices=(-20, 27, 85), default=27)
    p.add_argument("--reference-cm-mode", choices=("tracking", "fixed"), default="tracking")
    p.add_argument("--numeric-profile", choices=PROFILES, default="baseline")
    r = sub.add_parser("run")
    r.add_argument("campaign", type=Path)
    r.add_argument("--max-batches", type=int, default=1)
    r.add_argument("--timeout-seconds", type=float, default=900)
    r.add_argument("--retry-incomplete", action="store_true")
    c = sub.add_parser("collect")
    c.add_argument("campaign", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        if args.batch_size < 1 or args.warmup < 0 or (args.inputs and args.stage != "smoke"):
            parser.error("invalid batching or input override")
        make_plan(args)
    elif args.command == "run":
        if args.max_batches < 1 or args.timeout_seconds <= 0:
            parser.error("positive batch count and timeout required")
        run(args.campaign.resolve(), args.max_batches, args.timeout_seconds, args.retry_incomplete)
    else:
        result = collect(args.campaign.resolve())
        return 2 if result["status"] == "INCOMPLETE_COVERAGE" else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
