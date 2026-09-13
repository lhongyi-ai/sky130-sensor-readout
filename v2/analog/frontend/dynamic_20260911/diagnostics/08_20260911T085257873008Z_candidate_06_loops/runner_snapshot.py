#!/usr/bin/env python3
"""One bounded ngspice solve for three formal loop probes at all gains."""
from __future__ import annotations

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
CANDIDATE = HERE / "candidate_06.spice"
SAMPLER = HERE / "sampling_switch.spice"
ADC = HERE.parent.parent / "adc" / "adc_blocks.spice"
LIB = "/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice"
NGSPICE = "/foss/tools/ngspice/bin/ngspice"
GAINS = (1, 4, 16)
MODES = ("dm", "stage1_cm", "output_cm")
MAX_DIAGNOSTICS = 8


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"Expected exactly one source match for: {old}")
    return source.replace(old, new, 1)


def injected_source() -> str:
    """Create a test-only netlist that is topologically identical at DC."""
    source = CANDIDATE.read_text()
    source = replace_once(
        source,
        ".subckt rd_fdota INP INN OUTP OUTN VDD VSS VCM",
        ".subckt rd_fdota INP INN OUTP OUTN VDD VSS VCM params: NCMAC=0 OCMAC=0",
    )
    source = replace_once(
        source,
        "XMLP N1 NCM VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=64",
        "VTESTNCM NCM_GATE NCM dc 0 ac {NCMAC}\n"
        "XMLP N1 NCM_GATE VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=64",
    )
    source = replace_once(
        source,
        "XMLN N2 NCM VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=64",
        "XMLN N2 NCM_GATE VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=64",
    )
    source = replace_once(
        source,
        "XCMS DS CMS CS VSS sky130_fd_pr__nfet_01v8 L=1 W=20",
        "VTESTOCM CMS_ERROR CMS dc 0 ac {OCMAC}\n"
        "XCMS DS CMS_ERROR CS VSS sky130_fd_pr__nfet_01v8 L=1 W=20",
    )
    source = replace_once(
        source,
        ".subckt sky130_v2_switchable_pga VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1",
        ".subckt sky130_v2_switchable_pga VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1 "
        "params: DMAC=0 NCMAC=0 OCMAC=0",
    )
    source = replace_once(
        source,
        "XOTA SUMPOS SUMNEG OUTP OUTN VDD VSS VCM rd_fdota",
        "VTESTP I_SUMPOS SUMPOS dc 0 ac {DMAC*.5}\n"
        "VTESTN I_SUMNEG SUMNEG dc 0 ac {-DMAC*.5}\n"
        "XOTA I_SUMPOS I_SUMNEG OUTP OUTN VDD VSS VCM rd_fdota "
        "NCMAC={NCMAC} OCMAC={OCMAC}",
    )
    return source


def build_deck() -> tuple[str, list[str]]:
    lines = [
        "* Formal loop injection: three isolated measurement copies per gain",
        f".lib {LIB} tt",
        ".include measurement_injections.spice",
        ".include adc_blocks_snapshot.spice",
        ".include sampling_switch_snapshot.spice",
        ".temp 27",
        ".options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18 method=gear maxord=2 klu",
        "VDD VDD 0 1.8",
        "VCM VCM 0 .9",
        "VINP VINP 0 .9",
        "VINN VINN 0 .9",
        "VACQ ACQ 0 1.8",
        "VACQB ACQB 0 0",
    ]
    vectors: list[str] = []
    for gain in GAINS:
        s0 = 1.8 if gain == 4 else 0
        s1 = 1.8 if gain == 16 else 0
        lines.extend((
            f"VSEL0_{gain} SEL0_{gain} 0 {s0}",
            f"VSEL1_{gain} SEL1_{gain} 0 {s1}",
        ))
        for mode in MODES:
            tag = f"g{gain}_{mode}"
            params = {
                "dm": "DMAC=1 NCMAC=0 OCMAC=0",
                "stage1_cm": "DMAC=0 NCMAC=1 OCMAC=0",
                "output_cm": "DMAC=0 NCMAC=0 OCMAC=1",
            }[mode]
            lines.extend((
                f"RSP_{tag} VINP IP_{tag} 350",
                f"RSN_{tag} VINN IN_{tag} 350",
                f"XPGA_{tag} IP_{tag} IN_{tag} OP_{tag} ON_{tag} VDD 0 VCM "
                f"SEL0_{gain} SEL1_{gain} sky130_v2_switchable_pga {params}",
                f"XRIP_{tag} OP_{tag} FP_{tag} 0 rd_hr R=1500",
                f"XRIN_{tag} ON_{tag} FN_{tag} 0 rd_hr R=1500",
                f"XCFP_{tag} FP_{tag} 0 rd_c4p",
                f"XCFN_{tag} FN_{tag} 0 rd_c4p",
                f"XTGP_{tag} FP_{tag} HP_{tag} ACQ ACQB VDD 0 rd_sampling_tgate",
                f"XTGN_{tag} FN_{tag} HN_{tag} ACQ ACQB VDD 0 rd_sampling_tgate",
                f"XCP_{tag} HP_{tag} VCM adc_mim_bank COUNT=4096",
                f"XCN_{tag} HN_{tag} VCM adc_mim_bank COUNT=4096",
                f"RLEAKP_{tag} HP_{tag} VCM 1g",
                f"RLEAKN_{tag} HN_{tag} VCM 1g",
            ))
    lines.extend((
        ".control",
        "set noaskquit",
        "set num_threads=1",
        "set wr_singlescale",
        "set wr_vecnames",
        "set numdgt=12",
        "op",
        "ac dec 100 1 1g",
    ))
    for gain in GAINS:
        dm = f"xpga_g{gain}_dm"
        icm = f"xpga_g{gain}_stage1_cm.xota"
        ocm = f"xpga_g{gain}_output_cm.xota"
        definitions = (
            (f"g{gain}_dm", f"-(v({dm}.sumpos)-v({dm}.sumneg))/(v({dm}.i_sumpos)-v({dm}.i_sumneg))"),
            (f"g{gain}_stage1_cm", f"-v({icm}.ncm)/v({icm}.ncm_gate)"),
            (f"g{gain}_output_cm", f"-v({ocm}.cms)/v({ocm}.cms_error)"),
        )
        for name, expression in definitions:
            lines.extend((
                f"let {name}={expression}",
                f"let {name}_r=real({name})",
                f"let {name}_i=imag({name})",
            ))
            vectors.extend((f"{name}_r", f"{name}_i"))
    lines.extend((f"wrdata loops.dat {' '.join(vectors)}", "quit", ".endc", ".end"))
    return "\n".join(lines) + "\n", ["frequency"] + vectors


def crossing_report(frequency: np.ndarray, z: np.ndarray) -> dict:
    magnitude_db = 20 * np.log10(np.abs(z))
    phase = np.unwrap(np.angle(z)) * 180 / np.pi
    phase -= 360 * np.round(phase[0] / 360)
    crossings = []
    for index in np.flatnonzero(magnitude_db[:-1] * magnitude_db[1:] < 0):
        fraction = -magnitude_db[index] / (magnitude_db[index + 1] - magnitude_db[index])
        crossing_phase = phase[index] + fraction * (phase[index + 1] - phase[index])
        crossings.append({
            "frequency_hz": float(10 ** (np.log10(frequency[index]) + fraction * np.log10(frequency[index + 1] / frequency[index]))),
            "phase_deg": float(crossing_phase),
            "phase_margin_deg": float(180 + crossing_phase),
            "direction": "down" if magnitude_db[index] > 0 else "up",
        })
    down = [item for item in crossings if item["direction"] == "down"]
    return {
        "low_frequency_gain_db": float(magnitude_db[0]),
        "low_frequency_phase_deg": float(phase[0]),
        "unity_crossings": crossings,
        "minimum_downcrossing_phase_margin_deg": min((item["phase_margin_deg"] for item in down), default=None),
        "phase_margin_gate_pass": bool(down and all(item["phase_margin_deg"] >= 60 for item in down)),
    }


def write_manifest(folder: Path) -> None:
    files = {}
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.name != "evidence_manifest.json":
            files[path.name] = {"sha256": digest(path), "size_bytes": path.stat().st_size}
    save(folder / "evidence_manifest.json", {
        "version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Artifact integrity only; electrical pass is in summary.json.",
        "files": files,
    })


def main() -> None:
    if not all(path.is_file() for path in (CANDIDATE, SAMPLER, ADC)):
        raise ValueError("Candidate, sampler, or ADC primitive is missing")
    diagnostics = HERE / "diagnostics"
    diagnostics.mkdir(exist_ok=True)
    ordinal = sum(path.is_dir() for path in diagnostics.iterdir()) + 1
    if ordinal > MAX_DIAGNOSTICS:
        raise ValueError("Eight-diagnostic dynamic-closure budget exhausted")
    folder = diagnostics / f"{ordinal:02d}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_candidate_06_loops"
    folder.mkdir()
    (folder / "candidate_snapshot.spice").write_bytes(CANDIDATE.read_bytes())
    (folder / "sampling_switch_snapshot.spice").write_bytes(SAMPLER.read_bytes())
    (folder / "adc_blocks_snapshot.spice").write_bytes(ADC.read_bytes())
    (folder / "measurement_injections.spice").write_text(injected_source())
    (folder / "runner_snapshot.py").write_bytes(Path(__file__).read_bytes())
    deck, columns = build_deck()
    (folder / "bench.spice").write_text(deck)
    save(folder / "columns.json", columns)
    report = {
        "status": "RUNNING",
        "ordinal": ordinal,
        "diagnostic_budget": MAX_DIAGNOSTICS,
        "candidate": CANDIDATE.name,
        "candidate_sha256": digest(CANDIDATE),
        "worker_count": 1,
        "gains": list(GAINS),
        "measured_loops_per_gain": list(MODES),
        "real_sampler_and_4096_unit_load_in_acquisition_state": True,
        "formal_loop_stability_gate_pass": False,
        "full_frontend_qualified": False,
        "full_chip_qualified": False,
        "noise_included": False,
    }
    started = time.monotonic()
    env = dict(os.environ, SPICE_USERINIT_DIR="/foss/pdks/sky130A/libs.tech/ngspice", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    with (folder / "console.txt").open("x") as stream:
        process = subprocess.Popen(
            [NGSPICE, "-b", "-o", "simulator.log", "bench.spice"], cwd=folder, env=env,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            process.wait(timeout=170)
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
    if report["status"] == "RUNNING" and (process.returncode or "error:" in log.lower() or "ngspice-47 done" not in log):
        report["status"] = "SIMULATOR_FAILURE"
    if report["status"] == "RUNNING":
        try:
            data = np.loadtxt(folder / "loops.dat", skiprows=1, ndmin=2)
            if data.shape[1] != len(columns) or not np.isfinite(data).all() or abs(data[0, 0] - 1) > 1e-9 or abs(data[-1, 0] - 1e9) > 2:
                raise ValueError(f"Invalid AC data shape or span: {data.shape}")
            report["loops"] = {}
            ci = {name: index for index, name in enumerate(columns)}
            for gain in GAINS:
                report["loops"][str(gain)] = {}
                for mode in MODES:
                    key = f"g{gain}_{mode}"
                    z = data[:, ci[key + "_r"]] + 1j * data[:, ci[key + "_i"]]
                    report["loops"][str(gain)][mode] = crossing_report(data[:, 0], z)
            report["formal_loop_stability_gate_pass"] = all(
                result["phase_margin_gate_pass"]
                for gain in report["loops"].values() for result in gain.values()
            )
            report["status"] = "LOOP_STABILITY_PASS" if report["formal_loop_stability_gate_pass"] else "LOOP_STABILITY_FAIL"
        except (OSError, ValueError, KeyError, IndexError) as error:
            report["status"] = "INVALID_OR_INCOMPLETE_DATA"
            report["analysis_error"] = str(error)
    report["limitations"] = [
        "Voltage injection sources are testbench-only and preserve the production candidate's DC topology.",
        "Each reported scalar loop is broken while the other two loops remain closed.",
        "This is schematic-level TT/1.8 V/27 C stability with acquisition load, not PVT, noise, PEX, Cadence, or silicon signoff.",
    ]
    save(folder / "summary.json", report)
    write_manifest(folder)
    print(json.dumps({"summary_path": str(folder / "summary.json"), **report}, indent=2), flush=True)


if __name__ == "__main__":
    main()
