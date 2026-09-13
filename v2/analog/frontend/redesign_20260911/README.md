# Non-Cadence frontend redesign (2026-09-11)

This directory is an independent experiment with a new architecture. It does not modify or overwrite the old frontend or the failed evidence in
`repair_20260910/` and `closure_20260911/`. The goal is one programmable sensor frontend with gains 1/4/16
using real SKY130 devices, rather than combining the three gain settings from different candidates.

Candidate 01 uses a fully differential inverting closed loop: both inputs pass through real high-resistance polysilicon resistors into the OTA
summing nodes, with cross-feedback from the opposite output to the same node. The OTA itself is a two-input, two-stage, fully differential
transistor amplifier. Output average is continuously sensed with resistors and regulated by an independent transistor common-mode loop.
There are no ideal current sources, ideal controlled amplifiers, or ideal switches inside.

All candidates and experiments must use `run_diagnostic.py` to create append-only timestamped directories containing
source snapshots, raw data, logs, configuration, results, and SHA-256 manifests. Before the budget of 12 small nominal diagnostics
is exhausted, only simultaneous checking of all three gains on the same candidate is allowed. One 45-PVT DC screen is permitted only
after all three gains simultaneously pass the prerequisite gates for static performance, real sampling settling, differential/common-mode stability, and power.

## Current candidate and actual results

- Current source: `candidate_01.spice`
- Current source SHA-256: `2c36c23fb47036272a8dfe4a7fff6ee9101a9091fdcb1f13cb742880f257891e`
- Reproducible summary: `qualification.json`
- Selected frozen evidence: `diagnostics/06_20260911T082721717297Z_candidate_01/`
- Real sampling switch: `sampling_switch.spice`

The same candidate source completed 81 static points at each of the three gains under TT / 1.8 V / 27 °C.
After fitting −80%, 0, and +80%, the remaining 78 independent points had these maximum residuals:

| Gain | Maximum static residual | Maximum static common-mode error | Maximum DC frontend power | Key-device operating regions |
|---:|---:|---:|---:|---|
| 1 | 0.117264 LSB | Approximately 0.409 mV | Approximately 0.535 mW | All listed devices retain at least 20 mV saturation margin |
| 4 | 0.015870 LSB | Approximately 0.409 mV | Approximately 0.526 mW | Same |
| 16 | 0.019776 LSB | Approximately 0.409 mV | Approximately 0.525 mW | Same |

These are **static passes from one source**, not a full frontend pass. They show that the inverting fully differential loop eliminates the old
FDDA's large-signal input-headroom problem and that the added first-stage common-mode loop stabilizes the first-stage nodes near
0.705 V. They do not establish sampling, noise, or stability qualification.

## Why dynamics still fail

The final test used a real main LVT transmission gate, two dummy transistors with shorted diffusions, and 4096 real
MIM cells per side. With 10 ns digital edges, the simulation reached 28.010 µs before encountering
`timestep too small` at the third reset edge. The first fully recorded sampling cycle before that point already rejects the dynamic gate:

| Gain | First acquisition error | Peak-to-peak in the 16–19 µs reference window | Result |
|---:|---:|---:|---|
| 1 | Approximately 70.55 µV | Approximately 14.47 mV | Failed |
| 4 | Approximately 9.39 µV | Approximately 10.84 mV | Failed: reference not settled |
| 16 | Approximately 917.07 µV | Approximately 4.80 mV | Failed |

The acquisition-error limit is 48.828125 µV, and the quiet-reference-window limit is 4.8828125 µV. References at all three gains
still show millivolt-level ringing, so G4's single instantaneous error cannot establish a settling pass. Formal injection measurements of differential and common-mode phase
margins are also incomplete, so the stability gate is explicitly failed/unresolved.

Under the bounded-experiment rules, tuning stopped after diagnostic 6/12. Because three-gain dynamics and formal stability
prerequisites had not passed together, the 45-PVT DC screen was not started and noise figures from old candidates were not reused.
A file's existence does not imply a pass; the authoritative final status is `qualification.json`.

## Physical implementability audit

The feedback network has no millimeter-scale resistor: with 0.35 µm-wide high-resistance polysilicon, the model lengths for 10 kΩ, 10.35 kΩ,
41.4 kΩ, and 165.6 kΩ are approximately 9.10, 9.46, 40.72, and 165.80 µm. The largest
single feedback resistor has an effective resistive-body area of approximately 58.0 µm²; contacts, guard rings, and routing will enlarge the final footprint.
At G1, the sensor sees approximately 20.7 kΩ differential load, and each input branch carries approximately 19.3 µA at ±0.2 V.
The approximately 3.38% drop from the 350 Ω source impedance is already included in feedback-resistor design and static calibration.

This round also found a physical-rule violation that cannot be hidden: the two 1.2 kΩ Miller zero-setting resistors have calculated lengths
of approximately 0.241 µm under the current 0.35 µm model formula, below the PDK PCell's 0.5 µm minimum.
Because dynamics already failed, this round did not silently round the dimensions and continue claiming the same candidate. The physical
implementability gate therefore fails. A future version must use a legal wider/lower-resistance PDK resistor option or
the minimum legal dimensions, then repeat both static and dynamic verification.

![Redesigned frontend architecture](architecture.svg)

## Using the files

`run_diagnostic.py` is the rerun entry point; every invocation creates a new timestamped evidence directory without overwriting
old results. `build_qualification.py` only reads and verifies the frozen evidence from diagnostic 6, then rebuilds the summary.
`test_evidence.py` checks hashes, diagnostic counts, and the requirement that a static pass cannot conceal a dynamic failure.

All results are pre-layout results from open-source ngspice＋SKY130 models, not a native Cadence design,
post-parasitic simulation, full-ADC conversion result, tapeout, or silicon measurement.
