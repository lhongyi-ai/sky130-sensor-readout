#!/usr/bin/env python3
"""Reproducible transistor-level frontend qualification using ngspice.

Run inside the pinned IIC container, from any working directory. All outputs
remain under this frontend directory. This is NOT Cadence or extracted data.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import numpy as np

HERE = Path(__file__).resolve().parent
PDK = Path(os.environ.get("PDK_ROOT", "/foss/pdks")) / "sky130A"
LIB = PDK / "libs.tech/combined/sky130.lib.spice"


def validate_log(path: Path) -> None:
    log=path.read_text()
    failure_text=any(term in log.lower() for term in ['error:', 'timestep too small',
                      'simulation(s) aborted', 'simulation interrupted'])
    if 'ngspice-47 done' not in log or failure_text:
        raise RuntimeError(f'Simulation did not complete cleanly: {path}\n{log[-4000:]}')


def run_deck(stem: str, text: str, folder: Path) -> Path:
    deck = folder / (stem + ".spice")
    deck.write_text(text)
    proc = subprocess.run(["ngspice", "-b", "-o", str(folder / (stem + ".log")), str(deck)],
                          cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (folder / (stem + ".console.txt")).write_text(proc.stdout)
    validate_log(folder/(stem+'.log'))
    if proc.returncode:
        raise RuntimeError(f'Simulator returned {proc.returncode}: {deck}')
    return deck


def header(corner: str, vdd: float, temp: float, core: Path) -> str:
    return f"""* SKY130 transistor frontend pre-layout experiment; inspect included snapshot for passive types.
.lib {LIB} {corner}
.include {core}
.temp {temp}
.options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18 itl1=200 itl2=200
VDD VDD 0 {vdd}
VCM VCM 0 {vdd/2}
"""


def bench(corner: str, vdd: float, temp: float, gain: int, load_pf: float, folder: Path, core: Path) -> None:
    stem = f"{corner}_{vdd:.2f}_{temp:g}_g{gain}_c{load_pf:g}"
    text = header(corner, vdd, temp, core) + f"""
VIP SP 0 dc {vdd/2} ac 0.5 PULSE({vdd/2-0.18/gain} {vdd/2+0.18/gain} 5u 10n 10n 10u 20u)
VIN SN 0 dc {vdd/2} ac -0.5 PULSE({vdd/2+0.18/gain} {vdd/2-0.18/gain} 5u 10n 10n 10u 20u)
RSP SP IP 350
RSN SN IN 350
XPGA IP IN OP ON VDD 0 VCM sky130_v2_pga RF=10000 RG={10000/gain-350}
CLP OP 0 {load_pf}p
CLN ON 0 {load_pf}p
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
let power=-v(vdd)*i(vdd)
wrdata {stem}_op.dat v(op) v(on) v(xpga.xamp.bn) v(xpga.xamp.bp) v(xpga.xamp.xp) v(xpga.xamp.cmctl) power
ac dec 80 1 1g
let ad=v(op)-v(on)
let av=db(ad)
let ph=180/pi*cph(ad)
wrdata {stem}_ac.dat av ph
tran 5n 35u
let od=v(op)-v(on)
let oc=(v(op)+v(on))/2
wrdata {stem}_tran.dat od oc v(sp) v(sn) v(xpga.xamp.bn)
quit
.endc
.end
"""
    run_deck(stem, text, folder)


def analyze(folder: Path) -> list[dict]:
    rows = []
    for path in sorted(folder.glob("*_op.dat")):
        stem = path.name.removesuffix("_op.dat")
        corner, supply, temp, gain, load = stem.split("_")
        op = np.loadtxt(path, skiprows=1, ndmin=2)[0]
        ac = np.loadtxt(folder / (stem + "_ac.dat"), skiprows=1)
        tr = np.loadtxt(folder / (stem + "_tran.dat"), skiprows=1)
        dc_gain = 10 ** (ac[0, 1] / 20)
        gain_expected = int(gain[1:])
        final_pos = np.mean(tr[(tr[:, 0] > 13e-6) & (tr[:, 0] < 14e-6), 1])
        final_neg = np.mean(tr[(tr[:, 0] > 23e-6) & (tr[:, 0] < 24e-6), 1])
        def settle(start, stop, final):
            part = tr[(tr[:, 0] >= start) & (tr[:, 0] < stop)]
            bad = np.flatnonzero(np.abs(part[:, 1] - final) > 0.8/4096/4)
            return 0.0 if not len(bad) else float(part[bad[-1], 0]-start)
        crossing = np.flatnonzero(ac[:, 1] < ac[0, 1]-3)
        rows.append({
            "corner": corner, "vdd_v": float(supply), "temp_c": float(temp),
            "gain_setting": gain_expected, "load_pf_per_output": float(load[1:]),
            "measured_dc_gain_vv": float(dc_gain), "gain_error_percent": float((dc_gain/gain_expected-1)*100),
            "output_common_mode_v": float((op[1]+op[2])/2),
            "bias_bn_v": float(op[3]), "bias_bp_v": float(op[4]),
            "power_w": float(op[-1]),
            "bandwidth_3db_hz": None if not len(crossing) else float(ac[crossing[0], 0]),
            "step_positive_final_v": float(final_pos), "step_negative_final_v": float(final_neg),
            "settling_positive_s": settle(5.01e-6, 14e-6, final_pos),
            "settling_negative_s": settle(15.02e-6, 24e-6, final_neg),
            "cm_deviation_during_step_v": float(np.max(np.abs(tr[:, 2]-float(supply)/2))),
            "settling_reference": "own settled endpoint; excludes static gain/offset error",
            "evidence_level": "actual SKY130 MOS, pre-layout ngspice; inspect snapshot for passive class",
            "settling_2p5us_gate": bool(settle(5.01e-6,14e-6,final_pos)<=2.5e-6 and settle(15.02e-6,24e-6,final_neg)<=2.5e-6 and abs(final_pos)>0.32 and abs(final_neg)>0.32),
            "output_cm_50mv_gate": bool(np.max(np.abs(tr[:,2]-float(supply)/2))<=0.05),
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corner", choices=["tt", "ss", "ff", "sf", "fs"], default="tt")
    parser.add_argument("--vdd", type=float, default=1.8)
    parser.add_argument("--temp", type=float, default=27)
    parser.add_argument("--gains", type=int, nargs="+", default=[1,4,16])
    parser.add_argument("--loads", type=float, nargs="+", default=[5])
    parser.add_argument("--out", default="results/replay")
    parser.add_argument("--core", default="frontend_pdk.spice")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    folder = (HERE / args.out).resolve()
    if not folder.is_relative_to(HERE):
        raise ValueError("Output must remain inside owned frontend directory")
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = folder / "frontend_core_snapshot.spice"
    if snapshot.exists() and not args.analyze_only and snapshot.read_bytes() != (HERE / args.core).read_bytes():
        raise ValueError("Existing result folder belongs to a different circuit revision; choose a new --out")
    if not snapshot.exists():
        snapshot.write_bytes((HERE / args.core).read_bytes())
    if not args.analyze_only:
        for g in args.gains:
            for cl in args.loads:
                print(f"Running {args.corner} {args.vdd} V {args.temp} C gain {g} CL {cl} pF", flush=True)
                bench(args.corner, args.vdd, args.temp, g, cl, folder, snapshot)
    rows = analyze(folder)
    (folder / "summary.json").write_text(json.dumps(rows, indent=2)+"\n")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
