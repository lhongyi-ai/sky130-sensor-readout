# Results

**Current evidence level:** Day 4 schematic-level characterization and the Day
5 bounded nominal reconnaissance are complete and auditable. The final report
is published with the Day 4 baseline retained.

## Nominal conditions

| Item | Value |
|---|---:|
| Process / supply / temperature | TT / 1.8 V / 27 °C |
| Input common mode | 0.9 V |
| External reference | 10 µA |
| Output load | 5 pF || 100 kΩ to VSS |
| Compensation | 3 pF in series with 2 kΩ |

Final circuit evidence is the editable
[`two_stage_ota.sch`](../schematics/two_stage_ota.sch) and its
[rendered schematic](../results/plots/final_two_stage_ota_schematic.png).

## Day 4 core PVT qualification

All six core metrics pass their hard limits at every required point. Values
below come from [`results/pvt_summary.csv`](../results/pvt_summary.csv); the
point IDs and matrix are frozen by the specification.

| Point | Corner | VDD | Temp | A0 (dB) | UGB (MHz) | PM (°) | Power (µW) | SR+ / SR- (V/µs) | Core state |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| P01 | TT | 1.80 V | 27 °C | 67.6760 | 16.7454 | 69.0829 | 270.537 | 8.2020 / 11.5199 | PASS |
| P02 | FF | 1.80 V | 27 °C | 67.1053 | 17.2191 | 70.4796 | 269.399 | 8.2610 / 11.5403 | PASS |
| P03 | SS | 1.80 V | 27 °C | 68.0263 | 16.2352 | 67.6702 | 271.559 | 8.2007 / 11.4786 | PASS |
| P04 | FS | 1.80 V | 27 °C | 67.4452 | 16.1632 | 67.4462 | 270.215 | 8.0563 / 11.5472 | PASS |
| P05 | SF | 1.80 V | 27 °C | 67.8355 | 17.1917 | 70.5382 | 270.671 | 8.3781 / 11.4509 | PASS |
| P06 | TT | 1.62 V | -20 °C | 68.3184 | 18.4571 | 72.2364 | 239.356 | 7.9777 / 11.2405 | PASS |
| P07 | TT | 1.62 V | 27 °C | 67.1348 | 16.4699 | 69.1458 | 241.770 | 8.0942 / 11.2439 | PASS |
| P08 | TT | 1.62 V | 85 °C | 65.5351 | 14.5527 | 66.3929 | 244.489 | 8.2354 / 11.1958 | PASS |
| P09 | TT | 1.80 V | -20 °C | 68.8436 | 18.8030 | 72.2063 | 267.884 | 8.0979 / 11.5515 | PASS |
| P10 | TT | 1.80 V | 85 °C | 66.1050 | 14.7741 | 66.3042 | 273.558 | 8.3657 / 11.4568 | PASS |
| P11 | TT | 1.98 V | -20 °C | 69.2057 | 19.0761 | 72.2025 | 296.516 | 8.1986 / 11.8484 | PASS |
| P12 | TT | 1.98 V | 27 °C | 68.0506 | 16.9670 | 69.0493 | 299.400 | 8.3160 / 11.7962 | PASS |
| P13 | TT | 1.98 V | 85 °C | 66.4990 | 14.9549 | 66.2452 | 302.710 | 8.4880 / 11.7162 | PASS |

The limiting core observations are 65.5351 dB gain and 14.5527 MHz UGB at
P08, 66.2452° PM and 302.710 µW at P13, 7.97766 V/µs SR+ at P06, and
11.1958 V/µs SR- at P08. Every operating-point row retains signed `I(VDD)` and
M1–M10 operating data.

The PVT transient extraction also records settling even though settling is a
nominal-only requirement. P06 and P13 do not reach the frozen ±4 mV band in
either direction; P07 does not reach it on the rising edge. Their numeric
settling fields remain blank and their state is `SETTLING_NOT_REACHED`. This is
not part of the six-metric PVT gate and is not relabeled as a core failure.

## Day 4 nominal characterization

| Metric | Simulated result | Requirement | State |
|---|---:|---:|---|
| 1% settling, worse direction | 0.07475 µs | ≤1.5 µs | PASS |
| CMRR at 1 kHz | 71.3222 dB | ≥55 dB | PASS |
| PSRR+ at 1 kHz | 36.3313 dB | ≥45 dB | **FAIL** |
| PSRR- at 1 kHz | 36.2510 dB | ≥45 dB | **FAIL** |
| Full-OTA ICMR | 0.76–1.22 V | includes 0.8–1.3 V | **FAIL at high endpoint** |
| Output swing | 0.18–1.63 V | includes 0.3–1.5 V | PASS |
| Input-referred noise at 1 kHz | 401.170 nV/√Hz | report | REPORTED |
| Integrated input noise, 10 Hz–1 MHz | 52.3016 µV RMS | report | REPORTED |

The ICMR result is the largest continuous valid 10 mV-grid interval containing
0.9 V; the low endpoint passes and the 1.22 V high endpoint misses 1.3 V. The
output swing is common to forward and reverse offset-inverting sweeps and
therefore covers the required 0.3–1.5 V interval.

| Load | UGB | PM | Worst 1% settling | Oscillation check | State |
|---:|---:|---:|---:|---|---|
| 1 pF | 19.8637 MHz | 94.1626° | 0.05125 µs | no sustained/growing oscillation | PASS |
| 2 pF | 19.2153 MHz | 86.2882° | 0.04875 µs | no sustained/growing oscillation | PASS |
| 5 pF | 16.7454 MHz | 69.0829° | 0.07475 µs | no sustained/growing oscillation | PASS |

The Day 4 analyzer correlated nominal A0, UGB, PM, power, SR+/SR-, and settling
to the frozen Day 3 values; all seven correlation rows pass. All 171 required
logs completed, with 51 `PASS` and 120 `PASS_WITH_DYNAMIC_GMIN`. Twenty-four
noise-model conductance-reset warnings are retained rather than suppressed.

## Day 3 source checkpoint

| Metric | Result | Requirement | Status at nominal only |
|---|---:|---:|---|
| DC unity-follower output | 0.899999206 V | within 10 mV of 0.9 V | PASS |
| Open-loop gain | 67.6747747 dB | ≥50 hard / ≥60 stretch | PASS / PASS |
| Unity-gain bandwidth | 16.745448015512064 MHz | ≥5 / ≥10 MHz | PASS / PASS |
| Phase margin | 69.0829107715455° | ≥55° / ≥65° | PASS / PASS |
| Quiescent power | 270.536967 µW | ≤600 / ≤400 µW | PASS / PASS |
| Positive slew rate | 8.202029183242544 V/µs | ≥2 / ≥4 V/µs | PASS / PASS |
| Negative slew rate | 11.519947805768885 V/µs | ≥2 / ≥4 V/µs | PASS / PASS |
| Rising slew fit samples | 62 | ≥5 | PASS |
| Falling slew fit samples | 47 | ≥5 | PASS |
| Rising input 50% crossing | 1.01 µs | settling reference | INFO |
| Falling input 50% crossing | 3.03 µs | settling reference | INFO |
| Rising 1% settling | 0.07475000000000001 µs | report | INFO |
| Falling 1% settling | 0.04075000000000042 µs | report | INFO |
| Worst 1% settling | 0.07475000000000001 µs | ≤1.5 / ≤1.0 µs | PASS / PASS |
| Rising overshoot | 74.99684000000006 mV | report | INFO |
| Falling undershoot | 1.858472 mV | report | INFO |
| Minimum device saturation margin | 0.11613366350000001 V | ≥0 V | PASS |

The Day 4 nominal correlation reproduces this checkpoint. The 0.8→1.2→0.8 V
follower input uses 20 ns edges. Slew rate is a least-squares
fit over the monotonic 20–80% rising or 80–20% falling interval required by the
frozen specification. Settling time is measured from the corresponding input
50% crossing, not from the programmed source-edge start. The large positive
overshoot remains reported even
though the output subsequently meets the 1% settling criterion.

## Nominal operating point

| Device | Drain current | gm/ID | Intrinsic gain | Saturation margin |
|---|---:|---:|---:|---:|
| M1 | 19.0200621 µA | 20.0815093 V⁻¹ | 98.1531265 V/V | 0.502852403 V |
| M2 | 19.0201650 µA | 20.0814875 V⁻¹ | 98.1487149 V/V | 0.502800617 V |
| M3 | 19.0200607 µA | 15.8466320 V⁻¹ | 153.985345 V/V | 0.920646901 V |
| M4 | 19.0201614 µA | 15.8466250 V⁻¹ | 153.988301 V/V | 0.920698288 V |
| M5 | 38.0402241 µA | 16.8710800 V⁻¹ | 48.8225953 V/V | 0.116133664 V |
| M6 | 83.2666517 µA | 10.0347057 V⁻¹ | 96.4371720 V/V | 0.741566815 V |
| M7 | 92.2666438 µA | 10.4763188 V⁻¹ | 253.753087 V/V | 0.735559517 V |
| M8 | 9.99999882 µA | 10.2006294 V⁻¹ | 303.176420 V/V | 0.997543332 V |
| M9 | 9.99144222 µA | 10.2011327 V⁻¹ | 298.215079 V/V | 0.972317973 V |
| M10 | 9.99144270 µA | 17.2879516 V⁻¹ | 166.709481 V/V | 0.565614858 V |

All model saturation checks pass at this single point. The complete table,
including `gm`, `gds`, and `VDSAT`, is in
`results/day3_nominal_operating_point.csv`.

## Compensation evidence

The selected 3 pF/2 kΩ return ratio has 67.6747747 dB low-frequency gain,
16.745448 MHz UGB, and 69.0829108° phase margin. The 3 pF capacitor-only
baseline has the same gain, 17.2553341 MHz UGB, and 33.2236432° phase margin.
The 3 pF/1 kΩ candidate is a retained failure because 52.2886533° misses the
55° hard phase-margin limit, despite passing gain and UGB.

The feedback break uses a 1 GH DC-feedback inductor and 1 GF AC-injection
capacitor. Return ratio is `-V(VOUT)/V(VINN)`; the selected 1 Hz phase is
-0.00682757215°.

## Day 5 decision and evidence limits

The formal optimization is the Day 3 3 pF + 2 kΩ compensation selection versus
the 3 pF-only baseline: PM improves from 33.2236° to 69.0829° with UGB changing
from 17.2553 to 16.7454 MHz. The nominal-only Day 5 `first_stage_l2`,
`first_stage_l3`, and `m7_l2` reconnaissance does not supersede the frozen
design. `first_stage_l2` improves PSRR+/- to 72.419/67.315 dB, but PM drops to
61.524°. At the Day 4-equivalent 1 Hz checkpoint, the 1.3 V ICMR gain delta
worsens from -4.935 dB to -7.361 dB (-2.425 dB), and the channel-area proxy
becomes 2.195× baseline. It is rejected without a full PVT rerun;
`first_stage_l3` and `m7_l2` additionally regress the nominal hard PM limit.
The isolated campaign audits 32/32 logs, 48/48 raw TSVs, and 9/9 result CSVs
under manifest
`89f886ce2a150b84945a5378f29c2d4ee3faa5ef832876aeb122deb05e01391e`.

- Day 4 aggregate tables: [`results/summary.csv`](../results/summary.csv),
  [`results/pvt_summary.csv`](../results/pvt_summary.csv), and
  [`results/day4_nominal_summary.csv`](../results/day4_nominal_summary.csv).
- Day 4 audit/detail: [`results/day4_log_audit.csv`](../results/day4_log_audit.csv),
  [`results/day4_pvt_operating_points.csv`](../results/day4_pvt_operating_points.csv),
  and the metric-specific Day 4 CSV files in `results/`.
- Day 3 optimization source: [`results/day3_compensation_before_after.csv`](../results/day3_compensation_before_after.csv).
- Day 5 decision record: [`experiments/day5/README.md`](../experiments/day5/README.md),
  [`decision_summary.csv`](../experiments/day5/decision_summary.csv), and
  [`recon_summary.csv`](../experiments/day5/recon_summary.csv).
- Evidence level: schematic-level simulation with an ideal external 10 µA
  `IREF`. There is no mismatch/Monte Carlo, physical layout, extracted
  parasitics, post-layout simulation, fabrication, or silicon measurement.
