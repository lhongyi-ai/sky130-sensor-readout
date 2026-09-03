# Initial Design Calculations

**Status:** Day 3 compact M1–M10 sizing and compensation selected at the
nominal TT/1.8 V/27 °C checkpoint; PVT sizing robustness remains unverified.
**Important:** Day 1 values are characterization candidates and Day 2 values
are selected only for the first-stage checkpoint. Day 3 dimensions are the
current nominal complete-OTA choice, not a PVT-qualified or silicon-measured
design.

## 1. Initial design point

The following values are a first point for exploration, not a frozen result:

| Parameter | Initial estimate |
|---|---:|
| `VDD` | 1.8 V |
| `VCM` | 0.9 V |
| `CL` | 5 pF |
| `RL` | 100 kΩ |
| `IREF` | 10 µA |
| Tail current | 40 µA (explore 30–50 µA) |
| Input-pair current | 20 µA/device at zero differential input |
| Second-stage current | 100 µA (explore 80–120 µA) |
| Miller capacitor `CC` | 2.0 pF (explore 1.5–2.5 pF) |
| Input-pair channel length | explore 0.5–1.0 µm |
| Current-source channel length | explore 0.8–1.0 µm |
| Intended inversion | moderate inversion |

Use standard-threshold 1.8 V MOS devices. Day 1 lookup-table widths are recorded
in Section 8; the selected Day 2 M1–M5 implementation is recorded in Section
10.

## 2. Transconductance and bandwidth budget

The first-order Miller-compensated estimate is:

`fu ~= gm1 / (2*pi*CC)`

For `CC = 2.0 pF`:

- hard `fu = 5 MHz` needs `gm1 ~= 62.8 µS`;
- stretch `fu = 10 MHz` needs `gm1 ~= 125.7 µS`.

If the input device operates at `ID = 20 µA` and a characterization-selected
`gm/ID = 15 V^-1`, its estimated transconductance is:

`gm1 = (gm/ID)*ID = 15*20 µA = 300 µS`

Substituting this paper estimate gives `fu ~= 23.9 MHz`. This is not a predicted
final UGB: parasitic capacitances, finite output resistances, the actual
compensation topology, loading, and the PDK operating point can materially
change it. Its purpose is to show initial bandwidth margin for stabilization.

## 3. Slew-rate budget

Two useful upper-bound estimates are:

`SR_input_stage ~= Itail/CC = 40 µA/2 pF = 20 V/µs`

`SR_output_stage ~= Istage2/CL = 100 µA/5 pF = 20 V/µs`

The actual positive and negative directions depend on which devices source and
sink `CC` and `CL`, current-mirror dynamics, output voltage, and saturation.
Therefore 20 V/µs is a sizing sanity check, not a claimed result. Both directions
must be extracted from transient simulation using the frozen definition.

## 4. Current and power budget

The hard and stretch power limits correspond to total supply-current budgets:

- 600 µW / 1.8 V = 333 µA hard maximum;
- 400 µW / 1.8 V = 222 µA stretch maximum;
- 300 µW / 1.8 V = 167 µA optional bonus maximum.

A simplified initial current sum is:

`Itotal,estimate = Itail + Istage2 + IREF = 40 + 100 + 10 = 150 µA`

`Pestimate = 1.8 V * 150 µA = 270 µW`

This estimate omits topology-dependent mirror branches, startup paths, and any
other bias overhead. Only the final simulated current drawn from the VDD source
may be reported as quiescent power.

Day 3 closes this estimate at the nominal point: simulated supply current is
150.298315 µA and power is 270.536967 µW, only 0.536967 µW above the initial
paper estimate. This agreement is nominal-only and does not replace the PVT
power sweep.

## 5. Gain allocation

The 50 dB hard gain requirement is:

`A0 >= 10^(50/20) = 316 V/V`

For a balanced first estimate, each stage would need approximately:

`sqrt(316) = 17.8 V/V ~= 25 dB`

Use:

`A1 ~= gm1 * Rout1`

`A2 ~= gm6 * Rout2`

`A0 ~= A1 * A2`

Day 1 single-device sweeps now provide an initial `gm/gds` lookup at
`|VDS| = 0.9 V`, but `Rout1` and `Rout2` still cannot be assigned credibly until
`gds` is extracted from the connected circuit's actual operating points.
Longer channel lengths may improve intrinsic gain but cost area, capacitance,
voltage headroom, or bandwidth.

## 6. Second-stage and compensation starting point

For `Istage2 = 100 µA` and an initial `gm/ID = 10 V^-1`:

`gm6,estimate = 1.0 mS`

If an RHP-zero problem requires a series nulling resistor, the first order of
magnitude to explore is:

`RZ ~= 1/gm6 ~= 1 kΩ`

Start with `CC` alone. Add `RZ` only after the uncompensated/CC-only loop-gain
plot establishes the need, and log the before/after tradeoff.

Day 3 gives M6 `gm = 835.556346 µS`, so `1/gm ≈ 1.19681 kΩ`. The explored
3 pF/1 kΩ point nevertheless reaches only 52.2886533° phase margin and fails
the 55° hard limit. The selected measured-loop result is 3 pF/2 kΩ with
69.0829108° phase margin; the first-order `1/gm` estimate was therefore only a
search scale, not the final resistor value.

## 7. Initial mirror ratios

With `IREF = 10 µA`, the starting current ratios are:

- tail current: 4:1 for 40 µA;
- second-stage bias: 10:1 for 100 µA.

Implement ratios using documented multiplicity/geometry choices compatible with
matching, rather than assuming width ratios reproduce current ratios exactly.
Measure current error versus output voltage and identify the compliance range.

## 8. Day 1 device-characterization results

Standard-VT SKY130A devices were swept at TT, 27 °C, `W = 5 µm`, and fixed
`|VDS| = 0.9 V`. Gate voltage covered the 0–1.8 V range in 10 mV increments;
channel lengths were 0.15, 0.30, 0.50, 0.80, and 1.00 µm. The analysis retained
`ID`, `gm`, `gds`, `gm/ID`, `gm/gds`, threshold voltage, and model-reported
`VDSAT`. Width was then estimated from the sampled current density at the
target current and target `gm/ID`.

| Device group | Target current | L | Initial W | Sampled gm/ID | ID/W | gm/gds | VDSAT magnitude | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| M1/M2 input pair | 20 µA each | 0.50 µm | 6.73519 µm | 15.0158 V⁻¹ | 2.96948 µA/µm | 130.426 | 0.103957 V | INITIAL_CANDIDATE_NOT_FINAL |
| M3/M4 active load | 20 µA each | 0.80 µm | 22.4281 µm | 11.8668 V⁻¹ | 0.891740 µA/µm | 310.727 | 0.143911 V | INITIAL_CANDIDATE_NOT_FINAL |
| M5 tail source | 40 µA | 0.80 µm | 10.7814 µm | 11.8897 V⁻¹ | 3.71010 µA/µm | 169.600 | 0.137961 V | INITIAL_CANDIDATE_NOT_FINAL |
| M6 second stage | 100 µA | 0.50 µm | 11.1091 µm | 9.93948 V⁻¹ | 9.00164 µA/µm | 107.659 | 0.160126 V | INITIAL_CANDIDATE_NOT_FINAL |
| M7 second-stage load | 100 µA | 0.80 µm | 72.2005 µm | 10.1827 V⁻¹ | 1.38503 µA/µm | 270.722 | 0.173050 V | INITIAL_CANDIDATE_NOT_FINAL |
| Bias mirrors | topology-dependent | 0.80–1.00 µm | TBD | TBD | TBD | TBD | TBD | NOT_RUN |

The full source table is `results/device_sizing_candidates.csv`; the raw lookup
tables are under `results/raw/day1/`, and the combined visual review is
`results/plots/day1_device_characterization.png`.

The sizing method assumes current scales linearly with width at the sampled
single-device point. It does not account for connected-circuit drain voltages,
series resistance, mirror mismatch, parasitic capacitance, or layout choices.
Day 2 subsequently verified and revised M1–M5 with actual operating-point data.
Day 3 then checked the complete OTA at nominal TT, retained the M7 candidate,
and rebalanced M6 to 8.83907427 µm; Sections 13–15 record that closure.

## 9. Day 1 current-mirror check

A separate 1:1 NMOS mirror used `W/L = 5/0.8 µm`, forced `IREF = 10 µA`, TT,
27 °C, and swept `VOUT` from 0 to 1.8 V in 10 mV steps. At `VOUT = 0.9 V`, the
reference transistor carried 10.0000012 µA and the output transistor carried
10.1780846 µA. The magnitude error is 1.78084599% versus the forced 10 µA
reference, or 1.78083395% versus the measured reference-device current. Two
intervals are reported separately:

- model-saturation criterion (`VDS >= VDSAT`): `VOUT = 0.11–1.80 V`;
- saturation plus at most 5% current error: `VOUT = 0.28–1.30 V`.

Those endpoints are samples on the 10 mV grid, not higher-precision continuous
crossings. The 5% interval uses error versus the forced `IREF` definition.

The upper end of the 5% interval is caused by output-conductance error, not by
loss of the model saturation condition. This result motivates checking mirror
accuracy at the actual first- and second-stage node voltages instead of quoting
only a single compliance voltage. Evidence is in
`results/current_mirror_summary.csv` and
`results/plots/day1_current_mirror_compliance.png`. Provenance, log-validation
status, and 45 SHA-256 records are retained in
`results/day1_reproducibility_manifest.json`.

## 10. Day 2 selected M1–M5 dimensions

The connected-circuit checks showed that the Day 1 widths did not provide
enough tail-source headroom. The selected Day 2 first stage is:

| Group | Day 1 W/L | Selected Day 2 implementation | Selection purpose |
|---|---:|---:|---|
| M1/M2, each | 6.73519/0.5 µm | 16.83798/0.5 µm | 2.5× width lowers required VGS/VDSAT and recovers low-VCM headroom |
| M3/M4, each side | 22.4281/0.8 µm | two explicit 25/0.5 µm units; total W = 50 µm | Places `VX` near 0.8 V while limiting area/parasitics and gain variation |
| M5 | 10.7814/0.8 µm | 25.8754/0.8 µm | 2.4× width lowers tail-source VDSAT |
| MB | 2.69535/0.8 µm | 8.08605/0.8 µm | Produces approximately 40 µA in widened M5 from the 10 µA reference |

M3/M4 use explicit parallel subcircuit instances rather than relying on a
hierarchical multiplier. This also keeps each device inside the installed
compact-model width bins.

At `VCM = 0.9 V`, the selected block's operating point is:

| Quantity | Simulated value |
|---|---:|
| Supply current / first-stage power | 48.0713851 µA / 86.52849318 µW |
| M5 current | 38.0713829 µA |
| M1 current / M2 current | 19.0356918 / 19.0356918 µA |
| `VBN` / tail / `VX` | 0.658036427 / 0.214664546 / 0.792073469 V |
| M1 `gm/ID` / `gm/gds` | 20.07881048 V⁻¹ / 98.14990379 V/V |
| M1/M2 saturation margin | 0.5028161704 V |
| M3/M4 saturation margin | 0.9206745920 V |
| M5 saturation margin | 0.1160701611 V |
| AC gain at 1 Hz | 36.2697407 dB |
| Near-zero differential-DC gain | 65.06995036 V/V (36.26760951 dB) |
| First-stage 3 dB bandwidth | 45.524514446 MHz |
| First-stage 0 dB crossing | 1.6936999222 GHz |

The frequency rows describe the isolated, unloaded first-stage bench. They do
not predict the complete OTA's UGB or phase margin after M6/M7, Miller
compensation, and the frozen output load are added.

## 11. Formal first-stage-only ICMR

For each common-mode point, ngspice recomputed the DC bias and measured 1 Hz
differential gain. A point is valid when gain is no more than 3 dB below its
0.9 V value, every M1–M5 model saturation margin is nonnegative, and
`0.05 V < VX < 1.75 V`. The largest contiguous valid interval containing
0.9 V is **0.76–1.24 V** on the 20 mV VCM grid.

| VCM | Gain relative to 0.9 V | Minimum saturation margin | Result |
|---:|---:|---:|---|
| 0.8 V | +0.3527407 dB | 0.0355600256 V | PASS |
| 1.3 V | -4.2908617 dB | 0.163156821 V | FAIL — gain change exceeds 3 dB |

Thus, 1.3 V fails even though the tracked devices remain saturated. The
preliminary DC operating-region heuristic spans 0.76–1.49 V, but that check
uses current/saturation/node-voltage limits without measuring gain flatness; it
is diagnostic only and is not the formal ICMR. This first-stage result also
cannot be substituted for the final loaded OTA's nominal ICMR.

## 12. Selected area/bandwidth tradeoff

The main comparison is between the selected PMOS load and the legal oversized
explicit-parallel iteration:

| Quantity | Selected M3/M4: 50 µm/side, L=0.5 µm | Oversized M3/M4: 179.4248 µm/side, L=0.8 µm |
|---|---:|---:|
| Channel-area proxy, `sum(W × L)` | 94.0071 µm² | 331.0868 µm² |
| First-stage gain at 1 Hz | 36.2697 dB | 38.2056 dB |
| First-stage 3 dB bandwidth | 45.524514446 MHz | 13.106718 MHz |
| Formal first-stage ICMR | 0.76–1.24 V | 0.76–1.22 V |

The selected design reduces the proxy by 71.6065% and raises bandwidth by
3.473× while giving up 1.9359 dB of first-stage gain. The area proxy counts MOS
channel `W × L` only; it is a relative sizing measure, not a layout area.

Before the legal parallel implementation, a single PMOS with
`W = 179.4248 µm, L = 0.8 µm` failed because it exceeded the installed model's
`wmax = 100 µm`. That failure, the corrected legal implementation, the parser
failure caused by ngspice's extra `wrdata` scale column, and all rejected sizing
iterations are retained under `results/raw/day2/` and summarized in
`results/day2_iteration_summary.csv`.

## 13. Day 3 second-stage balance and compact dimensions

The second-stage sizing aid fixes `VX = 0.792073469 V`, clamps
`VOUT = 0.9 V`, and includes the frozen resistive-load current explicitly:

`IRL = 0.9 V / 100 kΩ = 9 µA`

The root condition is `IM7 - IM6 - IRL = 0`. The residual is
+0.471056959 µA at `W6 = 8.8 µm` and -0.734485599 µA at 8.9 µm. Linear
interpolation selects `W6 = 8.839074270408297 µm`, rendered as 8.83907427 µm
at `L6 = 0.5 µm`.

The complete nominal device set is:

| Devices | Selected geometry |
|---|---|
| M1/M2 | each `16.83798/0.5 µm` |
| M3/M4 | each side two `25/0.5 µm` units, 50 µm total width |
| M5 | `25.8754/0.8 µm` |
| M6 | `8.83907427/0.5 µm` |
| M7 | `72.2005/0.8 µm` |
| M8/M9 | each `7.22005/0.8 µm` |
| M10 | `8.08605/0.8 µm` |

At the final follower bias, M6 sinks 83.2666517 µA and M7 sources
92.2666438 µA; the approximately 9 µA difference supplies the 100 kΩ load.

## 14. Day 3 compensation closure

The return-ratio bench retains DC unity feedback with a 1 GH inductor and
injects AC through a 1 GF capacitor. It evaluates
`T = -V(VOUT)/V(VINN)`. The selected 1 Hz phase is -0.00682757215°, confirming
the intended near-zero low-frequency sign before phase-margin extraction.

| Network | A0 | UGB | PM | Hard AC result |
|---|---:|---:|---:|---|
| 3 pF, `RZ ≈ 0` (`0.001 Ω`) | 67.6747747 dB | 17.2553341 MHz | 33.2236432° | FAIL |
| 3 pF, 1 kΩ | 67.6747747 dB | 16.3621278 MHz | 52.2886533° | FAIL |
| 3 pF, 2 kΩ | 67.6747747 dB | 16.7454480 MHz | 69.0829108° | PASS; selected |

Adding the selected resistor improves phase margin by 35.8592675° versus the
capacitor-only baseline, at a 2.95495% UGB reduction. This is the documented
nominal stability tradeoff.

## 15. Day 3 nominal budget closure

| Quantity | Day 3 result | Interpretation |
|---|---:|---|
| A0 | 67.6747747 dB | hard and stretch pass at TT only |
| UGB | 16.7454480155 MHz | hard and stretch pass at TT only |
| PM | 69.0829107715° | hard and stretch pass at TT only |
| Power | 270.536967 µW | hard and stretch pass at TT only |
| SR+ / SR- | 8.20202918 / 11.51994781 V/µs | frozen-definition hard and stretch pass at TT only |
| Slew fit samples, rise/fall | 62 / 47 | monotonic 20–80% least-squares fits |
| Rise/fall 1% settling | 0.07475 / 0.04075 µs | hard and stretch worst-case pass at TT only |
| Rising overshoot | 74.99684 mV | reported; not a pass metric |
| Minimum M1–M10 saturation margin | 0.1161336635 V | positive at nominal |

These figures use the frozen 5 pF || 100 kΩ-to-VSS load. They are
schematic-level TT results; no PVT, extracted-layout, fabricated, or measured
claim is made. Settling is measured from the input 50% crossings at 1.01 µs
rising and 3.03 µs falling.
The transient completed with dynamic-gmin stepping, which is retained in the
log audit and must be rechecked across corners. SR is the frozen monotonic
20–80% least-squares fit, not a maximum derivative.
