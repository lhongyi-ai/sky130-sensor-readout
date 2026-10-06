# Numerical repair candidates r2 — historical rationale

This dated preparation proposed isolated controls, not accepted repairs: first cthresh=1p for an equivalent large-capacitor equation representation, then equivalent native Spectre reference R/C if justified. The real reference network remains 1 Ω/10 nF; no extra capacitance or relaxed threshold is introduced.

Installed help also supports traponly, trapgear2 and lteratio. Pure trapezoidal integration can expose ringing; a method name or reduced warning count is not accuracy evidence. Reducing lteratio from 10 to 1 tightens the LTE target relative to Newton tolerances and can increase recovery/runtime. It does not guarantee removal of discontinuity-related problems.

The retained body probe associates external VDS reversal and a 449.092 µV internal-body change in one 201.302 fs accepted step, without proving a PDK bug. Common-point forcing had already failed to improve the complete short-domain comparison, so it was not adopted as a repair.

These candidates were later actually tested and failed or remained incomplete; see `../RESULTS.md`. The full physical 0.05 LSB threshold, actual phase/load circuit and original RTL remain mandatory. Driver sizing is a circuit design change requiring independent review and requalification, not a numerical shortcut.
