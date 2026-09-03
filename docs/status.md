# Project Status

**Current gate:** Day 4 characterization and Day 5 nominal reconnaissance are
complete, and the final six-page report is published. The frozen reported
design remains the Day 3-selected 3 pF + 2 kΩ OTA.

| Gate | State | Evidence |
|---|---|---|
| Day 1 environment/devices | COMPLETE | tool/PDK smoke test, MOS lookup data, mirror sweep, checksum manifest |
| Day 2 M1–M5 first stage | COMPLETE WITH KNOWN FAIL | formal first-stage ICMR 0.76–1.24 V; 1.3 V high end fails gain-flatness criterion |
| Day 3 nominal two-stage OTA | COMPLETE | 3 pF/2 kΩ selected; nominal gain, UGB, PM, power, transient, and M1–M10 OP retained |
| Day 4 PVT/full characterization | COMPLETE WITH DOCUMENTED SPEC FAILURES | all 13 core-PVT rows pass; PSRR± and ICMR high endpoint fail |
| Day 5 optimization/report | COMPLETE | 32/32 logs, 48/48 TSVs, and 9/9 CSVs audited; formal compensation optimization frozen; nominal geometry variants rejected; six-page report published |

## Frozen design

- Compact M1–M5 dimensions from Day 2.
- M6 `8.83907427/0.5 µm`; M7 `72.2005/0.8 µm`.
- M8/M9 `7.22005/0.8 µm`; M10 `8.08605/0.8 µm`.
- Miller network: `CC = 3 pF`, `RZ = 2 kΩ`.
- Nominal load: 5 pF || 100 kΩ to VSS.

Day 4 reproduced the nominal result at 67.6760 dB A0, 16.7454 MHz UGB,
69.0829° PM, 270.537 µW, and 8.20203/11.51995 V/µs SR+/SR-. Worst nominal 1%
settling is 0.07475 µs.

Across the frozen 13-point matrix, the worst core values are 65.5351 dB gain
(P08), 14.5527 MHz UGB (P08), 66.2452° PM (P13), 302.710 µW power (P13),
7.97766 V/µs SR+ (P06), and 11.1958 V/µs SR- (P08). All six satisfy their hard
limits at all 13 points.

## Nominal characterization truth

| Metric | Result | State |
|---|---:|---|
| 1% settling | 0.07475 µs | PASS |
| CMRR at 1 kHz | 71.3222 dB | PASS |
| PSRR+ / PSRR- at 1 kHz | 36.3313 / 36.2510 dB | FAIL / FAIL |
| Full-OTA ICMR | 0.76–1.22 V | low endpoint PASS; 1.3 V high endpoint FAIL |
| Output swing | 0.18–1.63 V | PASS |
| Input noise | 401.170 nV/√Hz at 1 kHz; 52.3016 µV RMS from 10 Hz–1 MHz | REPORTED |
| CL = 1/2/5 pF phase margin | 94.1626° / 86.2882° / 69.0829° | PASS; no sustained/growing oscillation |

P06, P07, and P13 retain `SETTLING_NOT_REACHED` for the optional non-nominal
settling readout. Settling is nominal-only and is not one of the six core PVT
qualification metrics.

## Day 5 decision

The formal optimization is the Day 3 addition of `RZ = 2 kΩ` to the 3 pF
Miller capacitor: PM improves from 33.2236° to 69.0829° while UGB changes from
17.2553 to 16.7454 MHz. `first_stage_l2`, `first_stage_l3`, and `m7_l2` are
nominal reconnaissance only and are rejected as reported-design replacements. In
particular, `first_stage_l2` moves PSRR+/- to 72.419/67.315 dB but lowers PM to
61.524°. At the Day 4-equivalent 1 Hz checkpoint, it worsens the 1.3 V ICMR
gain delta from -4.935 dB to -7.361 dB (-2.425 dB), raises total area proxy to
2.195×, and has no PVT requalification. The reconnaissance completed 32/32
logs, 48/48 raw TSV checks, and 9/9 result CSV checks under manifest
`89f886ce2a150b84945a5378f29c2d4ee3faa5ef832876aeb122deb05e01391e`.

## Release artifacts and truth boundary

- Use `docs/sky130_two_stage_ota_report.pdf` as the final report; it preserves
  the core-PVT-qualified baseline and does not promote an unrequalified variant.
- Preserve PSRR± and high-end ICMR as explicit failures.
- Retain the 171-run Day 4 log audit, including dynamic-gmin and noise-model
  warnings, rather than claiming a warning-free campaign.
- Treat results as schematic-level simulation using an ideal external 10 µA
  reference. There is no mismatch/Monte Carlo, layout, extracted-parasitic,
  post-layout, fabricated, or measured-silicon evidence.

Reproduce the complete workflow with `./scripts/run_all.sh`. The authoritative
aggregate state is in `results/summary.csv` and `results/pvt_summary.csv`;
`results/day4_nominal_summary.csv` records
`DAY4_CHARACTERIZATION_COMPLETE`.
