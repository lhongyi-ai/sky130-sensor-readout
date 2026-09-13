#!/usr/bin/env python3
"""Bounded real ADC/RTL matrix, not full ADC/system signoff or calibration.

Every case retains all three raw conversions. No fitting or bad-frame removal.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend",type=Path)
    parser.add_argument("--gain",type=int,choices=(1,4,16),default=1)
    parser.add_argument("--adc-blocks",type=Path,default=ROOT / "analog/adc/adc_blocks.spice")
    args = parser.parse_args()
    out = HERE/"results"/("matrix_"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True)
    # Freeze analog sources before dispatch, independent of parallel design edits.
    sources = [ROOT/"analog/adc/adc_analog12_bottom_preamp.spice",ROOT/"analog/adc/adc_preamp.spice",args.adc_blocks]
    if args.frontend:
        sources.append(args.frontend)
    hashes = {}
    for source in sources:
        data = source.read_bytes()
        (out/source.name).write_bytes(data)
        hashes[str(source.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    cases = [{"name":f"vin_{v:+.3f}","input_v":v} for v in (-.36,-.32,-.123,0,.123,.32,.36)]
    cases += [{"name":f"reference_{r:g}ohm","input_v":.32,"reference_r":r} for r in (10,100)]
    cases += [{"name":f"cm_{c:+g}mv","input_v":.32,"input_cm_offset_mv":c} for c in (-50,50)]
    cases += [{"name":f"source_{r:g}ohm","input_v":.32,"source_r":r} for r in (0,1000)]
    def run(case):
        command = [sys.executable,str(HERE/"run_adc_cosim.py"),"--adc-wrapper",str(out/sources[0].name),
                   "--adc-subckt","adc_analog12_bottom_preamp","--adc-preamp",str(out/sources[1].name),
                   "--adc-blocks",str(out/args.adc_blocks.name),"--gain",str(args.gain)]
        if args.frontend:
            command += ["--frontend",str(out/args.frontend.name)]
        for key,value in case.items():
            if key != "name":
                command += ["--"+key.replace("_","-"),str(value)]
        try:
            proc = subprocess.run(command,capture_output=True,text=True,timeout=1110)
            (out/(case["name"]+".log")).write_text(proc.stdout+proc.stderr)
            result = {"case":case,"returncode":proc.returncode,"pass":False}
            printed = json.loads(proc.stdout)
            source = Path(printed["report"])
            result["report"] = str(source.relative_to(ROOT))
            detail = json.loads(source.read_text())
            result.update({key:detail.get(key) for key in ("status","raw_codes","expected_ideal_code","code_error_lsb","valid_times_s","analog_and_reference_port_power_w","reference_peak_port_currents_a")})
            result["pass"] = proc.returncode==0
        except (ValueError,KeyError,OSError,subprocess.TimeoutExpired) as error:
            result = {"case":case,"pass":False,"error":str(error)}
        print(json.dumps({"case":case["name"],"pass":result["pass"],"codes":result.get("raw_codes")}),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run,cases))
    report = {"status":"BOUNDED_TRANSISTOR_RTL_SMOKE_PASS" if all(row["pass"] for row in results) else "FAIL",
              "source_sha256":hashes,"frontend_included":bool(args.frontend),"gain":args.gain,
              "counts":{"cases":len(cases),"passed":sum(row["pass"] for row in results)},"results":results,
              "complete_adc_qualified":False,"complete_chip_qualified":False,"cadence_used":False,
              "limitations":["Three deterministic conversions per case, not full-code INL/DNL or a noise-inclusive FFT.",
                 "Nominal process/supply/temperature only; a separate 45-PVT qualification remains mandatory.",
                 "2-LSB raw-code tolerance is a smoke/debug gate, not a replacement for the frozen INL/calibration targets.",
                 "No calibration fitting occurs in this matrix. Raw transient errors are retained.",
                 "Reference capacitors are external 10 nF; port power excludes generator quiescent power and ideal digital bridges."]}
    (out/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"status":report["status"],"counts":report["counts"],"report":str(out/"summary.json")},indent=2))
    return 0 if all(row["pass"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
