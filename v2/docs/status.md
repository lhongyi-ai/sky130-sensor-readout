# Implementation Status

**Current status, 2026-09-13:** The user has resumed work in the school's Cadence environment and requested continued local verification and more reliable school upload packages. Additions include a corresponding 32-item local characterization of the legacy OTA, same-source frontend dual-injection/coupling-matrix and noise diagnostics, 12 real continuous ADC conversion frames, reusable macro-assembly GDS, and new-package release checks. The complete chip has not passed acceptance. Start with [Local progress and school delivery preparation](local_preparation_20260913.md).

| Current work | Evidence completed this round | Still unfinished |
|---|---|---|
| Legacy OTA | 32/32 corresponding local tests and two differential references, with complete raw data and reports | School extra raw results; existing PSRR/ICMR/PVT settling failures retained |
| Frontend | Same-source dual injection at three gains, four-plane coupling matrices, acquisition/hold noise diagnostics, small migration benchmark | Formal full multiloop stability, sampled noise, 45-PVT, native school migration |
| ADC | Baseline/strict runs each agree across 12 real continuous functional frames; KLU operating point available | Full CDAC numerical waveforms fail convergence; reliable continuous conversion, all-code, long-record, and full-system mismatch not released |
| Physical/post-layout simulation | Real local macro assembly, unrouted assembly geometry DRC=0; 135-row matrix and readiness gate | Missing analog-module layouts, intermacro routing, full-core LVS/PEX, top-level post-layout simulation |
| New school package | Existing install/export recovery regression; manifest/compatibility/same-package field-evidence release checks | New frontend not frozen, no new school package released, no actual minimum field trial of a new package |

The following preserves **historical stage records from 2026-09-10**. Their old candidates or “Cadence deferred” labels do not supersede the current status above. Old status metadata in frozen `config/spec.json` is also historical; this round did not change its numerical specification or source hash.

2026-09-10: Continued frontend repair, an ADC all-code execution framework, noise-model qualification, and evidence-chain strengthening; [Results and unfinished work from this round](non_cadence_20260910.md). The new frontend's gain-16 setting shows local nominal improvements from the same source. However, its complete 45-point DC process/voltage/temperature screen passes only 30 points and fails 15, with a worst residual of 457.828 LSB. No final revision satisfying all three gains and all voltage/temperature conditions has been frozen.

| Stage | Current status | Existing evidence / gaps |
|---|---|---|
| M0 Environment qualification | OPEN_FLOW_PARTIAL; CADENCE_DEFERRED | Open-source single-device, statistical-model, and small-layout closed-loop runs completed; school Virtuoso/Spectre, Cadence-compatible PDK, and sign-off rules not checked |
| M1 Legacy Cadence reproduction | DEFERRED_BY_USER | Legacy files fully retained; no native Cadence reproduction |
| M2 System model and budget | PARTIAL | Evidence exists for models, calibration, FFT, analytical noise-folding budgets, real MIM matching, and finite reference loading; joint system noise/linearity/power feasibility is not closed |
| M3 Frontend transistor level | IN_PROGRESS_NOT_QUALIFIED | New repair candidate G16 nominal DC residual approximately 0.820 LSB and local sampling error approximately 43 µV; same-source G1/G4 not released. Legacy FDDA10 oscillation/static failures retained; three-gain results cannot be assembled across candidates |
| M4 Frontend physical implementation | NOT_STARTED | Digital-macro and switch layouts are not frontend layouts; frontend not frozen, so complete frontend DRC/LVS/PEX cannot be claimed |
| M5 Standalone SAR ADC | PARTIAL | Added six continuous conversions at three inputs using real analog circuits plus original RTL, and a resumable all-code verification framework; all-code long runs, noise, mismatch, and complete ADC layout not released |
| M6 Full-chain physical integration | SCHEMATIC_SMOKE_ONLY | Legacy G16 frontend plus real ADC plus original RTL completed short continuous conversions; no full-core layout/top-level parasitic acceptance |
| M7 Complete acceptance and presentation | PARTIAL_DOCUMENTATION | Chip explanation, interfaces, learning checkpoint, raw data, and failure records available; final performance report must await overall verification, without entering targets as achieved results |

## Historical design details identified and addressed

1. Continuous 100 kS/s operation cannot insert an extra idle cycle after each 16-cycle frame. The control interface defines busy as request backpressure and permits the next frame request during the final decision cycle; start is still strictly ignored while busy is high.
2. In gapless conversion, gain selection switches to the next frame. Therefore data_gain is latched with the current output to prevent external calibration from using incorrect gain coefficients.
3. The comparator now has a real output-holding latch; the real R/MIM/CMOS phase generator has been checked at all 45 PVT points. The shortest measured acquisition window is approximately 2.47685 µs. Subsequent sampling tests use this window rather than claiming coverage from ideal 2.5 µs results.
4. FFT analysis must not discard otherwise valid SNDR merely because a particular noise or harmonic component is unresolved. Unavailable independent metrics return null with a reason, rather than fabricated infinite performance.
5. Calibration points are strictly fixed; validation and calibration points are separate, and subsequent drift cannot be hidden by refitting.

6. A 3×3 µm MIM is nominally 19.845 fF; 4096 units are approximately 81.285 pF per side. Actual PDK experiments show that `m=N` alone does not provide independent-unit local statistical scaling; `m=N mult=N` passes positive/negative controls. The 200 CDAC mismatch samples are not full-ADC or full-chip yield.
7. The original frontend's 350 Ω source impedance, gain-switch on-resistance, and on-chip resistor temperature drift jointly invalidate fixed calibration. The high-input-impedance candidate instead compares sensor voltage with a high-impedance feedback tap, while retaining real source impedance, a two-stage fully differential structure, and CMFB. Noise, power, and stability must be rechecked, not just DC repaired.
8. Bottom-plate sampling and comparator preamplification reduce near-threshold kickback misdecisions. The actual MSB standard-threshold reference switch fails settling at the low-voltage cold corner; a low-threshold candidate passes limited boundary retests but has not completed full ADC acceptance. A counterexample using minimum-size switches must not be described as the original array's actual MSB size.
9. Hold-time problems exposed by digital-macro placement/routing were repaired with actual cells/buffers. Final nine-corner STA and routed all-code functional tests pass; zero-delay netlist function was not substituted for physical timing.
10. The four-MOS sampling switch completed independent layout DRC/LVS and R/C parasitic extraction. All 2430 condition points pass: 45 PVT × three inputs × three common modes × three source impedances × schematic/RC. It uses an ideal clock with the specified window and excludes mismatch/random noise; these are not 2430 full-ADC acceptance tests.
11. New reference switches, comparator preamplifier, and compensated sampling switch were integrated with the real phase circuit and original SAR RTL: one complete conversion each at nominal and SS/1.62 V/−20 °C produces code 2677 for input 0.123 V. This is short connection/function evidence, not passing all-code, noise, or system accuracy.
12. Same-revision measurements of frozen FDDA10 clearly fail: G16 nominal static-calibration residual is 1.35887 LSB, and frozen coefficients give 4.00399 LSB at TT/1.62 V/85 °C. Persistent oscillation in the sampling reference window prevents calculation and declaration of qualified settling error. Approximately 1.816 mW and 108.9 µV calibrated small-signal noise are diagnostic values for this unstable candidate, not chip performance.
13. For 200 actual mismatch instances of the bare comparator and holding latch, after freezing nominal offset coefficients, local ±4 LSB checks at 1.62 V/−20 °C, 1.62 V/85 °C, 1.98 V/−20 °C, and 1.98 V/85 °C fail in 12, 1, 0, and 32 instances respectively. No voltage/temperature refitting was used. This excludes the new preamplifier and floating capacitor array and does not directly represent new-ADC or full-chip calibration.
14. Sampling-switch checks added opposite-full-scale initial states at four selected process/voltage/temperature points; 216 schematic/RC conditions pass. This limited boundary test is not claimed as full 45-point full-scale coverage.

15. With the same `564f4776…` source, the new frontend repair reduces G16 nominal static-calibration residual to approximately 0.820 LSB, with three endpoint errors of approximately 43 µV under the actual four-MOS sampling load. With fixed nominal coefficients, static residuals at TT high-temperature/low-voltage and low-temperature/high-voltage are approximately 1.18/1.73 LSB. This does not pass other gains, noise-inclusive dynamic accuracy, or the entire hold interval.
16. The new ADC static framework strictly distinguishes short conversions, 4096-code-center coverage, and threshold-ramp linearity. Measured all-code computation cost is high; a 10 ns maximum step produces the same six codes but fails full-waveform numerical comparison and has not replaced the original 2 ns setting.
17. Available VACASK and original ngspice SKY130 device noise are not equivalent; correct intrinsic RC noise and matched single-transistor DC/AC do not replace noise-model qualification. This nonequivalent model must not generate final SNDR results.
18. New experiments freeze calibration reports and raw-evidence hashes; nonnominal voltage/temperature runs cannot refit temporarily. Reanalysis does not overwrite original summaries. Software-test counts come from the unified validation report and are not converted into counts of passing chip-performance tests.

## Historical tasks and still-valid acceptance requirements

- After freezing a frontend candidate, complete three-gain noise, differential/common-mode loop stability, real sampling settling, fixed-calibration full voltage/temperature regression, and startup/overload/PSRR/CMRR tests under one source snapshot.
- Resolve joint convergence of ADC sampling/reference switches and preamplifier/comparator; complete all-code static linearity, long-record dynamic distortion, boundary tests, and required mismatch coverage.
- Integrate the new stable frontend, sampling structure, real reference loading, and digital physical interface, then regress all input/gain/process/voltage/temperature conditions. Short integration tests cannot replace complete system acceptance.
- Complete analog-core layout and parasitic verification have not been implemented. Open-source tools can perform some work, but it will not be renamed as completed native Cadence design. Final Cadence physical delivery under the original plan remains deferred in this historical record.
- This round has not established a simulation flow supporting a claim of complete dynamic device random-noise inclusion. Alternative methods can continue to be analyzed/qualified, but noiseless FFT or assumed artificial noise must not be presented as real SNDR.

After Cadence resumes, follow M0→M1 to complete actual environment qualification and legacy OTA comparison, then migrate the same-revision candidate, implement full physical design, and run unified top-level post-layout simulation. Do not switch processes without authorization or fabricate screenshots.

Complete targets and numerical thresholds are unchanged. Unresolved items remain unfinished and are not relaxed because local tests pass.
