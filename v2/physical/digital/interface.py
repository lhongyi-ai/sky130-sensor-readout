#!/usr/bin/env python3
"""Extract analog receiver requirements from actual routed controller libs."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
rows = []
for path in sorted((HERE / "artifacts/lib").rglob("*.lib")):
    text = path.read_text()
    if "capacitive_load_unit (1,pF)" not in text or not re.search(r'time_unit\s*:\s*"1ns"', text):
        raise ValueError("Review units before extracting interface bounds")
    section = text.split('pin("comparator_bit")')[1].split('pin("comparator_evaluate")')[0]
    capacitance = float(re.search(r"capacitance : ([0-9.]+)", section)[1])*1000
    constraints = [float(s) for s in re.findall(r'values\("([-0-9.]+)"\)', section)]
    if len(constraints) != 4 or "hold_rising" not in section or "setup_rising" not in section:
        raise ValueError("Unexpected interface timing structure")
    rows.append({"corner": path.parent.name, "comparator_bit_capacitance_ff": capacitance,
        "hold_rising_rise_ns": constraints[0], "hold_rising_fall_ns": constraints[1],
        "setup_rising_rise_ns": constraints[2], "setup_rising_fall_ns": constraints[3],
        "liberty_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
if len(rows) != 9:
    raise ValueError("Expected the nine routed Liberty/RC corners")
report = {"evidence_level": "routed_digital_macro_liberty_interface",
    "max_comparator_bit_capacitance_ff": max(r["comparator_bit_capacitance_ff"] for r in rows),
    "max_setup_ns": max(max(r["setup_rising_rise_ns"], r["setup_rising_fall_ns"]) for r in rows),
    "max_hold_ns": max(max(r["hold_rising_rise_ns"], r["hold_rising_fall_ns"]) for r in rows),
    "analog_test_contract": {"comparator_output_load_ff": 5, "comparator_clock_load_limit_ff": 50,
        "decision_max_after_falling_edge_ns": 250, "preserve_decision_after_capture_ns": 5},
    "limitations": ["Receiver values are conditional on the routed macro's characterized SDC input slew and load assumptions.",
        "Negative internal hold does not authorize an analog comparator reset race; keep the independent 5ns post-capture hold test.",
        "Top-level interconnect capacitance and skew are additional integration requirements."],
    "corners": rows, "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(HERE / "results/interface_validation.json").write_text(json.dumps(report, indent=2)+"\n")
print(json.dumps({k: v for k, v in report.items() if k != "corners"}, indent=2))
