# Public 3µm CDAC static routing closure

A new complete old-public3×3µm CDAC candidate was physically rerouted and checked locally. P/N/top public Magic full DRC returned0/0/0 and Netgen matched all three. Actual top-level C extraction and all4096 static codes gave maximum abs(INL)=0.327237LSB, DNL−0.177832…+0.171533LSB and zero nonpositive transitions.

The original layout's3.562071LSB INL, −3.854472LSB minimum DNL and255 nonpositive transitions remain preserved. Independent carry/charge analysis localizes small-weight routing coupling rather than duplicate RC counting. The frozen public unit is19.845fF for3×3µm, not the school's34.62225fF4×4µm unit.

See [full candidate](full_candidate/README.md) for geometry, area and retained layout failures. This is an actual C-only static extracted-array result with ideal established bit/reference voltages, not real ADC all-code conversion, full RC dynamics, school migration or complete-core PEX.

`open_3um_static_reroute_pass=true`, `full_CDAC_repair_pass=false`, `formal_ADC_PEX_allowed=false`. School4µm work must respect the actual top/bottom polarity and verified access structure in `school4um_preparation/`, rather than scaling the old layout and reusing its best result.
