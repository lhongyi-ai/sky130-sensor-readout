# MIM electrical network and unresolved physical boundaries

Twelve retained DSPFs and the frozen functional model were independently analyzed by node equations and network power. Numerical connectivity is understood, but internal-model/extracted-RC physical ownership is not proven.

| Geometry | PLUS access R, Ω | MINUS access R, Ω | Model series R, Ω |
| --- | ---: | ---: | ---: |
| 4×4 µm | 0.081678 | 0.043084 | 0.114679348 |
| 8×8 µm | 0.052830 | 0.044864 | 0.063813923 |
| 4×4 µm long lead | 1.616599 | 0.043084 | 0.114679348 |

These are access resistances to the functional instance, not two-terminal DC resistance through an open capacitor. Extracted instance endpoints lie at plate centers while external pins are elsewhere; the original model gives electrical c0/c1, without a proved geometric reference plane.

Actual contacts 81/361/171 differ from model effective counts 50.384646/202.808115/101.086177. The continuous density formula cannot be replaced by integer cuts. Swapping 4×8 to 8×4 preserves C/contact count but changes internal M3 R from 0.094295597 to 0.023426332 Ω. LVS dimension rejection does not prove its axis convention matches the original model.

Graph/Spectre AC agreement is same-network numerical consistency, not physical calibration. Unblocked/local-blocked outputs are sensitivities, not guaranteed bounds. No arbitrary deletion/addition of internal R or perimeter C is justified.
