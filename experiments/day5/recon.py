#!/usr/bin/env python3
"""Fail-closed Day 5 nominal tradeoff reconnaissance.

The experiment is intentionally isolated below ``experiments/day5``. Its
baseline is cryptographically bound to the selected Day 3 parameters, the
Day 3 compensation evidence, and the Day 4 manifest. Three bounded geometry
changes are compared without promoting a new production design.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GENERATED = HERE / "generated"
RAW = HERE / "raw"
DAY3_SELECTED = ROOT / "results" / "generated" / "day3" / "selected_parameters.json"
DAY3_COMPENSATION = ROOT / "results" / "day3_compensation_before_after.csv"
DAY4_MANIFEST = ROOT / "results" / "generated" / "day4" / "day4_manifest.json"
MANIFEST_PATH = HERE / "day5_manifest.json"

IMAGE = "hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7"
VARIANT_TAGS = ("baseline", "first_stage_l2", "first_stage_l3", "m7_l2")
VCM_POINTS = (0.8, 0.9, 1.3)
BENCH_NAMES = ("loop", "differential", "psrr_plus", "psrr_minus", "transient", "icmr_0p8", "icmr_0p9", "icmr_1p3")
CSV_OUTPUTS = (
    "variant_manifest.csv", "generated_inventory.csv", "raw_inventory.csv",
    "recon_summary.csv", "icmr_checkpoints.csv", "icmr_device_margins.csv",
    "log_audit.csv", "retained_failure_audit.csv", "decision_summary.csv",
)
DEVICE_ROLES = {
    1: "NMOS input, VINN side",
    2: "NMOS input, VINP side",
    3: "PMOS diode mirror load, two units",
    4: "PMOS mirror output load, two units",
    5: "NMOS tail current source",
    6: "NMOS second-stage gain device",
    7: "PMOS second-stage current source",
    8: "PMOS diode IREF reference",
    9: "PMOS VBN-bias current source",
    10: "NMOS diode VBN reference",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_finite_tree(value: Any, context: str = "JSON authority") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError(f"Non-finite number in {context}: {value!r}")
        return
    if isinstance(value, list):
        for index, member in enumerate(value):
            validate_finite_tree(member, f"{context}[{index}]")
        return
    if isinstance(value, dict):
        for key, member in value.items():
            validate_finite_tree(member, f"{context}.{key}")
        return
    raise TypeError(f"Unsupported value in {context}: {type(value).__name__}")


def strict_json_load(path: Path) -> dict[str, Any]:
    def reject_constant(token: str) -> None:
        raise ValueError(f"Non-standard JSON constant {token!r} in {path}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    validate_finite_tree(value, str(path))
    return value


def canonical_hash(payload: dict[str, Any]) -> str:
    validate_finite_tree(payload)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def same_number(actual: float, expected: float, label: str, *, rel: float = 1e-10, abs_: float = 1e-12) -> None:
    actual_float, expected_float = float(actual), float(expected)
    if not math.isfinite(actual_float) or not math.isfinite(expected_float):
        raise ValueError(f"{label} contains a non-finite value: {actual!r} versus {expected!r}")
    if not math.isclose(actual_float, expected_float, rel_tol=rel, abs_tol=abs_):
        raise ValueError(f"{label} mismatch: {actual!r} versus {expected!r}")


def require_finite(value: Any, context: str) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(float(value)):
        raise ValueError(f"Non-finite value in {context}: {value!r}")


def read_csv_records(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        records = list(reader)
    if not records:
        raise ValueError(f"CSV has no records: {path}")
    return records


def load_authorities() -> tuple[dict[str, Any], dict[str, float], dict[str, dict[str, object]]]:
    selected = strict_json_load(DAY3_SELECTED)
    day4 = strict_json_load(DAY4_MANIFEST)
    claimed_day4_hash = str(day4["manifest_sha256"])
    day4_payload = {key: value for key, value in day4.items() if key not in ("manifest_sha256", "hash_definition")}
    calculated_day4_hash = canonical_hash(day4_payload)
    if calculated_day4_hash != claimed_day4_hash:
        raise ValueError(f"Day 4 manifest hash mismatch: {claimed_day4_hash} versus {calculated_day4_hash}")
    if str(day4["source_of_design_truth"]) != "results/generated/day3/selected_parameters.json":
        raise ValueError("Day 4 source_of_design_truth is not the selected Day 3 parameter file")
    selected_file_hash = sha256_file(DAY3_SELECTED)
    if selected_file_hash != str(day4["source_sha256"]):
        raise ValueError("Day 3 selected parameters changed after the Day 4 manifest was built")

    sizes = selected["device_sizes_um"]
    base = {
        "w12": float(sizes["M1"]["w"]), "l12": float(sizes["M1"]["l"]),
        "w34": float(sizes["M3"]["unit_w"]), "l34": float(sizes["M3"]["l"]),
        "w5": float(sizes["M5"]["w"]), "l5": float(sizes["M5"]["l"]),
        "w6": float(sizes["M6"]["w"]), "l6": float(sizes["M6"]["l"]),
        "w7": float(sizes["M7"]["w"]), "l7": float(sizes["M7"]["l"]), "m7_mult": 1.0,
        "w8": float(sizes["M8"]["w"]), "l8": float(sizes["M8"]["l"]),
        "w9": float(sizes["M9"]["w"]), "l9": float(sizes["M9"]["l"]),
        "w10": float(sizes["M10"]["w"]), "l10": float(sizes["M10"]["l"]),
    }
    same_number(sizes["M2"]["w"], base["w12"], "Day 3 M2 width")
    same_number(sizes["M2"]["l"], base["l12"], "Day 3 M2 length")
    same_number(sizes["M4"]["unit_w"], base["w34"], "Day 3 M4 unit width")
    same_number(sizes["M4"]["l"], base["l34"], "Day 3 M4 length")
    if int(sizes["M3"]["units"]) != 2 or int(sizes["M4"]["units"]) != 2:
        raise ValueError("Day 5 expects two explicit units for each of M3 and M4")

    day4_sizes = day4["dut"]["device_sizes_um"]
    for device in range(1, 11):
        source = sizes[f"M{device}"]
        frozen = day4_sizes[f"M{device}"]
        for key, expected in source.items():
            if isinstance(expected, (int, float)):
                same_number(frozen[key], expected, f"Day 4 M{device}.{key}")
    same_number(day4["dut"]["miller_capacitance_f"], selected["cc_f"], "Day 4 CC")
    same_number(day4["dut"]["nulling_resistance_ohm"], selected["rz_ohm"], "Day 4 RZ")
    same_number(day4["dut"]["external_ideal_iref_a"], 10e-6, "Day 4 IREF")

    compensation_rows = read_csv_records(DAY3_COMPENSATION)
    selected_rows = [row for row in compensation_rows if row["selection_role"] == "SELECTED"]
    before_rows = [row for row in compensation_rows if row["selection_role"] == "CC_ONLY_BASELINE"]
    if len(selected_rows) != 1 or len(before_rows) != 1:
        raise ValueError("Day 3 compensation evidence must contain exactly one before and one selected row")
    after, before = selected_rows[0], before_rows[0]
    if after["tag"] != selected["selected_tag"]:
        raise ValueError("Day 3 compensation selection tag disagrees with selected_parameters.json")
    same_number(float(after["cc_pf"]) * 1e-12, selected["cc_f"], "selected compensation CC")
    same_number(after["rz_ohm"], selected["rz_ohm"], "selected compensation RZ")
    if after["hard_ac_specs_pass"] != "True" or before["hard_ac_specs_pass"] != "False":
        raise ValueError("Day 3 compensation before/after pass evidence is inconsistent")

    def changed(**updates: float) -> dict[str, float]:
        result = dict(base)
        result.update(updates)
        return result

    variants: dict[str, dict[str, object]] = {
        "baseline": {"description": "Frozen Day 3/Day 4 geometry", "sizes": dict(base)},
        "first_stage_l2": {
            "description": "Lengthen M1-M4 by 2x at constant W/L",
            "sizes": changed(w12=2*base["w12"], l12=2*base["l12"], w34=2*base["w34"], l34=2*base["l34"]),
        },
        "first_stage_l3": {
            "description": "Lengthen M1-M4 by 3x at constant W/L",
            "sizes": changed(w12=3*base["w12"], l12=3*base["l12"], w34=3*base["w34"], l34=3*base["l34"]),
        },
        "m7_l2": {
            "description": "Lengthen only M7 by 2x at constant total W/L (mult=2)",
            "sizes": changed(w7=base["w7"], l7=2*base["l7"], m7_mult=2.0),
        },
    }
    if tuple(variants) != VARIANT_TAGS:
        raise ValueError("Variant order changed")

    nominal = day4["nominal"]
    if str(selected["corner"]).lower() != "tt" or str(nominal["corner"]).lower() != "tt":
        raise ValueError("Day 5 reconnaissance is intentionally frozen to the TT process corner")
    if str(nominal["corner"]).lower() != str(selected["corner"]).lower():
        raise ValueError("Day 3 and Day 4 nominal corners disagree")
    same_number(nominal["vdd_minus_vss_v"], selected["vdd_v"], "nominal VDD")
    same_number(nominal["temperature_c"], selected["temperature_c"], "nominal temperature")
    same_number(nominal["vcm_v"], selected["vcm_v"], "nominal VCM")
    same_number(nominal["load_capacitance_f"], selected["cload_f"], "nominal CLOAD")
    same_number(nominal["load_resistance_ohm"], selected["rload_ohm"], "nominal RLOAD")
    if nominal["load_return"] != "VSS":
        raise ValueError("Day 4 nominal load is not returned to VSS")
    same_number(nominal["vdd_minus_vss_v"], 1.8, "frozen Day 5 nominal VDD")
    same_number(nominal["temperature_c"], 27.0, "frozen Day 5 nominal temperature")
    same_number(nominal["vcm_v"], 0.9, "frozen Day 5 nominal VCM")
    same_number(nominal["load_capacitance_f"], 5e-12, "frozen Day 5 nominal load capacitance")
    same_number(nominal["load_resistance_ohm"], 100e3, "frozen Day 5 nominal load resistance")

    authorities = {
        "day3_selected": selected,
        "day3_selected_file_sha256": selected_file_hash,
        "day3_compensation_file_sha256": sha256_file(DAY3_COMPENSATION),
        "day3_compensation_before": before,
        "day3_compensation_after": after,
        "day4_manifest": day4,
        "day4_manifest_internal_sha256": claimed_day4_hash,
        "day4_manifest_file_sha256": sha256_file(DAY4_MANIFEST),
    }
    pdk_path = Path(str(day4["pdk"]["library_path"]))
    if pdk_path.exists() and sha256_file(pdk_path) != str(day4["pdk"]["library_sha256"]):
        raise ValueError("Mounted SKY130 model library hash disagrees with the Day 4 manifest")
    return authorities, base, variants


def expected_decks() -> list[str]:
    return [f"{tag}_{bench}.spice" for tag in VARIANT_TAGS for bench in BENCH_NAMES]


def expected_raw_contract() -> dict[str, dict[str, Any]]:
    loop_op_header = [
        "vss", "v(VOUT)", "v(XOTA.VX)", "v(XOTA.VBN)", "v(VBP)",
        "v(XOTA.TAIL)", "v(XOTA.NMIR)", "ivdd_signed", "idd",
    ]
    icmr_op_header = [
        "vss", "v(VOUT)", "v(XOTA.VX)", "v(XOTA.VBN)", "v(VBP)",
        "v(XOTA.TAIL)", "v(XOTA.NMIR)",
        *(field for number in range(1, 11) for field in (f"m{number}_id", f"m{number}_vdsat")),
    ]

    def spec(header: list[str], rows: int, grid: str) -> dict[str, Any]:
        return {"header": header, "columns": len(header), "rows": rows, "grid": grid}

    contract: dict[str, dict[str, Any]] = {}
    for tag in VARIANT_TAGS:
        contract[f"{tag}_loop_op.tsv"] = spec(loop_op_header, 1, "OP_SINGLE_SCALE_ZERO")
        contract[f"{tag}_loop.tsv"] = spec(["frequency", "gain_db", "phase_raw_deg"], 1081, "AC_DEC_120_1HZ_1GHZ")
        contract[f"{tag}_differential_1k.tsv"] = spec(["frequency", "ad", "ad"], 1, "AC_SINGLE_1KHZ")
        contract[f"{tag}_psrr_plus_1k.tsv"] = spec(["frequency", "asupply", "asupply"], 1, "AC_SINGLE_1KHZ")
        contract[f"{tag}_psrr_minus_1k.tsv"] = spec(["frequency", "asupply", "asupply"], 1, "AC_SINGLE_1KHZ")
        contract[f"{tag}_transient.tsv"] = spec(["time", "v(VINP)", "v(VOUT)"], 10020, "TRAN_0_TO_5US_MAXSTEP_0P5NS")
        for vcm in VCM_POINTS:
            point = str(vcm).replace(".", "p")
            contract[f"{tag}_icmr_{point}_op.tsv"] = spec(icmr_op_header, 1, f"OP_VCM_{vcm:.1f}V_SCALE_ZERO")
            contract[f"{tag}_icmr_{point}_ac.tsv"] = spec(["frequency", "ad", "ad"], 1, "AC_SINGLE_1HZ")
    return contract


def build_day5_manifest(authorities: dict[str, Any], base: dict[str, float], variants: dict[str, dict[str, object]]) -> tuple[dict[str, Any], str]:
    day4 = authorities["day4_manifest"]
    before = authorities["day3_compensation_before"]
    after = authorities["day3_compensation_after"]
    payload: dict[str, Any] = {
        "schema": "sky130-two-stage-ota/day5-recon-manifest/v2",
        "authorities": {
            "day3_selected_parameters": {
                "path": "results/generated/day3/selected_parameters.json",
                "file_sha256": authorities["day3_selected_file_sha256"],
                "selected_tag": authorities["day3_selected"]["selected_tag"],
            },
            "day3_compensation_evidence": {
                "path": "results/day3_compensation_before_after.csv",
                "file_sha256": authorities["day3_compensation_file_sha256"],
                "before_tag": before["tag"], "before_pm_deg": float(before["phase_margin_deg"]),
                "after_tag": after["tag"], "after_pm_deg": float(after["phase_margin_deg"]),
                "pm_improvement_deg": float(after["phase_margin_improvement_vs_cc_only_deg"]),
            },
            "day4_manifest": {
                "path": "results/generated/day4/day4_manifest.json",
                "file_sha256": authorities["day4_manifest_file_sha256"],
                "internal_manifest_sha256": authorities["day4_manifest_internal_sha256"],
            },
        },
        "workflow": {
            "recon_py_sha256": sha256_file(HERE / "recon.py"),
            "run_sh_sha256": sha256_file(HERE / "run.sh"),
            "container_image": IMAGE,
            "simulation_and_analysis_runtime": "same_digest_pinned_container",
        },
        "pdk": day4["pdk"],
        "baseline": {
            "sizes_um": base,
            "cc_f": float(authorities["day3_selected"]["cc_f"]),
            "rz_ohm": float(authorities["day3_selected"]["rz_ohm"]),
            "external_ideal_iref_a": float(day4["dut"]["external_ideal_iref_a"]),
        },
        "nominal": day4["nominal"],
        "variants": [
            {"tag": tag, "description": definition["description"], "sizes_um": definition["sizes"]}
            for tag, definition in variants.items()
        ],
        "test_contract": {
            "executed_decks": expected_decks(), "expected_log_count": 32,
            "expected_exit_code_count": 32, "raw_tsv": expected_raw_contract(),
        },
        "metric_definitions": {
            "psrr_1khz": "20*log10(abs(Ad/Asupply)) at the identical 1-kHz bias point",
            "slew": "Day 4 directed monotonic least-squares 20%-80% output fit",
            "settling": "Day 4 earliest point remaining within +/-4 mV through the measurement window, referenced to input 50% crossing",
            "icmr_checkpoint": "Day 4-equivalent 1-Hz gain no more than 3 dB below VCM=0.9 V, all M1-M10 margins nonnegative, output tracking error <=10 mV",
            "ugb": "unique non-boundary downward 0-dB return-ratio crossing",
        },
        "decision_policy": {
            "production_design": "KEEP_FROZEN_DAY4_BASELINE",
            "adopted_optimization": "DAY3_ADD_RZ_2K_WITH_CC_3P",
            "candidate_promotion_requires_full_day4_revalidation": True,
        },
        "limitations": [
            "schematic-level nominal reconnaissance only", "no mismatch or Monte Carlo simulation",
            "no layout or extracted parasitics", "three ICMR checkpoints do not establish a continuous ICMR",
        ],
    }
    manifest_hash = canonical_hash(payload)
    return {
        **payload, "manifest_sha256": manifest_hash,
        "hash_definition": "SHA-256 of canonical JSON payload excluding manifest_sha256 and hash_definition",
    }, manifest_hash


def load_expected_manifest() -> tuple[dict[str, Any], str, dict[str, float], dict[str, dict[str, object]], dict[str, Any]]:
    authorities, base, variants = load_authorities()
    expected, manifest_hash = build_day5_manifest(authorities, base, variants)
    return expected, manifest_hash, base, variants, authorities


def load_and_verify_written_manifest() -> tuple[dict[str, Any], str, dict[str, float], dict[str, dict[str, object]], dict[str, Any]]:
    expected, expected_hash, base, variants, authorities = load_expected_manifest()
    actual = strict_json_load(MANIFEST_PATH)
    claimed = str(actual["manifest_sha256"])
    payload = {key: value for key, value in actual.items() if key not in ("manifest_sha256", "hash_definition")}
    if canonical_hash(payload) != claimed:
        raise ValueError("Written Day 5 manifest does not verify against its own hash")
    if claimed != expected_hash or actual != expected:
        raise ValueError("Written Day 5 manifest is stale relative to Day 3/Day 4/workflow authorities")
    return actual, claimed, base, variants, authorities


def csv_text(records: list[dict[str, Any]], manifest_hash: str, context: str) -> str:
    if not records:
        raise ValueError(f"Refusing to serialize empty CSV: {context}")
    stamped: list[dict[str, Any]] = []
    for row_number, record in enumerate(records, start=1):
        copy = dict(record)
        for key, value in copy.items():
            require_finite(value, f"{context} row {row_number} field {key}")
        if "manifest_sha256" in copy and copy["manifest_sha256"] != manifest_hash:
            raise ValueError(f"Conflicting manifest stamp in {context}")
        copy["manifest_sha256"] = manifest_hash
        stamped.append(copy)
    fields = list(stamped[0])
    if any(set(row) != set(fields) for row in stamped):
        raise ValueError(f"Inconsistent CSV schema in {context}")
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(stamped)
    return handle.getvalue()


def write_csv(path: Path, records: list[dict[str, Any]], manifest_hash: str) -> None:
    path.write_text(csv_text(records, manifest_hash, path.name), encoding="utf-8")


def verify_csv_exact(path: Path, records: list[dict[str, Any]], manifest_hash: str) -> None:
    expected = csv_text(records, manifest_hash, path.name)
    actual = path.read_text(encoding="utf-8", errors="strict")
    if actual != expected:
        raise ValueError(
            f"CSV content mismatch in {path}; expected SHA-256 {sha256_text(expected)}, "
            f"found {sha256_text(actual)}"
        )


def verify_csv_stamp(path: Path, manifest_hash: str, expected_rows: int) -> None:
    rows = read_csv_records(path)
    if len(rows) != expected_rows:
        raise ValueError(f"{path.name} row count {len(rows)} != {expected_rows}")
    if any(row.get("manifest_sha256") != manifest_hash for row in rows):
        raise ValueError(f"CSV manifest stamp mismatch: {path}")


def dut(tag: str, sizes: dict[str, float], cc_f: float, rz_ohm: float, manifest_hash: str) -> str:
    p = {name: f"{value:.12g}" for name, value in sizes.items()}
    return f"""* Day 5 isolated DUT: {tag}
* DAY5_MANIFEST_SHA256={manifest_hash}
* Frozen topology; candidate geometry only. CC={cc_f:.12g} F; RZ={rz_ohm:.12g} ohm.
.subckt OTA VDD VSS VINP VINN VOUT VBP
XM8  VBP  VBP VDD VDD sky130_fd_pr__pfet_01v8 L={p['l8']} W={p['w8']} nf=1 mult=1
XM9  VBN  VBP VDD VDD sky130_fd_pr__pfet_01v8 L={p['l9']} W={p['w9']} nf=1 mult=1
XM10 VBN  VBN VSS VSS sky130_fd_pr__nfet_01v8 L={p['l10']} W={p['w10']} nf=1 mult=1
XM1  NMIR VINN TAIL VSS sky130_fd_pr__nfet_01v8 L={p['l12']} W={p['w12']} nf=1 mult=1
XM2  VX   VINP TAIL VSS sky130_fd_pr__nfet_01v8 L={p['l12']} W={p['w12']} nf=1 mult=1
XM3A NMIR NMIR VDD VDD sky130_fd_pr__pfet_01v8 L={p['l34']} W={p['w34']} nf=1 mult=1
XM3B NMIR NMIR VDD VDD sky130_fd_pr__pfet_01v8 L={p['l34']} W={p['w34']} nf=1 mult=1
XM4A VX   NMIR VDD VDD sky130_fd_pr__pfet_01v8 L={p['l34']} W={p['w34']} nf=1 mult=1
XM4B VX   NMIR VDD VDD sky130_fd_pr__pfet_01v8 L={p['l34']} W={p['w34']} nf=1 mult=1
XM5  TAIL VBN  VSS VSS sky130_fd_pr__nfet_01v8 L={p['l5']} W={p['w5']} nf=1 mult=1
XM6  VOUT VX   VSS VSS sky130_fd_pr__nfet_01v8 L={p['l6']} W={p['w6']} nf=1 mult=1
XM7  VOUT VBP  VDD VDD sky130_fd_pr__pfet_01v8 L={p['l7']} W={p['w7']} nf=1 mult={p['m7_mult']}
RZ1 VX NCC {rz_ohm:.12g}
CC1 NCC VOUT {cc_f:.12g}
.ends OTA
"""


def header(tag: str, cfg: dict[str, float | str], manifest_hash: str) -> str:
    return f"""* DAY5_MANIFEST_SHA256={manifest_hash}
.lib \"{cfg['pdk']}\" {cfg['corner']}
.temp {float(cfg['temp_c']):.12g}
.include \"experiments/day5/generated/dut_{tag}.spice\"
"""


def footer() -> str:
    return ".end\n"


def loop_deck(tag: str, cfg: dict[str, float | str], manifest_hash: str) -> str:
    return header(tag, cfg, manifest_hash) + f"""
VSSSUP VSS 0 0
VDD VDD VSS {float(cfg['vdd_v']):.12g}
IREF VBP VSS {float(cfg['iref_a']):.12g}
VINP VINP VSS DC {float(cfg['vcm_v']):.12g} AC 0
VTEST VTEST VSS DC 0 AC 1
LBREAK VOUT VINN 1G
CBREAK VTEST VINN 1G
RLOAD VOUT VSS {float(cfg['rload_ohm']):.12g}
CLOAD VOUT VSS {float(cfg['cload_f']):.12g}
XOTA VDD VSS VINP VINN VOUT VBP OTA
.save all
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
let ivdd_signed=i(VDD)
let idd=abs(ivdd_signed)
wrdata experiments/day5/raw/{tag}_loop_op.tsv v(VOUT) v(XOTA.VX) v(XOTA.VBN) v(VBP) v(XOTA.TAIL) v(XOTA.NMIR) ivdd_signed idd
ac dec 120 1 1G
let tloop=-v(VOUT)/v(VINN)
let gain_db=db(tloop)
let phase_raw_deg=180/pi*ph(tloop)
wrdata experiments/day5/raw/{tag}_loop.tsv gain_db phase_raw_deg
quit
.endc
""" + footer()


def differential_deck(tag: str, cfg: dict[str, float | str], manifest_hash: str) -> str:
    return header(tag, cfg, manifest_hash) + f"""
VSSSUP VSS 0 0
VDD VDD VSS {float(cfg['vdd_v']):.12g}
IREF VBP VSS {float(cfg['iref_a']):.12g}
VINP VINP VSS DC {float(cfg['vcm_v']):.12g} AC 0.5
VNEG VNEG VSS DC 0 AC -0.5
LBREAK VOUT VINN 1G
CBREAK VNEG VINN 1G
RLOAD VOUT VSS {float(cfg['rload_ohm']):.12g}
CLOAD VOUT VSS {float(cfg['cload_f']):.12g}
XOTA VDD VSS VINP VINN VOUT VBP OTA
.control
set noaskquit
set wr_singlescale
set wr_vecnames
ac lin 1 1k 1k
let vdiff=v(VINP)-v(VINN)
let ad=v(VOUT)/vdiff
wrdata experiments/day5/raw/{tag}_differential_1k.tsv ad
quit
.endc
""" + footer()


def supply_deck(tag: str, rail: str, cfg: dict[str, float | str], manifest_hash: str) -> str:
    if rail == "plus":
        supplies = f"VSSSUP VSS 0 DC 0 AC 0\nVDD VDD VSS DC {float(cfg['vdd_v']):.12g} AC 1"
        inputs = f"VINP VINP VSS DC {float(cfg['vcm_v']):.12g} AC 0\nVINN VINN VSS DC {float(cfg['vcm_v']):.12g} AC 0"
        response = "v(VOUT)/v(VDD,VSS)"
    elif rail == "minus":
        supplies = f"VSSSUP VSS 0 DC 0 AC 1\nVDD VDD 0 DC {float(cfg['vdd_v']):.12g} AC 0"
        inputs = f"VINP VINP 0 DC {float(cfg['vcm_v']):.12g} AC 0\nVINN VINN 0 DC {float(cfg['vcm_v']):.12g} AC 0"
        response = "v(VOUT)/v(VSS)"
    else:
        raise ValueError(rail)
    return header(tag, cfg, manifest_hash) + f"""
{supplies}
IREF VBP VSS {float(cfg['iref_a']):.12g}
{inputs}
RLOAD VOUT VSS {float(cfg['rload_ohm']):.12g}
CLOAD VOUT VSS {float(cfg['cload_f']):.12g}
XOTA VDD VSS VINP VINN VOUT VBP OTA
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
ac lin 1 1k 1k
let asupply={response}
wrdata experiments/day5/raw/{tag}_psrr_{rail}_1k.tsv asupply
quit
.endc
""" + footer()


def transient_deck(tag: str, cfg: dict[str, float | str], manifest_hash: str) -> str:
    return header(tag, cfg, manifest_hash) + f"""
VSSSUP VSS 0 0
VDD VDD VSS {float(cfg['vdd_v']):.12g}
IREF VBP VSS {float(cfg['iref_a']):.12g}
VINP VINP VSS PULSE(0.8 1.2 1u 20n 20n 2u 5u)
RLOAD VOUT VSS {float(cfg['rload_ohm']):.12g}
CLOAD VOUT VSS {float(cfg['cload_f']):.12g}
XOTA VDD VSS VINP VOUT VOUT VBP OTA
.control
set noaskquit
set wr_singlescale
set wr_vecnames
tran 0.5n 5u
wrdata experiments/day5/raw/{tag}_transient.tsv v(VINP) v(VOUT)
quit
.endc
""" + footer()


def icmr_deck(tag: str, vcm: float, cfg: dict[str, float | str], manifest_hash: str) -> str:
    point = f"{vcm:.1f}".replace(".", "p")
    device_lines: list[str] = []
    output_vectors: list[str] = []
    for number in range(1, 11):
        model = "pfet" if number in (3, 4, 7, 8, 9) else "nfet"
        instance = f"xm{number}a" if number in (3, 4) else f"xm{number}"
        if number in (3, 4):
            device_lines.append(f"let m{number}_id=abs(@m.xota.xm{number}a.msky130_fd_pr__{model}_01v8[id])+abs(@m.xota.xm{number}b.msky130_fd_pr__{model}_01v8[id])")
        else:
            device_lines.append(f"let m{number}_id=abs(@m.xota.{instance}.msky130_fd_pr__{model}_01v8[id])")
        device_lines.append(f"let m{number}_vdsat=abs(@m.xota.{instance}.msky130_fd_pr__{model}_01v8[vdsat])")
        output_vectors.extend((f"m{number}_id", f"m{number}_vdsat"))
    controls = "\n".join(device_lines)
    vectors = " ".join(output_vectors)
    return header(tag, cfg, manifest_hash) + f"""
VSSSUP VSS 0 0
VDD VDD VSS {float(cfg['vdd_v']):.12g}
IREF VBP VSS {float(cfg['iref_a']):.12g}
VINP VINP VSS DC {vcm:.1f} AC 0.5
VNEG VNEG VSS DC 0 AC -0.5
LBREAK VOUT VINN 1G
CBREAK VNEG VINN 1G
RLOAD VOUT VSS {float(cfg['rload_ohm']):.12g}
CLOAD VOUT VSS {float(cfg['cload_f']):.12g}
XOTA VDD VSS VINP VINN VOUT VBP OTA
.control
set noaskquit
set wr_singlescale
set wr_vecnames
op
{controls}
wrdata experiments/day5/raw/{tag}_icmr_{point}_op.tsv v(VOUT) v(XOTA.VX) v(XOTA.VBN) v(VBP) v(XOTA.TAIL) v(XOTA.NMIR) {vectors}
ac lin 1 1 1
let vdiff=v(VINP)-v(VINN)
let ad=v(VOUT)/vdiff
wrdata experiments/day5/raw/{tag}_icmr_{point}_ac.tsv ad
quit
.endc
""" + footer()


def simulation_config(authorities: dict[str, Any]) -> dict[str, float | str]:
    day4, nominal = authorities["day4_manifest"], authorities["day4_manifest"]["nominal"]
    return {
        "pdk": str(day4["pdk"]["library_path"]), "corner": str(nominal["corner"]).lower(),
        "temp_c": float(nominal["temperature_c"]), "vdd_v": float(nominal["vdd_minus_vss_v"]),
        "vcm_v": float(nominal["vcm_v"]), "rload_ohm": float(nominal["load_resistance_ohm"]),
        "cload_f": float(nominal["load_capacitance_f"]), "iref_a": float(day4["dut"]["external_ideal_iref_a"]),
    }


def render_generated(
    manifest_hash: str, variants: dict[str, dict[str, object]], authorities: dict[str, Any],
) -> tuple[dict[str, str], list[str], list[dict[str, Any]]]:
    selected, cfg = authorities["day3_selected"], simulation_config(authorities)
    rendered: dict[str, str] = {}
    run_list: list[str] = []
    variant_rows: list[dict[str, Any]] = []
    for tag, definition in variants.items():
        sizes = definition["sizes"]
        if not isinstance(sizes, dict):
            raise TypeError(f"Variant sizes are not a mapping: {tag}")
        rendered[f"dut_{tag}.spice"] = dut(
            tag, sizes, float(selected["cc_f"]), float(selected["rz_ohm"]), manifest_hash,
        )
        decks = {
            "loop": loop_deck(tag, cfg, manifest_hash), "differential": differential_deck(tag, cfg, manifest_hash),
            "psrr_plus": supply_deck(tag, "plus", cfg, manifest_hash),
            "psrr_minus": supply_deck(tag, "minus", cfg, manifest_hash), "transient": transient_deck(tag, cfg, manifest_hash),
        }
        for vcm in VCM_POINTS:
            decks[f"icmr_{str(vcm).replace('.', 'p')}"] = icmr_deck(tag, vcm, cfg, manifest_hash)
        for bench, content in decks.items():
            relative = f"{tag}_{bench}.spice"
            rendered[relative] = content
            run_list.append(relative)
        variant_rows.append({
            "tag": tag, "role": "BASELINE" if tag == "baseline" else "CANDIDATE",
            "description": definition["description"], **sizes,
        })
    if run_list != expected_decks():
        raise ValueError("Rendered deck order does not match the manifest contract")
    return rendered, run_list, variant_rows


def verify_generated(
    manifest_hash: str, variants: dict[str, dict[str, object]], authorities: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    expected_contents, run_list, variant_rows = render_generated(manifest_hash, variants, authorities)
    expected_files = set(expected_contents) | {"run_list.txt"}
    actual_files = {path.name for path in GENERATED.iterdir() if path.is_file()}
    actual_directories = {path.name for path in GENERATED.iterdir() if path.is_dir()}
    if actual_files != expected_files or actual_directories:
        raise ValueError(
            f"Generated set mismatch; missing={sorted(expected_files-actual_files)}, "
            f"extra={sorted(actual_files-expected_files)}, directories={sorted(actual_directories)}"
        )
    expected_run_list = "\n".join(run_list) + "\n"
    actual_run_list = (GENERATED / "run_list.txt").read_text(encoding="utf-8", errors="strict")
    if actual_run_list != expected_run_list:
        raise ValueError("run_list.txt does not exactly match the deterministic 32-deck order")
    records: list[dict[str, Any]] = []
    for name in sorted(expected_contents):
        expected_content = expected_contents[name]
        actual_content = (GENERATED / name).read_text(encoding="utf-8", errors="strict")
        if actual_content != expected_content:
            raise ValueError(
                f"Generated deck differs from authority-derived rendering: {name}; "
                f"expected SHA-256 {sha256_text(expected_content)}, found {sha256_text(actual_content)}"
            )
        stamp_count = actual_content.count(f"DAY5_MANIFEST_SHA256={manifest_hash}")
        if stamp_count != 1:
            raise ValueError(f"Generated deck must contain exactly one Day 5 manifest stamp: {name}")
        records.append({
            "generated_file": f"generated/{name}",
            "role": "DUT" if name.startswith("dut_") else "EXECUTED_BENCH",
            "sha256": sha256_text(expected_content), "manifest_stamp_count": stamp_count,
        })
    return records, variant_rows


def generate() -> None:
    manifest, manifest_hash, _, variants, authorities = load_expected_manifest()
    for name in CSV_OUTPUTS:
        path = HERE / name
        if path.exists():
            path.unlink()
    for name in ("assessment.md", "last_success.json"):
        path = HERE / name
        if path.exists():
            path.unlink()
    shutil.rmtree(GENERATED, ignore_errors=True)
    shutil.rmtree(RAW, ignore_errors=True)
    GENERATED.mkdir(parents=True)
    RAW.mkdir(parents=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8",
    )
    rendered, run_list, variant_rows = render_generated(manifest_hash, variants, authorities)
    for name, content in rendered.items():
        (GENERATED / name).write_text(content, encoding="utf-8")
    (GENERATED / "run_list.txt").write_text("\n".join(run_list) + "\n", encoding="utf-8")
    generated_rows, verified_variant_rows = verify_generated(manifest_hash, variants, authorities)
    if verified_variant_rows != variant_rows:
        raise ValueError("Internal variant rendering changed during generation")
    write_csv(HERE / "variant_manifest.csv", variant_rows, manifest_hash)
    write_csv(HERE / "generated_inventory.csv", generated_rows, manifest_hash)
    print(f"DAY5_RECON_GENERATED manifest={manifest_hash} variants={len(variants)} decks={len(run_list)}")


def strict_numeric_rows(
    path: Path, expected_header: list[str], manifest_hash: str, *, require_stamp: bool,
) -> tuple[list[str], list[list[float]]]:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    if len(lines) < 2:
        raise ValueError(f"TSV has no data rows: {path}")
    if any(not line.strip() for line in lines):
        raise ValueError(f"TSV contains an unexpected blank line: {path}")
    physical_header = lines[0].split()
    stamped = bool(physical_header and physical_header[-1] == "manifest_sha256")
    if require_stamp and not stamped:
        raise ValueError(f"TSV lacks manifest column: {path}")
    logical_header = physical_header[:-1] if stamped else physical_header
    if logical_header != expected_header:
        raise ValueError(f"TSV header mismatch in {path}: {logical_header!r} != {expected_header!r}")
    expected_width = len(expected_header) + (1 if stamped else 0)
    rows: list[list[float]] = []
    for line_number, line in enumerate(lines[1:], start=2):
        fields = line.split()
        if len(fields) != expected_width:
            raise ValueError(f"TSV row width mismatch in {path}:{line_number}: {len(fields)} != {expected_width}")
        if stamped:
            if fields[-1] != manifest_hash:
                raise ValueError(f"TSV manifest mismatch in {path}:{line_number}")
            fields = fields[:-1]
        try:
            values = [float(value) for value in fields]
        except ValueError as exc:
            raise ValueError(f"Non-numeric TSV data in {path}:{line_number}") from exc
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Non-finite TSV data in {path}:{line_number}")
        rows.append(values)
    return logical_header, rows


def normalize_simulator_text() -> None:
    paths = [*RAW.glob("*.tsv"), *RAW.glob("*.log"), *RAW.glob("*.exit_code")]
    for path in paths:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
        path.write_text("\n".join(line.rstrip() for line in lines) + "\n", encoding="utf-8")


def stamp_raw_tsv(manifest_hash: str) -> None:
    contract = expected_raw_contract()
    actual = {path.name for path in RAW.glob("*.tsv")}
    if actual != set(contract):
        raise ValueError(f"Raw TSV set mismatch before stamping; missing={sorted(set(contract)-actual)}, extra={sorted(actual-set(contract))}")
    for name, specification in contract.items():
        path = RAW / name
        _, rows = strict_numeric_rows(path, list(specification["header"]), manifest_hash, require_stamp=False)
        lines = path.read_text(encoding="utf-8").splitlines()
        if lines[0].split()[-1] == "manifest_sha256":
            strict_numeric_rows(path, list(specification["header"]), manifest_hash, require_stamp=True)
            continue
        stamped = [lines[0].rstrip() + "\tmanifest_sha256"]
        stamped.extend(line.rstrip() + "\t" + manifest_hash for line in lines[1:])
        path.write_text("\n".join(stamped) + "\n", encoding="utf-8")
        if len(rows) != int(specification["rows"]):
            raise ValueError(f"Raw row count mismatch while stamping {name}")


def close(actual: float, expected: float, *, rel: float = 2e-8, abs_: float = 1e-15) -> bool:
    return math.isclose(actual, expected, rel_tol=rel, abs_tol=abs_)


def reconcile_raw(manifest_hash: str) -> tuple[list[dict[str, Any]], dict[str, list[list[float]]]]:
    contract = expected_raw_contract()
    actual = {path.name for path in RAW.glob("*.tsv")}
    if actual != set(contract):
        raise ValueError(f"Raw TSV set mismatch; missing={sorted(set(contract)-actual)}, extra={sorted(actual-set(contract))}")
    records: list[dict[str, Any]] = []
    data: dict[str, list[list[float]]] = {}
    transient_reference: list[float] | None = None
    loop_reference: list[float] | None = None
    for name, specification in sorted(contract.items()):
        header, rows = strict_numeric_rows(
            RAW / name, list(specification["header"]), manifest_hash, require_stamp=True,
        )
        if len(rows) != int(specification["rows"]):
            raise ValueError(f"Raw row count mismatch in {name}: {len(rows)} != {specification['rows']}")
        grid = str(specification["grid"])
        x = [row[0] for row in rows]
        if grid == "AC_DEC_120_1HZ_1GHZ":
            expected = [10.0 ** (index / 120.0) for index in range(1081)]
            if any(not close(a, b, rel=2e-8, abs_=1e-12) for a, b in zip(x, expected)):
                raise ValueError(f"Loop frequency grid mismatch in {name}")
            if any(b <= a for a, b in zip(x, x[1:])):
                raise ValueError(f"Loop frequency grid is not strictly increasing in {name}")
            if loop_reference is None:
                loop_reference = x
            elif x != loop_reference:
                raise ValueError(f"Loop frequency grids are not identical: {name}")
        elif grid == "AC_SINGLE_1KHZ":
            if len(x) != 1 or not close(x[0], 1000.0, rel=0.0, abs_=1e-9):
                raise ValueError(f"Single-frequency grid is not exactly 1 kHz in {name}")
        elif grid == "AC_SINGLE_1HZ":
            if len(x) != 1 or not close(x[0], 1.0, rel=0.0, abs_=1e-12):
                raise ValueError(f"Single-frequency grid is not exactly 1 Hz in {name}")
        elif grid == "TRAN_0_TO_5US_MAXSTEP_0P5NS":
            if not close(x[0], 0.0, rel=0.0, abs_=1e-18) or not close(x[-1], 5e-6, rel=0.0, abs_=1e-15):
                raise ValueError(f"Transient boundary mismatch in {name}")
            if any(b <= a for a, b in zip(x, x[1:])):
                raise ValueError(f"Transient time is not strictly increasing in {name}")
            if max(b-a for a, b in zip(x, x[1:])) > 0.500001e-9:
                raise ValueError(f"Transient maximum step exceeds 0.5 ns in {name}")
            if transient_reference is None:
                transient_reference = x
            elif x != transient_reference:
                raise ValueError(f"Transient time grids are not identical: {name}")
        elif grid.startswith("OP_"):
            if len(x) != 1 or not close(x[0], 0.0, rel=0.0, abs_=1e-18):
                raise ValueError(f"Operating-point output is not a singleton at scale zero in {name}")
        else:
            raise ValueError(f"Unknown raw grid contract {grid}")
        data[name] = rows
        records.append({
            "raw_tsv": f"raw/{name}", "expected_columns_without_stamp": specification["columns"],
            "actual_columns_without_stamp": len(header), "expected_rows": specification["rows"],
            "actual_rows": len(rows), "grid_contract": grid, "grid_status": "PASS",
            "sha256": sha256_file(RAW/name), "status": "PASS",
        })
    return records, data


def audit_logs() -> list[dict[str, Any]]:
    stems = [Path(name).stem for name in expected_decks()]
    expected_logs, expected_exits = ({f"{stem}.log" for stem in stems}, {f"{stem}.exit_code" for stem in stems})
    actual_logs, actual_exits = ({path.name for path in RAW.glob("*.log")}, {path.name for path in RAW.glob("*.exit_code")})
    if actual_logs != expected_logs or actual_exits != expected_exits:
        raise ValueError(
            f"Log/exit set mismatch: missing_logs={sorted(expected_logs-actual_logs)}, extra_logs={sorted(actual_logs-expected_logs)}, "
            f"missing_exits={sorted(expected_exits-actual_exits)}, extra_exits={sorted(actual_exits-expected_exits)}"
        )
    fatal_pattern = re.compile(
        r"(^|\n)\s*(?:Error(?: on line)?:|Fatal)|failed to converge|timestep too small|singular matrix|no such vector|could not find a valid modelname",
        re.IGNORECASE,
    )
    records: list[dict[str, Any]] = []
    for stem in stems:
        log_path, exit_path = RAW/f"{stem}.log", RAW/f"{stem}.exit_code"
        text = log_path.read_text(encoding="utf-8", errors="strict")
        exit_text = exit_path.read_text(encoding="utf-8", errors="strict").strip()
        if not re.fullmatch(r"-?\d+", exit_text):
            raise ValueError(f"Malformed exit code: {exit_path}")
        exit_code, done_count = int(exit_text), text.count("ngspice-47 done")
        fatal = bool(fatal_pattern.search(text))
        status = "PASS" if exit_code == 0 and done_count == 1 and not fatal else "FAIL"
        records.append({
            "deck": f"generated/{stem}.spice", "log": f"raw/{stem}.log",
            "exit_code_file": f"raw/{stem}.exit_code", "exit_code": exit_code,
            "ngspice_done_count": done_count, "fatal_diagnostic": fatal,
            "known_multiplier_warning_count": text.count("m=xx on .subckt line will override multiplier"),
            "warning_count": len(re.findall(r"^Warning:", text, flags=re.MULTILINE)),
            "log_sha256": sha256_file(log_path), "status": status,
        })
    if len(records) != 32 or any(row["status"] != "PASS" for row in records):
        raise RuntimeError(f"Corrected log audit is not 32/32 PASS: {sum(row['status']=='PASS' for row in records)}/32")
    return records


def magnitude(row: list[float]) -> float:
    result = math.hypot(row[1], row[2])
    if result <= 0.0 or not math.isfinite(result):
        raise ValueError("Complex magnitude is not finite and positive")
    return result


def loop_metrics(tag: str, data: dict[str, list[list[float]]], vdd_v: float) -> dict[str, Any]:
    rows = data[f"{tag}_loop.tsv"]
    frequency, gain, raw_phase = ([row[0] for row in rows], [row[1] for row in rows], [row[2] for row in rows])
    phase: list[float] = []
    for value in raw_phase:
        if not phase:
            value -= round(value/360.0)*360.0
        else:
            while value-phase[-1] > 180.0:
                value -= 360.0
            while value-phase[-1] < -180.0:
                value += 360.0
        phase.append(value)
    exact_zero_samples = [index for index, value in enumerate(gain) if value == 0.0]
    if exact_zero_samples:
        raise ValueError(
            f"{tag}: exact 0-dB sample(s) make the interpolated UGB ambiguous: {exact_zero_samples}"
        )
    downward = [i for i in range(len(gain)-1) if gain[i] > 0.0 and gain[i+1] < 0.0]
    all_crossings = [
        i for i in range(len(gain)-1)
        if (gain[i] > 0.0 > gain[i+1]) or (gain[i] < 0.0 < gain[i+1])
    ]
    if len(downward) != 1 or len(all_crossings) != 1:
        raise ValueError(f"{tag}: UGB crossing is not unique downward (down={len(downward)}, all={len(all_crossings)})")
    index = downward[0]
    boundary = index == 0 or index == len(gain)-2
    if boundary:
        raise ValueError(f"{tag}: UGB crossing occurs at an AC sweep boundary")
    fraction = -gain[index]/(gain[index+1]-gain[index])
    ugb = 10**(math.log10(frequency[index]) + fraction*(math.log10(frequency[index+1])-math.log10(frequency[index])))
    phase_at = phase[index] + fraction*(phase[index+1]-phase[index])
    op = data[f"{tag}_loop_op.tsv"][-1]
    vout, vx, vbn, vbp, tail, nmir, ivdd_signed, idd = op[1:9]
    if not math.isclose(idd, abs(ivdd_signed), rel_tol=1e-7, abs_tol=1e-12):
        raise ValueError(f"{tag}: signed and absolute supply currents disagree")
    return {
        "a0_db": gain[0], "loop_phase_1hz_deg": phase[0],
        "zero_db_downward_crossings": len(downward), "zero_db_all_crossings": len(all_crossings),
        "zero_db_exact_samples": len(exact_zero_samples),
        "ugb_crossing_index": index, "ugb_crossing_at_boundary": boundary,
        "ugb_mhz": ugb/1e6, "phase_at_ugb_deg": phase_at, "pm_deg": 180+phase_at,
        "ivdd_signed_ua": ivdd_signed*1e6, "power_uw": vdd_v*idd*1e6,
        "vout_v": vout, "vx_v": vx, "vbn_v": vbn, "vbp_v": vbp, "tail_v": tail, "nmir_v": nmir,
    }


def crossing_time(time_s: list[float], signal_v: list[float], *, level_v: float, start_s: float, stop_s: float, rising: bool) -> float:
    for index in range(len(time_s)-1):
        if time_s[index] < start_s or time_s[index+1] > stop_s:
            continue
        y0, y1 = signal_v[index], signal_v[index+1]
        directed = y0 <= level_v < y1 if rising else y0 >= level_v > y1
        if directed:
            fraction = 0.0 if y1 == y0 else (level_v-y0)/(y1-y0)
            return time_s[index] + fraction*(time_s[index+1]-time_s[index])
    raise ValueError(f"No {'rising' if rising else 'falling'} {level_v}-V crossing")


def linear_slope(x: list[float], y: list[float]) -> float:
    if len(x) < 2:
        raise ValueError("Linear fit requires at least two samples")
    xm, ym = sum(x)/len(x), sum(y)/len(y)
    denominator = sum((value-xm)**2 for value in x)
    if denominator <= 0:
        raise ValueError("Linear fit has zero time span")
    return sum((a-xm)*(b-ym) for a, b in zip(x, y))/denominator


def fitted_slew(time_s: list[float], output_v: list[float], *, start_s: float, stop_s: float, rising: bool) -> tuple[float, int]:
    first_level, second_level = ((0.88, 1.12) if rising else (1.12, 0.88))
    window = [i for i, value in enumerate(time_s) if start_s <= value < stop_s]
    first_candidates = [i for i in window if output_v[i] >= first_level] if rising else [i for i in window if output_v[i] <= first_level]
    if not first_candidates:
        raise ValueError("Output did not reach first slew threshold")
    first = first_candidates[0]
    remaining = [i for i in window if i >= first]
    second_candidates = [i for i in remaining if output_v[i] >= second_level] if rising else [i for i in remaining if output_v[i] <= second_level]
    if not second_candidates:
        raise ValueError("Output did not reach second slew threshold")
    indices = list(range(first, second_candidates[0]+1))
    if len(indices) < 5:
        raise ValueError("Fewer than five points in 20%-80% slew fit")
    differences = [output_v[b]-output_v[a] for a, b in zip(indices, indices[1:])]
    if rising and any(value < -1e-6 for value in differences):
        raise ValueError("Rising slew interval is not monotonic")
    if not rising and any(value > 1e-6 for value in differences):
        raise ValueError("Falling slew interval is not monotonic")
    slope = linear_slope([time_s[i] for i in indices], [output_v[i] for i in indices])
    return abs(slope)/1e6, len(indices)


def settling_time(time_s: list[float], output_v: list[float], target_v: float, reference_s: float, stop_s: float) -> float:
    indices = [i for i, value in enumerate(time_s) if reference_s <= value < stop_s]
    if not indices:
        raise ValueError("Settling window has no samples")
    within = [abs(output_v[i]-target_v) <= 0.004 for i in indices]
    stays, running = [False]*len(within), True
    for offset in range(len(within)-1, -1, -1):
        running = running and within[offset]
        stays[offset] = running
    candidates = [indices[offset] for offset, value in enumerate(stays) if value]
    if not candidates:
        raise ValueError("Output never remains inside 1% settling band")
    return time_s[candidates[0]]-reference_s


def transient_metrics(tag: str, data: dict[str, list[list[float]]]) -> dict[str, Any]:
    rows = data[f"{tag}_transient.tsv"]
    time_s, input_v, output_v = ([row[0] for row in rows], [row[1] for row in rows], [row[2] for row in rows])
    rise_mid = crossing_time(time_s, input_v, level_v=1.0, start_s=1e-6, stop_s=1.02e-6, rising=True)
    fall_mid = crossing_time(time_s, input_v, level_v=1.0, start_s=3.02e-6, stop_s=3.04e-6, rising=False)
    sr_pos, pos_points = fitted_slew(time_s, output_v, start_s=1e-6, stop_s=2.2e-6, rising=True)
    sr_neg, neg_points = fitted_slew(time_s, output_v, start_s=3e-6, stop_s=4.2e-6, rising=False)
    rise_settle = settling_time(time_s, output_v, 1.2, rise_mid, 3.02e-6)
    fall_settle = settling_time(time_s, output_v, 0.8, fall_mid, 5e-6)
    high = [output_v[i] for i, value in enumerate(time_s) if 1.02e-6 <= value < 3.02e-6]
    low = [output_v[i] for i, value in enumerate(time_s) if 3.04e-6 <= value <= 5e-6]
    return {
        "sr_plus_v_per_us": sr_pos, "sr_minus_v_per_us": sr_neg,
        "sr_plus_fit_points": pos_points, "sr_minus_fit_points": neg_points,
        "rise_input_50_us": rise_mid*1e6, "fall_input_50_us": fall_mid*1e6,
        "rise_settling_us": rise_settle*1e6, "fall_settling_us": fall_settle*1e6,
        "worst_settling_us": max(rise_settle, fall_settle)*1e6,
        "overshoot_mv": max(0.0, max(high)-1.2)*1e3, "undershoot_mv": max(0.0, 0.8-min(low))*1e3,
    }


def icmr_margins(values: dict[str, float], vdd_v: float) -> dict[int, float]:
    return {
        1: values["nmir"]-values["tail"]-values["m1_vdsat"],
        2: values["vx"]-values["tail"]-values["m2_vdsat"],
        3: vdd_v-values["nmir"]-values["m3_vdsat"],
        4: vdd_v-values["vx"]-values["m4_vdsat"],
        5: values["tail"]-values["m5_vdsat"], 6: values["vout"]-values["m6_vdsat"],
        7: vdd_v-values["vout"]-values["m7_vdsat"], 8: vdd_v-values["vbp"]-values["m8_vdsat"],
        9: vdd_v-values["vbn"]-values["m9_vdsat"], 10: values["vbn"]-values["m10_vdsat"],
    }


def icmr_point(tag: str, vcm: float, data: dict[str, list[list[float]]], vdd_v: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    point = str(vcm).replace(".", "p")
    op, ac = data[f"{tag}_icmr_{point}_op.tsv"][-1], data[f"{tag}_icmr_{point}_ac.tsv"][-1]
    values: dict[str, float] = {"vout": op[1], "vx": op[2], "vbn": op[3], "vbp": op[4], "tail": op[5], "nmir": op[6]}
    for number in range(1, 11):
        values[f"m{number}_id"] = op[7+2*(number-1)]
        values[f"m{number}_vdsat"] = op[8+2*(number-1)]
    margins = icmr_margins(values, vdd_v)
    devices = [{
        "tag": tag, "vcm_v": vcm, "device": f"M{number}", "role": DEVICE_ROLES[number],
        "drain_current_ua": values[f"m{number}_id"]*1e6, "vdsat_abs_v": values[f"m{number}_vdsat"],
        "saturation_margin_v": margins[number], "saturation_status": "PASS" if margins[number] >= 0 else "FAIL",
    } for number in range(1, 11)]
    result: dict[str, Any] = {
        "tag": tag, "vcm_v": vcm, "gain_db": 20*math.log10(magnitude(ac)),
        "vout_v": values["vout"], "vx_v": values["vx"], "vbn_v": values["vbn"], "vbp_v": values["vbp"],
        "tail_v": values["tail"], "nmir_v": values["nmir"],
        "output_tracking_error_mv": abs(values["vout"]-vcm)*1e3,
        "minimum_saturation_margin_v": min(margins.values()),
        "all_m1_m10_saturated": all(value >= 0 for value in margins.values()),
    }
    for number in range(1, 11):
        result[f"m{number}_saturation_margin_v"] = margins[number]
    return result, devices


def gate_area_proxy(sizes: dict[str, float]) -> float:
    return (
        2*sizes["w12"]*sizes["l12"] + 4*sizes["w34"]*sizes["l34"] + sizes["w5"]*sizes["l5"]
        + sizes["w6"]*sizes["l6"] + sizes["m7_mult"]*sizes["w7"]*sizes["l7"]
        + sizes["w8"]*sizes["l8"] + sizes["w9"]*sizes["l9"] + sizes["w10"]*sizes["l10"]
    )


def retained_failure_records() -> list[dict[str, Any]]:
    definitions = (
        ("baseline_loop.log", "BENCH_SAVE_LIST_ERROR", "Added .save all before AC; corrected baseline rerun PASS"),
        ("first_stage_l2_loop.log", "BENCH_SAVE_LIST_ERROR", "Added .save all before AC; corrected candidate rerun PASS"),
        ("first_stage_l3_loop.log", "BENCH_SAVE_LIST_ERROR", "Added .save all before AC; corrected candidate rerun PASS"),
        ("m7_l2_loop.log", "MODEL_BIN_GEOMETRY_ERROR", "Used legal W=baseline, L=2x, mult=2 for equal total W/L; corrected rerun PASS"),
    )
    directory = HERE/"retained_failures"/"attempt1"
    expected, actual = ({name for name, _, _ in definitions}, {path.name for path in directory.glob("*.log")})
    if actual != expected:
        raise ValueError(f"Retained failure set mismatch; missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    return [{
        "retained_log": f"retained_failures/attempt1/{name}", "classification": classification,
        "candidate_electrical_failure": False, "resolution": resolution, "sha256": sha256_file(directory/name),
    } for name, classification, resolution in definitions]


def verify_baseline_against_compensation(baseline: dict[str, Any], authorities: dict[str, Any]) -> None:
    selected = authorities["day3_compensation_after"]
    same_number(baseline["a0_db"], selected["a0_db"], "baseline A0 versus Day 3 selected evidence", rel=1e-7, abs_=1e-6)
    same_number(baseline["ugb_mhz"]*1e6, selected["ugb_hz"], "baseline UGB versus Day 3 selected evidence", rel=1e-7, abs_=1.0)
    same_number(baseline["pm_deg"], selected["phase_margin_deg"], "baseline PM versus Day 3 selected evidence", rel=1e-7, abs_=1e-5)


def analyze() -> None:
    _, manifest_hash, _, variants, authorities = load_and_verify_written_manifest()
    actual_csv_names = {path.name for path in HERE.glob("*.csv")}
    unexpected_csv = actual_csv_names - set(CSV_OUTPUTS)
    if unexpected_csv:
        raise ValueError(f"Unexpected Day 5 CSV output(s): {sorted(unexpected_csv)}")
    required_preanalysis_csv = {"variant_manifest.csv", "generated_inventory.csv"}
    if not required_preanalysis_csv <= actual_csv_names:
        raise ValueError(f"Missing pre-analysis CSV(s): {sorted(required_preanalysis_csv-actual_csv_names)}")
    generated_rows, variant_rows = verify_generated(manifest_hash, variants, authorities)
    verify_csv_exact(HERE/"variant_manifest.csv", variant_rows, manifest_hash)
    verify_csv_exact(HERE/"generated_inventory.csv", generated_rows, manifest_hash)
    normalize_simulator_text()
    log_rows = audit_logs()
    stamp_raw_tsv(manifest_hash)
    raw_rows, data = reconcile_raw(manifest_hash)

    nominal_vdd = float(authorities["day4_manifest"]["nominal"]["vdd_minus_vss_v"])
    records: list[dict[str, Any]] = []
    icmr_rows: list[dict[str, Any]] = []
    device_rows: list[dict[str, Any]] = []
    for tag, definition in variants.items():
        sizes = definition["sizes"]
        assert isinstance(sizes, dict)
        metrics, transient = loop_metrics(tag, data, nominal_vdd), transient_metrics(tag, data)
        ad = magnitude(data[f"{tag}_differential_1k.tsv"][-1])
        as_plus = magnitude(data[f"{tag}_psrr_plus_1k.tsv"][-1])
        as_minus = magnitude(data[f"{tag}_psrr_minus_1k.tsv"][-1])
        points: list[dict[str, Any]] = []
        for vcm in VCM_POINTS:
            point, per_device = icmr_point(tag, vcm, data, nominal_vdd)
            points.append(point)
            device_rows.extend(per_device)
        nominal_gain = next(float(point["gain_db"]) for point in points if point["vcm_v"] == 0.9)
        for point in points:
            delta = float(point["gain_db"])-nominal_gain
            valid = (
                delta >= -3 and bool(point["all_m1_m10_saturated"])
                and float(point["output_tracking_error_mv"]) <= 10 and 0.05 < float(point["vout_v"]) < 1.75
            )
            point["gain_delta_vs_0p9_db"], point["checkpoint_valid"] = delta, valid
            point["checkpoint_status"] = "PASS" if valid else ";".join(
                reason for condition, reason in (
                    (delta < -3, "GAIN_FAIL"), (not bool(point["all_m1_m10_saturated"]), "SATURATION_FAIL"),
                    (float(point["output_tracking_error_mv"]) > 10, "TRACKING_FAIL"),
                    (not (0.05 < float(point["vout_v"]) < 1.75), "OUTPUT_CLIPPED"),
                ) if condition
            )
            icmr_rows.append(point)
        by_vcm = {float(point["vcm_v"]): point for point in points}
        core_hard = (
            float(metrics["a0_db"]) >= 50 and float(metrics["ugb_mhz"]) >= 5 and float(metrics["pm_deg"]) >= 55
            and float(metrics["power_uw"]) <= 600 and float(transient["sr_plus_v_per_us"]) >= 2
            and float(transient["sr_minus_v_per_us"]) >= 2 and float(transient["worst_settling_us"]) <= 1.5
            and abs(float(metrics["loop_phase_1hz_deg"])) <= 5 and int(metrics["zero_db_downward_crossings"]) == 1
            and int(metrics["zero_db_all_crossings"]) == 1 and int(metrics["zero_db_exact_samples"]) == 0
            and not bool(metrics["ugb_crossing_at_boundary"])
        )
        records.append({
            "tag": tag, "role": "BASELINE" if tag == "baseline" else "CANDIDATE",
            "description": definition["description"], "total_gate_area_proxy_um2": gate_area_proxy(sizes),
            **metrics, **transient, "ad_1k_db": 20*math.log10(ad),
            "asupply_plus_1k_v_per_v": as_plus, "asupply_minus_1k_v_per_v": as_minus,
            "psrr_plus_1k_db": 20*math.log10(ad/as_plus), "psrr_minus_1k_db": 20*math.log10(ad/as_minus),
            "icmr_0p8_valid": by_vcm[0.8]["checkpoint_valid"], "icmr_1p3_valid": by_vcm[1.3]["checkpoint_valid"],
            "icmr_1p3_gain_delta_db": by_vcm[1.3]["gain_delta_vs_0p9_db"],
            "icmr_1p3_minimum_margin_v": by_vcm[1.3]["minimum_saturation_margin_v"], "core_hard_specs_pass": core_hard,
        })

    baseline = records[0]
    verify_baseline_against_compensation(baseline, authorities)
    for record in records:
        record["delta_psrr_plus_db"] = float(record["psrr_plus_1k_db"])-float(baseline["psrr_plus_1k_db"])
        record["delta_psrr_minus_db"] = float(record["psrr_minus_1k_db"])-float(baseline["psrr_minus_1k_db"])
        record["delta_a0_db"] = float(record["a0_db"])-float(baseline["a0_db"])
        record["delta_pm_deg"] = float(record["pm_deg"])-float(baseline["pm_deg"])
        record["delta_icmr_1p3_gain_db"] = float(record["icmr_1p3_gain_delta_db"])-float(baseline["icmr_1p3_gain_delta_db"])
        record["total_gate_area_factor_vs_baseline"] = float(record["total_gate_area_proxy_um2"])/float(baseline["total_gate_area_proxy_um2"])
        record["changed_device_area_factor"] = {"baseline": 1.0, "first_stage_l2": 4.0, "first_stage_l3": 9.0, "m7_l2": 4.0}[str(record["tag"])]
        if record["tag"] == "baseline":
            record["disposition"] = "PRODUCTION_BASELINE_RETAINED"
        elif not bool(record["core_hard_specs_pass"]):
            record["disposition"] = "REJECT_CORE_HARD_REGRESSION"
        elif float(record["psrr_plus_1k_db"]) < 45 or float(record["psrr_minus_1k_db"]) < 45:
            record["disposition"] = "REJECT_PSRR_HARD_FAIL"
        else:
            record["disposition"] = "REJECTED_TRADEOFF_NOT_PRODUCTION_SELECTED"
        record["bounded_nominal_rank"] = "NOT_BEST"
    eligible = [r for r in records[1:] if bool(r["core_hard_specs_pass"]) and float(r["psrr_plus_1k_db"]) >= 45 and float(r["psrr_minus_1k_db"]) >= 45]
    best = max(eligible, key=lambda r: min(float(r["psrr_plus_1k_db"]), float(r["psrr_minus_1k_db"]))) if eligible else None
    if best is not None:
        best["bounded_nominal_rank"] = "BEST_NOMINAL_PSRR_CANDIDATE"

    retained_rows = retained_failure_records()
    decision_reason = (
        f"{best['tag']} improves nominal PSRR but changes PM by {float(best['delta_pm_deg']):.3f} deg, "
        f"changes the 1.3-V gain delta by {float(best['delta_icmr_1p3_gain_db']):.3f} dB, and changes total gate-area proxy by "
        f"{float(best['total_gate_area_factor_vs_baseline']):.3f}x without full Day 4 revalidation"
        if best is not None else "No candidate clears both nominal PSRR hard limits while retaining every core hard limit"
    )
    revalidation = (
        "13-point PVT gain/UGB/PM/power/SR and M1-M10 operating points;strict nominal P01 1%-settling plus "
        "Day4-defined transient status at every other PVT point;121-point continuous ICMR;"
        "bidirectional output swing;CMRR and PSRR frequency curves;input noise;CL=1/2/5-pF loop and transient stability;"
        "complete log/raw/manifest audit"
    )
    decision_rows = [{
        "production_decision": "KEEP_FROZEN_DAY4_BASELINE", "adopted_optimization": "DAY3_ADD_RZ_2K_WITH_CC_3P",
        "adopted_before": authorities["day3_compensation_before"]["tag"], "adopted_after": authorities["day3_compensation_after"]["tag"],
        "adopted_pm_improvement_deg": float(authorities["day3_compensation_after"]["phase_margin_improvement_vs_cc_only_deg"]),
        "day5_best_nominal_candidate": best["tag"] if best is not None else "NONE",
        "day5_candidate_disposition": "REJECTED_TRADEOFF_NOT_PRODUCTION_SELECTED" if best is not None else "NO_ELIGIBLE_CANDIDATE",
        "reason": decision_reason, "full_day4_revalidation_required_before_promotion": True,
        "full_day4_revalidation_scope": revalidation, "corrected_logs_passed": sum(r["status"] == "PASS" for r in log_rows),
        "corrected_logs_total": len(log_rows), "raw_tsv_passed": sum(r["status"] == "PASS" for r in raw_rows),
        "raw_tsv_total": len(raw_rows), "retained_initial_failures": len(retained_rows),
    }]

    write_csv(HERE/"raw_inventory.csv", raw_rows, manifest_hash)
    write_csv(HERE/"recon_summary.csv", records, manifest_hash)
    write_csv(HERE/"icmr_checkpoints.csv", icmr_rows, manifest_hash)
    write_csv(HERE/"icmr_device_margins.csv", device_rows, manifest_hash)
    write_csv(HERE/"log_audit.csv", log_rows, manifest_hash)
    write_csv(HERE/"retained_failure_audit.csv", retained_rows, manifest_hash)
    write_csv(HERE/"decision_summary.csv", decision_rows, manifest_hash)

    nominal = authorities["day4_manifest"]["nominal"]
    report = [
        "# Day 5 isolated optimization reconnaissance", "",
        f"Manifest: `{manifest_hash}`. The baseline is bound to Day 3 selected parameters, Day 3 compensation evidence, and Day 4 manifest `{authorities['day4_manifest_internal_sha256']}`.", "",
        f"All values are SKY130A {str(nominal['corner']).upper()}, {float(nominal['vdd_minus_vss_v']):g} V, "
        f"{float(nominal['temperature_c']):g} C, VCM={float(nominal['vcm_v']):g} V, "
        f"{float(nominal['load_capacitance_f'])*1e12:g} pF || {float(nominal['load_resistance_ohm'])/1e3:g} kohm to "
        f"{nominal['load_return']} unless noted. PSRR is 20log10(|Ad/Asupply|) at 1 kHz; ICMR checkpoint gain is "
        "the Day 4-equivalent 1-Hz value. The three ICMR values are checkpoints, not a continuous-range claim.", "",
        "| Variant | A0 dB | UGB MHz | PM deg | Pq uW | SR+/- V/us | 1% settle us | PSRR+/- dB | ICMR 0.8/1.3 | Disposition |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for record in records:
        report.append(
            f"| {record['tag']} | {float(record['a0_db']):.3f} | {float(record['ugb_mhz']):.3f} | {float(record['pm_deg']):.3f} | "
            f"{float(record['power_uw']):.3f} | {float(record['sr_plus_v_per_us']):.3f}/{float(record['sr_minus_v_per_us']):.3f} | "
            f"{float(record['worst_settling_us']):.4f} | {float(record['psrr_plus_1k_db']):.3f}/{float(record['psrr_minus_1k_db']):.3f} | "
            f"{record['icmr_0p8_valid']}/{record['icmr_1p3_valid']} | {record['disposition']} |"
        )
    report += ["", "## Decision", ""]
    if best is None:
        report.append("No candidate clears both nominal PSRR hard limits while preserving all core hard limits. The frozen Day 4 baseline remains the production design.")
    else:
        report.append(f"`{best['tag']}` is the strongest nominal PSRR candidate, but it is not selected: {decision_reason}. The frozen Day 4 baseline remains the production design.")
    report.append(
        f"The adopted optimization remains the Day 3 change from `{authorities['day3_compensation_before']['tag']}` to "
        f"`{authorities['day3_compensation_after']['tag']}`, which improved PM by "
        f"{float(authorities['day3_compensation_after']['phase_margin_improvement_vs_cc_only_deg']):.3f} degrees."
    )
    report += [
        "", "## Promotion gate", "",
        "Any candidate promotion requires a complete Day 4 rerun: all 13 PVT points with gain/UGB/PM/power/SR and M1-M10 operating points; strict nominal P01 1% settling plus Day4-defined transient status at every other PVT point; the full 121-point continuous ICMR; bidirectional output swing; CMRR/PSRR frequency curves; input noise; CL=1/2/5 pF loop and transient stability; and the complete log/raw/manifest integrity audit.",
        "", "## Audit scope", "",
        f"- Corrected simulations: {sum(r['status']=='PASS' for r in log_rows)}/{len(log_rows)} logs PASS with matching exit records.",
        f"- Raw evidence: {sum(r['status']=='PASS' for r in raw_rows)}/{len(raw_rows)} TSV files pass exact set, row, column, finite, stamp, and grid checks.",
        f"- ICMR: {len(device_rows)} device rows cover M1-M10 at all {len(VCM_POINTS)} checkpoints for all {len(VARIANT_TAGS)} variants.",
        f"- Retained initial failures: {len(retained_rows)} classified logs remain under `retained_failures/attempt1`.",
        "- Every loop has exactly one downward 0-dB crossing, no extra crossing, and no boundary crossing.",
        "- Slew and 1% settling use the strict Day 4 definitions.",
        "- Schematic-level only; no mismatch, Monte Carlo, layout, or extracted parasitics.",
    ]
    report_text = "\n".join(report)+"\n"
    (HERE/"assessment.md").write_text(report_text, encoding="utf-8")
    written_report = (HERE/"assessment.md").read_text(encoding="utf-8", errors="strict")
    if written_report != report_text or written_report.count(manifest_hash) != 1:
        raise ValueError("assessment.md content or unique manifest stamp verification failed")

    expected_csv_rows = {
        "variant_manifest.csv": 4, "generated_inventory.csv": 36, "raw_inventory.csv": 48,
        "recon_summary.csv": 4, "icmr_checkpoints.csv": 12, "icmr_device_margins.csv": 120,
        "log_audit.csv": 32, "retained_failure_audit.csv": 4, "decision_summary.csv": 1,
    }
    expected_csv_records = {
        "variant_manifest.csv": variant_rows, "generated_inventory.csv": generated_rows,
        "raw_inventory.csv": raw_rows, "recon_summary.csv": records,
        "icmr_checkpoints.csv": icmr_rows, "icmr_device_margins.csv": device_rows,
        "log_audit.csv": log_rows, "retained_failure_audit.csv": retained_rows,
        "decision_summary.csv": decision_rows,
    }
    actual_csv_names = {path.name for path in HERE.glob("*.csv")}
    if actual_csv_names != set(expected_csv_rows):
        raise ValueError(
            f"Final CSV set mismatch; missing={sorted(set(expected_csv_rows)-actual_csv_names)}, "
            f"extra={sorted(actual_csv_names-set(expected_csv_rows))}"
        )
    for filename, count in expected_csv_rows.items():
        verify_csv_exact(HERE/filename, expected_csv_records[filename], manifest_hash)
        verify_csv_stamp(HERE/filename, manifest_hash, count)
    success = {
        "schema": "sky130-two-stage-ota/day5-last-success/v1", "manifest_sha256": manifest_hash,
        "logs_passed": 32, "logs_total": 32, "raw_tsv_passed": 48, "raw_tsv_total": 48,
        "csv_outputs_verified": len(expected_csv_rows), "production_decision": "KEEP_FROZEN_DAY4_BASELINE",
        "assessment_sha256": sha256_text(report_text),
        "csv_sha256": {filename: sha256_file(HERE/filename) for filename in sorted(expected_csv_rows)},
    }
    (HERE/"last_success.json").write_text(
        json.dumps(success, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8",
    )
    print(f"DAY5_RECON_ANALYZED manifest={manifest_hash} logs=32/32 raw=48/48 csv=9/9 best={best['tag'] if best else 'NONE'}")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"generate", "analyze"}:
        raise SystemExit("usage: recon.py generate|analyze")
    generate() if sys.argv[1] == "generate" else analyze()


if __name__ == "__main__":
    main()
