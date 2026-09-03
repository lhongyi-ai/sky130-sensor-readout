# Project Log

Use this log for decisions, failures, and quantitative design iterations. Do not
rewrite unsuccessful runs out of the history.

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

### Not yet started

- Final bias-network sizing and the M1–M5 first stage.
- Full OTA schematic, compensation tuning, and closed-loop verification.
- OTA performance extraction and the 13-point PVT sweep.

### Next action

- Build the Day 2 bias network and M1–M5 differential stage, then retain its
  operating-point table, differential gain, symmetry check, and ICMR sweep.
- OTA-level `summary.csv` and `pvt_summary.csv` remain `NOT_RUN` until those
  circuits are simulated.

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

### Next action

- Add and bias M6/M7, then introduce Miller compensation and measure the
  complete OTA's nominal operating point, open-loop gain, UGB, phase margin,
  power, and unity-gain transient response.
- Preserve the Day 2 high-VCM failure as a known limitation; do not silently
  promote the first-stage-only interval to a full-OTA ICMR claim.

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
