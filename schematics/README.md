# Schematics

`two_stage_ota.sch` is the final annotated Xschem 3.4.8RC source for the
frozen Day 3 OTA core. Its pin order is `VINP VINN VOUT VDD VSS IREF`.
The matching standalone electrical source is
`netlists/ota/two_stage_ota_core.spice`.

For review and reporting, the same topology is redrawn as:

- `results/plots/final_two_stage_ota_schematic.svg` — vector artwork;
- `results/plots/final_two_stage_ota_schematic.png` — 3489 × 1976 raster.

The Xschem file was netlisted headlessly. The automated comparison in
`results/smoke/xschem/final_ota/connectivity_check.json` reports `PASS` for all
14 core components, including connectivity, model, W/L, `nf`, `mult`, RZ, and
CC. The canonical subcircuit also completed a nominal ngspice 47 operating-
point smoke test and reproduced the Day 3 output, internal-node, and supply-
current values.

The 100 kΩ / 5 pF output load and the 1 GH / 1 GF feedback-break elements are
testbench-only. They are shown in a separate inset in the review drawing and
are intentionally absent from the OTA core. These are schematic-level sources;
there is no layout, extraction, fabricated silicon, or measurement claim.
