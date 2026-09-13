#!/usr/bin/env python3
"""Bounded serial TT diagnostic for the independent front-end redesign.

One invocation evaluates one frozen source snapshot at all three gains.  It is
an experiment, not signoff: no more than 12 timestamped diagnostics can be
created, and existing evidence is never overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import numpy as np


HERE = Path(__file__).resolve().parent
ADC_SOURCE = HERE.parent.parent / "adc" / "adc_blocks.spice"
SAMPLER_SOURCE = HERE / "sampling_switch.spice"
LIB = "/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice"
GAINS = (1, 4, 16)
LSB = 0.8 / 4096
ACQ_WINDOW = 2.476847754e-6
MAX_DIAGNOSTICS = 12


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def device_vector(prefix: str, dev: str, model: str, field: str) -> str:
    return f"@m.{prefix}.{dev}.msky130_fd_pr__{model}[{field}]"


def build_deck(candidate_name: str) -> tuple[str, list[str], list[str], list[str]]:
    case = """
.subckt rd_case params: SUP=1.8 G=4 S0=1.8 S1=0
VDDC VDD 0 {SUP}
VCMC VCM 0 {SUP/2}
BSP SP 0 V={SUP/2+V(SW)/(2*G)}
BSN SN 0 V={SUP/2-V(SW)/(2*G)}
RSP SP IP 350
RSN SN IN 350
VSEL0 SEL0 0 {S0}
VSEL1 SEL1 0 {S1}
XDUT IP IN COREP COREN VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga

* Same real isolation/filter and 4096-unit ADC sampling load for every gain.
XRIP COREP FILTP 0 rd_hr R=1800
XRIN COREN FILTN 0 rd_hr R=1800
XCFP FILTP 0 rd_c4p
XCFN FILTN 0 rd_c4p
XTGP FILTP HP ACQ ACQB VDD 0 rd_sampling_tgate
XTGN FILTN HN ACQ ACQB VDD 0 rd_sampling_tgate
XCP HP VCM adc_mim_bank COUNT=4096
XCN HN VCM adc_mim_bank COUNT=4096
XRSTP VCM HP RST RSTB VDD 0 rd_sampling_tgate
XRSTN VCM HN RST RSTB VDD 0 rd_sampling_tgate
RLEAKP HP VCM 1g
RLEAKN HN VCM 1g
.ends rd_case
"""

    instances = []
    for gain in GAINS:
        s0 = 1.8 if gain == 4 else 0
        s1 = 1.8 if gain == 16 else 0
        instances.append(f"XG{gain} rd_case SUP=1.8 G={gain} S0={s0} S1={s1}")

    basic = ["v(sw)"]
    op = []
    transient = []
    dc = ["v(sw)"]
    device_fields = ("id", "gm", "gds", "vds", "vdsat", "vgs", "vth")
    devices = {
        "xdut.xota.xmip": "nfet_01v8",
        "xdut.xota.xmin": "nfet_01v8",
        "xdut.xota.xmtail": "nfet_01v8",
        "xdut.xota.xmlp": "pfet_01v8",
        "xdut.xota.xmln": "pfet_01v8",
        "xdut.xota.xmsp": "pfet_01v8",
        "xdut.xota.xmsn": "pfet_01v8",
        "xdut.xota.xmop": "nfet_01v8",
        "xdut.xota.xmon": "nfet_01v8",
        "xdut.xota.xcms": "nfet_01v8",
        "xdut.xota.xcmr": "nfet_01v8",
        "xdut.xota.xcmt": "nfet_01v8",
        "xdut.xota.xbias.xdbn": "nfet_01v8",
        "xdut.xota.xfcs": "nfet_01v8",
        "xdut.xota.xfcr": "nfet_01v8",
        "xdut.xota.xft": "nfet_01v8",
    }
    for gain in GAINS:
        p = f"xg{gain}"
        nodes = [
            f"v({p}.sp)", f"v({p}.sn)", f"v({p}.ip)", f"v({p}.in)",
            f"v({p}.corep)", f"v({p}.coren)", f"v({p}.filtp)", f"v({p}.filtn)",
            f"v({p}.hp)", f"v({p}.hn)", f"v({p}.xdut.xota.n1)",
            f"v({p}.xdut.xota.n2)", f"v({p}.xdut.xota.tail)",
            f"v({p}.xdut.xota.cms)", f"v({p}.xdut.xota.cmctl)",
            f"v({p}.xdut.xota.ds)", f"v({p}.xdut.xota.bn)",
            f"v({p}.xdut.xota.bp)", f"v({p}.xdut.xota.ncm)",
            f"v({p}.xdut.xota.fds)", f"v({p}.xdut.xota.ftail)",
            f"i(v.{p}.vddc)", f"i(v.{p}.vcmc)",
        ]
        op.extend(nodes)
        dc.extend(nodes)
        transient.extend(nodes)
        for dev, model in devices.items():
            for field in device_fields:
                vector = device_vector(p, dev, model, field)
                op.append(vector)
                dc.append(vector)

    text = f"""* Frozen redesign TT diagnostic: all gains, real sampler
.lib {LIB} tt
.include candidate_snapshot.spice
.include adc_blocks_snapshot.spice
.include sampling_switch_snapshot.spice
.temp 27
.options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18 itl1=300 itl2=300 method=gear maxord=2
VSW SW 0 PULSE(-.36 .36 10u 10n 10n 10u 20u)
VACQ ACQ 0 PULSE(0 1.8 10u 1n 1n {ACQ_WINDOW} 10u)
VACQB ACQB 0 PULSE(1.8 0 10u 1n 1n {ACQ_WINDOW} 10u)
VRST RST 0 PULSE(0 1.8 8u 1n 1n 1u 10u)
VRSTB RSTB 0 PULSE(1.8 0 8u 1n 1n 1u 10u)
.global SW ACQ ACQB RST RSTB
{case}
{chr(10).join(instances)}
.control
set noaskquit
set num_threads=1
set wr_singlescale
set wr_vecnames
set numdgt=12
op
wrdata op.dat {' '.join(op)}
dc VSW -.4 .4 .01
wrdata dc.dat {' '.join(dc)}
tran 5n 40u 0 5n
wrdata transient.dat {' '.join(transient)}
quit
.endc
.end
"""
    return text, ["scale"] + op, ["scale"] + dc, ["scale"] + transient


def checked_data(path: Path, columns: list[str], rows: int | None = None) -> np.ndarray:
    data = np.loadtxt(path, skiprows=1, ndmin=2)
    if data.shape[1] != len(columns) or not np.isfinite(data).all():
        raise ValueError(f"{path.name}: expected {len(columns)} columns, got {data.shape}")
    if rows is not None and data.shape[0] != rows:
        raise ValueError(f"{path.name}: expected {rows} rows, got {data.shape[0]}")
    if data.shape[0] > 1 and np.any(np.diff(data[:, 0]) <= 0):
        raise ValueError(f"{path.name}: scale is not strictly increasing")
    return data


def interval_mean_and_pp(t: np.ndarray, y: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    mask = (t >= lo) & (t <= hi)
    if np.sum(mask) < 3:
        raise ValueError("Incomplete measurement window")
    trap = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    return float(trap(y[mask], t[mask]) / (t[mask][-1] - t[mask][0])), float(np.ptp(y[mask]))


def analyze(folder: Path, opcols: list[str], dccols: list[str], trcols: list[str]) -> dict:
    op = checked_data(folder / "op.dat", opcols, 1)
    dc = checked_data(folder / "dc.dat", dccols, 81)
    tr = checked_data(folder / "transient.dat", trcols)
    if abs(tr[0, 0]) > 1e-15 or abs(tr[-1, 0] - 40e-6) > 1e-12:
        raise ValueError("Transient did not cover exactly 0 to 40 us")

    ci_dc = {name: i for i, name in enumerate(dccols)}
    ci_tr = {name: i for i, name in enumerate(trcols)}
    target = dc[:, ci_dc["v(sw)"]]
    if not np.allclose(target, np.linspace(-.4, .4, 81), atol=1e-10, rtol=0):
        raise ValueError("DC target is not the required 81-point full range")

    results = {}
    all_static = True
    all_sampling = True
    all_power = True
    all_regions = True
    for gain in GAINS:
        p = f"xg{gain}"
        od = dc[:, ci_dc[f"v({p}.filtp)"]] - dc[:, ci_dc[f"v({p}.filtn)"]]
        cm = (dc[:, ci_dc[f"v({p}.filtp)"]] + dc[:, ci_dc[f"v({p}.filtn)"]]) / 2
        fit_idx = np.array([8, 40, 72])
        fit = np.polyfit(od[fit_idx], target[fit_idx], 1)
        hold = np.ones(81, dtype=bool)
        hold[fit_idx] = False
        residual = (fit[0] * od + fit[1] - target) / LSB
        static_error = float(np.max(np.abs(residual[hold])))
        static_pass = bool(static_error <= 1.0 and np.max(np.abs(cm - .9)) <= .05)

        t = tr[:, 0]
        filt = tr[:, ci_tr[f"v({p}.filtp)"]] - tr[:, ci_tr[f"v({p}.filtn)"]]
        held = tr[:, ci_tr[f"v({p}.hp)"]] - tr[:, ci_tr[f"v({p}.hn)"]]
        tcm = (tr[:, ci_tr[f"v({p}.filtp)"]] + tr[:, ci_tr[f"v({p}.filtn)"]]) / 2
        references = []
        reference_pp = []
        acquisition_errors = []
        post_errors = []
        for start, rlo, rhi in ((10e-6, 16e-6, 19e-6), (20e-6, 26e-6, 29e-6), (30e-6, 36e-6, 39e-6)):
            ref, pp = interval_mean_and_pp(t, filt, rlo, rhi)
            aperture = start + ACQ_WINDOW - 10e-9
            acquisition_errors.append(float(np.interp(aperture, t, held) - ref))
            post_errors.append(float(np.interp(aperture + 30e-9, t, held) - ref))
            references.append(ref)
            reference_pp.append(pp)
        acq_error = max(abs(x) for x in acquisition_errors)
        post_error = max(abs(x) for x in post_errors)
        sampling_pass = bool(
            acq_error <= LSB / 4
            and post_error <= LSB / 4
            and max(reference_pp) <= LSB / 40
            and max(abs(x) for x in references) >= .25
            and np.max(np.abs(tcm[t >= 9e-6] - .9)) <= .05
        )

        power = -1.8 * tr[:, ci_tr[f"i(v.{p}.vddc)"]] - .9 * tr[:, ci_tr[f"i(v.{p}.vcmc)"]]
        mean_power, power_pp = interval_mean_and_pp(t, power, 10e-6, 40e-6)
        power_pass = bool(mean_power <= 1.85e-3)

        regions = {}
        region_pass = True
        for dev, model in (
            ("xdut.xota.xmip", "nfet_01v8"), ("xdut.xota.xmin", "nfet_01v8"),
            ("xdut.xota.xmtail", "nfet_01v8"), ("xdut.xota.xmlp", "pfet_01v8"),
            ("xdut.xota.xmln", "pfet_01v8"), ("xdut.xota.xmsp", "pfet_01v8"),
            ("xdut.xota.xmsn", "pfet_01v8"), ("xdut.xota.xmop", "nfet_01v8"),
            ("xdut.xota.xmon", "nfet_01v8"), ("xdut.xota.xcms", "nfet_01v8"),
            ("xdut.xota.xcmr", "nfet_01v8"), ("xdut.xota.xcmt", "nfet_01v8"),
        ):
            vd = device_vector(p, dev, model, "vds")
            vs = device_vector(p, dev, model, "vdsat")
            margin = np.abs(dc[:, ci_dc[vd]]) - np.abs(dc[:, ci_dc[vs]])
            idx = int(np.argmin(margin))
            regions[dev] = {
                "min_abs_vds_minus_abs_vdsat_v": float(margin[idx]),
                "worst_target_v": float(target[idx]),
                "zero_margin_v": float(margin[40]),
            }
            if margin[idx] < -0.02:
                region_pass = False

        results[str(gain)] = {
            "calibration_points_target_v": [-.32, 0, .32],
            "calibration_coefficients": fit.tolist(),
            "max_independent_holdout_error_lsb": static_error,
            "max_static_output_cm_error_v": float(np.max(np.abs(cm - .9))),
            "output_endpoints_v": [float(od[0]), float(od[-1])],
            "static_gate_pass": static_pass,
            "acquisition_window_s": ACQ_WINDOW,
            "acquisition_errors_v": acquisition_errors,
            "max_acquisition_error_v": acq_error,
            "post_aperture_errors_v": post_errors,
            "max_post_aperture_error_v": post_error,
            "settled_references_v": references,
            "reference_peak_to_peak_v": reference_pp,
            "max_transient_output_cm_error_v": float(np.max(np.abs(tcm[t >= 9e-6] - .9))),
            "sampling_gate_pass": sampling_pass,
            "mean_frontend_vdd_vcm_power_w": mean_power,
            "power_peak_to_peak_w": power_pp,
            "provisional_frontend_power_limit_w": 1.85e-3,
            "power_gate_pass": power_pass,
            "device_regions": regions,
            "device_region_gate_pass": region_pass,
        }
        all_static &= static_pass
        all_sampling &= sampling_pass
        all_power &= power_pass
        all_regions &= region_pass

    return {
        "status": "DIAGNOSTIC_COMPLETE",
        "corner": "tt",
        "vdd_v": 1.8,
        "temp_c": 27,
        "gains": results,
        "all_gain_static_gate_pass": all_static,
        "all_gain_real_sampling_gate_pass": all_sampling,
        "all_gain_power_gate_pass": all_power,
        "all_gain_device_region_gate_pass": all_regions,
        "loop_stability_measured": False,
        "nominal_frontend_prerequisites_pass": False,
        "scope": "Schematic-level real SKY130 devices and real 4096-unit CDAC acquisition load; no noise, mismatch, PVT, PEX, ADC conversion, or silicon claim.",
    }


def write_manifest(folder: Path) -> None:
    files = {}
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.name != "evidence_manifest.json":
            files[path.name] = {"sha256": sha256(path), "size_bytes": path.stat().st_size}
    save_json(folder / "evidence_manifest.json", {
        "version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Artifact integrity only; does not imply an electrical PASS.",
        "files": files,
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if not 0 < args.timeout <= 180:
        parser.error("timeout must be in (0, 180] seconds")
    candidate = args.candidate.resolve()
    if candidate.parent != HERE or not candidate.name.startswith("candidate_") or candidate.suffix != ".spice":
        parser.error("candidate must be a candidate_*.spice direct child of this directory")
    if not candidate.is_file() or not ADC_SOURCE.is_file() or not SAMPLER_SOURCE.is_file():
        parser.error("candidate, ADC primitive, or sampling-switch source is missing")

    results = HERE / "diagnostics"
    results.mkdir(exist_ok=True)
    ordinal = sum(path.is_dir() for path in results.iterdir()) + 1
    if ordinal > MAX_DIAGNOSTICS:
        raise ValueError("Twelve-diagnostic redesign budget exhausted")
    folder = results / f"{ordinal:02d}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{candidate.stem}"
    folder.mkdir()
    (folder / "candidate_snapshot.spice").write_bytes(candidate.read_bytes())
    (folder / "adc_blocks_snapshot.spice").write_bytes(ADC_SOURCE.read_bytes())
    (folder / "sampling_switch_snapshot.spice").write_bytes(SAMPLER_SOURCE.read_bytes())
    (folder / "runner_snapshot.py").write_bytes(Path(__file__).read_bytes())
    deck, opcols, dccols, trcols = build_deck(candidate.name)
    (folder / "bench.spice").write_text(deck)
    save_json(folder / "columns.json", {"op": opcols, "dc": dccols, "transient": trcols})
    report = {
        "status": "RUNNING",
        "ordinal": ordinal,
        "diagnostic_budget": MAX_DIAGNOSTICS,
        "candidate": candidate.name,
        "candidate_sha256": sha256(candidate),
        "worker_count": 1,
        "full_frontend_qualified": False,
        "full_chip_qualified": False,
        "noise_included": False,
    }
    save_json(folder / "experiment_config.json", report)

    env = dict(
        os.environ,
        SPICE_USERINIT_DIR="/foss/pdks/sky130A/libs.tech/ngspice",
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    started = time.monotonic()
    with (folder / "console.txt").open("x") as stream:
        process = subprocess.Popen(
            ["ngspice", "-b", "-o", "simulator.log", "bench.spice"],
            cwd=folder,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
            report["status"] = "TIMEOUT_INCOMPLETE"
    report["elapsed_s"] = time.monotonic() - started
    report["returncode"] = process.returncode
    log = (folder / "simulator.log").read_text(errors="replace") if (folder / "simulator.log").exists() else ""
    bad = any(mark in log.lower() for mark in ("error:", "timestep too small", "simulation(s) aborted", "simulation interrupted"))
    if report["status"] == "RUNNING" and (process.returncode or bad or "ngspice-47 done" not in log):
        report["status"] = "SIMULATOR_FAILURE"
    if report["status"] == "RUNNING":
        try:
            report.update(analyze(folder, opcols, dccols, trcols))
        except (OSError, ValueError, KeyError, IndexError) as error:
            report["status"] = "INVALID_OR_INCOMPLETE_DATA"
            report["analysis_error"] = str(error)
    save_json(folder / "summary.json", report)
    write_manifest(folder)
    print(json.dumps({"summary_path": str(folder / "summary.json"), **report}, indent=2), flush=True)


if __name__ == "__main__":
    main()
