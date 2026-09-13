# ADC all-code acceleration closure experiment (2026-09-11)

## Conclusion

This round identified a technique that is **effective but insufficient to resolve the all-code computational cost**: replace point-by-point fitting of 33 digital-bridge waveforms with records containing only the start and end of logic edges. The PWL point count fell from 120,372 to 800 (a 150.465-fold reduction). The real SKY130 CDAC, switches, phase circuit, preamplifier, and dynamic comparator were not replaced by models.

However, six real conversions still required 178.086 s, compared with 180.284 s for the live RTL baseline after fixing the 33-bit shim: only a **1.012-fold** speedup. More importantly, the complete CDAC waveforms failed the original 0.05 LSB numerical-equivalence gate:

- 0.05 LSB = 9.765625 µV;
- On the union of the two solvers' accepted-point grids, the worst CDAC difference was 527.880 µV;
- On the 1 ns common grid used by the earlier experiment, the worst difference was still 53.542 µV;
- At the 72 predecision checkpoints, the worst difference was only 0.267 nV, and all 72/72 decisions agreed.

Therefore, **the long 131,073-point all-code job cannot be started, and the complete ADC cannot be declared qualified**. `gate.py` remains fail-closed; it should currently reject the long job with exit code 2.

## Work actually completed

### 1. The repaired 33-bit bridge is the sole reference

The reference is `closure_20260911/results/20260911T081221912898Z_bridge_fixed/`: it uses the locally repaired `uint64_t(1) << i` output mask, with the original SKY130 analog core and SAR RTL unchanged. This directory does not write to `/foss`, copy the PDK, or modify the frozen circuit.

Event compression first reconstructs every 1 ns rising/falling edge from the reference waveform's 0.9 V crossings. Before starting SPICE, it reconstructs all 33 sources at every saved accepted point of the reference. The maximum error is 17.264 nV, approximately 0.0000884 LSB, below the 0.05 LSB threshold.

### 2. Real-circuit experiment with a known trajectory

Directory: `results/20260911T082551662858Z_known/`

- All six conversions and 72 real comparator decisions agreed;
- The real phase circuit, CDAC, switches, reference network, preamplifier, and dynamic comparator were retained;
- Measured runtime: 178.086 s, 96,936 accepted timepoints, and 322,957 iterations;
- The PWL point count decreased substantially, but matrix computation barely changed;
- The complete-waveform 0.05 LSB gate failed, so this route cannot be promoted to an all-code qualification path.

This identifies the bottleneck as loading, factoring, and solving the many nonlinear transistor equations in each real conversion, rather than simply an excessively long PWL file.

### 3. Independent bit-by-bit prediction for entirely new inputs

Directory: `results/20260911T083114860787Z_predicted/`

Six ideal code centers absent from the old trajectories were used:

| Differential input | Predicted code |
|---:|---:|
| +0.18603515625 V | 3000 |
| −0.08720703125 V | 1601 |
| −0.02744140625 V | 1907 |
| +0.03037109375 V | 2203 |
| +0.09951171875 V | 2557 |
| +0.24677734375 V | 3311 |

Digital trial codes were generated in advance using the recurrence of the frozen SAR RTL, but no voltage source drove Q/QB. The real comparator had to independently accept each prediction in every read window:

- 72/72 real Q/QB decisions accepted the predictions;
- All six timing windows were complete;
- Deliberately flipping frame 1's predicted LSB reduced acceptance to 71/72; the negative test successfully rejected the incorrect trajectory;
- Measured runtime: 184.284 s and 97,247 accepted timepoints.

This is a **conditional certificate for six inputs and a finite trajectory**. It establishes that, if every predicted bit is accepted by the real comparator, the control trajectory written in advance is equivalent to live RTL for that trajectory. It does not establish correctness for all 131,073 inputs, nor prove that live RTL remained in the feedback loop of this simulation.

## Why the bit-by-bit proof holds

For each 12-bit conversion:

1. Base case: before the MSB decision, both the frozen RTL and predicted trajectory set `trial_code` to `0x800`.
2. Inductive hypothesis: before deciding bit `b`, the predicted trajectory has the same high-bit prefix as the frozen RTL, sets the current bit to 1, and clears lower bits.
3. The real dynamic comparator produces Q/QB. This round does not trust the software prediction; it checks valid complementary levels point by point in the ±10 ns window in which the RTL would read them.
4. If the real decision equals the predicted bit, the frozen RTL's `decided_code` retains or clears the current bit and sets the next bit to 1. This is exactly the next predicted `trial_code` segment.
5. By induction, if all 12 decisions are accepted, the final data word equals the predicted word.

All 72 steps across six frames were individually verified. The negative test confirms that the certificate does not accept arbitrary supplied predictions.

## Two retained failures

The real processes `20260911T082931655937Z_predicted` and `20260911T083032868118Z_predicted` both stopped at 3.503 µs, with ngspice reporting a minimum timestep of 2.5e−21 s. Changing the first input did not move the failure. The eventual diagnosis was that a newly generated trial time differed from a sample time reconstructed from the reference by only approximately 2.5e−19 s, creating artificially near-coincident PWL breakpoints.

The final script makes trial/data reuse exactly the same event-time grid as the frozen bridge. Only the final experiment completed. Both failures' netlists, partial waveforms, and logs remain preserved.

`20260911T082521485574Z_known` was a PATH configuration error: no ngspice process started, so it does not count toward the limit of four real SPICE runs.

## Quantified bottleneck and lower bounds

Within the known-trajectory experiment's 173.446 s analysis time:

- Matrix loading, factoring, and solving totaled 153.797 s, or 88.67%;
- Total wall time exceeded analysis time by only 4.640 s;
- Even assuming all saved-node and output costs were removed, the optimistic speedup ceiling is only approximately 1.027-fold;
- One raw six-conversion waveform occupies approximately 95 MB. Full coverage with the same saved signals would produce approximately 2.08 TB, so a formal long run must save less data. This primarily solves storage, not solver time.

The all-code static grid remains 4096×32+1 = 131,073 inputs, requiring 1,572,876 real comparator decisions. Linear extrapolation from this round's 178.086 s / 6 conversions gives:

- Approximately 45.03 days of optimistic continuous operation with one worker;
- Approximately 43.85 days even with every non-analysis cost removed;
- Approximately 96.86 days for the existing resumable batch=8 scheme, including history replay/warmup.

These are engineering lower bounds/extrapolations, not completion promises. Tighter error settings are generally slower. The earlier maximum-timestep experiment from 2 ns→10 ns achieved only approximately 1.104-fold acceleration while introducing approximately 0.356 LSB CDAC waveform difference; it also fails the numerical gate.

## Verification and continuation

From `/repo` in the existing configured container:

```sh
python3 -m unittest discover -s v2/analog/adc/acceleration_20260911 -p 'test_*.py' -v
python3 v2/analog/adc/acceleration_20260911/build_delivery.py
python3 v2/analog/adc/acceleration_20260911/gate.py
```

The last command must currently print `long_all_code_campaign_allowed: false` and exit with code 2. This is not a script failure; it prevents finite predictions or behavioral-model all-code results from being presented as transistor-level all-code verification.

Primary machine-readable evidence:

- `results/delivery_report.json`: conclusions, runtimes, error gates, prediction certificates, and computational lower bounds;
- `manifest.json`: SHA-256 and byte count for every file in this directory except itself and Python caches;
- Each `results/*/adc.spice`: the complete netlist snapshot actually executed;
- Each `results/*/simulation.log`, `native.log`, and `waveform.dat`: raw logs and waveforms.

Cadence was not used. ADC all-code linearity, noise, mismatch, PVT, and layout qualification remain incomplete, with no tapeout or silicon-measurement claims.
