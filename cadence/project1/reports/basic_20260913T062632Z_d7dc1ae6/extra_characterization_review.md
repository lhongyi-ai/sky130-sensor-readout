# Legacy OTA extra-test review: execution complete, full acceptance still has gaps

All **32 extra tests in this report actually ran and exported successfully**. Native netlists, executed inputs, logs, and recalculated results passed review; the original report shows **13 PASS, 14 FAIL, and 5 REVIEW_REQUIRED**. The previous 52 nominal/PVT tests and 3 passive tests also have execution evidence, so **all 87 predefined entry points in the current package have been executed**. This completes execution of the test inventory, not acceptance of every legacy OTA performance requirement.

Report: `project1_basic_report_20260913T062632Z_d7dc1ae6.zip`  
SHA256: `413e1edf9477d189f043045c2c49c17ef7900432de9b4e5962b545ee78822c27`

The school still uses `basic_design_v1_0_4` + `1.0.4p3`. Transistors, compensation, supplies, simulation options, runtime package, and original pass/fail labels were not changed this time. Review results are separate files and do not overwrite returned school evidence.

## 1. What each group measures

| Test | Count | Purpose | Current conclusion |
|---|---:|---|---|
| Common-mode and supply rejection | 3 | Measure propagation of common input and supply perturbations to output | Transfer curves are available, but differential-reference operating points and the negative-supply test definition still require alignment |
| Noise | 1 | Measure static small-signal device noise versus frequency | Data and units verified; a report-only item without an originally specified numerical pass gate |
| Output DC sweep | 1 | Observe output following as input changes | Currently a forward voltage-follower sweep; the original output-swing method has not yet been reproduced |
| Loop and step at different loads | 8 | Measure stability margin and response at 1, 2, 10, and 20 pF | Six tests pass; phase margins at 10 and 20 pF are insufficient |
| Input common-mode sweep | 19 | Change input DC level to inspect gain and transistor operating regions | Seven points pass the initial screen; original-criteria review passes only the five sampled points at 0.8, 0.9, 1.0, 1.1, and 1.2 V |

These tests characterized the old circuit's operating scope and found that some basic-package methods/criteria were not fully aligned with the original design. Those omissions must be completed in the delivered package; they are not user-operation errors.

## 2. Larger loads reduce phase margin with the existing compensation

Fixed TT, 1.8 V, 27°C, and 100 kΩ output load. The 5 pF row reuses previously validated P01; the remaining rows use this run's data.

| Capacitive load | Loop unity-gain frequency | Phase margin | Worst 1% settling time | Result |
|---:|---:|---:|---:|---|
| 1 pF | 19.854 MHz | 93.78° | 51.73 ns | Pass |
| 2 pF | 19.203 MHz | 85.93° | 48.97 ns | Pass |
| 5 pF | 16.733 MHz | 68.79° | 74.19 ns | Pass, existing nominal result |
| 10 pF | 13.656 MHz | **53.77°** | 140.39 ns | **Phase margin below 55°** |
| 20 pF | 10.436 MHz | **40.55°** | 249.69 ns | **Phase margin below 55°** |

Measured loops for all five loads have only one downward 0 dB crossing and the correct low-frequency sign. All four new steps meet the legacy 1.5 µs settling requirement, but this does not replace the phase-margin gate. Rising-edge overshoots at 10 and 20 pF are approximately 111.87 and 87.19 mV respectively, with decaying ringing visible in the plot; insufficient phase margin must not be described directly as sustained oscillation.

The original ngspice extra-load baseline only includes 1, 2, and 5 pF, with phase margins 94.16°, 86.29°, and 69.08°, close to this run. The 10 and 20 pF cases are extended tests; no corresponding historical pass results were fabricated. The legacy gate is 55°; the new frontend's 60° and multi-loop requirements belong to separate acceptance.

## 3. Common-mode range: correcting the meaning of initial-screen labels

The basic package's automatic criteria are low-frequency gain ≥50 dB, positive saturation margin for every MOS device, and power ≤600 µW. This explains why `icmr_08`–`icmr_14` display PASS.

However, the original Day 4 ICMR requirements are stricter: gain must not fall more than 3 dB below its 0.9 V nominal value, actual differential stimulus must be correct, all transistors must occupy specified operating regions, output must retain 50 mV rail headroom, and follower error must be ≤10 mV. The original sweep step is 10 mV; this package uses only 100 mV.

This run's nominal gain is 67.68355 dB, giving an original ICMR gain floor of **64.68355 dB**.

| Input common-mode voltage | Low-frequency gain | Basic-package label | Original-criteria review |
|---:|---:|---|---|
| 0.8 V | 67.85 dB | PASS | Sampled point passes |
| 0.9 V | 67.68 dB | PASS | Sampled point passes |
| 1.0 V | 67.27 dB | PASS | Sampled point passes |
| 1.1 V | 66.52 dB | PASS | Sampled point passes |
| 1.2 V | 65.22 dB | PASS | Sampled point passes |
| 1.3 V | 62.78 dB | PASS | **Gain drops 4.91 dB; fails** |
| 1.4 V | 56.72 dB | PASS | **Gain drops 10.97 dB; fails** |

Sampled points from 0 to 0.7 V fail at least M5's saturation-margin requirement; 0 and 0.1 V also involve M6. At 1.5–1.8 V, the input pair M1/M2 fails saturation-margin requirements. Some low-common-mode points have numerical-sensitivity notices; preserve their data and do not use anomalous edge-point gain to infer a usable range.

Therefore, “ICMR is 0.8–1.4 V” cannot be claimed. Current evidence establishes the original criteria only at **five measured points from 0.8 to 1.2 V**; exact endpoints require a fine sweep. The original ngspice record is 0.76–1.22 V, whose upper endpoint did not meet the original 1.3 V target; this run's failure at 1.3 V is consistent with that limitation.

Original PASS labels remain in `received/`; stricter review conclusions appear separately in the [common-mode criteria comparison table](icmr_criteria_comparison.csv).

## 4. Noise: values and units verified, a static report-only item

501 points cover 10 Hz–1 MHz with 100 points per decade. The original binary PSF `in` and `out` traces both reference the `V/sqrt(Hz)` type; this was verified without guessing units from screenshots.

| Measurement | Cadence | Historical ngspice |
|---|---:|---:|
| Input-referred noise density at 1 kHz | **401.150 nV/√Hz** | 401.170 nV/√Hz |
| Integrated input noise, 10 Hz–1 MHz | **52.2998 µV RMS** | 52.3016 µV RMS |

Integration squares noise density, trapezoidally integrates it over frequency, then takes the square root. Input referral corresponds to the current static test with `VINP` as the input source and the other input AC-grounded. The original school label remains REVIEW_REQUIRED; locally it is interpreted as “data review complete, report only,” because the original design provides no numerical acceptance threshold for this item.

These results do not validate switched-sampling noise, ADC dynamic accuracy, statistical mismatch, or full-chain noise acceptance.

## 5. What remains for common-mode/supply rejection and output swing

**Common-mode/supply rejection:** The three current curves have output transfers of −3.6799 dB, 31.3133 dB, and 31.5445 dB at 1 kHz. These are transfer gains, not CMRR/PSRR.

The P01 differential test has a static output near 0.900012 V, whereas the three rejection tests have approximately 0.929208 V. Differential gain must be obtained at the same static operating point before ratios are calculated at matching frequencies. The best data from two operating points must not be silently combined.

Furthermore, both inputs in the current negative-supply test move with VSS; the original method holds inputs and VDD AC-fixed relative to absolute ground. Current VOUT export also references absolute ground. These definitions must be explicitly aligned for a same-condition comparison. Historical PSRR+ and PSRR− are about 36.33 and 36.25 dB, both below the original 45 dB requirement; prior failures remain recorded, and current data do not claim to eliminate them.

**Output swing:** The current 181 points are a forward 0→1.8 V voltage-follower sweep, where input common mode changes too. Output extrema are approximately 0.0226–1.6177 V and must not be treated as a qualified swing interval. The original method uses an inverting structure with equal 10 MΩ input/feedback resistors, holding input common mode near 0.9 V, and performs forward/reverse sweeps with pointwise M6/M7 operating-region checks. This package has not reproduced those steps; separately exported `dcOp` corresponds only to initial parameters, not operating regions throughout the sweep.

## 6. Logs and data completeness

- All 32 Spectre jobs terminated normally; exit-code records agree with logs, and all have 0 errors and 0 warnings.
- Notices were not ignored: individual jobs have 2–15 counted notices, including bad pivoting. The output DC sweep has GminDC solution-influence notices at low input and **207 suppressed notices**; `icmr_00`–`icmr_03` also have GminDC notices. Zero warnings do not mean all operating points are free of numerical risk.
- Checked every ZIP file and extracted content; **all 1604 runs files from the prior report remain byte-for-byte unchanged**. Failures were not overwritten.
- All 32 jobs agree in frozen task definitions, site configuration, native-netlist audits, reconstructed execution decks, export completeness, and recalculated measurements; all use the same OTA subcircuit and model-entry hashes as prior PVT.
- Twenty-six AC analyses each have 1081 frequency points; noise has 501 points; the DC sweep has 181 points; four steps span 0–5 µs with maximum exported spacing meeting 0.5 ns. All 13 MOS operating points and name mappings are complete.
- Cadence was not run locally. School OA library databases and PDK model dependencies were not directly inspected; separate OCEAN numeric exit codes were not archived. Exports were cross-checked against recorded successful statuses, completion markers, logs, and finite data.
- Historical supplemental tables and original analysis sources were saved separately in `historical_context/` with source hashes; their design manifest matches the basic package's frozen Day 4 manifest. Current file modification times were not used to select a baseline, and old labels were not rewritten.

## 7. Next steps

**The user currently does not need to rerun `extra`, PVT, or reload `create.il`.** This attachment is sufficient to complete the review above. Legacy PVT P06_step, P07_step, and P13_step still fail; repeating execution without circuit/method changes will not resolve the confirmed static follower error.

The next local delivery should complete the following measurements together, followed by one user upload and execution:

1. Measure differential, common-mode, and positive/negative-supply transfers at a shared static operating point; define supply perturbations and input/output references explicitly.
2. Reproduce ICMR on the original 10 mV grid while applying relative-gain, operating-region, actual-stimulus, and output-follower criteria together.
3. Reproduce the original fixed-input-common-mode output-swing circuit, sweep in both directions, and export M6/M7 operating points at every point; perform targeted convergence review for numerical notices affecting endpoint decisions.
4. Consolidate original requirements, original ngspice, Cadence results, and missing items; retain noise as report-only and preserve prior failures.

**This supplemental package has not yet been generated; this report contains no new upload package.** What is complete is the full review of this returned dataset. The legacy OTA remains the migration comparison baseline; whether its circuit should change depends on its role in the new system, not on tuning dimensions merely to turn all historical labels green.

Subsequent work still includes the new three-range frontend, complete SAR ADC, Cadence physical verification, full core layout, and top-level post-layout simulation. Completing execution of these 87 entry points does not complete that work.

## 8. Files and English summary

- [Complete audit and values](review.json)
- [Original status summary for 32 jobs](extra_results.csv)
- [Load comparison table](load_comparison.csv)
- [ICMR screening versus original criteria](icmr_criteria_comparison.csv)
- [Results plot PNG](extra_characterization.png) / [PDF](extra_characterization.pdf)
- [Local review log](local_review.log)

All 32 additional Cadence jobs completed and exported data successfully: 13 automated passes, 14 performance failures, and five review-required results. All 87 predefined package entrypoints now have execution evidence, but original characterization acceptance remains incomplete. The 10 pF and 20 pF phase margins are 53.77° and 40.55°, below the legacy 55° limit. Applying the original relative-gain ICMR rules to the returned coarse grid passes only the sampled points from 0.8 through 1.2 V. Stationary input-referred noise is 401.150 nV/√Hz at 1 kHz and 52.2998 µV RMS over 10 Hz–1 MHz. Matched-operating-point rejection measurements, original fine-grid ICMR endpoints, and the original fixed-common-mode bidirectional output-swing method remain outstanding. Previous PVT failures and original report labels are preserved. No circuit tuning or local Cadence execution was performed.
