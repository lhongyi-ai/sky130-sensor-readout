# Frozen Design Specification

**Revision:** 0.1  
**Status:** Frozen for the five-day schematic-level project  
**Results status:** Day 4 characterization complete. All six core metrics pass
at all 13 PVT points. Nominal settling, CMRR, output swing, and 1/2/5 pF load
stability pass; PSRR+ and PSRR- fail, and the full-OTA 0.76–1.22 V ICMR fails
the 1.3 V high endpoint. Noise is reported without a pass limit.

This document is the authoritative source for pass/fail decisions. A target is
not evidence that the design achieves it.

## 1. Design under test

- Process design kit: SKY130A
- Devices: standard-threshold 1.8 V NFET/PFET models
- Topology: two-stage CMOS OTA with Miller compensation
- Supply pins: `VDD` and `VSS`
- Signal pins: `VINP`, `VINN`, and `VOUT`
- Bias interface: external `IREF`; nominal starting value 10 µA
- All MOS devices are four-terminal devices:
  - NMOS bulk connects to `VSS` unless an explicitly documented well permits otherwise.
  - PMOS bulk connects to `VDD` unless an explicitly documented well permits otherwise.

The circuit is called an OTA because it has no dedicated low-output-resistance
buffer stage. It may be used as a unity-gain op-amp in closed-loop testbenches.

## 2. Reference conditions

Unless a test explicitly overrides a condition:

| Condition | Frozen value |
|---|---:|
| Process corner | TT |
| `VDD - VSS` | 1.80 V |
| Temperature | 27 °C |
| Input common-mode voltage | 0.90 V |
| Load capacitance | 5 pF |
| Load resistance | 100 kΩ |

`CL` and `RL` are connected from `VOUT` to AC ground. The schematic must make
the DC reference of `RL` explicit; the default implementation is `RL` from
`VOUT` to `VSS`. If this reference changes, the specification revision must be
incremented and existing results must not be mixed with the new setup.

## 3. Pass policy

There are three distinct scopes:

1. **Core PVT-qualified metrics:** A0, UGB, PM, quiescent power, SR+, and SR-.
   Project-level pass requires the hard limit at every one of the 13 required
   PVT points with the nominal 5 pF || 100 kΩ load.
2. **Nominal characterization metrics:** settling time, CMRR, PSRR, ICMR,
   output swing, and noise are required only at TT/1.8 V/27 °C.
3. **Nominal load stability:** PM and unity-gain transient stability are checked
   at TT/1.8 V/27 °C for CL = 1 pF, 2 pF, and 5 pF, with RL = 100 kΩ.

A missing, non-convergent, numerically invalid, or silently omitted required run
is a failure, not a pass. Use explicit states such as `NOT_RUN`,
`NO_CONVERGENCE`, `SATURATION`, `GAIN_FAIL`, or `PM_FAIL`.

Stretch targets describe optimization goals and never replace hard limits.
Earlier planning values of 300 µW and 5 V/µs are bonus goals only; they are not
used in the hard or stretch Pass column.

## 4. Frozen performance limits

| Metric | Hard requirement | Stretch target | Scope |
|---|---:|---:|---|
| Open-loop DC gain, A0 | >= 50 dB | >= 60 dB | 13-point PVT |
| Unity-gain bandwidth, UGB | >= 5 MHz | >= 10 MHz | 13-point PVT |
| Phase margin, PM | >= 55° | >= 65° | 13-point PVT |
| Quiescent power | <= 600 µW | <= 400 µW | 13-point PVT |
| Positive slew rate, SR+ | >= 2 V/µs | >= 4 V/µs | 13-point PVT |
| Negative slew rate, SR- | >= 2 V/µs | >= 4 V/µs | 13-point PVT |
| 1% settling time | <= 1.5 µs | <= 1.0 µs | Nominal |
| CMRR at 1 kHz | >= 55 dB | >= 65 dB | Nominal |
| PSRR+ at 1 kHz | >= 45 dB | >= 55 dB | Nominal |
| PSRR- at 1 kHz | >= 45 dB | >= 55 dB | Nominal |
| Input common-mode range | Includes 0.8–1.3 V | Maximize | Nominal |
| Output swing | Includes 0.3–1.5 V | Maximize | Nominal |
| Input-referred noise | Report density and integrated RMS | Lower is better | Nominal |

## 5. Measurement definitions

### 5.1 DC operating point and saturation

At each required operating point, record for every MOS device:

- drain current `ID`;
- `VGS`/`VSG` and `VDS`/`VSD`;
- model-reported `VDSAT`;
- `gm` and `gds`;
- saturation headroom (`VDS - VDSAT` for NMOS, corresponding magnitude for PMOS).

The testbench must converge to the intended bias state. A device that is meant
to act as a current source or gain device but is outside its intended operating
region is flagged `SATURATION`, even if SPICE converges.

### 5.2 Open-loop differential gain, A0

Bias both inputs at the specified common mode. Apply AC +0.5 V to `VINP` and
-0.5 V to `VINN`, so the total differential small-signal stimulus is 1 V.

`Ad(f) = VOUT(f) / (VINP(f) - VINN(f))`

`A0 = 20 log10(|Ad|)` at the low-frequency gain plateau. The automated report
uses 1 Hz unless 1 Hz is not on a settled plateau; any alternate readout
frequency must be stated and used consistently for every corner.

### 5.3 Loop gain, UGB, and phase margin

Use a unity-gain negative-feedback bench that preserves the closed-loop DC
operating point while breaking/injecting the loop for AC return-ratio analysis.
Record the signed loop gain `T(f)` and retain its magnitude and unwrapped phase.

- UGB is the first downward crossing of `|T(f)| = 1` (0 dB).
- PM is `180° + phase(T)` at that crossing under the negative-feedback sign
  convention.
- If there is no valid downward 0 dB crossing, UGB and PM fail.
- PM may not be inferred solely from a closed-loop transient waveform.

The final Bode plot must identify low-frequency gain, the 0 dB crossing, and PM.

### 5.4 Quiescent power

With zero differential input and no time-varying stimulus:

`PQ = (VDD - VSS) * abs(I(VDD source))`

Use the settled DC supply current, including the on-chip bias network represented
in the design under test. Testbench-only ideal-source power is excluded. Report
µW and retain the signed raw source current for traceability.

### 5.5 Slew rate

Connect the OTA as a unity-gain follower and apply a 0.8 V to 1.2 V step, then a
1.2 V to 0.8 V step, using identical finite input rise/fall times. Document those
edge times in the testbench.

- SR+ is the slope of a least-squares line fitted to the monotonic 20%–80%
  portion of the rising output transition.
- SR- is the absolute slope of the corresponding 80%–20% falling transition.
- Numerical spikes at the input edge are excluded.

The 20% and 80% levels refer to the 0.4 V commanded step amplitude.

### 5.6 One-percent settling time

Use the same unity-gain 0.8 V <-> 1.2 V transient. Time zero is the input's 50%
crossing. Settling time is the earliest subsequent time after which

`abs(VOUT - Vfinal) <= 0.01 * 0.4 V = 4 mV`

and the output remains in that band through the measurement window. Report the
worse of rising and falling settling times and retain both values separately.

### 5.7 Input common-mode range

Sweep equal DC input voltages from low to high while keeping the nominal load.
At each common-mode point, preserve a valid output operating point and evaluate
small-signal differential gain. A point is valid only when:

- differential gain is no more than 3 dB below its value at VCM = 0.9 V;
- the intended input-pair and bias current-source devices remain in their
  documented operating regions;
- the output is not clipped or pinned to a rail.

The ICMR is the largest continuous valid interval containing 0.9 V. It passes if
that interval contains the entire 0.8–1.3 V hard range.

### 5.8 Output swing

Output swing must be measured without confusing it with ICMR. Use an offset
inverting closed-loop configuration that holds the non-inverting input at
0.9 V while commanding the output across the supply range; use equal, documented
feedback/input resistors large enough not to dominate the frozen 100 kΩ load.

A commanded output point is valid when:

- `abs(VOUT - VOUT_command) <= 10 mV` after DC convergence;
- there is no clipping;
- output-stage devices retain the documented intended operating condition.

The output swing is the largest continuous valid interval. It passes if it
contains 0.3–1.5 V.

### 5.9 CMRR

At the same bias point and frequency, measure:

- differential gain `Ad` with +0.5/-0.5 V AC input excitation;
- common-mode gain `Acm = VOUT/VCM_AC` with both inputs driven by the same
  1 V AC excitation.

`CMRR(f) = 20 log10(|Ad(f) / Acm(f)|)`

Report the value at 1 kHz and retain the frequency curve.

### 5.10 PSRR+ and PSRR-

Define the supply-to-output transfer as `Aps = VOUT / Vsupply` for a 1 V AC
supply perturbation. Use the differential gain `Ad` measured at the same
frequency and operating point to refer the disturbance to the input:

`PSRR(f) = 20 log10(|Ad(f) / Aps(f)|)`

For PSRR+, perturb `VDD` while `VSS` is AC ground. For PSRR-, perturb `VSS` and
hold all DC source relationships explicit so the intended 1.8 V DC bias is
unchanged. Report both at 1 kHz and retain both frequency curves.

### 5.11 Input-referred noise

Use SPICE noise analysis with the differential input source declared as the
input reference. Report:

- input-referred noise-density curve in V/sqrt(Hz);
- input-referred density at 1 kHz in nV/sqrt(Hz);
- integrated input-referred RMS noise from 10 Hz through 1 MHz in µV RMS.

No noise pass/fail limit is assigned because no application-specific noise
budget was specified.

### 5.12 Load stability

At TT/1.8 V/27 °C, repeat the loop-gain and follower transient tests with
CL = 1 pF, 2 pF, and 5 pF; RL remains 100 kΩ. Each case requires PM >= 55° and
no sustained or growing oscillation. Record overshoot as characterization data.

## 6. Required PVT matrix

Core metrics are evaluated at exactly these 13 points:

1. TT, FF, SS, FS, and SF at 1.80 V and 27 °C (five points).
2. TT at each combination of VDD = 1.62, 1.80, and 1.98 V and temperature =
   -20, 27, and 85 °C (nine points).
3. The duplicated TT/1.80 V/27 °C point is counted once.

The complete matrix is populated in `results/pvt_summary.csv`. Settling, CMRR,
PSRR, ICMR, output swing, and noise are nominal-only in this five-day scope;
their worst-PVT fields say `N/A_NOT_SWEPT`, rather than implying missing data.
The PVT transient benches may retain additional non-qualifying observations.
In the completed campaign P06, P07, and P13 are
`SETTLING_NOT_REACHED` under the absolute ±4 mV definition; these observations
do not change the explicitly six-metric core-PVT pass policy.

## 7. Change control

Any change to a hard limit, measurement definition, load connection, PVT point,
or pass scope requires:

1. a dated entry in `project_log.md`;
2. a new specification revision;
3. regeneration of every affected result;
4. no comparison of results produced under incompatible revisions.

## 8. Recorded qualification outcome

This section records results under Revision 0.1; it does not change any target,
definition, load, PVT point, or pass scope.

| Metric | Recorded result | Status |
|---|---:|---|
| A0 across 13 PVT points | minimum 65.5351 dB (P08) | PASS |
| UGB across 13 PVT points | minimum 14.5527 MHz (P08) | PASS |
| PM across 13 PVT points | minimum 66.2452° (P13) | PASS |
| Power across 13 PVT points | maximum 302.710 µW (P13) | PASS |
| SR+ across 13 PVT points | minimum 7.97766 V/µs (P06) | PASS |
| SR- across 13 PVT points | minimum 11.1958 V/µs (P08) | PASS |
| Nominal 1% settling | 0.07475 µs | PASS |
| Nominal CMRR at 1 kHz | 71.3222 dB | PASS |
| Nominal PSRR+ / PSRR- at 1 kHz | 36.3313 / 36.2510 dB | FAIL / FAIL |
| Nominal full-OTA ICMR | 0.76–1.22 V | FAIL — high endpoint |
| Nominal output swing | 0.18–1.63 V | PASS |
| Nominal input noise | 401.170 nV/√Hz at 1 kHz; 52.3016 µV RMS, 10 Hz–1 MHz | REPORTED |
| Nominal load PM, CL=1/2/5 pF | 94.1626° / 86.2882° / 69.0829° | PASS |

The result authority is `results/summary.csv`; detailed PVT rows are in
`results/pvt_summary.csv`. The result set is schematic-level only, uses an
ideal external 10 µA reference, and includes no mismatch/Monte Carlo, layout,
extraction, post-layout, fabricated-device, or silicon-measurement evidence.
