# Real SAR ADC static verification: resumable batches and integrity gates

**Status: verification infrastructure is implemented; full-ADC all-code linearity remains incomplete.**

This is neither a CDAC charge-conservation calculation nor a behavioral ADC that directly returns the ideal code for a supplied input.
For every conversion, the original `sar_controller.v` reads the real SKY130 comparator result live,
then controls the next bit's real reference switches and capacitor array. Neither the core RTL nor the frozen analog circuit has been modified.

## Frozen objects and external conditions

The composite candidate in `integration/candidates/20260908T045601001817Z` is fixed:

- Bottom-plate sampling, a real continuous-time preamplifier, dynamic comparator, and holding latch.
- Dual-LVT reference/acquisition switches sized by capacitor bit weight.
- Both top-plate clamps use four-MOS dummy-compensated switches from the independent physical module, without reversing their orientation.
- The original SAR RTL and original `sensor_phases.spice` transistor phase generator.
- Ideal logic-voltage bridges still connect digital and analog domains; mapped digital-cell delay and power are not included.

Each campaign freezes all of the above source, the bridge qualification report, the runner, and their SHA256 hashes.
Runtime records also include ngspice/Verilator versions, resolved PDK paths, and hashes of every file in the combined-model directory.
The PDK, rules, and licenses are not copied. The frontend, analog layout parasitics, mismatch, and random device noise are absent.

Defaults are TT, 1.8 V, 27°C, 350 Ω input sources per side, and references with 1 Ω plus an external 10 nF per side.
`tracking` references are VDD/2 ± 0.2 V; `fixed` references are 1.1/0.7 V. They have separate configurations,
and a pass in one mode cannot be extended to the other. Full 45-PVT coverage is not currently available.

## Three strictly distinct evidence classes

| Stage | Required input points | What it establishes | What it does not establish |
|---|---:|---|---|
| `smoke` | A small, explicitly listed set of points | Interfaces, successive approximation, and local outputs | All-code coverage, INL/DNL, effective accuracy |
| `centres` | 4096 ideal code centers | Output coverage on this input grid | Transition thresholds and code widths; it cannot be presented as a linearity pass |
| `ramp` | By default, 32 steps per LSB, totaling 131073 points | Once complete, intervals for 4095 transition thresholds and static-linearity bounds | Noise, mismatch, dynamic SNDR, or complete ADC qualification |

`ramp` INL uses the actual T1 and T4095 for its endpoint line. DNL for internal codes 1…4094
is normalized by the endpoint-fitted LSB, consistent with the project's main analyzer. The two saturated endpoint codes do not have
finite code widths over unbounded external voltage, so actual observation of 0 and 4095 within the specified input range is required separately.
Nominal-LSB code widths clipped at ±0.4 V are also retained, but only as a boundary diagnostic, not as internal-code DNL.

A threshold is not reduced directly to one floating-point value: the interval between the last low-code input and first high-code input is retained,
and interval uncertainty propagates into INL/DNL. `GRID_STATIC_LIMITS_PASS` is assigned only if the entire error interval
lies within the targets; an interval crossing a limit gives `GRID_RESOLUTION_INCONCLUSIVE`.
Even if the grid passes, numerical convergence remains unverified and `complete_adc_qualified` stays false.

## Continuous-conversion and resume semantics

A campaign builds the real RTL shared library only once. A batch performs multiple consecutive 100 kS/s conversions
within the same ngspice process, instead of reloading the PDK, recompiling, or resetting the circuit for every input point.

- Input changes start approximately 10 ns after the preceding real `data_valid` and finish in 1 ns, within the next acquisition window.
- By default, one conversion is discarded and one retained per input to expose and mitigate previous-value history effects.
- Between batches, the operating point is recomputed and the circuit reset, so the previous input point is explicitly replayed before applying the same warmup.
  **This remains a finite-history protocol, not an infinite continuous ramp that never resets.**
- All `data_valid` events are checked against SPICE time, not `$realtime`, which may stay zero in the Verilator shim.
- The actual SPICE 12-bit output-voltage bus is decoded again and must agree with the RTL log.
- A timed-out log does not count as a complete batch even if it already contains correct codes; original logs and all attempts are retained.
- `worker.lock` limits each campaign to one worker. The current shared container also schedules only one ADC ngspice worker.

`baseline` uses reltol=1e-5, vntol=10 nV, abstol=0.1 pA, and a 2 ns maximum timestep;
`strict` uses reltol=1e-6, vntol=1 nV, abstol=0.01 pA, and a 1 ns maximum timestep.
These profiles only provide entry points for cross-checking numerical settings; one stricter run is not automatically a convergence proof.

## Running

Execute in the `sky130-v2-resume-20260910` container. Every new plan must use a directory that does not already exist.
By default, `run` **executes only one batch**, preventing an accidental multiday full-range test.

```sh
python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py plan \
  /repo/v2/analog/adc/verification_20260910/campaigns/example_smoke \
  --stage smoke --inputs 0.123 -0.000048828125 0.000048828125 \
  --batch-size 3 --warmup 1

python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py run \
  /repo/v2/analog/adc/verification_20260910/campaigns/example_smoke \
  --max-batches 1 --timeout-seconds 900

python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py collect \
  /repo/v2/analog/adc/verification_20260910/campaigns/example_smoke
```

If the runner is later modified, use the campaign's frozen
`frozen/static_campaign.py run|collect <campaign>`. New versions refuse to apply new analysis semantics to old campaigns.
`--retry-incomplete` creates a new attempt without overwriting failures. Completed batches are skipped by default.
If an interruption leaves `worker.lock`, confirm that the original worker has exited before removing that exact lock file; do not race concurrent workers.

Before starting full coverage, record short-batch throughput and approve a reasonable compute budget. The commands below create plans only; they do not launch long runs:

```sh
python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py plan \
  /repo/v2/analog/adc/verification_20260910/campaigns/full_centres \
  --stage centres --batch-size 8 --warmup 1
python3 /repo/v2/analog/adc/verification_20260910/static_campaign.py plan \
  /repo/v2/analog/adc/verification_20260910/campaigns/full_ramp32 \
  --stage ramp --steps-per-lsb 32 --batch-size 8 --warmup 1
```

The collector rereads raw waveforms instead of trusting a summary's PASS string alone.
Missing batches, duplicate input IDs, modified source/raw results, incomplete waveforms, and count mismatches all fail the integrity gate.

## Reviewable evidence from this round

- `campaigns/nominal_static_subset`: 3 inputs were planned, but only the first actually completed, yielding
  **INCOMPLETE_COVERAGE, 1/3**. One complete conversion at 0.123 V returned 2677, consistent with the SPICE output bus.
  The entire process for the 12 µs transient took **43.079 s**; this value is not the transient-only CPU time.
- `campaigns/continuous_three_point`: **all 6 real conversions completed in one process**,
  with raw outputs `[2677,2677,2047,2047,2048,2048]`. Inputs were
  0.123 V, −48.828125 µV, and +48.828125 µV, each repeated twice with the latter retained.
  All three retained codes equaled the ideal codes, giving **3/3 coverage, SMOKE_POINTS_COMPLETE_NOT_LINEARITY**.
  This is evidence of continuous input changes and local thresholds, not all-code or noise-limited accuracy qualification.
- `test_static_campaign.py`: 13 synthetic-data software tests cover rejection of missing codes, nonmonotonicity, nonlinearity,
  modified plans, missing coverage, timeout, and actual output-bus disagreement.
  **These synthetic data are never SKY130 simulation results.**
- `profile_runtime.py`: separately runs an OP-only workload using the same circuit as a completed batch, recording
  compilation and model-loading-plus-operating-point process times. Any transient-time estimate derived from it is explicitly labeled an extrapolation, not a direct measurement.

### Measured runtime cost rather than assumed immediate full coverage

The **62 µs** waveform containing six consecutive conversions took **210.515 s**; one RTL compilation took **0.592 s**.
Starting a separate model-load＋OP process for the same ADC took **2.836 s**. Subtracting that gives
an estimated transient-plus-output time of approximately **207.679 s**, not a direct measurement of solver-internal CPU time.
The first OP-only fixture failed timing qualification because it had not saved the printed nodes. Its original record remains;
the second attempt succeeded after correcting only the `.save` list, without changing the analog circuit.

Extrapolating from the very small throughput sample of these three inputs, using batch=8 with one discarded frame per point and cross-batch replay:

| Plan | Estimated one-worker runtime at one PVT condition |
|---|---:|
| 4096 code centers, 8703 conversions | Approximately 3.50 days |
| 32 points/LSB ramp, 278530 conversions | Approximately 112.12 days |

These are not promised completion times; inputs, process corners, timesteps, convergence, and machine load can all affect throughput.
Therefore, **no long run was started**. Source-level batching amortizes compilation and PDK loading, but real transient solution remains the principal cost.
Next, review timestep optimization qualified by numerical-convergence checks, or an adaptive search retaining the same threshold uncertainty.
The sampling grid must not be silently reduced, and CDAC-only calculations cannot replace the complete SAR.

`summarize_evidence.py` reruns the frozen raw-waveform audit, executes software tests, and generates a hash-indexed
`results/<timestamp>/summary.json`, where `all_non_cadence_work_complete` is explicitly false.

## Subsequent bounded timestep-acceleration experiment: 10 ns did not qualify for the complete waveform

Only two real simulations were run: a **2 ns baseline** with added DAC/reference observations and a **10 ns maximum-timestep comparison**.
Both used the same frozen analog circuit, core RTL, PDK, tolerances, input sequence, 1 ns clock/input edges, and
62 µs duration. Only saved nodes were added and the `.tran` maximum-timestep parameter changed; no 20 ns run occurred.

`timestep_results/20260910T063430835346Z/comparison.json` is the final decision for this pair of experiments.
`manifest.json` is the declaration snapshot captured at launch; its initial RUNNING field is not the final status.

| Comparison | 2 ns | 10 ns |
|---|---:|---:|
| Actual whole-process time | 198.762 s | 179.991 s |
| Accepted waveform points | 96,923 | 75,132 |
| Steps below 100 ps | 60,704 | 60,699 |
| Six output codes | 2677,2677,2047,2047,2048,2048 | Identical |

Acceleration was only **1.104×, an approximately 9.4% runtime reduction**, not the 5× implied by the maximum-step ratio.
The 2 ns baseline's median timestep was only **12.08 ps**. Of all steps, 47.2% fell within
20 ns windows after evaluate transitions, although these windows occupy only approximately 4.7% of simulated duration. Relaxing the upper bound mainly reduced flat-region sampling;
fine steps around switching barely changed. This is timestep-density evidence, not a CPU profile, and cannot determine
how much CPU was consumed by `d_cosim`, Newton iterations, or rejected steps.

Every original column of the 2 ns waveform with added observations was elementwise identical to the old waveform, confirming that observation did not change the old trajectory.
The actual analog comparison also checked more than output codes:

- Before all 72 comparisons, the maximum differential DAC difference was **2.066 nV**, below the predefined 0.05 LSB＝9.765625 µV threshold.
- The maximum precomparison RP/RN difference was approximately **9.95 pV**; the maximum reference difference on the full-duration common 1 ns grid was approximately **0.984 µV**.
- Timing comparisons for six valid outputs and 72 evaluate events all passed the 1 ns tolerance.
- **The maximum difference across the entire DAC waveform on the common grid was 69.509 µV＝0.356 LSB, above the predefined 0.05 LSB threshold.**
  The worst point occurred at 1.286 µs during the first acquisition; later conversions also had brief differences above 0.05 LSB.

The final status is therefore **TIMESTEP_COMPARISON_FAIL**. The default remains 2 ns; 10 ns has not been promoted to a general setting.
This means the relaxed timestep failed this complete-waveform numerical comparison, not that the ADC gained or lost final electrical qualification.

`summarize_timestep.py` further separates the resampling component from the residual relative to the 2 ns reference curve. At the worst common-grid point,
reference resampling alone contributes approximately **0.167 µV**, with a remaining residual of approximately **−69.675 µV**. The failure cannot be explained purely as an interpolation artifact.
The experiment still provides no exact continuous solution, and the 1 ns grid may miss narrower glitches. Identical codes and small precomparison errors
provide only local evidence for these three inputs at this process/voltage/temperature condition, not proof of all-code, PVT, mismatch, or noise accuracy.

There are now **16 software tests** (the original 13＋3 timestep-fixture tests). Both real experiments have ended;
no additional simulation or all-code scan was launched.

### Final prerequisite check for the charge-tolerance route: no modified-tolerance experiment started

The bounded experiment was conditioned on relaxing `chgtol=1e-18` to `1e-17`. However, the frozen ADC deck does not
explicitly set chgtol, so the tolerance of a different frontend testbench cannot simply be assumed.

The initial load-only option print showed an uninitialized default structure before analysis:
even reltol and the integration method had not been applied from the deck, so it was not valid runtime-configuration evidence.
A subsequent short OP run of the same frozen circuit, followed by option printing, confirmed:

| Effective option | Value |
|---|---:|
| Integration method | GEAR |
| reltol | 1e-5 |
| abstol | 1e-13 A |
| vntol | 1e-8 V |
| **chgtol** | **1e-14 C** |
| trtol | 1, automatically reduced by XSPICE |

Actual evidence is in `option_probes/20260910T064511260501Z/native.log`,
with probe program `probe_options.py --after-op`. The original deck, PDK, and RTL remain unchanged.

The baseline **is not 1e-18**, so the task's explicit prerequisite required stopping: **no new-tolerance transient was run**,
and chgtol was not changed to 1e-17. Relative to the actual 1e-14, this would tighten the tolerance 1000-fold rather than relax it 10-fold;
it cannot be presented as the planned acceleration experiment.

## Still incomplete

There is no complete 4096-code-center scan, 131073-point ramp, convergence check across numerical settings, 45-PVT static coverage,
dynamic accuracy with real time-varying device noise, full ADC mismatch, frontend integration, or ADC layout/PEX.
This advances real verification capability and small-scale circuit evidence; it must not be described as completion of all work that does not require Cadence.
