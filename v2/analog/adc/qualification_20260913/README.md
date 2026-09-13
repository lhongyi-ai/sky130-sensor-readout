# ADC local circuit-level progress report (2026-09-13)

**The 12 frames agree functionally, but the numerical waveforms have not converged, so reliable continuous conversion cannot be considered qualified.** The maximum difference between the same physical differential CDAC nodes in the two runs is **48.393 mV** on the union of accepted timepoints; it remains **4.077 mV** on the common **1 ns** grid. Both greatly exceed **0.05 LSB = 9.765625 µV**.

This round covers positive and negative near-full-scale inputs, both sides of zero, several new code centers, and large alternating jumps. Full ADC qualification remains incomplete; all-code coverage, long-record spectra, and complete ADC mismatch have not been falsely reported as passing.

| Profile | Actual runtime | Result | Complete conversions / real decisions |
|---|---:|---|---:|
| baseline | 393.553 s | CONTINUOUS_12_FRAME_FUNCTIONAL_PASS | 12 / 144 |
| strict | 839.944 s | CONTINUOUS_12_FRAME_FUNCTIONAL_PASS | 12 / 144 |

Each complete run lasts 122 µs at 100 kS/s, resets only once, and retains all 12 frames. Conditions are TT, 1.8 V, 27 °C, 350 Ω per input, and reference sources of 1 Ω + 10 nF. The real SKY130 CDAC, switches, preamplifier, dynamic comparator, and SAR RTL are retained, using the local bridge with the repaired 33-bit output mask.

Output codes are cross-checked among the actual bus, RTL log, and 144 Q/QB decision windows; 50 ready/busy state points are checked independently. Ideal codes are diagnostic only and do not determine real comparator results. Each simulation's original netlist, waveforms, logs, exit code, and hashes are in its corresponding results/ directory.

Numerical-comparison status: **NUMERICAL_CONVERGENCE_FAIL**. baseline uses a 2 ns maximum timestep and reltol=1e-5; strict uses a 1 ns maximum timestep and tightens reltol/abstol/vntol tenfold.

Differential CDAC error: maximum 48393.343798 µV (247.773920 LSB) on the union of accepted timepoints; maximum 4076.773191 µV on the common 1 ns grid; maximum 0.013376 µV across all predecision checkpoints. The strict threshold remains 0.05 LSB = 9.765625 µV. Small predecision errors and identical output codes do not override the complete-waveform failure.

Extrapolating from the slowest completed profile in this round, 131073 continuous conversions without warmup would take approximately 106.19 days; the current batch=8 scheme with warmup and previous-point replay approximately 225.65 days; and one continuous record of 16384 points plus 256 warmup conversions approximately 13.48 days. This is a linear resource estimate from one measurement, not a runtime commitment or full-PVT budget.

The all-code plan remains fixed at 4096 × 32 + 1 = **131073 points**, with **0 points** completed. The campaign.py run entry point was observed to exit with code 2, keeping the quality gate closed. The plan and underlying resume protocol retain one worker, preserved failures, explicit retries, and at most one batch per invocation. This version does not allow long runs; new numerical qualification requires a separately auditable version and must not modify existing failed results.

campaigns/spectrum_and_mismatch.json fixes the constraints for a continuous sine record of **16384 points**, bin=7373, 45001.220703125 Hz, and −1 dBFS, plus a requirement for **200 independent complete-ADC mismatch samples**. These are unexecuted requirement descriptions. A deterministic FFT is not SNDR with device noise; independently reset short records cannot be concatenated into a continuous spectrum. The historical 200-case CDAC and 200-case comparator statistics are not full-ADC mismatch samples.

The existing real CDAC PEX still fails monotonicity in all-4096-code static linearity. It is a dependency for subsequent complete-ADC post-layout simulation; this directory has changed neither its layout nor its conclusion.

## Reproduction and limits of migration to the university environment

The only qualified runtime environment is the existing local Linux AArch64 container with its frozen ngspice/PDK. The bridge binary is ELF e_machine=183 (ARM64) and cannot directly serve as an x86_64 university Linux executable. run_checked.py explicitly rejects an incorrect architecture and verifies the hashes of the actually loaded helpers, RTL, circuit, and bridge. The runner rechecks PDK and tool identities. The supplementary helper audit in support/ is byte-for-byte consistent with the original frozen source; this supplementary audit was recorded after the baseline run.

Execute under /repo in the existing container:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py check
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py baseline
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/run_checked.py strict
PYTHONDONTWRITEBYTECODE=1 python3 v2/analog/adc/qualification_20260913/campaign.py collect
```

Each of the two real experiment profiles saves a new independent result directory and is limited to 900 s per run; collect should currently exit with code 2 and report 0/131073. Migration to the university environment still requires rebuilding the bridge for its architecture, actual university models and licenses, Spectre syntax/model verification, and initial qualification of short handshake and conversion tests. This directory contains no Spectre batch job that bypasses university-environment qualification.

## Evidence entry points

- report.json: all actual runs, numerical results, budgets, historical-evidence boundaries, ABI, and validation exit codes.
- snapshot/manifest.json and support/manifest.json: source hashes for the circuit, RTL, repaired bridge, PDK/tool records, and analysis helpers.
- numerical_comparison.json: strict numerical comparisons on the union of accepted timepoints and the common 1 ns grid.
- peak_diagnosis/: both raw time axes around the largest error, voltages at the same physical TP/TN nodes, and digital/real phase-edge locations; the specific mechanism causing this error has not yet been isolated.
- results/*/conversion_table.csv: per-frame input, actual output code, comparator word, and valid time.
- validation/: actual output from negative software tests, the closed quality gate, zero all-code coverage, and source/architecture checks. These software tests are not additional circuit samples.
- solver_probe/: a separate KLU operating-point capability diagnostic; operating-point completion does not establish transient speed or numerical qualification. See the [official ngspice description](https://ngspice.sourceforge.io/applic.html) for the option basis.

Still incomplete: complete all-code INL/DNL, long-record spectra with device noise, 200 complete-ADC mismatch cases, full PVT, full-ADC post-parasitic qualification, and university Cadence qualification.
