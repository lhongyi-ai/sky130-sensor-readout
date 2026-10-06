# Public functional MIM wrapper r1

This isolated public model supports M3/CAPM/via3/M4 and exposes p1_mim_public_r1 with PLUS,MINUS terminal order. PLUS is the top electrode through M4; MINUS is the M3 bottom. External w/l are SI metres: use 4u or 4e−6, never a suffix-free 4. The internal original model uses micrometre-valued numbers, with explicit wrapper conversion by 1e6.

```spectre
include "p1_mim_public_tt_r1.scs"
XCAP (PLUS MINUS) p1_mim_public_r1 w=4u l=4u
```

The deterministic nominal wrapper preserves area/perimeter capacitance and original series-metal/contact terms. It does not establish statistical qualification, physical PEX accuracy or support arbitrary contact geometry. Original mf is fixed to one and is not a physical parallel-capacitance multiplier.

LVS compares the measured physical primitive and geometry, rather than treating the expanded C+2R simulation network as multiple physical devices or blackboxing it. Source provenance and public licences are retained. No installed school PDK, proprietary deck or license is distributed.
