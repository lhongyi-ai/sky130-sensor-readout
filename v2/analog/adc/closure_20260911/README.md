# ADC closure without Cadence: bounded experiments on 2026-09-11

This round repaired a real digital/analog cosimulation interface defect, completed performance profiling, and evaluated unsuccessful routes. **All-code ADC qualification remains incomplete, and the computational cost of all-code transistor simulation remains unresolved.** Neither the coverage requirement of 4096 codes at 32 points per LSB nor the 0.05 LSB numerical-comparison threshold was relaxed.

## Unchanged objects

The frozen object remains the composite ADC in `verification_20260910/campaigns/continuous_three_point/frozen/`: the preamplifier, LVT reference switches, four-MOS dummy top-plate clamps, and real dynamic comparator from 20260908T045601001817Z. The SAR RTL, phase circuit, and all ADC transistors remain unchanged. All three runs used TT, 1.8 V, 27 °C, 350 Ω per input, 1 Ω＋10 nF reference sources, 62 µs duration, identical 1 ns input/clock edges, a 2 ns maximum timestep, and identical error tolerances.

Only three inputs were used: 0.123 V, −0.25 LSB, and +0.25 LSB, each with two real conversions. LSB = 0.8/4096 V. The runs did not cover three frontend gains, noise, mismatch, 45 process/voltage/temperature combinations, or a complete analog layout.

## Three measured runs

| Experiment | Measured runtime | Accepted timepoints | Actual comparator decisions | Complete-waveform 0.05 LSB gate |
|---|---:|---:|---|---|
| Original bridge with live RTL; complete output observation added | 196.556 s | 96,923 | 72/72; identical to the old baseline | Difference of 0 from the old 2 ns baseline |
| Only the testbench digital bridge replaced by known-trajectory PWL | 334.741 s | 210,312 | 72/72 accepted the known trajectory | **Failed**: maximum CDAC difference 375.723 µV |
| Locally repaired 33-bit bridge output mask, live RTL | 180.284 s | 96,947 | 72/72; actual output codes agreed | **Failed**: maximum CDAC difference 53.452 µV |

The strict threshold is 9.765625 µV. Common timepoints use a 1 ns interpolated grid across the full duration, with additional CDAC/reference checks 1 ns before each of 72 real EVAL rising edges. PWL replay's maximum predecision CDAC difference was only 0.311 nV; the repaired bridge's maximum predecision difference was only 6.60 pV. Small predecision differences and identical output codes **do not erase the complete-waveform gate failure**. The 1 ns common grid itself may miss shorter spikes and therefore is not a continuous-time mathematical proof.

These were single runs on the same host, possibly concurrent with other team work. Runtime is only a measured engineering budget; the approximately 1.09-fold runtime change in the third run is not presented as proven acceleration.

## Real defect identified and locally repaired

The frozen wrapper packs 33 digital bits into one output: bit 32 is ready and bit 31 is busy. The installed ngspice-47 `verilator_shim.cpp` scans output using `1 << i`. Here `1` is a narrow signed integer: shifting by 32 invokes undefined behavior, and sign extension of bit 31 may also affect a 64-bit port.

With the original bridge, measured ready followed the least-significant evaluate bit exactly and busy stayed high, contradicting the internal RTL ready/busy signals. In a minimal C++ reproduction with 1089 bit checks across 33 one-hot words, the old expression produced 3 errors; explicit `uint64_t(1) << i` produced 0. The specific observed outcome of the old undefined behavior applies only to the recorded compiler/platform, not inevitably to every platform.

Within its own directory, this round replaced only the two shim output masks with `uint64_t(1) << i`, then relinked the hash-locked Verilator objects. **The `/foss` installation, original wrapper, RTL, and analog core were not modified.** No claim is made that wide inputs, inout, or other shim issues were also fixed.

The repaired real cosimulation confirmed:

- All 26 checks of reset, idle, acquisition, comparison, final-bit, and next-acquisition states passed; ready/busy were complementary on the common grid after 1 µs, with a maximum complementarity error of 0.288 pV.
- The actual exported data pins read `2677, 2677, 2047, 2047, 2048, 2048`, consistent with the real comparator's bit-by-bit decisions.
- valid and EVAL timings agreed; the maximum reference-waveform difference was below 0.394 µV.
- The 53.452 µV complete CDAC waveform difference described above remains. Finer timestep/error-tolerance convergence must be repeated on the repaired bridge before complete numerical qualification can be claimed.

**The old bridge qualification record has a coverage gap for the two highest status bits.** This result does not invalidate the limited conversion data that depend only on the correct lower 31 bits, but the old record cannot establish correct ready/busy behavior or qualification of the full handshake interface. The original records and failures are retained.

Source path and original hash: `/foss/tools/ngspice/share/ngspice/scripts/src/verilator_shim.cpp`, SHA-256 `ddf28192068013b402f1481be2530407036c62a6ac0bf9093fce59f90174c77e`. The affected source excerpt, locally modified source, compile commands, compiler version, reproduction output, reused objects, and binary hashes are stored in the third run's `build/` and `provenance.json`.

## Why the computation problem remains unresolved

The first run contained 3703 circuit equations and 325530 iterations. `rusage all` reported 191.187 s total analysis time, including 118.323 s for matrix loading, 34.029 s for factoring, and 15.180 s for solving; netlist loading took approximately 2.251 s. Most cost lies in nonlinear transient solution, not repeatedly generating RTL or reading the PDK. These timings cannot precisely isolate d_cosim overhead.

PWL replaced only six testbench bridge/controller declaration lines. The real comparator Q/QB, phases, CDAC, sampling switches, and reference network remained, and Q/QB were never driven by voltage sources. Input bits came from the first run's existing trajectory, so this establishes only **known-trajectory replay**, with no prediction capability for new inputs. Actual Q/QB must retain valid complementary logic in every decision window and independently accept every predicted bit for this limited replay evidence to remain valid. The software test that deliberately flips a predicted bit is rejected.

Replay used piecewise-linear compression with a 1e−10 V error bound, yet the 33 channels still retained 120372 PWL points. Accepted timepoints increased to 210312, and matrix loading increased to 204.210 s. Many PWL breakpoints/source evaluations are a plausible cause of the slowdown, and the numerical trajectory changed as well. Without an isolated experiment, the precise cause has not been proven. Compression retaining only digital-event edges, or relaxing digital-replay compression error, may be future routes. This round neither verified prediction for new inputs nor passed the strict complete-waveform gate, so this route cannot replace real all-code conversions.

### Limits of two-stage methods and state saving

An extracted CDAC capacitance/threshold network combined with all-code RTL can provide submodule static evidence, but not full-ADC all-code transient evidence. Equivalence would require a uniform error bound over every input and history, covering real-switch charge injection/feedthrough, comparator dynamic offset and memory, CDAC/reference settling, and input history, followed by proof that these errors cannot change any bit decision. Near-threshold decisions may be arbitrarily sensitive; a finite-sample fit or isolated capacitor-weight formula provides no such proof. No such model or error bound currently exists, so two-stage results cannot replace this task's all-code verification.

ngspice does have snapshot functionality, but its manual explicitly states that `snsave/snload` does not support circuits with XSPICE devices. This live fixture contains `d_cosim`, `adc_bridge`, and `dac_bridge`, so supported snapshot restoration cannot directly bypass its state history. A new fixture without XSPICE could potentially be studied for snapshots, but different inputs' sampling charge and histories cannot automatically share one state, and this round's PWL equivalence gate failed. [ngspice snapshot command manual](https://nmg.gitlab.io/ngspice-manual/interactiveinterpreter/commands/snsave__saveasnapshotfile.html), [official complete manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf).

Independent batches can run in parallel, but each starts from OP/reset and replays the previous point; they do not seamlessly preserve infinite history. Memory and shared CPU also constrain parallelism. Linear estimates after the bridge repair, using 180.284 s / 6 conversions, are:

| Coverage | Batch size | Total real conversions, including warmup/history replay | One worker / one PVT | Ideal lower bound with 3 workers |
|---|---:|---:|---:|---:|
| 4096 code centers | 3 | 9557 | 3.32 days | 1.11 days |
| 32 points/LSB, 131073 inputs | 3 | 305836 | 106.36 days | 35.45 days |
| 32 points/LSB, 131073 inputs | 8 | 278530 | 96.86 days | 32.29 days |

These are not promises. They include loading/output time apportioned across six conversions, without precisely extrapolating each batch's fixed overhead; stricter numerical settings may be slower. They cover only one process/voltage/temperature condition and are not a full-PVT budget. Parallelism does not change total computation and is insufficient to bring the problem within a reasonable runtime for this round, so no multiday job was launched.

## Resumable delivery and safeguards against false completion

`resume_campaign.py` reuses the old runner's source/PDK/binary hashes, single-worker lock, retained per-batch failures, and explicit retry mechanism. New plans are created only in this directory and bind the locally repaired binary, no longer automatically invoking the defective old shim compiler path. Each explicit run is limited to one batch and 360 s.

`campaigns/fixed_ramp32/` contains a complete plan for 131073 points at 32 points per LSB, but **no points have run**. Coverage returns `INCOMPLETE_COVERAGE`, 0/131073. Because the repaired bridge failed the strict numerical gate, the run entry point reports `NUMERICAL_GATE_BLOCKED` before starting any SPICE process. This is an intentional quality gate; do not remove it to obtain a completion claim. First obtain qualifying new numerical evidence, then create a new immutable plan; this round's results must not be modified.

Run the following in `/repo` inside the configured container, without downloading tools again:

```sh
python3 -m unittest discover -s v2/analog/adc/closure_20260911 -p 'test_*.py' -v
python3 v2/analog/adc/closure_20260911/resume_campaign.py collect v2/analog/adc/closure_20260911/campaigns/fixed_ramp32
# This should currently be rejected before simulation starts:
python3 v2/analog/adc/closure_20260911/resume_campaign.py run v2/analog/adc/closure_20260911/campaigns/fixed_ramp32
```

18 software/saved-waveform regressions passed, covering rejection of incorrect predicted bits, incomplete word lists, and an artificial 0.06 LSB waveform error; detection of the old status-port defect; preservation of the full grid; and refusal to run without numerical qualification. **18 software tests are not 18 new circuit qualifications.**

The main result index is `results/feasibility_and_bridge_report.json`, which includes saved output from the first 14 tests. The final 18 tests and resume-entry audit are in `results/delivery_audit.json`. The three runs are `20260911T080054695882Z_live`, `20260911T080430354263Z_replay`, and `20260911T081221912898Z_bridge_fixed`. Raw waveforms, netlists, logs, parameters, and results are retained. There is no claim of completed Cadence work, layout, tapeout, or silicon measurement.
