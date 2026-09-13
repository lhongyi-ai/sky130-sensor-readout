# V2 real SKY130 fully differential frontend prototype

For a first visit, start at the [analog frontend access guide](ACCESS.md), which provides signal diagrams, the current candidate, results, and reproduction paths.

This is **ngspice transistor-level design and module-level experimentation**, not a native Cadence design,
complete chip, complete layout, or silicon measurement. M3/M4 and the overall project cannot currently be declared complete.

## Frozen delivery from this round: FDDA10, frontend qualification failed

Parameter tuning stopped for this round, and `frontend_fdda.spice` was frozen with SHA-256:
`c231e378a499ddee7b950dcdc40714fa16a21b81b29de6fb8798ead36bc125e6`.
Results from that same version are consolidated in `results/frozen_delivery.json`. Best results from different historical versions are not combined.

| Frozen-source test | Measured result | Status |
|---|---|---|
| G16 nominal 81-point DC, three-point fit and independent-point validation | Maximum 1.35887 LSB, target ≤1 LSB | Failed |
| Fixed nominal coefficients, TT/1.62V/85°C | 4.00399 LSB; CM error 74.86 mV | Failed; not rounded to a pass |
| Fixed nominal coefficients, TT/1.98V/−20°C | 2.36960 LSB, target ≤4 LSB | This DC subtest passed |
| G16 real 81.285 pF/side sampling load, 2.476847754 µs acquisition window | CM deviation 125.78 mV; reference window still oscillates by 160–207 mVpp | Stability/settling failed |
| Nominal VDD supply power | Static 1.81624 mW; time-integrated average in the above transient 1.81551 mW | Supply-power measurement only, not a performance pass |
| G16 1 Hz–1 GHz small-signal noise | 108.564 µVrms; 108.901 µVrms after fixed calibration scaling | Static budget screening only |
| G1/G4 operating points and 1 kHz small-signal gain | 0.99017/3.99211, correct polarity | Basic connectivity/polarity subtest only |

The static VCM reference terminal absorbs approximately 16.83 µW, reported separately rather than subtracted from the VDD budget to claim an advantage.
The first Gear/5 ns sampling simulation terminated numerically, and its failure log is retained. A retry with the same source and stimulus at a 2 ns timestep
completed and measured oscillation. Neither numerical termination nor the mean of a nonstationary window was treated as pass evidence.

Although static noise is below the provisional 113 µV frontend budget, **this operating point has not passed dynamic stability**,
so it does not establish effective accuracy or 65 dB SNDR. Loop injection is also diagnostic only: the differential-mode primary downward crossing
has a scalar margin of approximately 105.9°, but the common-mode system risks coupled positive feedback/right-half-plane poles, and both curves
cross again at high frequency. Formal qualification of at least 60° for both differential and common modes remains incomplete.

The key remaining design issues are coupling between common-mode feedback and input-pair tail-current modulation, full-scale nonlinearity,
and low-voltage/high-temperature headroom. These circuit issues can be addressed without waiting for Cadence, but
this round cannot be described as completing all non-Cadence work.

## Implemented circuits

Two distinct design tracks exist, neither meeting all specifications. `frontend_pdk.spice` is the measured
resistive-input PGA baseline; `frontend_fdda.spice` is the high-input-impedance improvement candidate under verification.
**Do not include both files together**: their auxiliary subcircuit names overlap.

The resistive-input PGA baseline implements:

- A real fully differential NMOS input stage, cascoded tail-current source, and two common-source output stages.
- Diode-loaded, current-output continuous-time common-mode feedback; not two old OTAs connected together.
- A resistor-degenerated self-biased current source, MOS startup injection, and shutdown, with no external ideal IREF.
- Real SKY130 high-resistance polysilicon resistors and MIM capacitors; all internal R/C elements are PDK devices.
- A low-noise feedback structure with fixed RF=10 kΩ; sensor source impedance remains 350 Ω per side.
- Actual CMOS gain decoding and six transmission gates selecting nominal gains 1/4/16 for 00/01/10.
- An output isolation network jointly tested with the ADC's real transmission gates and 81.285 pF/side MIM array.

`frontend_core.spice` is a retained intermediate version with **real MOS devices but ideal R/C**, and cannot establish
that all devices have a physical implementation. Early unstable versions and failed data remain in `results/`.

## Integration interface

| Subcircuit | Pins and meaning |
|---|---|
| `sky130_v2_frontend` | `INP INN OUTP OUTN VDD VSS VCM`, core without feedback |
| `sky130_v2_pga` | `VINP VINN OUTP OUTN VDD VSS VCM`; static RF/RG parameters |
| `sky130_v2_sample_driver` | Same pins; static GAIN parameter, with 150 Ω/4 pF isolation network |
| `sky130_v2_switchable_pga` | The above 7 pins followed by `SEL0 SEL1`; real switches, supports an external isolation network |

The digital controller should latch and hold the two selection bits at conversion start. 11 is reserved and currently
disconnects the sensor input branch; **its handling has not yet been aligned with the digital module's invalid-code handling**. Runtime gain switching,
control-signal injection, and nonoverlap timing remain unverified.

Early switch on-resistance reduced the actual gain in the 16 setting to approximately 14.06. After compensating the input branches,
`gm3x_rz` reached a nominal gain near 15.97, correctable by static calibration. However, the 350 Ω sensor source impedance
and switch on-resistance enter the gain formula, and temperature/supply changes cause severe failure of fixed nominal coefficients.

### High-input-impedance FDDA improvement

`frontend_fdda.spice` retains two fully differential stages, real resistive feedback, and continuous-time common-mode feedback,
while replacing the first amplifier stage with two cross-summed differential error pairs comparing `VINP−FBP`
and `VINN−FBN`. Sensors connect to transistor gates, retaining 350 Ω source impedance per side. 16 identical PDK resistors
from each output to VCM provide 1/4/16 taps. Real transmission gates select only high-impedance feedback gates, so
switch Ron and source impedance no longer directly set DC gain. This is not two old OTAs joined together.

The additional error pair increases input-stage power and area. Feedback-resistor thermal noise, low-voltage headroom, and the common-mode loop
must be reverified. The CMFB's 1 kΩ source degeneration was added in response to actual common-mode oscillation; it is not a behavioral model.
The FDDA contains no ideal amplifier, ideal current source, or ideal R/C. Its public interface is
`sky130_v2_switchable_pga VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1`;
`sky130_v2_switchable_sample_driver` has the same pins, plus an `RISO` parameter and 4 pF storage capacitance per side.
The FDDA does not provide the old `sky130_v2_pga` static-parameter interface; run scripts must include `--switchable`.

## Evidence and important failures

- The original CMFB with a high-impedance output node had a correct operating point but severe transient oscillation; the failure is retained.
- Current-output CMFB removed that additional high-impedance node and operates stably with a small nominal load.
- A directly connected 81.285 pF load can fail settling; 5 pF results cannot substitute for it.
- With the early 150 Ω/4 pF isolation network, static gain configurations at all three nominal gains had acquisition settling and post-turnoff hold errors
  below 48.8 µV. Two selected G16 conditions, SS/1.62V/85°C and FF/1.98V/−20°C, also passed;
  **this is not complete PVT across 45 conditions × 3 gains**.
- The real switch-selection network has undergone sampling tests at three gains and an 81-point DC transfer test at gain 16.
  After fitting positive/negative 80% full scale and zero, errors at points excluded from the fit were approximately 0.03 LSB.
  This is frontend static transfer only, not ADC INL/DNL or conversion accuracy with noise.
- Enlarging the input transistors reduced gain-16 static-configuration output noise to approximately 87 µVrms over 1–5 kHz,
  and approximately 107 µVrms over 1–50 kHz, while 1–1 GHz remained approximately 242 µVrms.
  **The broadband noise budget fails**; truncating integration at 5 kHz or 50 kHz cannot support a claim that the system meets 65 dB.
- Actual noise must account for sampling-noise folding, gain-calibration scaling, and reference/comparator noise. The present
  ordinary small-signal noise analysis is not periodic-steady-state/sampled-noise verification of the complete switched circuit.
- The 0.914 mW, 242 µV noise, and 14.06 gain figures above belong to historical versions and cannot be combined with later results.
- `gm3x_rz` increases input transconductance/current 3-fold and retunes the Miller zero. Nominal broadband static
  noise falls to 106.66 µV at 1.219 mW, and the old nominal sampling tests pass at all three gains. However, fixed
  nominal calibration on the same version gives 77.59 and 92.74 LSB at TT/1.62V/85°C and TT/1.98V/−20°C respectively, both failures.
- `gm3x_rz_matrix` completed 135 real frontend sampling subtests across 5 corners × 3 voltages × 3 temperatures × 3 gains.
  The old report counted 64 passes; independent numerical auditing corrected this to 63 passes and 72 failures. The old report is retained,
  with corrections in `results/legacy_measurement_audit.json`. This is not 135 full-chain qualification tests, and completing the matrix
  does not mean PVT passed.
- The frozen snapshot of stable FDDA5 is in `results/fdda5_ro/`: G16, actual shortest acquisition window
  2.476847754 µs, Riso 2.2 kΩ per side, maximum pre-aperture error 25.0 µV, maximum error after opening the old top-plate TG
  20.7 µV, and CM error ≤15.9 mV throughout; 0.401 LSB after three-point calibration over 81 points.
  This version consumes 1.519 mW with 131.57 µV broadband static noise, or approximately
  135.23 µV after multiplying by the 1.02781 calibration coefficient, leaving insufficient margin for quantization and ADC noise. **It is still not a qualified final frontend.**
- The rounds of candidates after FDDA5 have concluded with FDDA10 frozen. Use the circuit hash and complete test set of each specific directory;
  do not combine FDDA2's best DC, FDDA5's transient behavior, and another version's noise into one performance record.
- `results/fdda2/AUDIT.md` records a cross-version calibration error in sequential commands. The corresponding cold-end result
  is marked INVALID with original output retained. New scripts enforce identical hashes for calibration and test circuits.

Per-experiment data and version snapshots are the numerical evidence; see `results/frontend_manifest.json` for the index.
Small-signal loop-injection scripts are diagnostic only: the common-mode path contains coupled loops and high-frequency parasitic feedback,
and reliable multiloop stability qualification of at least 60° for both differential and common modes has not been completed.

## Reproducible runs

In the configured IIC-OSIC container, set
`SPICE_USERINIT_DIR=/foss/pdks/sky130A/libs.tech/ngspice`, then run:

```sh
python3 run_frontend.py --gains 1 4 16 --loads 81.285 --out results/new_static
python3 qualify_advanced.py sampling --gain 16 --switchable --out results/new_sample
python3 qualify_advanced.py linearity --gain 16 --switchable --out results/new_dc
python3 qualify_advanced.py noise --gain 16 --switchable --isolation-r 1800 --out results/new_noise
python3 qualify_advanced.py startup --gain 4 --ramp-us 1 --out results/new_startup
python3 qualify_advanced.py sampling --core frontend_fdda.spice --gain 16 --switchable --isolation-r 2800 --transient-method gear --max-step-ns 2 --out results/new_fdda
python3 build_manifest.py
```

Every experiment retains model references, a design snapshot, netlists, logs, raw numerical data, and a summary. Different design
versions/stimuli must use different output directories; existing experiments refuse overwriting. New experiments save an immutable
`experiment_config.json`; `--analyze-only` reads it and rechecks logs, simulation
coverage, data finiteness, and sampler hashes. Old experiments lacking this configuration cannot be relabeled using current defaults.
Historical data are analyzed with an independent audit script without overwriting raw results.
Sampling experiments require the sibling `adc/adc_blocks.spice`, which is copied into an experiment snapshot.
When running several tests sequentially, each `--core` after the first must point to that first test's saved
`frontend_pdk_snapshot.spice`, not a live source that may undergo further tuning.
The default sampling window is now the shortest 2.476847754 µs measured from the real phase circuit; early directories retain
the original 2.49 µs stimulus. All raw results are interpreted against their own netlists; stimuli are not rewritten retrospectively.
Early directories did not explicitly override ngspice numerical tolerances. Newly generated netlists fix reltol=1e-6,
vntol=1 nV, and abstol=10 fA. Frozen candidates must be retested under these stricter tolerances; early results
near the 48.8 µV threshold cannot be treated as having completed numerical-convergence qualification.

`measurements.py` uses time integration for nonuniform-grid averages and interpolates at exact time/frequency
endpoints. Sampling reference windows must also be sufficiently stationary, preventing the mean of persistent oscillation from being called a final value.
The 5 regressions in `python3 -m unittest test_measurements.py` cover these numerical-audit rules.

## Remaining work

Complete sampled noise and SNDR; loop stability under time-varying loads; exact gains and conversion dynamics;
qualified PVT across 45 conditions × three gains; 200 real mismatch runs; fixed-calibration coefficient errors over temperature/voltage; CMRR/PSRR;
startup coverage; reference disturbances; full SAR comparator-kickback cosimulation; native editable Xschem schematics;
and the full frontend layout with DRC/LVS/post-parasitic simulation. Incomplete work is not attributed to unavailable Cadence.

W=800 µm input devices, segmented resistors, and parallel MIM cells still require actual fingered and matched layouts.
A runnable model does not establish DRC-clean complete geometry, and transistor channel area is not chip area.
