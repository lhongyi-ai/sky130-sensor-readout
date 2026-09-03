#!/usr/bin/env python3
"""Compare the Xschem-generated core netlist with the canonical OTA subcircuit."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "netlists" / "ota" / "two_stage_ota_core.spice"
XSCHEM = ROOT / "results" / "smoke" / "xschem" / "final_ota" / "two_stage_ota.spice"
OUTDIR = ROOT / "results" / "smoke" / "xschem" / "final_ota"
EXPECTED = {
    "XM1",
    "XM2",
    "XM3A",
    "XM3B",
    "XM4A",
    "XM4B",
    "XM5",
    "XM6",
    "XM7",
    "XM8",
    "XM9",
    "XM10",
    "RZ1",
    "CC1",
}
EXTERNAL_ONLY = {"RLOAD", "CLOAD", "LBREAK", "CBREAK"}


def logical_lines(path: Path) -> list[str]:
    lines: list[str] = []
    current = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("+"):
            current += " " + stripped[1:].strip()
            continue
        if current:
            lines.append(current)
        current = stripped
    if current:
        lines.append(current)
    return lines


def normalize(path: Path) -> tuple[tuple[str, ...], dict[str, dict[str, object]]]:
    pins: tuple[str, ...] | None = None
    devices: dict[str, dict[str, object]] = {}
    for line in logical_lines(path):
        subckt = re.match(r"^(?:\*\*)?\.subckt\s+\S+\s+(.+)$", line, flags=re.IGNORECASE)
        if subckt:
            pins = tuple(token.upper() for token in subckt.group(1).split())
            continue
        tokens = line.split()
        if not tokens:
            continue
        name = tokens[0].upper()
        if name.startswith("XM") and len(tokens) >= 6:
            params = {}
            for token in tokens[6:]:
                if "=" in token:
                    key, value = token.split("=", 1)
                    if key.lower() in {"l", "w", "nf", "mult"}:
                        params[key.lower()] = value.lower()
            devices[name] = {
                "pins": tuple(token.upper() for token in tokens[1:5]),
                "model": tokens[5].lower(),
                "value": params,
            }
        elif name in {"RZ1", "CC1"} and len(tokens) >= 4:
            devices[name] = {
                "pins": tuple(token.upper() for token in tokens[1:3]),
                "model": "resistor" if name.startswith("R") else "capacitor",
                "value": tokens[3].lower(),
            }
    if pins is None:
        raise ValueError(f"No .subckt declaration found in {path}")
    return pins, devices


def main() -> None:
    canonical_pins, canonical = normalize(CANONICAL)
    xschem_pins, xschem = normalize(XSCHEM)
    rows: list[dict[str, str]] = []
    all_names = sorted(set(canonical) | set(xschem))
    for name in all_names:
        left = canonical.get(name)
        right = xschem.get(name)
        status = "PASS" if left == right else "FAIL"
        rows.append(
            {
                "component": name,
                "canonical_pins": " ".join(left["pins"]) if left else "MISSING",
                "xschem_pins": " ".join(right["pins"]) if right else "MISSING",
                "canonical_model_or_value": json.dumps(
                    {"model": left["model"], "value": left["value"]} if left else None,
                    sort_keys=True,
                ),
                "xschem_model_or_value": json.dumps(
                    {"model": right["model"], "value": right["value"]} if right else None,
                    sort_keys=True,
                ),
                "status": status,
            }
        )

    OUTDIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTDIR / "connectivity_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    actual = set(canonical)
    testbench_intrusions = sorted((actual | set(xschem)) & EXTERNAL_ONLY)
    status = (
        "PASS"
        if canonical_pins == xschem_pins == ("VINP", "VINN", "VOUT", "VDD", "VSS", "IREF")
        and actual == set(xschem) == EXPECTED
        and all(row["status"] == "PASS" for row in rows)
        and not testbench_intrusions
        else "FAIL"
    )
    summary = {
        "status": status,
        "canonical_source": str(CANONICAL.relative_to(ROOT)),
        "xschem_source": "schematics/two_stage_ota.sch",
        "xschem_generated_netlist": str(XSCHEM.relative_to(ROOT)),
        "canonical_pin_order": canonical_pins,
        "xschem_pin_order": xschem_pins,
        "matched_component_count": sum(row["status"] == "PASS" for row in rows),
        "expected_component_count": len(EXPECTED),
        "external_testbench_elements_inside_core": testbench_intrusions,
        "comparison_scope": "connectivity, device model, W/L/nf/mult, RZ, and CC; Xschem-generated diffusion geometry is intentionally ignored",
    }
    json_path = OUTDIR / "connectivity_check.json"
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
