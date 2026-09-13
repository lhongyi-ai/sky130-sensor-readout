#!/usr/bin/env python3
"""Save analytical physical constraints separately from simulated performance."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sensor_readout.physical_budget import make_physical_budget


def main():
    report = make_physical_budget()
    output = ROOT / "results/physical_budget.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    lines = ["# Budget Checks Informed by Real Device Data", "", "These are analytical constraints and risk screening, not chip simulation performance.", "",
        "## Feedback Network and Noise Folding", "",
        "With actual resistive feedback, signal gain G differs from noise gain 1+G. Source impedance of 350 Ω per terminal both changes gain and contributes thermal noise.",
        "The comparison below uses an ideal single pole satisfying full-scale settling in 2.5 µs and includes only input/feedback resistor noise, excluding transistor noise.",
        "Instantaneous sampling folds noise above 50 kHz back into band; a full-Nyquist FFT must include that noise.", "",
        "| Total input resistance/terminal | Gain | Feedback resistance/terminal | Resistor output noise RMS | Resistor-only SNR upper bound |", "|---|---:|---:|---:|---:|"]
    for row in report["resistor_noise_cases"]:
        total = row["source_resistance_per_leg_ohm"] + row["input_resistor_per_leg_ohm"]
        lines.append(f"| {total:g} Ω | {row['gain']} | {row['feedback_resistor_per_leg_ohm']:g} Ω | {row['full_nyquist_sampled_rms_v']*1e6:.2f} µV | {row['resistor_noise_only_snr_upper_bound_db']:.2f} dB |")
    lines += ["", "This motivates lower feedback resistance and joint design of sampling isolation/filtering, without establishing compliance for any new value.",
        "Changing integration bandwidth from 50 kHz to 5 kHz alone cannot establish passing SNDR.", "", "## MIM Capacitors and Reference Terminals", "",
        "Continuous model in the frozen PDK: a 3×3 µm MIM unit is 19.845 fF; 4096 units per side are 81.28512 pF.",
        "Bare plate area of the two arrays is 73,728 µm², not core area. Minimum-unit DRC/LVS and capacitance extraction were performed separately; the complete array still needs actual routing.",
        "Reference terminals are loaded. The JSON retains conservative upper bounds for switched charge, instantaneous current, decoupling, and settling time; actual values must come from transient tests with source impedance.", "",
        "## Still Requires Real Circuits", "",
        "These calculations cannot replace transistor thermal/flicker noise, time-varying sampling noise, reference loops, comparator kickback, stability, power, or complete-layout parasitics.", ""]
    (ROOT / "results/physical_budget_report.md").write_text("\n".join(lines))
    print(json.dumps({"status": "ANALYTICAL_CONSTRAINTS_GENERATED", "chip_qualified": False, "report": str(output)}))


if __name__ == "__main__":
    main()
