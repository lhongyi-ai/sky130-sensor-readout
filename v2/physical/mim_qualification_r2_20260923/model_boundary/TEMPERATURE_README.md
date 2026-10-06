# Ordinary-interconnect temperature validation

The seven structures at −20/25/27/30/85°C produced 35 directly solvable DSPFs and 35 actual Spectre DC runs, all zero errors/warnings. Four pure-metal lines passed 20 normalized-temperature checks. Fifteen explicit-via outputs support 95 material-branch checks: M3=50, M4=25, via3=20.

Scaling each 25°C branch by its material law and resolving the network matched all fifteen target networks. Explicit/merged-via outputs were port-equivalent within printed-precision bounds, though their graphs differ. Four parallel vias appear as an equivalent 0.8525 Ω via term versus one via's 3.41 Ω at25°C; total port resistance also includes metal access.

Spectre loaded the unmodified DSPFs with target-temperature numeric resistors and no duplicate TC scaling. Maximum graph/Spectre relative difference was 4.391×10⁻¹³, source-current KCL residual 2.852×10⁻¹⁷ A. Rayleigh-monotonic branch rounding bounds distinguish print precision from unmeasured material/meshing uncertainty.

Only two structures had direct original-school25°C whole-graph controls; the other five remain NOT_AVAILABLE. Compiled technology hashes bind the batch preparation, without claiming every QRC call independently hashed the technology. This validates ordinary-interconnect temperature execution, not absolute resistance calibration, CAPM coupling or MIM RC de-duplication. Current pointer: `temperature_latest.json`.
