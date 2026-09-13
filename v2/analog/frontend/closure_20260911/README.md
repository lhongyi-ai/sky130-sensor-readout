# Frontend closure experiments: 2026-09-11

This directory completes fault diagnosis and bounded experiments on three candidates built from real PDK devices; **the programmable analog frontend remains incomplete**. The old circuit, old results, and existing measurement scripts were not modified. The complete index is `closure_summary.json`; each experiment retains the circuit, stimulus, source snapshots, raw data, logs, results, and SHA-256 manifest.

## Plain-language explanation

Amplifier transistors need enough voltage headroom above and below to behave as controlled current sources. At higher supply and temperature, the old candidate's average input voltage rose but the bias above the input devices did not follow. As headroom disappeared, increasing input no longer produced the expected output, compressing both large-signal endpoints. A software scale factor cannot repair this distortion.

Gain 1 has an additional issue: it allows a larger sensor-input swing, and at the low input endpoint the tail-current source below the input devices also lacks headroom. Tail current is no longer constant, making output common mode more prone to ringing. Common mode is the average voltage of the two output wires; the differential signal is their voltage difference.

This round first confirmed these headroom issues using actual transistor operating points, then adjusted bias, current mirrors, and compensation. Headroom improved, but quiet waveforms and simultaneous accuracy at all three gains have not yet been achieved, so the amplifier cannot be declared repaired.

## Quantitative findings from the old 45-point failures

All 45 G16 process/voltage/temperature conditions for the same `564f4776…` source were read completely. Original results were 30 static passes and 15 static failures. This round changed neither calibration coefficients nor thresholds.

- Of 15 conditions at 1.98 V, 8 failed; of 15 conditions at 85°C, 8 failed. Failures concentrate at large positive/negative inputs and are mainly odd-symmetric compression rather than zero offset.
- Worst case, SF / 1.98 V / 85°C: fixed-calibration residual 457.828 LSB; actual output approximately ±0.30970 V for an input target of ±0.4 V. Yet static output-common-mode error is only 3.35 mV.
- New diagnostic 01 confirmed a worst input-device `VDS−VDSAT` of −51.55 mV under that condition. At zero input, each measured input device has `gds≈1.04 mS`, indicating loss of normal high-output-resistance saturation operation.
- New diagnostic 02 confirmed −64.55 mV headroom for the upper tail transistor at TT nominal G1 full scale; static-calibration residual is 1.62650 LSB, with approximately 317.78 mV peak step common-mode deviation.
- Historical zero-input node evidence at FS / 1.62 V / −20°C also shows only 34.39 mV `VDS` for the upper tail device. This round did not rerun device-region analysis at that point, so the node-based inference is not a new simulation result.

Per-point signs, input amplitudes, common mode, bias nodes, source/data summaries, and integrity checks are in `baseline_analysis/*/summary.json`.

## Changes in the three candidates

Candidate A uses real SKY130 LVT input devices, an independent same-channel-length tail mirror with lower overdrive to lower the actual tail-cascode bias, smaller output NMOS devices to raise the preceding-stage voltage, and real resistors from VDD/VCM to generate a supply-tracking drain-cascode bias. Nominal G1 static error falls to 0.90194 LSB, but common-mode ringing remains pronounced and new LVT noise is unverified.

Candidate B adds more headroom to the bottom tail device and increases common-mode compensation from 1 pF to 4 pF. Results are unsatisfactory: G1 static error is 1.02275 LSB and ringing still fails. Small-signal diagnostic 05 measured a common-mode crossover near 1.804 MHz and scalar phase margin near 12.9°. The differential loop also has a high-frequency upward crossing, so neither result is formal loop-stability qualification.

Candidate C uses the same low-overdrive/cascode bias to generate geometrically scaled common-mode tail current, then attenuates the common-mode error signal by 1/16 using PDK resistors/capacitors to lower loop bandwidth. It substantially reduces late ringing but becomes more sensitive to small current-mirror ratio errors, producing approximately +40 mV static common-mode error. All three gains use the identical source `6f4684dc07d9d832dd25fe72a17a30aeba9984b751cc3f03e55d07fb92db9397`.

| Candidate C, TT / 1.8 V / 27°C | G1 | G4 | G16 |
|---|---:|---:|---:|
| 81-point independent static residual, LSB | 2.76370, failed | 0.357664, passed | 1.125913, failed |
| Maximum transient common-mode deviation, mV | 126.089 | 86.941 | 54.809 |
| Late negative-step common-mode peak-to-peak, µV | 575.885 | 23.517 | 15.274 |
| Absolute dynamic error 2.476847754 µs after the negative step starts, µV | 104.736, failed | 64.893, failed | 72.783, failed |
| Preliminary quiet step-window decision | Failed | Failed | Failed |
| Frontend VDD+VCM zero-input power, mW | 1.64014 | 1.64032 | 1.64035 |

The nominal static limit remains 1 LSB; the fixed-calibration cross-temperature/voltage limit remains 4 LSB. A's G1 static pass, C's G4 static pass, and the old candidate's noise results cannot be combined into one passing frontend. Improved nominal input/tail-device regions in C do not establish a pass across the old 45 process/voltage/temperature conditions.

The table's dynamic errors come from a separate read-only review of existing waveforms: at 2.476847754 µs after input-step start, compare the filtered output with the DC steady-state value of the same circuit at that input, accounting for static gain error separately. Negative-step errors at all three gains exceed the original 0.25 LSB (48.828125 µV) target, leaving even this static-capacitive-load diagnostic unresolved. This is not a real SAR sampling-switch test; even a pass could not replace sampling-settling qualification. Review results are in `settling_analysis/*/summary.json`, with no additional circuit simulations.

## Work not completed in this round

- Static accuracy and preliminary stability closure at all three gains on one candidate; G1/G16 static and all three transient tests still fail.
- Formal differential/common-mode loop stability for C; A/B loop results cannot be reused for C.
- Acquisition accuracy within 2.476847754 µs under real sampling-switch/CDAC dynamic loads, complete 7.5 µs hold, and SNDR with noise.
- Noise budgets for the new LVT devices, complete-chip power, mismatch, full PVT, startup, and all input-common-mode boundaries.
- Actual layout, DRC/LVS, parasitic extraction, or native Cadence design for the new candidates.

This round used the agreed **8/8 small diagnostics**, each with one ngspice process. All ended normally, and failure decisions are fully retained. Neither of the allowed **2 complete 45-point screens was started**: the three-gain nominal and preliminary step prerequisites were unmet, and expanding later stages cannot conceal failure. Normal experiment completion here means only that simulation data are complete, not that the circuit passed.

## Technical directions for the next round, not yet implemented

1. First resolve finite-output-resistance error in common-mode bias ratios. At C's G1 zero input, the actual first-stage PMOS mirror ratio is approximately 4.97156 rather than the geometric 5; the actual input-tail/common-mode-tail ratio is approximately 2.51202 rather than 2.5. Together they force imbalance in the common-mode sensing pair, and 1/16 attenuation amplifies a small detector-side error into the average output voltage. Replicated/regulated bias with matched drain-source voltage, or physical sizing correction verified over PVT, is needed; per-test-point fitting is not acceptable.
2. Reestablish evidence for all common-mode/differential crossings and loop poles on the same candidate, then check around the real sampling window. Simply increasing capacitance or observing eventual quietness after tens of microseconds is insufficient.
3. Jointly reallocate output-stage transconductance, feedback resistors, noise, and power budgets. Raising the first-stage voltage currently reduces output-stage transconductance, and G1 nonlinearity caused by finite loop gain still needs correction.
4. Start the complete 45-condition static screen and system verification with noise only after the same source passes prerequisites at all three gains.

## Review entry points

Running `run_diagnostic.py` or `run_loop_diagnostic.py` in the existing container checks the 8-run budget. Once this round's limit is reached, further runs are refused without overwriting experiments. `build_summary.py` only rebuilds a regenerable index and does not edit original experiments. `test_closure_evidence.py` audits evidence read-only and runs no circuit simulations.

All results are **pre-layout independent frontend diagnostics using SKY130 device models**, not full-chip post-layout simulations, tapeout, or silicon-measurement results.
