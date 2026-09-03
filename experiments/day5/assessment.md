# Day 5 isolated optimization reconnaissance

Manifest: `89f886ce2a150b84945a5378f29c2d4ee3faa5ef832876aeb122deb05e01391e`. The baseline is bound to Day 3 selected parameters, Day 3 compensation evidence, and Day 4 manifest `6b90c7326a881914a362e3b2e6e96e4716b20c8b8196590f22c2ce5e1ab460ab`.

All values are SKY130A TT, 1.8 V, 27 C, VCM=0.9 V, 5 pF || 100 kohm to VSS unless noted. PSRR is 20log10(|Ad/Asupply|) at 1 kHz; ICMR checkpoint gain is the Day 4-equivalent 1-Hz value. The three ICMR values are checkpoints, not a continuous-range claim.

| Variant | A0 dB | UGB MHz | PM deg | Pq uW | SR+/- V/us | 1% settle us | PSRR+/- dB | ICMR 0.8/1.3 | Disposition |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| baseline | 67.675 | 16.745 | 69.083 | 270.537 | 8.202/11.520 | 0.0748 | 36.331/36.251 | True/False | PRODUCTION_BASELINE_RETAINED |
| first_stage_l2 | 74.376 | 16.741 | 61.524 | 271.084 | 8.094/11.858 | 0.0767 | 72.419/67.315 | True/False | REJECTED_TRADEOFF_NOT_PRODUCTION_SELECTED |
| first_stage_l3 | 76.125 | 15.708 | 53.713 | 271.228 | 7.912/12.105 | 0.1017 | 83.418/72.821 | True/False | REJECT_CORE_HARD_REGRESSION |
| m7_l2 | 65.203 | 13.446 | 37.022 | 168.872 | 4.686/11.655 | 0.2657 | 71.574/61.817 | True/False | REJECT_CORE_HARD_REGRESSION |

## Decision

`first_stage_l2` is the strongest nominal PSRR candidate, but it is not selected: first_stage_l2 improves nominal PSRR but changes PM by -7.559 deg, changes the 1.3-V gain delta by -2.425 dB, and changes total gate-area proxy by 2.195x without full Day 4 revalidation. The frozen Day 4 baseline remains the production design.
The adopted optimization remains the Day 3 change from `cc3p_rz0` to `cc3p_rz2k`, which improved PM by 35.859 degrees.

## Promotion gate

Any candidate promotion requires a complete Day 4 rerun: all 13 PVT points with gain/UGB/PM/power/SR and M1-M10 operating points; strict nominal P01 1% settling plus Day4-defined transient status at every other PVT point; the full 121-point continuous ICMR; bidirectional output swing; CMRR/PSRR frequency curves; input noise; CL=1/2/5 pF loop and transient stability; and the complete log/raw/manifest integrity audit.

## Audit scope

- Corrected simulations: 32/32 logs PASS with matching exit records.
- Raw evidence: 48/48 TSV files pass exact set, row, column, finite, stamp, and grid checks.
- ICMR: 120 device rows cover M1-M10 at all 3 checkpoints for all 4 variants.
- Retained initial failures: 4 classified logs remain under `retained_failures/attempt1`.
- Every loop has exactly one downward 0-dB crossing, no extra crossing, and no boundary crossing.
- Slew and 1% settling use the strict Day 4 definitions.
- Schematic-level only; no mismatch, Monte Carlo, layout, or extracted parasitics.
