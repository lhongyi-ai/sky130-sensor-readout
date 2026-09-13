# V2 Local Behavioral Experiment Results

Behavioral models and budgets only, not SKY130 circuit performance.
Cadence deferred; M2 still lacks PDK feasibility evidence and cannot be marked fully passed.

## Sampling Results Under Assumed Budgets

| Gain | Input frequency Hz | SNDR dB | ENOB |
|---|---:|---:|---:|
| 1 | 994.873 | 69.244 | 11.210 |
| 1 | 4998.779 | 69.262 | 11.213 |
| 4 | 994.873 | 69.044 | 11.177 |
| 4 | 4998.779 | 69.042 | 11.176 |
| 16 | 994.873 | 66.651 | 10.779 |
| 16 | 4998.779 | 66.671 | 10.783 |

These numbers depend on assumed noise/gain/offset parameters in the configuration and cannot establish chip compliance.
Linear calibration improves static error without changing SNDR; this invariance has been checked automatically.

## Independent Static Calibration Validation

| Gain | Maximum mean error before calibration, LSB | After calibration |
|---|---:|---:|
| 1 | 8.637 | 0.167 |
| 4 | 10.721 | 0.155 |
| 16 | 18.836 | 0.116 |

Errors are means over multiple samples, not single-conversion accuracy. Test points are separate from calibration points.

## Failure Retention and Evidence Boundaries

- assumed_nominal_sndr_targets_met: PASS
- assumed_nominal_calibration_targets_met: PASS
- allocated_settling_target_met: PASS
- rss_budget_allocations_fit: PASS
- ideal_linearity_passes: PASS
- cdac_negative_control_fails: PASS
- all_high_noise_controls_fail_sndr: PASS
- slow_settling_control_fails: PASS
- fixed_calibration_exposes_high_gain_drift: PASS
- pvt_matrix_not_fabricated: PASS
- no_calibration_or_holdout_clipping: PASS

Here PASS means the checker correctly identifies preset failures, not that the chip passes acceptance.
The 135 rows of 45 process/voltage/temperature points times three gains are test definitions only; all remain NOT_RUN.

## Key Budgets

- LSB: 195.312500 µV; 0.25 LSB: 48.828125 µV。
- Acquisition window: 2.500 µs; single-pole time-constant upper limit for a full-scale step: 257.624 ns.
- A 20 fF unit is only a candidate assumption, corresponding to 81.92 pF per side; layout implementation and matching are not established.
- Noise folding, dynamic reference loading, the real comparator, power, area, layout, and parasitics still require circuit verification.
