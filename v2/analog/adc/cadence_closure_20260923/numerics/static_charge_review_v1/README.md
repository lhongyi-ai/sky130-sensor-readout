# Actual single-device DC mode-boundary results

Eight actual school DC sweeps contained 14,408 complete finite points, all with exit 0, zero errors/warnings and five notices. Spectre21.1.0.132.isr1 used the original PFET W/L=32 µm/150 nm, m/nf=1, fixed G=0.91642555277800053 V and S/B=1.8 V, TT/27°C. Baseline/strict relative and absolute tolerances tightened tenfold; model hashes remained unchanged.

Wide forward/reverse sweeps used 401/801 points over ±20 mV; fine sweeps 2001/4001 points over ±1 mV with 1/0.5 µV steps. The signed axis is external D−SB. Actual reversed=0 for negative bias and 1 at zero/positive bias, without swapping ports or changing raw-charge signs.

| Saved field | Negative-side slope, fF | Positive-side slope, fF |
| --- | ---: | ---: |
| qgi | −14.259191267 | −9.391433843 |
| qdi | +20.572942603 | +9.403545870 |
| qbi | −15.492381334 | +1.978716900 |

These 1–5 µV one-sided slopes repeat across precision, sweep direction and actual grid controls. Extrapolated intercept differences decrease with a smaller fit window; no finite charge jump is established. dQ/d(external bias) is not automatically a saved internal partial capacitance.

Actual qg/qgi, qd/qdi, qs/qsi and qb/qbi aliases are identical at every point despite nonzero overlap fields. Do not independently add overlap/junction terms without their definitions. Exported selector values 2147483647 and body-R nan are unresolved sentinels, not physical options. Source literals rbodymod=1 and 50 Ω body resistances are a separate evidence layer. Missing ig/is/ib OP aliases were not filled; independently saved terminal currents exist.

The actual effective dimensions and all bias/charge/metadata details remain in `all_sweeps_audit.json`, `branch_analysis.json`, `metadata_review.json` and inventories. Five independent parser/field tests passed. Actual AC port controls follow separately; no PDK bug or full-ADC repair is proven.
