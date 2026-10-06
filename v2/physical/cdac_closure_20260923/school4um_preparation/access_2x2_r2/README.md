# Actual school 4µm 2×2 shared-access controls

Status: SCOPED_2X2_SHARED_ACCESS_GEOMETRY_AND_LVS_VERIFIED. The four devices have a common M4 top and four separate M3 bottoms, at local positions(0,0),(12,0),(0,12),(12,12)µm. Actual GDS and native extraction were independently checked.

| Sample | Ordinary/project DRC violations | LVS | Devices / nets / ports |
| --- | --- | --- | --- |
| good | 0 / 0 | MATCH | 4 / 5 / 5 |
| open | 0 / 0 | MISMATCH | 4 / 6 / 5 |
| short | 0 / 0 | MISMATCH | 4 / 4 / 4 |

The open case leaves the lower pair's top on an internal floating node; the short merges B00/B10. All four devices and4µm dimensions remain present, with zero black boxes or skipped comparisons. Wrong connections were not accepted by altering the reference or deleting devices.

Only geometry/access/connectivity are qualified here. No new evidence establishes CAPM materials, absolute coupling, model reference planes or RC de-duplication. Full-array mapping and physical extraction remain separate gates; `formal_ADC_PEX_allowed=false`.
