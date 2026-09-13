# Original dimensions and Cadence migration dimensions

The original source is unchanged. The widths below are explicitly selected migration dimensions; 0.01 µm is not a minimum process grid inferred from the single M8 sample. All callbacks and exported netlists must still strictly match these target values.

| Device | Original W / µm | Migrated W / µm | Difference / µm | Relative change |
|---|---:|---:|---:|---:|
| M8 | 7.22005 | 7.22 | -0.00005 | -0.000693% |
| M9 | 7.22005 | 7.22 | -0.00005 | -0.000693% |
| M10 | 8.08605 | 8.09 | 0.00395 | 0.048850% |
| M1 | 16.83798 | 16.84 | 0.00202 | 0.011997% |
| M2 | 16.83798 | 16.84 | 0.00202 | 0.011997% |
| M3A | 25 | 25 | 0.00 | 0.000000% |
| M3B | 25 | 25 | 0.00 | 0.000000% |
| M4A | 25 | 25 | 0.00 | 0.000000% |
| M4B | 25 | 25 | 0.00 | 0.000000% |
| M5 | 25.8754 | 25.88 | 0.0046 | 0.017778% |
| M6 | 8.83907427041 | 8.84 | 0.00092572959 | 0.010473% |
| M7 | 72.2005 | 72.2 | -0.0005 | -0.000693% |

The migrated total M7 width of 72.2 µm is split into parallel PMOS devices M7A and M7B, each with W=36.1 µm, L=0.8 µm, and fingers=m=1; their D/G/S/B terminals connect to the corresponding original M7 terminals. The school report confirms a 50 µm single-finger limit. Each split device generates its own diffusion geometry; parasitics are not guaranteed to match a single instance and require simulation comparison.
Only the 7.22 µm M8 has independent school CDF diagnostic evidence; all instances in this version still await Linux validation. The maximum relative total-width adjustment is below 0.05%; this does not establish the performance difference. Comparisons between the old ngspice and new Cadence results must account for dimension mapping, parallel splitting, and model-version differences.
