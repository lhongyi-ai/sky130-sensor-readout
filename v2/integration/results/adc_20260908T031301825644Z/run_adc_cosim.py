#!/usr/bin/env python3
"""Unchanged SAR RTL + real SKY130 ADC blocks, schematic mixed simulation.

Logic-voltage bridges are ideal testbench fixtures. The default phase generator
is an explicit SKY130 transistor/resistor/MIM circuit; ideal delays are opt-in.
This milestone cannot qualify the complete physical ADC or whole sensor chip.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import numpy as np
from qualify_cosim import controller_elements, ROOT, HERE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-v", type=float, default=0.123)
    parser.add_argument("--corner", choices=("tt", "ff", "ss", "fs", "sf"), default="tt")
    parser.add_argument("--vdd", type=float, default=1.8)
    parser.add_argument("--temperature", type=float, default=27)
    parser.add_argument("--reference-r", type=float, default=1.0)
    parser.add_argument("--reference-c-nf",type=float,default=10.0)
    parser.add_argument("--source-r",type=float,choices=(0,350,1000),default=350)
    parser.add_argument("--duration-us", type=float, default=40.0)
    parser.add_argument("--phase-source", choices=("transistor", "ideal"), default="transistor")
    parser.add_argument("--frontend", type=Path, help="explicit frozen frontend PDK netlist snapshot")
    parser.add_argument("--adc-wrapper",type=Path,default=ROOT / "analog/adc/adc_analog12.spice")
    parser.add_argument("--adc-subckt",default="adc_analog12")
    parser.add_argument("--adc-preamp",type=Path,help="optional real transistor preamplifier include")
    parser.add_argument("--gain", type=int, choices=(1,4,16), default=1)
    args = parser.parse_args()
    if not -.4 <= args.input_v <= .4 or args.reference_r <= 0 or args.reference_c_nf <= 0 or args.duration_us < 12:
        parser.error("invalid ADC input, reference resistance, or conversion duration")
    if args.vdd not in (1.62,1.8,1.98):
        parser.error("only frozen specification supply points are accepted")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*",args.adc_subckt):
        parser.error("invalid ADC subcircuit name")
    qualification = HERE / f"results/bridge_{args.vdd:g}v_qualification.json"
    if not qualification.exists() or json.loads(qualification.read_text()).get("status") != "LIVE_RTL_SPICE_BRIDGE_PASS":
        parser.error("qualify_cosim.py must first qualify the logic bridge at this supply")
    out = HERE / "results" / ("adc_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True)
    report_path = out / "summary.json"
    argument_report = {key: str(value) if isinstance(value,Path) else value for key,value in vars(args).items()}
    initial = {"status": "RUNNING", "full_chip_qualified": False, "ideal_phase_fixture": args.phase_source=="ideal", "arguments": argument_report}
    report_path.write_text(json.dumps(initial, indent=2) + "\n")
    files = [HERE / "cosim_controller.v", HERE / "qualify_cosim.py", Path(__file__), ROOT / "rtl/sar_controller.v",
             ROOT / "analog/adc/adc_blocks.spice", args.adc_wrapper.resolve(), HERE / "sensor_phases.spice"]
    if args.adc_preamp:
        files.append(args.adc_preamp.resolve())
    if args.frontend:
        files.append(args.frontend.resolve())
    source_hashes = {}
    for path in files:
        data = path.read_bytes()
        (out / path.name).write_bytes(data)
        source_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    env = dict(os.environ, SPICE_USERINIT_DIR=str(out))
    (out / ".spiceinit").write_text("set ngbehavior=hsa\nset skywaterpdk\nset ng_nomodcheck\nset num_threads=1\n")
    build = subprocess.run(["ngspice", "vlnggen", "--", "-Wno-fatal", "--top-module", "cosim_controller",
                            "cosim_controller.v", "sar_controller.v"], cwd=out, env=env,
                           capture_output=True, text=True, timeout=180)
    (out / "build.log").write_text(build.stdout+build.stderr)
    binary = out / "cosim_controller.so"
    if build.returncode or not binary.exists():
        raise RuntimeError("RTL co-simulation build failed")
    vcm = args.vdd/2
    gain_code = {1:0,4:1,16:2}[args.gain]
    sensor_gain = args.gain if args.frontend else 1
    analog_frontend = ([f".include {args.frontend.name}",
        "XAFE sensorp sensorn inp inn vdd 0 vcm gain0 gain1 sky130_v2_switchable_sample_driver"]
        if args.frontend else ["VLINKP sensorp inp 0", "VLINKN sensorn inn 0"])
    phases = (["XPHASE sample top_sample top_sample_b acq conv vdd 0 sensor_phases"]
        if args.phase_source=="transistor" else [
             "Atop d_sample d_top phase_top", ".model phase_top d_buffer(rise_delay=20n fall_delay=0.5n)",
             "Aacq d_sample d_acq phase_acq", ".model phase_acq d_buffer(rise_delay=10n fall_delay=10n)",
             "Aconv d_sample d_conv phase_conv", ".model phase_conv d_inverter(rise_delay=30n fall_delay=0.5n)",
             "Aphase [d_top d_acq d_conv] [top_sample acq conv] logic_out",
             "XTOPB top_sample top_sample_b vdd 0 adc_inv"])
    source_connections = ([f"RINP vinp sensorp {args.source_r}",f"RINN vinn sensorn {args.source_r}"]
        if args.source_r else ["VSOURCEP vinp sensorp 0","VSOURCEN vinn sensorn 0"])
    lines = [f"SKY130 ADC real-transistor / unchanged-RTL mixed simulation; {args.phase_source} phases",
             f".lib /foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice {args.corner}",
             ".include adc_blocks.spice", f".include {args.adc_wrapper.name}", ".include sensor_phases.spice",
             *([f".include {args.adc_preamp.name}"] if args.adc_preamp else []),
             f".temp {args.temperature}", ".options reltol=1e-4 abstol=1e-12 vntol=1e-7 method=gear",
             f"VDD vdd 0 {args.vdd}", f"VVCM vcm_ideal 0 {vcm}",
             f"VVRP rp_ideal 0 {vcm+.2}", f"VVRN rn_ideal 0 {vcm-.2}",
             f"RRP rp_ideal rp_local {args.reference_r}", f"RRN rn_ideal rn_local {args.reference_r}",
             f"RVCM vcm_ideal vcm_local {args.reference_r}",
             f"CRP rp_local 0 {args.reference_c_nf}n", f"CRN rn_local 0 {args.reference_c_nf}n", f"CVCM vcm_local 0 {args.reference_c_nf}n",
             "VPORTP rp_local rp 0", "VPORTN rn_local rn 0", "VPORTCM vcm_local vcm 0",
             f"VINP vinp 0 {vcm+args.input_v/2/sensor_gain}", f"VINN vinn 0 {vcm-args.input_v/2/sensor_gain}",
             *source_connections, *analog_frontend,
             f"Vclk clk 0 PULSE(0 {args.vdd} 1u 1n 1n 311.5n 625n)",
             f"Vrst rst 0 PWL(0 0 200n 0 201n {args.vdd})",
             f"Vstart start 0 PWL(0 0 800n 0 801n {args.vdd})",
             f"Vg1 gain_sel1 0 {args.vdd*(gain_code//2)}", f"Vg0 gain_sel0 0 {args.vdd*(gain_code%2)}", *controller_elements(binary, "verilator",args.vdd), *phases,
             "XADC inp inn decision decision_b top_sample top_sample_b acq conv evaluate "
                 + " ".join(f"trial{i}" for i in range(11,-1,-1)) + f" rp rn vcm vdd 0 {args.adc_subckt}",
             "CQ decision 0 5f", "CQB decision_b 0 5f",
             ".control", "set num_threads=1", "set wr_singlescale", "set wr_vecnames", "set numdgt=12",
             f"tran 2n {args.duration_us}u 0 2n",
             "wrdata waveform.dat v(clk) v(top_sample) v(acq) v(conv) v(evaluate) v(valid) v(xadc.tp) v(xadc.tn) v(decision) v(decision_b) v(rp) v(rn) v(vcm) i(vdd) i(vportp) i(vportn) i(vportcm)",
             "quit", ".endc", ".end", ""]
    (out / "adc.spice").write_text("\n".join(lines))
    try:
        proc = subprocess.run(["ngspice", "-b", "-o", "native.log", "adc.spice"], cwd=out, env=env,
                              capture_output=True, text=True, timeout=300)
        log, rc = proc.stdout+proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as error:
        rc = None
        log = "TIMEOUT after 300 seconds\n"+(error.stdout or b"").decode(errors="replace")+(error.stderr or b"").decode(errors="replace")
    log += (out / "native.log").read_text(errors="replace") if (out / "native.log").exists() else ""
    (out / "simulation.log").write_text(log)
    codes = [int(c) for c in re.findall(r"COSIM_RESULT time_ns=[\d.]+ code=(\d+) gain_code=\d+", log)]
    expected = min(4095, math.floor((args.input_v+.4)/(.8/4096)))
    report = {**initial, "status": "FAIL", "source_sha256": source_hashes, "run": str(out.relative_to(ROOT)),
              "returncode": rc, "raw_codes": codes, "expected_ideal_code": expected,
              "code_error_lsb": [c-expected for c in codes], "complete_adc_qualified": False,
              "limitations": ["Only short deterministic conversion check, not full-code linearity or noise-inclusive FFT.",
                  "Live original RTL with ideal logic-voltage bridges; no mapped digital power/delay here. Phase source and amplifier inclusion are recorded in arguments.",
                  "Schematic MOS/MIM/resistor circuits; no analog layout extraction or mismatch included.",
                  "Reference network has the reported source resistance and local external capacitors, not infinite driver strength."]}
    waveform = out / "waveform.dat"
    if waveform.exists():
        values = np.loadtxt(waveform, skiprows=1)
        time = values[:,0]
        valid = values[:,6]
        edges = np.flatnonzero((valid[:-1]<args.vdd/2)&(valid[1:]>=args.vdd/2))
        report["valid_times_s"] = time[edges+1].tolist()
        use = time >= 11.5e-6
        if np.count_nonzero(use)>2:
            duration = time[use][-1]-time[use][0]
            # Device-side reference boundary energy, not generator static power.
            power = -args.vdd*values[:,14]+values[:,11]*values[:,15]+values[:,12]*values[:,16]+values[:,13]*values[:,17]
            report["analog_and_reference_port_power_w"] = float(np.trapezoid(power[use],time[use])/duration)
            report["reference_peak_port_currents_a"] = {"rp": float(np.max(np.abs(values[use,15]))),
                "rn": float(np.max(np.abs(values[use,16]))), "vcm": float(np.max(np.abs(values[use,17])))}
        count = len(edges)
    else:
        count = 0
    expected_frames = math.floor((args.duration_us-11.004)/10)+1
    checks = {"simulation_completed": rc == 0, "all_frames_completed": len(codes)==count==expected_frames,
              "short_nominal_code_check_within_2lsb": bool(codes) and all(abs(c-expected)<=2 for c in codes)}
    report["checks"] = checks
    report["status"] = "SHORT_LIVE_RTL_TRANSISTOR_CONVERSION_PASS" if all(checks.values()) else "FAIL"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    (HERE / "results/adc_cosim_latest.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": report["status"], "raw_codes": codes, "expected": expected, "checks": checks, "report": str(report_path)}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
