# Frozen Sampling-Switch Files and Interface

Read `results/sampling_switch_release.json` first. Only the final four-transistor version below belongs
to this complete qualification; historical top-level `artifacts/` and other candidate directories must not enter the final GDS.

| Purpose | File/cell |
|---|---|
| Schematic-level SPICE | `candidates/adc_tgate_dual_lvt_dummy.spice` |
| Schematic subcircuit name | `adc_tgate_dual_lvt_dummy` |
| Post-parasitic SPICE | `artifacts/dummy_layout_final/adc_tgate_flat.rc.spice` |
| Parasitic subcircuit name | `adc_tgate_flat` |
| GDS | `artifacts/dummy_layout_final/adc_tgate_layout.gds` |
| GDS top cell name | `adc_tgate_layout` |
| Native Magic layout | `artifacts/dummy_layout_final/adc_tgate_layout.mag` and 4 device subcells in the same directory |
| Physical layout render | `artifacts/dummy_layout_final/adc_tgate_layout.png` |
| DRC/LVS/extraction records | `layout.log`, `lvs.rpt`, `lvs.json`, `rc_extraction.log` in the same directory |
| Complete per-point 45PVT results | `results/dummy_w4w8_rc_full.json` |
| Full-scale boundary results | `results/dummy_fullscale_boundaries.json` |
| All final raw waveforms | `evidence/final_qualification/*.tsv.gz`, `evidence/fullscale_boundaries/*.tsv.gz` |
| Open-source geometry license | `THIRD_PARTY_NOTICE.md`, `LICENSE.sky130.txt` |

Both SPICE subcircuits use port order `A B EN ENB VDD VSS`, but A/B are asymmetric.
A connects to the driven source; B to the held node, with both dummy terminals shorted to B. As a VCM top-plate clamp:

```spice
.include /project/v2/physical/adc_switch/candidates/adc_tgate_dual_lvt_dummy.spice
XCLAMP VCM TOP TOP_EN TOP_ENB VDD VSS adc_tgate_dual_lvt_dummy
```

For post-parasitic replacement:

```spice
.include /project/v2/physical/adc_switch/artifacts/dummy_layout_final/adc_tgate_flat.rc.spice
XCLAMP VCM TOP TOP_EN TOP_ENB VDD VSS adc_tgate_flat
```

`/project` is an example project-root path; replace it with the actual location and include the relevant
process corner from the qualified PDK. Only defaults N4/.15, P8/.35, and dummy ratio 0.5 are qualified;
size, load, or clock-edge changes require revalidation. Do not apply this directly to every small reference-MUX switch.
Historical GDS/RC files reuse demonstration cell names; import only the selected final version, without merging them all.

Frozen SHA-256:

- Schematic source: `389d182342b2d1e88ba31530c6cc98d0e75756d8009126746d7d73b40d98d734`
- RC netlist: `7497a012a94c1e48c1c7de7d13f61bfa4c709aec709d52faeafb06bf1867e2d5`
- GDS: `5e26038355c6f8ca3d10542af81bc53ca660998ca036aef55f5384585bb263e2`

Independent A-terminal step tests in this directory do not replace system clamp experiments under actual CDAC bottom-plate switching.
Schematic/RC passing results use the public SKY130 open-source flow, not Cadence verification or silicon measurements.
