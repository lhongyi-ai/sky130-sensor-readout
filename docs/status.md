# Project Status

**Current gate:** Day 3 nominal checkpoint complete; Day 4 qualification is
next.

| Gate | State | Evidence |
|---|---|---|
| Day 1 environment/devices | COMPLETE | tool/PDK smoke test, MOS lookup data, mirror sweep, checksum manifest |
| Day 2 M1–M5 first stage | COMPLETE WITH KNOWN FAIL | formal first-stage ICMR 0.76–1.24 V; 1.3 V high end fails gain-flatness criterion |
| Day 3 nominal two-stage OTA | COMPLETE AT TT ONLY | 3 pF/2 kΩ selected; nominal gain, UGB, PM, power, transient, and M1–M10 OP retained |
| Day 4 PVT/full characterization | NOT_RUN | 13-point matrix and remaining nominal metrics pending |
| Day 5 optimization/report | NOT_RUN | final tradeoff, report, and repository polish pending |

## Selected Day 3 design

- Compact M1–M5 dimensions from Day 2.
- M6 `8.83907427/0.5 µm`; M7 `72.2005/0.8 µm`.
- M8/M9 `7.22005/0.8 µm`; M10 `8.08605/0.8 µm`.
- Miller network: `CC = 3 pF`, `RZ = 2 kΩ`.
- Nominal load: 5 pF || 100 kΩ to VSS.

At TT/1.8 V/27 °C, the design reports 67.6747747 dB A0,
16.7454480155 MHz UGB, 69.0829107715° PM, 270.536967 µW, and
8.20202918/11.51994781 V/µs SR+/SR-. The slew values use the frozen 20–80%
least-squares method with 62/47 rising/falling samples; worst 1% settling is
0.07475 µs (0.07475 µs rising, 0.04075 µs falling), measured from the 1.01 µs
rising and 3.03 µs falling input 50% crossings. These remain nominal
schematic-level results only.

## Open work and truth boundary

- Run all 13 required PVT points; preserve failed and nonconvergent cases.
- Complete CMRR, PSRR, full-OTA ICMR, output swing, noise, and 1/2/5 pF load
  stability.
- Investigate the Day 2 high-common-mode gain loss rather than claiming the
  required 0.8–1.3 V range.
- Recheck transient convergence across PVT because the nominal transient used
  successful dynamic-gmin stepping.
- Treat the known multiplier warning as disclosed, not as evidence of a clean
  warning-free run.
- Do not claim fabrication, measurement, layout extraction, Monte Carlo yield,
  or PVT qualification.

Reproduce the current nominal checkpoint with `./scripts/run_day3.sh`. The
machine-readable state is `DAY3_NOMINAL_COMPLETE_PVT_NOT_RUN` in
`results/day3_nominal_summary.csv`.
