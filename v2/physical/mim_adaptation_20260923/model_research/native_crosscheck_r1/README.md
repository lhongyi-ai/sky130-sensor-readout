# Public-tool cross-check of native project MIM layouts

Four project-owned Cadence GDS exports were checked with frozen public KLayout0.30.11 rules and Magic8.3.681 full DRC. Both tools returned zero geometric violations, and Magic recognized one correctly sized MIM with separate plates per sample.

| Sample | CAPM dimensions, µm | via3 count |
| --- | --- | ---: |
| array4 | 4×4 | 81 |
| array8 | 8×8 | 361 |
| array4x8 | 4×8 | 171 |
| arraylead | 4×4 | 81 |

KLayout enabled FEOL/BEOL/OFFGRID/SEAL/FLOATING_MET, retained all output categories and used one thread. CAPM checks include 1.0 µm width, 0.84 µm same-layer spacing, 1.2 µm bottom-related spacing and 0.14 µm relevant enclosure/contact spacing; these rules are enabled with FEOL. No filtering manufactured a zero result.

These valid samples do not exercise every rule branch or certify all manufacturing restrictions. This local public-tool cross-check is separate from school PVS, Quantus or Spectre, and does not establish full PEX physical accuracy. Complete source/version and output records remain adjacent.
