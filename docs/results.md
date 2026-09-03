# Results

**Current evidence level:** Day 3 nominal schematic-level checkpoint complete;
13-point PVT qualification not run.

## Nominal conditions

| Item | Value |
|---|---:|
| Process / supply / temperature | TT / 1.8 V / 27 °C |
| Input common mode | 0.9 V |
| External reference | 10 µA |
| Output load | 5 pF || 100 kΩ to VSS |
| Compensation | 3 pF in series with 2 kΩ |

## Day 3 nominal summary

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

The 0.8→1.2→0.8 V follower input uses 20 ns edges. Slew rate is a least-squares
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

## Evidence and limits

- Tables: `results/day3_nominal_summary.csv`,
  `results/day3_nominal_operating_point.csv`,
  `results/day3_design_parameters.csv`, `results/day3_m6_balance.csv`, and the
  two compensation CSVs.
- Plots: `results/plots/day3_m6_balance.png`,
  `results/plots/day3_loop_gain_compensation.png`, and
  `results/plots/day3_unity_follower_transient.png`.
- Log audit: 19/19 completion markers, no fatal token, one known multiplier
  warning per log; dynamic gmin appears only in the completed nominal transient.
- Scope: TT-only, schematic-level. `results/pvt_summary.csv` remains `NOT_RUN`.
  Missing results are not treated as passes.
