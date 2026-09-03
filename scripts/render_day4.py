#!/usr/bin/env python3
"""Validate the Day 3 handoff and render all immutable Day 4 decks."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "netlists" / "day4"
GENERATED = ROOT / "results" / "generated" / "day4"
RAW = ROOT / "results" / "raw" / "day4"
DAY3 = ROOT / "results" / "generated" / "day3"
PDK_REVISION = "026824c7969ce6f4fc9678e6ca04b0a06a596c4b"
PDK_LIB = Path(
    "/foss/pdks/ciel/sky130/versions/"
    + PDK_REVISION
    + "/sky130A/libs.tech/ngspice/sky130.lib.spice"
)

PVT_POINTS = (
    ("P01", "tt", 1.80, 27, "Nominal"),
    ("P02", "ff", 1.80, 27, "Process sweep"),
    ("P03", "ss", 1.80, 27, "Process sweep"),
    ("P04", "fs", 1.80, 27, "Process sweep"),
    ("P05", "sf", 1.80, 27, "Process sweep"),
    ("P06", "tt", 1.62, -20, "Voltage-temperature sweep"),
    ("P07", "tt", 1.62, 27, "Voltage-temperature sweep"),
    ("P08", "tt", 1.62, 85, "Voltage-temperature sweep"),
    ("P09", "tt", 1.80, -20, "Voltage-temperature sweep"),
    ("P10", "tt", 1.80, 85, "Voltage-temperature sweep"),
    ("P11", "tt", 1.98, -20, "Voltage-temperature sweep"),
    ("P12", "tt", 1.98, 27, "Voltage-temperature sweep"),
    ("P13", "tt", 1.98, 85, "Voltage-temperature sweep"),
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_param(deck: str, name: str) -> float:
    match = re.search(rf"(?:^|\s){re.escape(name)}=([0-9.eE+-]+)", deck, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Day 3 deck is missing parameter {name}")
    return float(match.group(1))


def read_summary() -> dict[str, str]:
    path = ROOT / "results" / "day3_nominal_summary.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["metric"]: row["value"] for row in csv.DictReader(handle)}


def validate_day3() -> dict[str, object]:
    """Reject rendering if any of the four Day 3 authorities disagree."""
    selected_path = DAY3 / "selected_parameters.json"
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    comparison_path = ROOT / "results" / "day3_compensation_comparison.csv"
    with comparison_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    chosen = [row for row in rows if row["selection_role"] == "SELECTED"]
    if len(chosen) != 1:
        raise ValueError(f"Day 3 comparison must have exactly one SELECTED row, found {len(chosen)}")
    row = chosen[0]
    if row["tag"] != selected["selected_tag"]:
        raise ValueError("Day 3 selected tag disagrees with comparison table")
    checks = (
        (float(row["cc_pf"]), float(selected["cc_f"]) * 1e12, "CC"),
        (float(row["rz_ohm"]), float(selected["rz_ohm"]), "RZ"),
    )
    for actual, expected, label in checks:
        if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(f"Day 3 {label} mismatch: {actual} versus {expected}")

    summary = read_summary()
    summary_checks = (
        ("w6_um", float(selected["w6_um"])),
        ("cc_pf", float(selected["cc_f"]) * 1e12),
        ("rz_ohm", float(selected["rz_ohm"])),
    )
    for key, expected in summary_checks:
        if not math.isclose(float(summary[key]), expected, rel_tol=1e-8, abs_tol=1e-10):
            raise ValueError(f"Day 3 summary {key} disagrees with selected_parameters.json")

    loop_deck = (DAY3 / f"{selected['selected_tag']}.spice").read_text(encoding="utf-8")
    tran_deck = (DAY3 / "nominal_transient.spice").read_text(encoding="utf-8")
    deck_checks = {
        "W12": float(selected["device_sizes_um"]["M1"]["w"]),
        "W34UNIT": float(selected["device_sizes_um"]["M3"]["unit_w"]),
        "W5": float(selected["device_sizes_um"]["M5"]["w"]),
        "W6": float(selected["device_sizes_um"]["M6"]["w"]),
        "W7": float(selected["device_sizes_um"]["M7"]["w"]),
        "W8": float(selected["device_sizes_um"]["M8"]["w"]),
        "W9": float(selected["device_sizes_um"]["M9"]["w"]),
        "W10": float(selected["device_sizes_um"]["M10"]["w"]),
        "CC": float(selected["cc_f"]),
        "RZ": float(selected["rz_ohm"]),
    }
    for name, expected in deck_checks.items():
        for label, deck in (("selected loop", loop_deck), ("selected transient", tran_deck)):
            actual = parse_param(deck, name)
            if not math.isclose(actual, expected, rel_tol=2e-8, abs_tol=1e-12):
                raise ValueError(f"Day 3 {label} {name}={actual} disagrees with manifest {expected}")
    if "LBREAK vout vinn 1G" not in loop_deck or "CBREAK vtest vinn 1G" not in loop_deck:
        raise ValueError("Day 3 selected loop deck no longer contains the validated 1-GH/1-GF break")
    if "XM1 nmir vout tail 0" not in tran_deck:
        raise ValueError("Day 3 selected transient deck is not a direct unity follower")
    return selected


def render_template(name: str, replacements: dict[str, str]) -> str:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    for old, new in replacements.items():
        text = text.replace(old, new)
    leftovers = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", text)))
    if leftovers:
        raise ValueError(f"Unresolved placeholders in {name}: {leftovers}")
    return text


def write_deck(relative: str, text: str, manifest_hash: str) -> None:
    if f"DAY4_MANIFEST_SHA256={manifest_hash}" not in text:
        raise ValueError(f"Rendered deck {relative} is missing the manifest hash")
    path = GENERATED / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def subckt_replacements(selected: dict[str, object], manifest_hash: str) -> dict[str, str]:
    sizes = selected["device_sizes_um"]
    values = {"@@MANIFEST_SHA256@@": manifest_hash}
    for number in (1, 2, 5, 6, 7, 8, 9, 10):
        # The SKY130 ngspice wrappers use option scale=1e-6, so their W/L
        # parameters are expressed as bare micrometre values (as in Day 3).
        values[f"@@W{number}@@"] = f"{float(sizes[f'M{number}']['w']):.12g}"
        values[f"@@L{number}@@"] = f"{float(sizes[f'M{number}']['l']):.12g}"
    for number in (3, 4):
        values[f"@@W{number}UNIT@@"] = f"{float(sizes[f'M{number}']['unit_w']):.12g}"
        values[f"@@L{number}@@"] = f"{float(sizes[f'M{number}']['l']):.12g}"
    values["@@CC_F@@"] = f"{float(selected['cc_f']):.12g}"
    values["@@RZ_OHM@@"] = f"{float(selected['rz_ohm']):.12g}"
    return values


def build_manifest(selected: dict[str, object]) -> tuple[dict[str, object], str]:
    if not PDK_LIB.is_file():
        raise FileNotFoundError(f"Pinned PDK library is unavailable: {PDK_LIB}")
    payload: dict[str, object] = {
        "schema": "sky130-two-stage-ota/day4-manifest/v1",
        "source_of_design_truth": "results/generated/day3/selected_parameters.json",
        "source_sha256": sha256_bytes((DAY3 / "selected_parameters.json").read_bytes()),
        "pdk": {
            "name": "SKY130A",
            "revision": PDK_REVISION,
            "library_path": str(PDK_LIB),
            "library_sha256": sha256_bytes(PDK_LIB.read_bytes()),
        },
        "dut": {
            "device_sizes_um": selected["device_sizes_um"],
            "miller_capacitance_f": float(selected["cc_f"]),
            "nulling_resistance_ohm": float(selected["rz_ohm"]),
            "external_ideal_iref_a": 10e-6,
        },
        "nominal": {
            "corner": "tt",
            "vdd_minus_vss_v": 1.8,
            "temperature_c": 27,
            "vcm_v": 0.9,
            "load_capacitance_f": 5e-12,
            "load_resistance_ohm": 100000.0,
            "load_return": "VSS",
        },
        "loop_break": {"dc_inductance_h": 1e9, "ac_coupling_capacitance_f": 1e9},
        "pvt_points": [
            {"point_id": p, "process": c, "vdd_v": v, "temp_c": t} for p, c, v, t, _ in PVT_POINTS
        ],
        "limitations": [
            "schematic-level simulation only",
            "external ideal 10-uA IREF; reference-generator variation is not modeled",
            "no mismatch or Monte Carlo simulation",
            "no extracted parasitics or layout",
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    manifest_hash = sha256_bytes(canonical)
    manifest = {**payload, "manifest_sha256": manifest_hash, "hash_definition": "SHA-256 of canonical JSON payload excluding manifest_sha256 and hash_definition"}
    return manifest, manifest_hash


def main() -> None:
    selected = validate_day3()
    manifest, manifest_hash = build_manifest(selected)
    GENERATED.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    (GENERATED / "day4_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    common = {"@@MANIFEST_SHA256@@": manifest_hash, "@@PDK_LIB_PATH@@": str(PDK_LIB)}
    subckt = render_template("ota_subckt.spice.in", subckt_replacements(selected, manifest_hash))
    write_deck("ota_subckt.spice", subckt, manifest_hash)

    for point_id, corner, vdd, temp, _ in PVT_POINTS:
        raw_prefix = f"results/raw/day4/pvt/{point_id}"
        base = {
            **common,
            "@@CORNER@@": corner,
            "@@VDD_V@@": f"{vdd:.2f}",
            "@@TEMP_C@@": str(temp),
            "@@CLOAD_PF@@": "5",
            "@@RAW_PREFIX@@": raw_prefix,
        }
        for template, suffix in (
            ("pvt_diff_ac.spice.in", "diff_ac"),
            ("pvt_loop.spice.in", "loop"),
            ("pvt_transient.spice.in", "transient"),
        ):
            write_deck(f"pvt/{point_id}_{suffix}.spice", render_template(template, base), manifest_hash)

    transfer_modes = {
        "common_mode": {
            "@@MODE@@": "COMMON_MODE_GAIN",
            "@@SUPPLY_SOURCES@@": "VSSSUP VSS 0 0\nVDD VDD VSS DC 1.8 AC 0",
            "@@INPUT_SOURCES@@": "VINP VINP VSS DC 0.9 AC 1\nVINN VINN VSS DC 0.9 AC 1",
            "@@RESPONSE_EXPR@@": "v(VOUT)/v(VINP)",
            "@@STIMULUS_EXPR@@": "v(VINP)",
        },
        "psrr_plus": {
            "@@MODE@@": "POSITIVE_SUPPLY_GAIN",
            "@@SUPPLY_SOURCES@@": "VSSSUP VSS 0 DC 0 AC 0\nVDD VDD VSS DC 1.8 AC 1",
            "@@INPUT_SOURCES@@": "VINP VINP VSS DC 0.9 AC 0\nVINN VINN VSS DC 0.9 AC 0",
            "@@RESPONSE_EXPR@@": "v(VOUT)/v(VDD,VSS)",
            "@@STIMULUS_EXPR@@": "v(VDD,VSS)",
        },
        "psrr_minus": {
            "@@MODE@@": "NEGATIVE_SUPPLY_GAIN",
            "@@SUPPLY_SOURCES@@": "VSSSUP VSS 0 DC 0 AC 1\nVDD VDD 0 DC 1.8 AC 0",
            "@@INPUT_SOURCES@@": "VINP VINP 0 DC 0.9 AC 0\nVINN VINN 0 DC 0.9 AC 0",
            "@@RESPONSE_EXPR@@": "v(VOUT)/v(VSS)",
            "@@STIMULUS_EXPR@@": "v(VSS)",
        },
    }
    for tag, values in transfer_modes.items():
        replacements = {**common, **values, "@@RAW_PREFIX@@": f"results/raw/day4/nominal/{tag}"}
        write_deck(f"nominal/{tag}.spice", render_template("nominal_transfer.spice.in", replacements), manifest_hash)

    for index in range(121):
        vcm = 0.40 + 0.01 * index
        tag = f"vcm_{vcm:.2f}".replace(".", "p")
        replacements = {
            **common,
            "@@VCM_V@@": f"{vcm:.2f}",
            "@@RAW_PREFIX@@": f"results/raw/day4/icmr/{tag}",
        }
        write_deck(f"icmr/{tag}.spice", render_template("icmr_point.spice.in", replacements), manifest_hash)

    write_deck("nominal/output_swing.spice", render_template("output_swing.spice.in", common), manifest_hash)
    write_deck("nominal/noise.spice", render_template("noise.spice.in", common), manifest_hash)

    for cl_pf in (1, 2, 5):
        raw_prefix = f"results/raw/day4/load/cl{cl_pf}p"
        replacements = {
            **common,
            "@@CORNER@@": "tt",
            "@@VDD_V@@": "1.80",
            "@@TEMP_C@@": "27",
            "@@CLOAD_PF@@": str(cl_pf),
            "@@RAW_PREFIX@@": raw_prefix,
        }
        write_deck(f"load/cl{cl_pf}p_loop.spice", render_template("pvt_loop.spice.in", replacements), manifest_hash)
        write_deck(f"load/cl{cl_pf}p_transient.spice", render_template("pvt_transient.spice.in", replacements), manifest_hash)

    decks = sorted(GENERATED.rglob("*.spice"))
    missing = [str(path) for path in decks if f"DAY4_MANIFEST_SHA256={manifest_hash}" not in path.read_text(encoding="utf-8")]
    if missing:
        raise ValueError(f"Manifest hash missing from generated decks: {missing}")
    print(f"DAY4_RENDER_OK manifest={manifest_hash} decks={len(decks)}")


if __name__ == "__main__":
    main()
