# Design Decision Log

This file records design selections and rejected alternatives. Chronological
execution details and earlier failures remain in `project_log.md`.

**Current decision:** keep the Day 3-selected/Day 4-characterized geometry with
`CC = 3 pF` and `RZ = 2 kΩ`. Day 5 geometry variants are nominal
reconnaissance and are not promoted.

## Day 3 — complete nominal signal path

**Scope:** SKY130A TT, 1.8 V, 27 °C, `VCM = 0.9 V`, 10 µA external reference,
and 5 pF || 100 kΩ from `VOUT` to VSS. All results are schematic-level
simulations.

### Compact device set

| Device | Function | Selected geometry |
|---|---|---|
| M1/M2 | NMOS input pair | each `16.83798/0.5 µm` |
| M3/M4 | PMOS mirror load | each side `2 × 25/0.5 µm` (50 µm total width) |
| M5 | NMOS tail sink | `25.8754/0.8 µm` |
| M6 | NMOS second stage | `8.83907427/0.5 µm` |
| M7 | PMOS second-stage source | `72.2005/0.8 µm` |
| M8/M9 | PMOS reference and VBN branch | each `7.22005/0.8 µm` |
| M10 | diode-connected NMOS VBN reference | `8.08605/0.8 µm` |

The automated size check confirms this set in both selected Day 3 decks.
M3/M4 remain explicit parallel units, avoiding ambiguous hierarchy-multiplier
behavior.

### M6 balance decision

The sizing bench clamps `VX = 0.792073469 V` and `VOUT = 0.9 V`, then sweeps M6
width from 6 to 10 µm at `L = 0.5 µm`. The balance residual is:

`Iresidual = IM7 - IM6 - VOUT/100 kΩ`

The explicit load term is 9 µA. Residual changes from +0.471056959 µA at
`W6 = 8.8 µm` to -0.734485599 µA at 8.9 µm; linear interpolation selects
`W6 = 8.839074270408297 µm` (written as 8.83907427 µm in the selected Day 3 deck).
At the final closed-loop operating point, M6/M7 currents are
83.2666517/92.2666438 µA and `VOUT = 0.899999206 V`.

### Compensation decision

Seventeen combinations of `CC = 1–4 pF` and series `RZ` were retained. The
selected point is `CC = 3 pF`, `RZ = 2 kΩ`.

| Candidate | A0 | UGB | Phase margin | Decision |
|---|---:|---:|---:|---|
| 3 pF, no practical series R (`0.001 Ω`) | 67.6747747 dB | 17.2553341 MHz | 33.2236432° | baseline, stability FAIL |
| 3 pF, 1 kΩ | 67.6747747 dB | 16.3621278 MHz | 52.2886533° | retained hard-PM FAIL |
| 3 pF, 2 kΩ | 67.6747747 dB | 16.745448 MHz | 69.0829108° | selected; hard and stretch AC PASS |

Relative to the 3 pF capacitor-only baseline, the selected resistor adds
35.8592675° phase margin while reducing UGB by 2.95495%. Larger resistors also
passed the nominal hard AC limits, but the 2 kΩ point was the smallest tested
3 pF resistor that cleared the 65° stretch target.

### Implemented loop break

The loop-gain bench is DC closed and AC open. `LBREAK = 1 GH` connects `VOUT`
to `VINN`, acting as a DC short and an AC open over the analysis band.
`CBREAK = 1 GF` couples a 1 V AC source to `VINN`, blocking it at DC and acting
as an AC short. The extracted return ratio is:

`T(f) = -V(VOUT)/V(VINN)`

The selected case has -0.00682757215° phase at 1 Hz, near the expected 0° for
this sign convention. UGB and phase margin come from this return ratio, not
from a closed-loop bandwidth approximation.

### Numerical and scope cautions

- All 19 top-level Day 3 logs end with `ngspice-47 done` and contain no fatal
  audit token.
- Every log contains one known PDK warning:
  `m=xx on .subckt line will override multiplier m hierarchy!`
- Only `nominal_transient.log` records dynamic-gmin stepping. It completed; Day
  4 later repeated the transient across all required corners and disclosed its
  own per-log convergence state.
- SR uses the frozen monotonic 20–80% least-squares fit: 62 rising and 47
  falling samples yield 8.20202918 and 11.51994781 V/µs, respectively.
- At the Day 3 checkpoint the decision was TT-only. Day 4 later established
  core PVT, complete-OTA ICMR/output swing, CMRR, PSRR, noise, and load
  stability without changing the geometry.
- The Day 2 first-stage ICMR remains 0.76–1.24 V and fails its 1.3 V high-end
  checkpoint; Day 3 did not rerun complete-OTA ICMR.

Primary evidence: `results/day3_design_parameters.csv`,
`results/day3_m6_balance.csv`, `results/day3_compensation_comparison.csv`,
`results/day3_compensation_before_after.csv`, and `results/day3_log_audit.csv`.

## Day 4 — retain geometry after full characterization

**Decision:** freeze the Day 3 dimensions and compensation. Do not resize or
hide failures after seeing the qualification results.

### Core PVT decision

All 13 required points pass all six core hard limits:

| Core metric | Worst value | Condition | Hard target | Decision |
|---|---:|---|---:|---|
| A0 | 65.5351 dB | P08 | ≥50 dB | PASS |
| UGB | 14.5527 MHz | P08 | ≥5 MHz | PASS |
| PM | 66.2452° | P13 | ≥55° | PASS |
| Power | 302.710 µW | P13 | ≤600 µW | PASS |
| SR+ | 7.97766 V/µs | P06 | ≥2 V/µs | PASS |
| SR- | 11.1958 V/µs | P08 | ≥2 V/µs | PASS |

P06, P07, and P13 retain `SETTLING_NOT_REACHED` for one or both directions
under the absolute ±4 mV definition. Settling is nominal-only, so the state is
reported but not folded into the six-metric core PVT gate.

### Nominal characterization decisions

- Keep the nominal settling result: 0.07475 µs, `PASS`.
- CMRR is 71.3222 dB at 1 kHz, `PASS`.
- Preserve PSRR+ = 36.3313 dB and PSRR- = 36.2510 dB as explicit hard-limit
  failures; do not reinterpret the 45 dB target.
- Preserve full-OTA ICMR = 0.76–1.22 V as `ICMR_HIGH_FAIL`; the low endpoint
  passes, but the required 1.3 V high endpoint does not.
- Accept output swing = 0.18–1.63 V; the bidirectional common-valid interval
  covers 0.3–1.5 V.
- Report, without a target, 401.170 nV/√Hz at 1 kHz and 52.3016 µV RMS from
  10 Hz to 1 MHz.
- Accept CL=1/2/5 pF load stability at 94.1626°/86.2882°/69.0829° PM with no
  sustained or growing oscillation.

The Day 4 loop bench continues to use the validated 1 GH/1 GF break. The
campaign retains 171 log-audit rows, all complete; parser/integrity failures
would make the analyzer exit nonzero, whereas genuine specification failures
remain visible in the result table.

Primary evidence: `results/summary.csv`, `results/pvt_summary.csv`,
`results/day4_nominal_summary.csv`, `results/day4_log_audit.csv`, and the
metric-specific `results/day4_*.csv` tables.

## Day 5 — optimization accounting and rejected reconnaissance

**Formal optimization:** credit the Day 3 3 pF + 2 kΩ compensation change
relative to 3 pF alone. It improves PM from 33.2236° to 69.0829°
(+35.8593°) while reducing UGB from 17.2553 to 16.7454 MHz (2.95495%). It is
the only optimization candidate here backed by the full Day 4 campaign.

**Reconnaissance decision:** do not promote `first_stage_l2`,
`first_stage_l3`, or `m7_l2`. The 32-run/48-TSV checks are nominal-only. The
most tempting case, `first_stage_l2`, moves PSRR+/- from 36.331/36.251 dB to
72.419/67.315 dB, but PM falls by 7.559° to 61.524°. At the Day 4-equivalent
1 Hz checkpoint, the 1.3 V ICMR gain delta worsens from -4.935 dB to
-7.361 dB (-2.425 dB), and total channel-area proxy rises to 2.195×. It has not
been rerun across PVT. `first_stage_l3` and `m7_l2` miss the nominal PM hard
limit. The frozen baseline remains the reported design.

Evidence is the retained Day 3 before/after table plus
`experiments/day5/decision_summary.csv`, `experiments/day5/recon_summary.csv`,
and `experiments/day5/README.md`; generated SPICE decks are reproducibility
products, not the sole decision evidence.

The claim boundary remains schematic-level simulation with an ideal external
10 µA reference. No mismatch/Monte Carlo, physical layout, extraction,
post-layout simulation, fabrication, or silicon measurement is claimed.
