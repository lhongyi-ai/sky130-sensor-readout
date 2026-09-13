#!/usr/bin/env python3
"""Measure the physical nonoverlap generator at all 45 specified PVT points.

These are schematic deterministic timing checks, not extracted ADC signoff.
The phase-width report must be used by the real sampling/settling test: the
usable aperture is shorter than the controller's nominal 2.5 us command.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import numpy as np

HERE = Path(__file__).resolve().parent


def crossings(time, voltage, level, rising):
    selected = ((voltage[:-1] < level) & (voltage[1:] >= level) if rising else
                (voltage[:-1] > level) & (voltage[1:] <= level))
    ix = np.flatnonzero(selected)
    return time[ix] + (time[ix+1]-time[ix])*(level-voltage[ix])/(voltage[ix+1]-voltage[ix])


def measure(values, vdd):
    time, command, top, topb, acq, conv, current = values.T
    cycles = []
    for begin in (1e-6, 11e-6):
        stop = begin+2.5e-6
        def edge(signal, level, rising, at):
            found = crossings(time, signal, vdd*level, rising)
            found = found[(found >= at-10e-9) & (found <= at+500e-9)]
            if len(found) != 1:
                raise ValueError(f"expected one phase edge near {at}, got {found}")
            return float(found[0])
        ca = edge(conv, .2, False, begin)
        aa = edge(acq, .2, True, begin)
        ab = edge(acq, .8, True, begin)
        ta = edge(top, .2, True, begin)
        tb = edge(top, .2, False, stop)
        ae = edge(acq, .2, False, stop)
        ce = edge(conv, .2, True, stop)
        cycles.append({"acquisition_dead_time_s": aa-ca, "conversion_dead_time_s": ce-ae,
                       "top_open_lead_s": ae-tb, "top_close_after_acq_high_s": ta-ab,
                       "actual_top_acquisition_width_s": tb-ta})
    settled = time >= .9e-6
    checks = {"no_acq_conv_overlap_above_20percent_vdd": not bool(np.any((acq[settled]>.2*vdd)&(conv[settled]>.2*vdd))),
              "both_dead_times_at_least_5ns": all(min(c["acquisition_dead_time_s"], c["conversion_dead_time_s"]) >= 5e-9 for c in cycles),
              "top_opens_at_least_5ns_before_bottom_release": all(c["top_open_lead_s"] >= 5e-9 for c in cycles),
              "top_closes_after_acq_reaches_80percent": all(c["top_close_after_acq_high_s"] >= 0 for c in cycles),
              "two_complete_sampling_windows": len(cycles)==2}
    return {"cycles": cycles, "checks": checks, "pass": all(checks.values()),
            "mean_generator_power_w": float(np.trapezoid(-vdd*current[settled],time[settled])/(time[settled][-1]-time[settled][0]))}


def main():
    out = HERE / "results" / ("phases_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True)
    source = HERE / "sensor_phases.spice"
    data = source.read_bytes()
    (out / source.name).write_bytes(data)
    (out / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    def run(case):
        corner, vdd, temp = case
        folder = out / f"{corner}_{vdd}_{temp}"
        folder.mkdir()
        (folder / ".spiceinit").write_text("set ngbehavior=hsa\nset skywaterpdk\nset ng_nomodcheck\nset num_threads=1\n")
        bench = ["Real PDK phase generator loaded schematic PVT test",
                 f".lib /foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice {corner}",
                 f".include ../{source.name}", f".temp {temp}",
                 ".options reltol=1e-4 abstol=1e-12 vntol=1e-7 method=gear",
                 f"VDD vdd 0 {vdd}", f"VCMD cmd 0 PULSE(0 {vdd} 1u 1n 1n 2.5u 10u)",
                 "XPH cmd top topb acq conv vdd 0 sensor_phases",
                 "CTOP top 0 100f", "CTOPB topb 0 100f", "CACQ acq 0 500f", "CCONV conv 0 500f",
                 ".control", "set wr_singlescale", "set wr_vecnames", "set numdgt=12",
                 "tran 2n 15u 0 2n", "wrdata waveform.dat v(cmd) v(top) v(topb) v(acq) v(conv) i(vdd)",
                 "quit", ".endc", ".end", ""]
        (folder / "bench.spice").write_text("\n".join(bench))
        result = {"corner":corner, "vdd_v":vdd, "temperature_c":temp, "pass":False}
        try:
            proc = subprocess.run(["ngspice","-b","-o","native.log","bench.spice"], cwd=folder,
                    env=dict(os.environ,SPICE_USERINIT_DIR=str(folder)), capture_output=True,text=True,timeout=90)
            (folder / "launcher.log").write_text(proc.stdout+proc.stderr)
            result["returncode"] = proc.returncode
            if proc.returncode:
                raise ValueError("ngspice failed")
            result.update(measure(np.loadtxt(folder / "waveform.dat",skiprows=1),vdd))
        except (ValueError,OSError,subprocess.TimeoutExpired) as error:
            result["error"] = str(error)
        (folder / "summary.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
        return result
    cases = list(itertools.product(("tt","ff","ss","fs","sf"),(1.62,1.8,1.98),(-20,27,85)))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run,cases))
    all_cycles = [c for r in results for c in r.get("cycles",[])]
    report = {"status":"SCHEMATIC_PHASE_45PVT_PASS" if all(r["pass"] for r in results) else "FAIL",
              "source_sha256":hashlib.sha256(data).hexdigest(),"run":str(out.relative_to(HERE)),
              "counts":{"total":45,"passed":sum(r["pass"] for r in results)},"results":results,
              "minimum_actual_top_acquisition_width_s":min((c["actual_top_acquisition_width_s"] for c in all_cycles),default=None),
              "load_f":{"top":100e-15,"topb":100e-15,"acq":500e-15,"conv":500e-15},
              "full_adc_qualified":False,"extracted":False,"cadence_used":False,
              "limitations":["Deterministic standalone schematic generator, not statistical timing or RC-extracted layout.",
                 "The real sampling circuit must settle within the measured shorter aperture, not an assumed full 2.5 us.",
                 "20 percent VDD nonoverlap is a phase-level check; actual transistor switch overlap is tested in ADC integration."]}
    (out / "summary.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    (HERE / "results/phase_qualification.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":report["status"],"counts":report["counts"],"minimum_aperture_s":report["minimum_actual_top_acquisition_width_s"],"run":str(out)},indent=2))
    return 0 if report["status"].endswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
