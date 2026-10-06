# Four-channel native STB results and r2 diagnostics

Actual conditional STB results were obtained after including the installed probe definition. Probe insertion preserved the fixed OP and differential AC response within the audit tolerances: maximum DC node change 2.22618 nV, branch-current change 0.260394 pA and differential AC relative change 0.531654 ppm.

| Channel | Observed unity crossings | Native PM | Native GM |
| --- | ---: | ---: | ---: |
| DM | 1, 2.212007 MHz | 82.8710° | 36.2177 dB |
| CM1 | 1, 4.377370 MHz | 95.6360° | 20.4587 dB |
| CM2 | 1, 6.239513 MHz | 118.6826° | 34.4118 dB |
| input_cm | 0 | not applicable | not returned |

Each saved curve has 1401 points from 0.01 Hz to 1 THz. All observed magnitude and real-axis crossings are retained in `stb_results_independent_review.json`; sampled searches do not exclude hidden paired crossings. The CM1 gain margin near 876 GHz is a model extrapolation, not evidence of physical process validity at that frequency.

Native margins refer to the exported L convention. Using `T=−L` requires a consistent critical point and continuous phase convention; arbitrary per-channel sign flips are invalid. Conditional positive margins and approximate zero-RHP QZ results do not establish global coupled-loop stability.

The historical r2 proposal separated two measured perturbations: G4 feedback segments 40.725→40.225 µm, and common-mode load segments 51.9→56.9 µm, before combining an independently checked candidate. Predictions were not simulation results. The current frontend still requires complete multi-loop, noise, actual sampling and PVT qualification.
