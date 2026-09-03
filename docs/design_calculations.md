# Initial Design Calculations

**Status:** Day 1 device characterization complete; circuit sizing remains
initial.  
**Important:** The widths below are characterization-based candidates, not
final device sizes or achieved OTA results. They must be re-evaluated at the
actual bias voltages, node voltages, and closed-loop operating points.

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
in Section 8; they are intentionally not frozen.

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
Day 2 must therefore verify every candidate with actual operating-point data.

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
