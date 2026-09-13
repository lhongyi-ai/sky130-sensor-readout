# 2026-09-10: Actual Progress on Work Without Cadence

Conclusion: Real circuits were further modified and verified without waiting for Cadence, but the three major items in the screenshot cannot all be checked off. Native Cadence schematics, the compatible PDK, and the final Cadence physical closed loop remain deferred at the user's request. Specifications were not lowered, and legacy OTA/failure records were not overwritten.

## What this round actually did

### 1. Repairing the frontend, beyond documentation updates

Added real PDK tail-current cascode devices and on-chip biasing to the fully differential amplifier, and MIM capacitors across the common-mode sensing resistors. The former reduces internal current variation with voltage; the latter lets common-mode feedback respond promptly to output changes. All devices are in new candidate snapshots, without overwriting original FDDA10.

Retested the same `564f4776…` circuit at gain 16, 350 Ω source impedance per terminal, and 2.6 kΩ isolation resistance under TT/1.8 V/27 °C:

| Local check | Actual result | What it establishes |
|---|---:|---|
| 81-point static transfer, three-point calibration, validation at remaining points | Maximum residual 0.820 LSB | This frontend's nominal static linearity meets this local threshold |
| Acquisition endpoint error with actual four-MOS switch | 42.99 µV | Three specified sampling endpoints are below 48.83 µV; not all inputs/PVT |
| Local error approximately 20 ns after switch turnoff | 41.71 µV | Local turnoff check passes; not complete 7.5 µs conversion-hold acceptance |
| 1 Hz–1 GHz output noise under static load | Raw 111.66 µV RMS | Continuous-time small-signal noise; no sampled-SNDR claim |
| Static net energy supply at this frontend's VDD+VCM terminals | Approximately 1.804 mW | Excludes full ADC, digital clock drivers, and references; not total chip power |
| Fixed nominal calibration, TT/1.62 V/85 °C | 1.18 LSB | This static voltage/temperature point is below 4 LSB |
| Fixed nominal calibration, TT/1.98 V/−20 °C | 1.73 LSB | This static voltage/temperature point is below 4 LSB |

Raw files are in [Same-source retest](../analog/frontend/repair_20260910/qualification_frozen_recheck/). Local sampling results at a finer 1 ns time step are close to the original 2 ns results, but do not fully prove numerical convergence of the entire circuit.

All **45 process/voltage/temperature DC conditions** for this same-source G16 candidate were then completed, with 81 inputs per condition and calibration only once per process corner at 1.8 V/27 °C. **30 points meet static-accuracy thresholds and 15 fail**, with no missing points or timeouts. TT/FF/SS/FS/SF pass 6/5/8/5/6 points respectively, out of 9 per corner. Worst-case residual at SF/1.98 V/85 °C is **457.828 LSB**. Progress at nominal and the two boundary points therefore cannot be generalized to full voltage/temperature passing.

FF/FS nominal residuals are 1.274/1.324 LSB respectively; nominal-specification failures are retained. Their mathematically valid frozen coefficients continue to diagnose other voltage/temperature conditions without refitting. See [45-point G16 static screen](../analog/frontend/repair_20260910/qualification_g16_pvt/20260910T065530849637Z/summary.json) for the complete summary and per-point raw evidence. This is not three-gain ×45-point full-chain acceptance; a DC solution also does not prove dynamic stability.

**Gain 1 of the same revision still fails; one gain-4 simulation did not finish because the time step became too small.** Later lower-bias/faster-common-mode-sensing candidates substantially reduce sustained gain-1 fluctuations but still exceed actual sampling limits. Their results cannot be combined with the gain-16 revision to pass all three gains. A low-threshold input-device control restores tail-device headroom but exposes another tradeoff involving input-transistor saturation and gain error; it is also retained as a failed candidate.

“Output common-mode deviation of 50 mV” is an existing module diagnostic gate and must not be confused with the original specification's “input common mode deviating VDD/2 ±50 mV.” Existing failures were not deleted; complete input common-mode boundaries still require itemized verification against the original specification.

The [Complete frontend experiment index](../analog/frontend/repair_20260910/repair_summary.json) is grouped by circuit hash and includes failed simulations lacking a summary. Native pole analysis was also attempted but returned a numerically suspicious root list, which cannot be interpreted as reliable stability proof.

### 2. ADC all-code testing now has a real resumable execution framework

Added batching, checkpoint recovery, real output-bus comparison, complete coverage checks, and endpoint INL/DNL threshold-interval calculations. The original SAR digital logic reads the real comparator and then drives the next capacitor-switch bit; a behavioral model does not directly generate ideal codes.

One continuous simulation actually completed six conversions: `2677, 2677, 2047, 2047, 2048, 2048`, two conversions at each of three inputs. **This proves only these three points; 4096-code or full-range linearity is unfinished.**

A measured 62 µs circuit waveform takes approximately 3.3–3.5 minutes. Extrapolating from a few samples, one worker, one warmup frame per point, and cross-batch replay: 4096 code centers take approximately 3.5 days; a full 32-point/LSB ramp takes approximately 112 days, for only one process/voltage/temperature condition. This estimate has substantial uncertainty and is not a schedule commitment; no months-long background task was silently started.

An acceleration control was run: increasing maximum step from 2 ns to 10 ns speeds execution by only approximately 1.10×. Although the six output codes agree, some DAC waveforms differ by 0.356 LSB, exceeding the preset numerical-comparison threshold, so the setting was not substituted for the original. The real ADC's effective `chgtol=1e-14` was also confirmed, rather than the frontend's `1e-18`; tolerances were not changed on an incorrect assumption.

[Method, execution entry points, and evidence](../analog/adc/verification_20260910/README.md).

### 3. Establishing whether the random-noise tool actually supports this process

The installed VACASK can simulate intrinsic RC random noise, with results near kT/C and valid noise on/off and random-seed checks.

However, extracting complete explicit parameters from the SKY130 single transistor actually selected by ngspice shows that ngspice uses BSIM4v5/4.5, while the available VACASK device falls back to 4.8.3. DC and AC are almost identical, but noise spectra differ by as much as 3.144 dB. Reinserting the extracted parameters into original ngspice gives control error below 1e-12, ruling out extraction error.

A matching device-noise implementation or rigorous model-migration verification is therefore required first. Applying a single scale factor cannot establish a pass, and a noiseless FFT cannot substitute. [Noise qualification report](../verification/noise_20260910/qualification.json).

### 4. Implementing acceptance rules in code

- Nonnominal voltage/temperature static tests must supply frozen nominal calibration; per-condition refitting is prohibited.
- New experiments record hashes of configuration, circuit, stimulus, raw data, logs, calibration source, and summary.
- Check these files before reanalysis; save new analysis separately without overwriting the original summary.
- Older experiments without complete manifests are explicitly marked as historical unverified format; no fabricated “verified” status.
- The unified software entry point adds ADC static-framework, noise-qualification, frontend-protection, and pole-audit tests. Software passing does not mean analog circuits pass.

This unified regression passes **124 Python software tests** (the original 80 plus 44 additions), with behavioral-model, analytical-budget, and digital RTL regressions also executed. See the [Validation report](../results/validation.json) for exact source hashes, output, and status.

## Still unfinished, and not all attributable to Cadence

1. All three gains simultaneously satisfying stability, settling time, noise, distortion, and power in the same implementable circuit.
2. Full-ADC all-code linearity, dynamic accuracy including random device noise, and complete mismatch screening.
3. Full-chain three-gain ×45 process/voltage/temperature combinations, frozen calibration, and startup/overload/interference boundary tests.
4. Complete analog-core layout, DRC/LVS, parasitic extraction, and top-level regression. The frontend is not yet stably frozen; a digital macro or standalone switch layout cannot substitute.

Next, resolve three-gain frontend stability and voltage/temperature bias/linearity while establishing a verifiable noise engine and a reasonable all-code computation route. Integration and complete analog layout follow only after passing. Downloading Cadence alone will not repair these circuit problems. Final native Cadence delivery resumes separately under the original plan.

## Files and history

The complete working copy was moved to `sky130-two-stage-ota/` in the user's designated workspace, including original Git history and legacy results. The new container may write only this copy's `v2/`; the old working copy remains untouched. No PDK, rules, licenses, or school information was uploaded, and no new candidate was published as a completed chip.
