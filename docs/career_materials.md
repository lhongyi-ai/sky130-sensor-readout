# SKY130 Two-Stage OTA Career Materials

> Scope: all results below are **schematic-level simulated only**, not tapeout measurements, post-layout simulations, or silicon validation. The circuit uses an ideal external 10 µA `IREF`. The core metrics were evaluated at 13 PVT points; settling, CMRR, PSRR, ICMR, output swing, and noise received nominal characterization only. The output swing is 0.18–1.63 V, covering the frozen specification's required 0.3–1.5 V interval.

## Resume bullets

- Designed and automated verification of a two-stage Miller-compensated OTA using SKY130A 1.8 V devices; generated and audited 171 ngspice tests. With the frozen 5 pF ∥ 100 kΩ load, all six core hard requirements—A0, UGB, PM, quiescent power, SR+, and SR−—passed at all 13 PVT points. Worst-case results were 65.54 dB, 14.55 MHz, 66.25°, 302.71 µW, and 7.98/11.20 V/µs, respectively.
- Selected a 3 pF Miller capacitor and 2 kΩ nulling resistor through a parameterized compensation sweep, raising nominal PM from 33.22° to 69.08° (+35.86°) while maintaining approximately 16.75 MHz UGB. Characterized settling, CMRR, PSRR, ICMR, output swing, and noise, and explicitly documented PSRR+/PSRR− of 36.33/36.25 dB and an ICMR upper limit of 1.22 V, which miss the frozen 45 dB and 1.3 V hard requirements.

## Approximately 90-second project introduction

I designed a two-stage CMOS OTA using SKY130A 1.8 V standard-threshold devices. The first stage uses an NMOS differential pair and a PMOS current-mirror load to convert a differential input into a single-ended output. The second stage is a common-source gain stage. M8 through M10 establish the bias from a single external 10 µA reference. A 3 pF Miller capacitor and a 2 kΩ series nulling resistor compensate the two stages.

The focus was to freeze the specifications and measurement definitions first, then make the design process reproducible. I characterized the devices and current mirror, sized the first and second stages, and checked their operating points and headroom. I then swept the compensation parameters and increased the phase margin from 33.22° to 69.08°. Finally, I automatically generated, ran, and audited 171 ngspice tests, including six core metrics across 13 PVT points. The worst PVT results still provided 65.54 dB gain, 14.55 MHz UGB, and 66.25° phase margin, with power no greater than 302.71 µW and positive and negative slew rates of at least 7.98 and 11.20 V/µs.

I retained the failures as well as the passing results. Nominal CMRR was 71.32 dB, but PSRR+ and PSRR− were only about 36 dB. The low end of the ICMR met its requirement, while the high end reached only 1.22 V instead of the required 1.3 V. All results are schematic-level simulations using an ideal external reference current. They do not yet include mismatch, Monte Carlo, layout parasitics, or silicon measurements. These limitations define the next optimization and verification steps.

## Interview questions and answers

### 1. What are the OTA topology and signal path?

M1/M2 form the NMOS differential input pair. M3/M4 are the PMOS current-mirror active load, converting differential current into a voltage at the first-stage single-ended node `VX`. M6 is the second-stage NMOS common-source transistor, and M7 is its PMOS current-source load; the output node is `VOUT`. The compensation branch runs from `VX` through the 2 kΩ `RZ`, an intermediate node, and the 3 pF `CC` to `VOUT`. M8–M10 establish the bias from a single external 10 µA `IREF`. Loop-break elements, loads, and stimulus sources in the testbench are not part of the OTA core.

### 2. Why call it an OTA rather than a complete operational amplifier?

It has two stages of voltage gain but no dedicated low-output-impedance buffer. The common-source stage drives the output directly, so OTA is the more precise description. It can be configured as a unity-gain follower in a testbench for transient measurements; this does not mean that the circuit contains an internal closed loop or output buffer.

### 3. How does a single 10 µA `IREF` establish the bias, and what are its limitations?

M8 is a diode-connected PMOS; the external 10 µA current establishes `VBP`. M9 mirrors that current into an internal branch, and diode-connected M10 generates `VBN`. `VBN` biases tail-current transistor M5, while `VBP` also biases second-stage load M7. This provides a simple interface and a consistent bias chain. The limitation is that this project treats `IREF` as ideal and excludes the PVT variation, noise, and mismatch of a real reference generator.

### 4. How did you determine device sizes instead of tuning blindly?

I first characterized devices and current mirrors using the SKY130 models, examining `gm/ID`, `gm/gds`, `VDSAT`, current error, and compliance. Initial branch sizes followed gain, speed, current, and swing budgets. I then checked first-stage gain and common-mode headroom, second-stage DC balance, and saturation margins for every device before sweeping the compensation network in the complete OTA. Each iteration changed only a few explainable variables and retained its raw data and failures.

### 5. What does the 3 pF Miller capacitor do here?

`CC` connects the high-impedance first-stage node `VX` to the output. It lowers the dominant pole and separates the two stage poles to improve closed-loop stability, at the cost of tradeoffs among UGB, transient speed, and load response. The project does not assess stability from the step waveform alone: UGB and PM are calculated at the first downward 0 dB crossing of the signed loop gain.

### 6. Why place a 2 kΩ `RZ` in series with `CC`, and what supports that choice?

A Miller capacitor alone introduces an unfavorable feedforward zero. Series resistor `RZ` moves or cancels that zero to reduce its phase penalty. In the parameter sweep, `CC=3 pF, RZ≈0` produced only 33.22° nominal PM. Adding `RZ=2 kΩ` raised PM to 69.08°, an increase of 35.86°, while UGB remained approximately 16.75 MHz and A0 was essentially unchanged. This combination became the frozen compensation point.

### 7. How do you break the feedback loop without disturbing the DC operating point?

The unity-gain negative-feedback testbench places a very large inductor, `LBREAK=1 GH`, between `VOUT` and the inverting input. It approximates a short at DC to retain the closed-loop bias and an open circuit in AC analysis. An AC test signal is injected through a very large capacitor, `CBREAK=1 GF`, which is open at DC and approximately short in AC analysis. This measures the return ratio at the same operating point. Both elements belong to the testbench, not the OTA circuit.

### 8. Why is the loop gain written as `T=-VOUT/VINN`, and how is PM calculated?

The minus sign explicitly includes the negative-feedback sign convention, putting the low-frequency phase of `T` near 0° and helping avoid a 180° interpretation error. UGB is the frequency of the first downward 0 dB crossing of `|T|`; PM is the unwrapped phase at that frequency plus 180°. Automated checks also require a single valid downward crossing, reject crossings at the frequency-sweep boundary, and confirm that the low-frequency phase is close to 0°.

### 9. Why were these 13 PVT points selected?

The matrix has two parts: TT, FF, SS, FS, and SF process corners at 1.8 V and 27 °C; and TT combinations of 1.62/1.80/1.98 V with −20/27/85 °C. Removing the duplicate nominal point gives 13 points. A0, UGB, PM, power, SR+, and SR− must meet the hard requirements at every point. Missing results, nonconvergence, and invalid numerical results are treated as failures.

### 10. What are the key 13-point PVT results and worst corners?

All six core hard requirements pass. The worst A0 is 65.54 dB and the worst UGB is 14.55 MHz, both at P08 (TT, 1.62 V, 85 °C). The worst PM is 66.25° and the maximum power is 302.71 µW, both at P13 (TT, 1.98 V, 85 °C). The worst SR+ is 7.98 V/µs and the worst SR− is 11.20 V/µs. This passing result applies only to the frozen core PVT scope and must not be extended to every metric or to silicon validation.

### 11. How do you measure slew rate, and why not divide the difference between two points?

The OTA is configured as a unity-gain follower, with an input switching between 0.8 V and 1.2 V and 20 ns edges. SR+ is obtained by a least-squares line fit over the monotonic 20%–80% portion of the output's rising edge. SR− uses the same method over the falling 80%–20% interval and takes the absolute value. A multipoint fit is less sensitive than two samples to time-step placement and edge spikes. Nominal results are 8.20/11.52 V/µs.

### 12. What is the definition and result for 1% settling time?

Time zero is the interpolated instant at which the actual input crosses 50%, not the pulse source's ideal scheduled edge. For a 0.4 V step, the 1% band is the final value ±4 mV. Settling time is the first time the output enters that band and stays within it for the rest of the observation window. Rising and falling results are saved separately and the worse value is used. The worst nominal result is 0.07475 µs, or 74.75 ns, below the 1.5 µs hard limit.

### 13. How is ICMR defined, and why does the current result still fail?

Both inputs are swept together in common mode. At each 10 mV grid point, the test measures small-signal differential gain at 1–10 Hz and the operating regions of M1–M10. A valid point requires gain no more than 3 dB below the 0.9 V reference, nonnegative saturation margins for all relevant devices, and an output that is not close to a supply rail. The reported interval is the largest contiguous valid range containing 0.9 V. The current nominal range is 0.76–1.22 V: the low end meets the ≤0.8 V requirement, but the high end does not reach ≥1.3 V, so the overall result is explicitly `ICMR_FAIL`.

### 14. Why cannot an ICMR sweep replace an output-swing test?

ICMR changes the input common mode and therefore also perturbs input-pair headroom. Output swing should instead be controlled by an independent output command. The test uses a biased inverting closed loop: the noninverting input is fixed at 0.9 V, and equal 10 MΩ input and feedback resistors sweep the output command over the supply range in both directions. Valid points require tracking error ≤10 mV, no clipping, and M6/M7 in their intended operating regions. The contiguous range valid in both sweep directions is 0.18–1.63 V, covering the frozen 0.3–1.5 V requirement.

### 15. How is CMRR measured, and what does the result establish?

At the same nominal bias and frequency, AC inputs of +0.5/−0.5 V first provide a 1 V differential input to measure `Ad`. Both inputs then receive an in-phase 1 V AC stimulus to measure `Acm`. The definition is `CMRR=20log10(|Ad/Acm|)`. The 1 kHz result is 71.32 dB, above the 55 dB hard limit and 65 dB stretch target. It establishes rejection only at nominal conditions and 1 kHz, not the same value over all frequencies or PVT conditions.

### 16. How are PSRR+ and PSRR− measured, and why are they known failures?

At 1 kHz, with the same bias and `Ad`, a 1 V AC disturbance is applied separately to VDD and VSS, and `PSRR=20log10(|Ad/Aps|)` is calculated. The PSRR− test specifically retains an explicit VSS voltage source and the 1.8 V DC relationship. PSRR+ is 36.33 dB and PSRR− is 36.25 dB, both below the 45 dB hard limit. The complete design therefore cannot be described as meeting every specification. The next iteration should improve supply coupling through the bias tree and high-impedance nodes, then rerun stability, power, ICMR, and PVT verification.

### 17. How is noise defined, and how would you report it?

SPICE `.noise` uses the differential input source as the input reference. The input-referred noise density is saved over 10 Hz–1 MHz; integrating its square and taking the square root gives RMS noise. Current nominal values are 401.17 nV/√Hz at 1 kHz and 52.30 µV RMS integrated over 10 Hz–1 MHz. The frozen specification has no hard noise threshold, so the status is `REPORTED`, not `PASS`. The 24 model conductance-reset warnings in the logs are also retained, and the results require further review in later model and layout flows.

### 18. How do you verify stability under different loads?

At TT, 1.8 V, 27 °C, and RL=100 kΩ, CL is set to 1, 2, and 5 pF. Return-ratio and unity-gain transient tests are repeated for each load. The respective phase margins are 94.16°, 86.29°, and 69.08°, all above 55°, and the transients show no sustained or growing oscillation. This verifies the frozen three-point nominal load sweep, not unconditional stability for arbitrary capacitance, resistance, or PVT conditions.

### 19. How is the project reproducible and auditable?

The specifications, test matrix, and measurement definitions are frozen first. Netlists are generated from templates and parameters, and the toolchain uses fixed IIC-OSIC container and PDK versions. All 171 expected Day 4 tests retain generated netlists, raw TSV data, ngspice logs, parsed CSV files, and manifest hashes. Summary tables point back to raw evidence. Log auditing distinguishes normal completion from completion using dynamic-gmin and retains known warnings instead of relying only on process exit codes or deleting failure information.

### 20. What are the main limitations and next steps?

The central boundary is **schematic-level simulated only**. The results do not yet include real reference-current PVT/noise, device mismatch, Monte Carlo, layout, parasitic extraction, package/board effects, or silicon measurements. Settling, CMRR, PSRR, ICMR, output swing, and noise were characterized only at nominal conditions. The immediate priorities are to fix the PSRR and high-end ICMR failures and rerun the full regression. Subsequent work should add the reference source, statistical simulation, and post-layout simulation, followed by tapeout measurements to validate model correlation.

## Numerical evidence index

- Frozen specification and measurement definitions: [`docs/specification.md`](specification.md), [`results/day4_measurement_definitions.csv`](../results/day4_measurement_definitions.csv)
- Compensation before/after: [`results/day3_compensation_before_after.csv`](../results/day3_compensation_before_after.csv)
- 13-point PVT: [`results/pvt_summary.csv`](../results/pvt_summary.csv)
- Day 4 aggregate results and known failures: [`results/summary.csv`](../results/summary.csv), [`results/day4_nominal_summary.csv`](../results/day4_nominal_summary.csv)
- Load stability and log auditing: [`results/day4_load_stability.csv`](../results/day4_load_stability.csv), [`results/day4_log_audit.csv`](../results/day4_log_audit.csv)
