# Project Log

Use this log for decisions, failures, and quantitative design iterations. Do not
rewrite unsuccessful runs out of the history.

**Current state:** all five planned days, the final evidence audit, and the
six-page report are complete; the Day 4-characterized baseline is retained.

## 2026-09-03 — Day 1: environment, characterization, and mirror gate

### Completed

- Selected the two-stage NMOS-input, Miller-compensated OTA architecture.
- Resolved conflicting planning targets into hard, stretch, and bonus levels.
- Frozen nominal conditions, measurement definitions, and the 13-point core PVT
  matrix in `specification.md`.
- Installed and recorded the Colima/Docker/IIC-OSIC-TOOLS/SKY130A toolchain.
- Passed an Xschem-to-ngspice smoke test using the PDK's official inverter
  example.
- Characterized standard-VT SKY130A NFET and PFET devices at TT/27 °C,
  `|VDS| = 0.9 V`, and five channel lengths from 0.15 to 1.00 µm.
- Simulated a 1:1 NMOS current mirror across `VOUT = 0–1.8 V`.
- Generated initial, characterization-backed width candidates for M1–M7.
- Completed `./scripts/run_day1.sh` end to end with exit status 0.
- Generated a reproducibility manifest with `PASS` validation for 11 logs and
  45 SHA-256 records covering inputs, generated decks, and run outputs.

### Quantitative evidence

- 1:1 NMOS mirror at TT/27 °C and `W/L = 5/0.8 µm`: forced
  `IREF = 10 µA`, measured reference-device current `= 10.0000012 µA`, and
  `IOUT(0.9 V) = 10.1780846 µA`.
- Error at 0.9 V: `1.78084599%` versus forced `IREF`, or `1.78083395%` versus
  the measured reference-device current.
- Model-saturation interval: `VOUT = 0.11–1.80 V`.
- Combined saturation and at-most-5% error-versus-forced-`IREF` interval:
  `VOUT = 0.28–1.30 V`.
- All interval endpoints are quantized to the 10 mV DC sweep grid.
- Initial candidate dimensions and sampled operating quantities:

| Group | Target current | L | Initial W | Sampled gm/ID | gm/gds | VDSAT magnitude | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| M1/M2 | 20 µA each | 0.50 µm | 6.73519 µm | 15.0158 V⁻¹ | 130.426 | 0.103957 V | INITIAL_CANDIDATE_NOT_FINAL |
| M3/M4 | 20 µA each | 0.80 µm | 22.4281 µm | 11.8668 V⁻¹ | 310.727 | 0.143911 V | INITIAL_CANDIDATE_NOT_FINAL |
| M5 | 40 µA | 0.80 µm | 10.7814 µm | 11.8897 V⁻¹ | 169.600 | 0.137961 V | INITIAL_CANDIDATE_NOT_FINAL |
| M6 | 100 µA | 0.50 µm | 11.1091 µm | 9.93948 V⁻¹ | 107.659 | 0.160126 V | INITIAL_CANDIDATE_NOT_FINAL |
| M7 | 100 µA | 0.80 µm | 72.2005 µm | 10.1827 V⁻¹ | 270.722 | 0.173050 V | INITIAL_CANDIDATE_NOT_FINAL |

These points were sampled from single-device sweeps at fixed `|VDS| = 0.9 V`.
They are starting values for actual-circuit operating-point iteration, not final
OTA dimensions or achieved specifications.

### Evidence paths

- Raw tables/logs: `results/raw/day1/`
- Characterization plot: `results/plots/day1_device_characterization.png`
- Mirror plot: `results/plots/day1_current_mirror_compliance.png`
- Candidate table: `results/device_sizing_candidates.csv`
- Mirror summary: `results/current_mirror_summary.csv`
- Reproducibility/validation manifest: `results/day1_reproducibility_manifest.json`
- Xschem smoke evidence: `results/smoke/xschem/`

### Failures retained and fixes

- The first Xschem/ngspice attempt inherited the container's `ihp-sg13g2`
  default and could not find the SKY130 library. The failed log is retained.
  Setting `PDK_ROOT=/foss/pdks`, sourcing `.designinit`, and explicitly using
  the SKY130A Xschem rcfile fixed model resolution.
- The first characterization run did not save the internal MOS operating-point
  vectors needed by post-processing. Explicit `.save` directives were added;
  the failed behavior was not treated as evidence.
- The first mirror extraction relied on an internal device-current scalar and
  did not retain the swept output node. Saving `i(VOUT)` and `v(out)`, then
  computing mirror current from the voltage-source branch, corrected the sweep.
- ngspice emits a multiplier-hierarchy warning for the PDK subcircuit instance
  syntax. It is retained in the raw logs; no convergence or fatal error remains
  in the successful Day 1 batch.

### Not yet started at this checkpoint

- Final bias-network sizing and the M1–M5 first stage.
- Full OTA schematic, compensation tuning, and closed-loop verification.
- OTA performance extraction and the 13-point PVT sweep.

### Next action recorded at this checkpoint

- Build the Day 2 bias network and M1–M5 differential stage, then retain its
  operating-point table, differential gain, symmetry check, and ICMR sweep.
- At this Day 1 checkpoint, OTA-level `summary.csv` and `pvt_summary.csv` were
  still `NOT_RUN`; Day 4 later populated both.

## 2026-09-03 — Day 2: M1–M5 first-stage selection and formal ICMR

### Completed

- Implemented the NMOS-input differential pair, PMOS mirror load, NMOS tail
  source, and diode-connected 10 µA NMOS bias reference.
- Preserved input polarity explicitly: M1 senses `VINN`, M2 senses `VINP`, and
  `VX` is the inverting first-stage output.
- Replaced reliance on multiplier hierarchy for M3/M4 with two explicit
  parallel PMOS units on each side.
- Ran operating-point, differential DC, AC, common-mode operating-point, and
  per-VCM 1 Hz differential-gain analyses at TT/1.8 V/27 °C.
- Compared the selected circuit with seven retained sizing/implementation
  iterations and completed `./scripts/run_day2.sh` successfully.

### Selected dimensions

| Group | Total width per device/side | Units | Unit width | L | Reason |
|---|---:|---:|---:|---:|---|
| M1/M2 | 16.83798 µm | 1 | 16.83798 µm | 0.5 µm | 2.5× Day 1 width for low-VCM/VDSAT headroom |
| M3/M4 | 50 µm per side | 2 | 25 µm | 0.5 µm | VX, area, parasitic, and gain-flatness compromise |
| M5 | 25.8754 µm | 1 | 25.8754 µm | 0.8 µm | 2.4× Day 1 width for tail-source headroom |
| MB | 8.08605 µm | 1 | 8.08605 µm | 0.8 µm | Restores M5 current near 40 µA with widened M5 |

### Nominal block-level evidence

| Quantity | Selected Day 2 value |
|---|---:|
| First-stage supply current | 48.0713851 µA |
| First-stage power | 86.52849318 µW |
| M5 tail current | 38.0713829 µA |
| M1 current / M2 current | 19.0356918 / 19.0356918 µA |
| `VBN` / tail / `VX` | 0.658036427 / 0.214664546 / 0.792073469 V |
| M1 `gm/ID` / `gm/gds` | 20.07881048 V⁻¹ / 98.14990379 V/V |
| Minimum nominal saturation margin | 0.1160701611 V (M5) |
| Differential gain at 1 Hz | 36.2697407 dB |
| Near-zero differential-DC gain | 65.06995036 V/V (36.26760951 dB) |
| First-stage 3 dB bandwidth | 45.524514446 MHz |
| First-stage 0 dB crossing | 1.6936999222 GHz |

The last two rows characterize only this unloaded first-stage bench. They are
not the complete OTA's UGB, loop gain, or stability.

### Formal first-stage ICMR result — FAIL at the high end

The formal block criterion requires, at each VCM point, 1 Hz differential gain
no more than 3 dB below the 0.9 V value, nonnegative model saturation margins
for M1–M5, and `0.05 V < VX < 1.75 V`. On the 20 mV VCM grid, the largest
contiguous valid interval containing 0.9 V is **0.76–1.24 V**.

- At 0.8 V: gain change `+0.3527407 dB`; minimum saturation margin
  `0.0355600256 V`; `PASS`.
- At 1.3 V: gain change `-4.2908617 dB`; minimum saturation margin
  `0.163156821 V`; `FAIL` due to gain loss despite every tracked device
  remaining saturated.
- A preliminary DC-only operating-region heuristic spans 0.76–1.49 V, but it
  is not the formal gain-based ICMR and cannot be used to claim 0.8–1.3 V.

The Day 2 first stage therefore does not meet the intended full range. The
retained stage state is `DAY2_FIRST_STAGE_CHARACTERIZED_NOT_FINAL_OTA`.

### Area/bandwidth tradeoff

An oversized iteration used legal explicit-parallel M3/M4 banks totaling
179.4248 µm per side at `L = 0.8 µm`. It produced 38.2056 dB gain,
13.106718 MHz 3 dB bandwidth, a 0.76–1.22 V formal ICMR, and a 331.0868 µm²
channel-area proxy. The selected 50 µm/0.5 µm banks produce 36.2697 dB,
45.524514446 MHz, 0.76–1.24 V, and 94.0071 µm². Selection therefore trades
1.9359 dB gain for a 71.6065% smaller proxy and 3.473× bandwidth, while slightly
improving the upper ICMR boundary. The proxy is `sum(W × L)` for comparison;
it is not a placed-layout area claim.

### Failures retained

- A single 179.4248 µm-wide PMOS exceeded the installed compact-model
  `wmax = 100 µm` bin and failed with `could not find a valid modelname`.
  Replacing it with explicit in-bin parallel units made the electrical
  iteration legal, but its area/parasitic cost was not selected.
- The first gain-versus-VCM analyzer expected three columns, while ngspice
  `wrdata` emitted four (including a constant-vector scale column). The
  electrical 91-point sweep completed; the parser failure and original output
  are retained, and the analyzer was corrected to parse all four columns.
- Earlier baseline/headroom/long-channel alternatives remain in
  `results/day2_iteration_summary.csv`; unsuccessful or rejected results were
  not deleted.

### Evidence paths

- Final summary: `results/day2_first_stage_summary.csv`
- Operating-point table: `results/day2_first_stage_operating_point.csv`
- Selected sizes: `results/day2_first_stage_sizing.csv`
- Formal ICMR sweep: `results/day2_icmr_gain_sweep.csv`
- Iteration comparison: `results/day2_iteration_summary.csv`
- Raw final and retained iteration outputs: `results/raw/day2/`
- Review plots: `results/plots/day2_first_stage_ac.png` and
  `results/plots/day2_first_stage_dc_icmr.png`

### Next action recorded at this checkpoint

- Add and bias M6/M7, then introduce Miller compensation and measure the
  complete OTA's nominal operating point, open-loop gain, UGB, phase margin,
  power, and unity-gain transient response.
- Preserve the Day 2 high-VCM failure as a known limitation; do not silently
  promote the first-stage-only interval to a full-OTA ICMR claim.

## 2026-09-03 — Day 3: second stage, loop break, and nominal compensation

### Completed

- Added the M6 NMOS common-source stage, M7 PMOS load, and single-`IREF` M8–M10
  bias tree while keeping the compact Day 2 M1–M5 sizes.
- Balanced M6 against M7 and the explicit 100 kΩ-to-VSS load current.
- Implemented a DC-closed/AC-open loop-gain testbench rather than inferring
  loop gain from the follower response.
- Retained 17 compensation candidates and selected `CC = 3 pF`, `RZ = 2 kΩ`.
- Ran the selected direct-feedback unity follower with 5 pF || 100 kΩ to VSS.
- Audited 19 top-level logs and produced the Day 3 summary, operating-point,
  comparison, and plot artifacts.

### Final compact nominal sizing

| Device | Geometry |
|---|---|
| M1/M2 | each `16.83798/0.5 µm` |
| M3/M4 | each side two `25/0.5 µm` units, 50 µm total width |
| M5 | `25.8754/0.8 µm` |
| M6 | `8.83907427/0.5 µm` |
| M7 | `72.2005/0.8 µm` |
| M8/M9 | each `7.22005/0.8 µm` |
| M10 | `8.08605/0.8 µm` |

The M6 balance residual `IM7 - IM6 - VOUT/100 kΩ` changes sign between
8.8 µm (+0.471056959 µA) and 8.9 µm (-0.734485599 µA). Interpolation selects
8.839074270408297 µm. At the final operating point, M6/M7 carry
83.2666517/92.2666438 µA and the load takes approximately 9 µA.

### Nominal result at TT/1.8 V/27 °C

| Metric | Result | Interpretation |
|---|---:|---|
| DC follower output | 0.899999206 V | PASS |
| Open-loop gain | 67.6747747 dB | hard + stretch PASS at nominal |
| UGB | 16.7454480155 MHz | hard + stretch PASS at nominal |
| Phase margin | 69.0829107715° | hard + stretch PASS at nominal |
| Supply current / power | 150.298315 µA / 270.536967 µW | hard + stretch power PASS at nominal |
| SR+ / SR- | 8.20202918 / 11.51994781 V/µs | hard + stretch PASS at nominal |
| Rise/fall slew-fit samples | 62 / 47 | frozen 20–80% least-squares method |
| Rise/fall 1% settling | 0.07475 / 0.04075 µs | hard + stretch worst-case PASS at nominal |
| Rise overshoot / fall undershoot | 74.99684 / 1.858472 mV | reported |
| Minimum M1–M10 saturation margin | 0.1161336635 V (M5) | PASS at nominal |

The SR extractor uses least-squares fits over the monotonic 20–80% rising and
80–20% falling intervals required by the frozen specification. The retained
sample counts exceed the five-point validity minimum.
Settling is measured from the corresponding input 50% crossing: 1.01 µs for
the rising edge and 3.03 µs for the falling edge.

### Implemented loop break and sign check

- `LBREAK = 1 GH` connects `VOUT` to `VINN`: effectively closed for DC bias and
  open for AC.
- `CBREAK = 1 GF` couples the 1 V AC test source to `VINN`: open at DC and
  effectively short for AC.
- The analyzer uses `T = -V(VOUT)/V(VINN)` and unwraps its phase.
- Selected low-frequency phase is -0.00682757215° at 1 Hz, validating the near-
  zero phase expected from the chosen return-ratio sign.

### Compensation before/after and retained failure

| Network | A0 | UGB | PM | State |
|---|---:|---:|---:|---|
| 3 pF, `RZ ≈ 0` | 67.6747747 dB | 17.2553341 MHz | 33.2236432° | baseline FAIL |
| 3 pF, 1 kΩ | 67.6747747 dB | 16.3621278 MHz | 52.2886533° | hard-PM FAIL retained |
| 3 pF, 2 kΩ | 67.6747747 dB | 16.7454480 MHz | 69.0829108° | selected PASS |

The selected resistor improves PM by 35.8592675° relative to the 3 pF-only
baseline with a 2.95495% UGB reduction. The 3 pF/1 kΩ point is not discarded:
its gain and UGB pass, but its PM misses the 55° hard limit.

### Numerical and scope limits

- `results/day3_log_audit.csv` shows all 19 logs completed without an audited
  fatal token.
- Each log contains one known PDK multiplier-hierarchy warning.
- Only `nominal_transient.log` used successful dynamic-gmin stepping; this is
  disclosed and must be rechecked at corners.
- At this Day 3 checkpoint, results were TT-only and PVT, complete-OTA
  ICMR/output swing, CMRR, PSRR, noise, and 1/2/5 pF load stability were
  `NOT_RUN`; Day 4 later completed them.
- The Day 2 first-stage-only 0.76–1.24 V ICMR and 1.3 V failure remain known;
  Day 3 did not replace them with a complete-OTA ICMR result.

### Evidence paths

- Final parameters and M6 balance: `results/day3_design_parameters.csv`,
  `results/day3_m6_balance.csv`
- Compensation: `results/day3_compensation_comparison.csv`,
  `results/day3_compensation_before_after.csv`
- Nominal summary/OP: `results/day3_nominal_summary.csv`,
  `results/day3_nominal_operating_point.csv`
- Plots: `results/plots/day3_m6_balance.png`,
  `results/plots/day3_loop_gain_compensation.png`,
  `results/plots/day3_unity_follower_transient.png`
- Raw decks/logs/data: `results/raw/day3/`

### Next action recorded at this checkpoint (completed in Day 4)

- Run the 13-point PVT matrix and remaining nominal/load-stability
  measurements, applying the same frozen SR/settling definitions.
- Preserve nonconvergence and spec failures in the aggregate summaries.

## 2026-09-03 — Day 4: full characterization and 13-point PVT

### Completed

- Rendered a shared explicit-`VSS` M1–M10 OTA from the Day 3 selected-parameter
  JSON; embedded one canonical manifest hash in every deck and result row.
- Validated Day 3 selection, nominal summary, and selected loop/transient deck
  consistency before running.
- Executed separate differential-gain, DC-closed/AC-open loop, operating-point,
  and direct-follower transient analyses at all 13 frozen PVT points.
- Completed nominal CMRR/PSRR± curves, a 121-point full-OTA ICMR sweep,
  362-row bidirectional output-swing evidence, 10 Hz–1 MHz noise, and CL=1/2/5
  pF loop/transient stability.
- Preserved all 171 required log rows: 51 `PASS` and 120
  `PASS_WITH_DYNAMIC_GMIN`; no required deck was omitted.
- Correlated seven nominal Day 4 quantities to Day 3; every correlation row
  passed.

### Core PVT result — all six metrics pass at all 13 points

| Metric | Worst result | Point | Hard limit | State |
|---|---:|---|---:|---|
| A0 | 65.5351 dB | P08 | ≥50 dB | PASS |
| UGB | 14.5527 MHz | P08 | ≥5 MHz | PASS |
| PM | 66.2452° | P13 | ≥55° | PASS |
| Quiescent power | 302.710 µW | P13 | ≤600 µW | PASS |
| SR+ | 7.97766 V/µs | P06 | ≥2 V/µs | PASS |
| SR- | 11.1958 V/µs | P08 | ≥2 V/µs | PASS |

Loop analysis accepts the first downward 0 dB crossing and rebuilds unwrapped
phase from the complex return ratio. All PVT points have one non-boundary
downward crossing. Power retains signed raw `I(VDD)` separately from its
absolute magnitude.

### Nominal characterization result

| Metric | Result | State |
|---|---:|---|
| Worst 1% settling | 0.07475 µs | PASS |
| CMRR at 1 kHz | 71.3222 dB | PASS |
| PSRR+ at 1 kHz | 36.3313 dB | FAIL |
| PSRR- at 1 kHz | 36.2510 dB | FAIL |
| Full-OTA ICMR | 0.76–1.22 V | FAIL at 1.3 V high endpoint |
| Output swing | 0.18–1.63 V | PASS |
| Input noise at 1 kHz | 401.170 nV/√Hz | REPORTED |
| Integrated noise, 10 Hz–1 MHz | 52.3016 µV RMS | REPORTED |
| PM at CL=1/2/5 pF | 94.1626° / 86.2882° / 69.0829° | PASS |

P06 and P13 do not remain within the absolute ±4 mV settling band in either
direction; P07 misses the rising direction. Their blank numeric fields and
`SETTLING_NOT_REACHED` states are retained. Settling is nominal-only and does
not change the core PVT pass policy.

### Failures and warnings retained

- PSRR+ and PSRR- miss 45 dB and remain explicit failures.
- Full-OTA ICMR low endpoint passes at 0.76 V, but the 1.22 V high endpoint
  misses 1.3 V and remains an explicit failure.
- Noise has no pass target; 24 model conductance-reset warnings are retained in
  the audit.
- Dynamic-gmin completion is represented by `PASS_WITH_DYNAMIC_GMIN`, not
  rewritten as warning-free execution.

### Evidence paths

- Aggregate results: `results/summary.csv`, `results/pvt_summary.csv`
- Nominal result index: `results/day4_nominal_summary.csv`
- Audit and operating points: `results/day4_log_audit.csv`,
  `results/day4_pvt_operating_points.csv`
- Detailed sweeps: `results/day4_cmrr_psrr_curves.csv`,
  `results/day4_icmr_sweep.csv`, `results/day4_output_swing_sweep.csv`,
  `results/day4_noise_curve.csv`, `results/day4_load_stability.csv`
- Figures: `results/plots/day4_*.png`

## 2026-09-03 — Day 5: bounded optimization reconnaissance and report closure

### Decision

- Use the Day 3 3 pF-only versus 3 pF + 2 kΩ compensation change as the formal
  optimization: PM improves 33.2236° → 69.0829° while UGB changes
  17.2553 → 16.7454 MHz.
- Keep the Day 4-characterized geometry and compensation as the reported result.
- Treat `first_stage_l2`, `first_stage_l3`, and `m7_l2` as nominal
  reconnaissance only, not replacements. The campaign completed 32/32 log,
  48/48 raw-TSV, and 9/9 result-CSV contract checks under manifest
  `89f886ce2a150b84945a5378f29c2d4ee3faa5ef832876aeb122deb05e01391e`.
- Reject `first_stage_l2` despite moving PSRR+/- to 72.419/67.315 dB: PM drops
  7.559° to 61.524°. At the Day 4-equivalent 1 Hz checkpoint, the 1.3 V ICMR
  gain delta worsens from -4.935 dB to -7.361 dB (-2.425 dB), while total
  channel-area proxy rises to 2.195×, and the full Day 4 campaign was not
  repeated.
- Reject `first_stage_l3` and `m7_l2` for nominal hard-PM regressions.

### Closure

- Published the six-page report at `docs/sky130_two_stage_ota_report.pdf` and
  linked it from the repository navigation alongside the retained,
  machine-readable evidence.
- The reconnaissance runner is fail-closed; four first-attempt failures remain
  retained, while all 32 corrected logs and 48 raw TSV contracts pass.
- Do not use untracked generated decks as the sole evidence for a design
  decision; cite stable summaries and the Day 3/Day 4 result tables.

### Scope boundary

The entire five-day project remains schematic-level simulation with an ideal
external 10 µA `IREF`. No mismatch/Monte Carlo, physical layout, DRC/LVS,
parasitic extraction, post-layout simulation, fabrication, packaging, or
silicon measurement has been completed.

## Daily entry template

### YYYY-MM-DD — Day N: short title

**Objective**

- What was intended for this session?

**Changes**

- What circuit, parameter, testbench, or automation changed?

**Evidence**

- Raw output path:
- Plot/table path:
- Conditions:

**Before / after / tradeoff**

| Quantity | Before | After | Unit | Interpretation |
|---|---:|---:|---|---|
| TBD | TBD | TBD | TBD | TBD |

**Failures retained**

- `NOT_RUN`, `NO_CONVERGENCE`, `SATURATION`, or specific spec failure:

**Next action**

- One concrete next step:
