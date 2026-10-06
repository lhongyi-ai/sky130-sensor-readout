# Actual body-network observation: no qualified repair

The 4.1 µs diagnostic completed with zero Spectre errors and two warnings. Its complete-protocol checker returned 2 as expected. All requested new fields existed; no missing values were filled. All 4951 original times and 76 common voltages matched the previous probe exactly.

| Observation | Before | After |
| --- | ---: | ---: |
| External CONV−VDD | 267.270 µV | −593.355 µV |
| Actual reversed state | 1 | 0 |
| int_b−VDD | 26.937 µV | −422.155 µV |
| dbnode−VDD | −1774.061 µV | −1839.803 µV |
| sbnode−VDD | 4.116 µV | −41.942 µV |

These changes share a 201.302 fs accepted step. They are not simply renamed or swapped body nodes. Saved OP vds follows the model's folded sign, so the plot uses externally calculated signed D−S.

Four-terminal current-sum residual was at most 2.276 fA. A reconstruction through three 50 Ω external-body resistances retained an 8.16e−10 A residual; it is not a complete physical current decomposition. Total terminal currents include displacement current. Port consistency does not prove physical accuracy or full-ADC convergence.

Actual inherited manifest frames=2/decisions=24 describes the source fixture. This short probe completes zero frames/decisions/protocol-abort checks. The scope clarification, all six mode events, raw neighbors and source hashes are retained in `review.json`, `scope_clarification.json` and `all_accepted_selected_points.csv`.
