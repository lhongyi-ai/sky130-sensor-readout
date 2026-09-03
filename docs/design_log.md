# Design Decision Log

This file records design selections and rejected alternatives. Chronological
execution details and earlier failures remain in `project_log.md`.

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

The automated size check confirms this set in both selected production decks.
M3/M4 remain explicit parallel units, avoiding ambiguous hierarchy-multiplier
behavior.

### M6 balance decision

The sizing bench clamps `VX = 0.792073469 V` and `VOUT = 0.9 V`, then sweeps M6
width from 6 to 10 µm at `L = 0.5 µm`. The balance residual is:

`Iresidual = IM7 - IM6 - VOUT/100 kΩ`

The explicit load term is 9 µA. Residual changes from +0.471056959 µA at
`W6 = 8.8 µm` to -0.734485599 µA at 8.9 µm; linear interpolation selects
`W6 = 8.839074270408297 µm` (written as 8.83907427 µm in the production deck).
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
- Only `nominal_transient.log` records dynamic-gmin stepping. It completed, but
  this convergence aid is disclosed and must be rechecked across corners.
- SR uses the frozen monotonic 20–80% least-squares fit: 62 rising and 47
  falling samples yield 8.20202918 and 11.51994781 V/µs, respectively.
- The decision is TT-only and schematic-level. PVT, complete-OTA ICMR/output
  swing, CMRR, PSRR, noise, and 1/2/5 pF load stability are not established.
- The Day 2 first-stage ICMR remains 0.76–1.24 V and fails its 1.3 V high-end
  checkpoint; Day 3 did not rerun complete-OTA ICMR.

Primary evidence: `results/day3_design_parameters.csv`,
`results/day3_m6_balance.csv`, `results/day3_compensation_comparison.csv`,
`results/day3_compensation_before_after.csv`, and `results/day3_log_audit.csv`.
