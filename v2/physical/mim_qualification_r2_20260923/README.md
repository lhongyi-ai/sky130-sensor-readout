# MIM r2: temperature and external-lead controls

Actual school tools created nine independent control layouts without changing the installed technology, old designs or r1 evidence. Ordinary M3/M4/via3 temperature binding was demonstrated numerically, while physical MIM RC ownership and CAPM coupling remain unqualified.

Seven ordinary-interconnect layouts cover M3/M4 10/50 µm lines, one via3, four parallel vias and two series vias. An isolated technology copy received documented temperature coefficients and was recompiled/read back. Thirty-five DSPFs cover −20/25/27/30/85°C; fifteen explicit-via outputs permit material checks. Twenty pure-metal temperature points, 95 material branches, fifteen scaled network predictions and fifteen merged/explicit equivalence comparisons passed.

All 35 actual Spectre DC runs had zero errors/warnings and agreed with the original DSPF graph solve to maximum relative difference 4.391×10⁻¹³. QRC outputs target-temperature resistances; Spectre did not apply a second temperature scaling.

Two fixed-reference MIM lead controls passed nine project DRC checks/LVS and retained the functional capacitor. Outer 10/30 µm leads measured 0.94/2.82 Ω, a 1.88 Ω increment. This verifies the current extraction arithmetic, not independent material calibration. Internal/model RC terms still overlap without a proven physical reference plane.

CAPM stack, coupling reference and absolute resistance provenance remain prerequisites. Formal ADC PEX is false; detailed evidence is in the temperature, model-boundary and physical-basis subdirectories.
