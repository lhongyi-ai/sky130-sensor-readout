#!/usr/bin/env python3
"""Render Day 3 balance, loop-gain, and transient SKY130A simulation decks."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "netlists" / "day3"
GENERATED = ROOT / "results" / "generated" / "day3"
RAW = ROOT / "results" / "raw" / "day3"

MODEL_CANDIDATES = (
    "/foss/pdks/sky130A/libs.tech/ngspice/sky130.lib.spice",
    "/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice",
    "/usr/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice",
    "/usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice",
)

VARIANTS = (
    {"tag": "cc1p_rz0", "cc_f": 1e-12, "rz_ohm": 1e-3},
    {"tag": "cc2p_rz0", "cc_f": 2e-12, "rz_ohm": 1e-3},
    {"tag": "cc3p_rz0", "cc_f": 3e-12, "rz_ohm": 1e-3},
    {"tag": "cc4p_rz0", "cc_f": 4e-12, "rz_ohm": 1e-3},
    {"tag": "cc2p_rz500", "cc_f": 2e-12, "rz_ohm": 500.0},
    {"tag": "cc2p_rz1k", "cc_f": 2e-12, "rz_ohm": 1000.0},
    {"tag": "cc2p_rz2k", "cc_f": 2e-12, "rz_ohm": 2000.0},
    {"tag": "cc2p_rz3k", "cc_f": 2e-12, "rz_ohm": 3000.0},
    {"tag": "cc3p_rz500", "cc_f": 3e-12, "rz_ohm": 500.0},
    {"tag": "cc3p_rz1k", "cc_f": 3e-12, "rz_ohm": 1000.0},
    {"tag": "cc3p_rz2k", "cc_f": 3e-12, "rz_ohm": 2000.0},
    {"tag": "cc3p_rz2p5k", "cc_f": 3e-12, "rz_ohm": 2500.0},
    {"tag": "cc3p_rz3k", "cc_f": 3e-12, "rz_ohm": 3000.0},
    {"tag": "cc3p_rz4k", "cc_f": 3e-12, "rz_ohm": 4000.0},
    {"tag": "cc4p_rz1k", "cc_f": 4e-12, "rz_ohm": 1000.0},
    {"tag": "cc4p_rz2k", "cc_f": 4e-12, "rz_ohm": 2000.0},
    {"tag": "cc4p_rz3k", "cc_f": 4e-12, "rz_ohm": 3000.0},
)
SELECTED_TAG = "cc3p_rz2k"


def model_deck() -> Path:
    configured = os.environ.get("SKY130_MODEL_DECK")
    candidates = ([configured] if configured else []) + list(MODEL_CANDIDATES)
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise FileNotFoundError("SKY130A model deck was not found")


def render(template_name: str, output_name: str, replacements: dict[str, str]) -> Path:
    text = (TEMPLATES / template_name).read_text(encoding="utf-8")
    common = {"@@MODEL_DECK@@": str(model_deck()), "@@CORNER@@": "tt"}
    for token, value in (common | replacements).items():
        text = text.replace(token, value)
    unresolved = sorted(set(re.findall(r"@@[A-Z0-9_]+@@", text)))
    if unresolved:
        raise ValueError(f"Unresolved placeholders: {unresolved}")
    GENERATED.mkdir(parents=True, exist_ok=True)
    output = GENERATED / output_name
    output.write_text(text, encoding="utf-8")
    print(f"Rendered {output}")
    return output


def numeric_rows(path: Path, expected_columns: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        tokens = line.split()
        if len(tokens) != expected_columns:
            continue
        try:
            rows.append([float(token) for token in tokens])
        except ValueError:
            continue
    return rows


def select_w6() -> tuple[float, list[dict[str, float]]]:
    rows = numeric_rows(RAW / "second_stage_balance.tsv", 6)
    if not rows:
        raise ValueError("No M6 balance data were found")
    records = [
        {
            "w6_um": row[1],
            "m6_current_ua": row[2] * 1e6,
            "m7_current_ua": row[3] * 1e6,
            "rl_current_ua": row[4] * 1e6,
            "residual_ua": row[5] * 1e6,
        }
        for row in rows
    ]
    records.sort(key=lambda record: record["w6_um"])
    selected = min(records, key=lambda record: abs(record["residual_ua"]))["w6_um"]
    for left, right in zip(records, records[1:]):
        y0, y1 = left["residual_ua"], right["residual_ua"]
        if y0 == 0 or y0 * y1 <= 0:
            if y1 == y0:
                selected = left["w6_um"]
            else:
                selected = left["w6_um"] - y0 * (right["w6_um"] - left["w6_um"]) / (y1 - y0)
            break
    if not math.isfinite(selected):
        raise ValueError("Interpolated M6 width is not finite")
    with (ROOT / "results" / "day3_m6_balance.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(*records[0].keys(), "selected_interpolated_w6_um"),
            lineterminator="\n",
        )
        writer.writeheader()
        for index, record in enumerate(records):
            writer.writerow(record | {"selected_interpolated_w6_um": selected if index == 0 else ""})
    return selected, records


def selected_parameters(w6_um: float) -> dict[str, object]:
    selected = next(item for item in VARIANTS if item["tag"] == SELECTED_TAG)
    parameters = {
        "corner": "tt",
        "temperature_c": 27,
        "vdd_v": 1.8,
        "vcm_v": 0.9,
        "cload_f": 5e-12,
        "rload_ohm": 100000.0,
        "w6_um": w6_um,
        "selected_tag": SELECTED_TAG,
        "cc_f": selected["cc_f"],
        "rz_ohm": selected["rz_ohm"],
        "device_sizes_um": {
            "M1": {"w": 16.83798, "l": 0.5},
            "M2": {"w": 16.83798, "l": 0.5},
            "M3": {"w_total": 50.0, "unit_w": 25.0, "units": 2, "l": 0.5},
            "M4": {"w_total": 50.0, "unit_w": 25.0, "units": 2, "l": 0.5},
            "M5": {"w": 25.8754, "l": 0.8},
            "M6": {"w": w6_um, "l": 0.5},
            "M7": {"w": 72.2005, "l": 0.8},
            "M8": {"w": 7.22005, "l": 0.8},
            "M9": {"w": 7.22005, "l": 0.8},
            "M10": {"w": 8.08605, "l": 0.8},
        },
        "variants": VARIANTS,
    }
    (GENERATED / "selected_parameters.json").write_text(json.dumps(parameters, indent=2), encoding="utf-8")
    return parameters


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("balance", "loopgain", "transient"))
    args = parser.parse_args()
    if args.phase == "balance":
        render("second_stage_balance.spice.in", "second_stage_balance.spice", {})
        return

    w6_um, _ = select_w6()
    parameters = selected_parameters(w6_um)
    if args.phase == "loopgain":
        for variant in VARIANTS:
            render(
                "ota_loopgain.spice.in",
                f"{variant['tag']}.spice",
                {
                    "@@W6_UM@@": f"{w6_um:.9g}",
                    "@@CC_F@@": f"{variant['cc_f']:.9g}",
                    "@@RZ_OHM@@": f"{variant['rz_ohm']:.9g}",
                    "@@TAG@@": str(variant["tag"]),
                },
            )
    else:
        render(
            "ota_transient.spice.in",
            "nominal_transient.spice",
            {
                "@@W6_UM@@": f"{w6_um:.9g}",
                "@@CC_F@@": f"{float(parameters['cc_f']):.9g}",
                "@@RZ_OHM@@": f"{float(parameters['rz_ohm']):.9g}",
            },
        )


if __name__ == "__main__":
    main()
