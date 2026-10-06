# First native frontend result review

The complete 133-device native netlist matched the independent inventory, and school Spectre completed OP, AC and three DC points. school_r1 is a migrated candidate, not a qualified replacement for candidate_06.

| Quantity | Original ngspice candidate | School r1 Spectre |
| --- | ---: | ---: |
| Zero-input output common mode, V | 0.886288513 | 0.847279073 |
| Error from 0.9 V, mV | −13.711487 | −52.720927 |
| 1 kHz differential gain | 4.039493645 | 4.160373729 |
| Output for ±80 mV input, V | approximately ±0.323151835 | approximately ±0.332653415 |
| NCM, V | 0.662188818 | 0.664184019 |
| BN, V | 0.705724403 | 0.685314298 |

Actual 1 Hz branch ratios gave Rin ≈10.767329 kΩ, Rfb ≈45.884186 kΩ, feedback TG ≈489.394 Ω and core gain ≈1973.1. Including each 350 Ω sensor source, `G≈K/[1+(1+K)/A]` predicts 4.160384 versus the measured 4.160376. CDF display resistance was not used as the electrical reference.

The output common-mode servo had XCMS/XCMR currents 5.232506/7.765181 µA and tail current 12.997688 µA. These measurements localize the imbalance but do not assign all of it to one device. VDD+VCM static supply power was approximately 0.678978 mW for this frontend assembly only.

An earlier 81-point ngspice export repeated scalar MOS OP values in 210 columns. Those columns cannot prove device-region coverage at every input, although the original voltage and transient results remain preserved. The proposed follow-up separates gmin sensitivity, common-mode reference sweep and explicitly diagnostic bias clamping before selecting real-device changes.

Exact values, provenance and limitations: `school_r1_canary_independent_review.json`; analysis: `review_school_r1_canary.py`.
