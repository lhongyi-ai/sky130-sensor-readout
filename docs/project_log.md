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
