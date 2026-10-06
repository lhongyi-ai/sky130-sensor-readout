# Native STB probe topology and scope

Contracting the three ideal probes recovered all 133 original devices with matching connections and parameters. DM_PROBE cuts the differential summing-node path to the input pair; CM1_PROBE cuts NCM to first-stage PMOS gates; CM2_PROBE cuts CMG to second-stage NMOS load gates. Their results are conditional return ratios with other loops closed.

The first STB attempt failed because the installed diffstbprobe definition was missing from the input. No valid margins were produced by that attempt; the failure is retained. Later successful runs explicitly include the installed analogLib dependency and are reviewed separately.

Input common mode must be checked in addition to the two explicit CMFB paths. Moving a probe changes the reference network, so margins from different cuts are not interchangeable. Preserve the complex return ratio, sign convention, all crossings and phase branches. No unity crossing means margin is not applicable, not automatically ≥60°.

The fixed QZ diagnostic returned 104 poles and zero RHP poles, with rightmost real part −218.544 Hz, but reported a BSIM4 frequency-dependent-equivalent warning. It is an approximate linear diagnostic, not complete coupled-loop, hidden-mode, switched-load or PVT qualification. Evidence: `stb_topology_independent_review.json`.
