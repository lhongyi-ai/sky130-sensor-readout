# TT three-temperature failures and conditional revisions

The same r3 native netlist and stimulus were run at −20, 27 and 85°C. Each gain used coefficients fitted only at 27°C, fixed for the other temperatures, and 78 independent validation points. No failed endpoint was removed.

| Gain | 27°C residual, LSB | −20°C residual, LSB | 85°C residual, LSB |
| --- | ---: | ---: | ---: |
| 1 | 0.05150 | 30.37607 | 29.07123 |
| 4 | 0.45560 | 3.77419 | 1.01078 |
| 16 | 0.31777 | 2.83472 | 4.65990 |

G1 failed at both temperature extremes and G16 failed at 85°C against 4 LSB. At low-temperature G1, 2/81 points exceeded ±0.4 V; G16 at 85°C retained only about 179 µV endpoint headroom. All 13 saved core MOS devices remained in region 2, so these failures were not explained by observed loss of saturation.

Measured 1 Hz branch decomposition distinguishes the resistor ratio, feedback TG, fixed 350 Ω source-loading factor and finite core gain. G1 drift is dominated by the feedback TG term; G16 high-temperature drift has a larger resistor-ratio contribution. The exact resistance/gain tables and log-factor decomposition are in `temperature_screen_r3_independent_review.json`.

The historical r4 proposal widened only G1 feedback TGs and predicted a 9.400 µm feedback length. The separate G16 candidate halved its TG widths and predicted 79.185 µm segments. Their residual predictions are sensitivity estimates, not passed measurements, and do not cover changed curvature, PVT, mismatch, noise or stability. The three-temperature analog proxy is not 45-PVT or real ADC qualification.
