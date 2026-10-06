# Native schematic generator review

The fixed generator and the 20-device mapping probe were reviewed independently. All probe connections and principal simulation parameters matched the creation inventory; 11 method tests passed. This is a topology/parameter result, not qualification of the complete 133-device frontend.

Pin coordinates come from the first pin figure and the instance transform. Short-wire directions and placement spacing are heuristic: new symbols, multiple pin figures, wire intersections and missing ground instances require explicit exported-netlist checks. Labels are attached to wire objects, but graphical proximity alone does not establish connectivity. CDF readback must be compared against the requested parameters; total width alone does not preserve diffusion parasitics after fingering.

For analogLib/vdc, the database property is `vdc`, while the netlisted parameter is `dc`. analogLib/res uses `r`. Ground creation and schematic diagnostics must be checked, and every missing or unexpected device, model, terminal, multiplier, size or stimulus must stop migration.

Evidence: `mapping_probe_r2_audit_expectation.json`, `mapping_probe_r2_native_audit.json` and the complete native topology audit. Original source hashes remain in the evidence records.
