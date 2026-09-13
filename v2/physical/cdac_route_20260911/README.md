# 12-bit Differential CDAC: Real SKY130 Routing, DRC/LVS, and RC Extraction

## Conclusion

This directory advances the previous CDAC floorplan of real but unconnected capacitors into an **independent passive differential CDAC macro with real metal connections**:

- Each P/N side has 4096 active unit capacitors and 260 edge dummies; the top has **8192 active MIMs** and **520 edge MIMs**, totaling **8712 real SKY130 MIM instances**.
- The original 64 × 64 electrical assignment is unchanged; each side still exactly satisfies `B11…B0 = 2048…1`, plus one electrical `DUMMY`.
- All 15 physical ports per side—`TOP`, `B11…B0`, `DUMMY`, and `EDGE_BIAS`—are connected; the differential top has 30 ports.
- Magic DRC is 0 for P, N, and the differential top.
- The representative tile, P side, N side, and differential top all **match uniquely in Netgen** against independent reference netlists.
- The complete differential top has flattened RC extraction retaining 8712 MIMs and producing 26,210 interconnect-resistor segments and 17,710 extracted-capacitor entries.

Final machine-readable status is `SKY130_CDAC_ROUTED_OPEN_PDK_PASS`; see [`qualification.json`](qualification.json). This PASS applies only to this directory's **passive CDAC macro**, not the complete SAR ADC, frontend, or chip, and is not Cadence/foundry sign-off.

The following two images are for presentation. To keep port names and text inside every MIM from obscuring devices or wires, the rendering script hides all GDS text only in an in-memory copy; it **does not rewrite the GDS**. Original evidence images with complete labels remain in `artifacts/cdac_diff_routed.png` and `artifacts/cdac_routing_detail.png`.

![Full differential CDAC routing without obscuring text](artifacts/cdac_diff_routed_display_no_labels.png)

The central B0/DUMMY region is enlarged below. Individual MIMs, M4 escapes from capacitor terminals, interrow M4 wires, via4 landings, and vertical M5 trunks are visible without text covering metal.

![Central routing detail without obscuring text](artifacts/cdac_routing_detail_display_no_labels.png)

## Actual connectivity

Each active capacitor has two terminals:

1. Terminal `C2` connects through an M3 horizontal wire actually overlapping the terminal to each row's TOP rail; an M3 vertical wire then joins all 64 rows into one `TOP` net.
2. Terminal `C1` first uses an M4 finger to enter the adjacent interrow routing channel; consecutive capacitors belonging to the same bit within a row join an M4 row bus.
3. Each row bus connects through real `via4` to an M5 trunk. There are 24 M5 trunks per side; multiple trunks for the same bit are physically joined by separate M4 peripheral buses above the array.
4. Every peripheral bus extends to a real pin landing before its port label is placed. Labels only name existing conductors and never replace metal across empty space.
5. Both terminals of the 260 perimeter edge dummies are locally shorted and connected to a separate M3 `EDGE_BIAS` ring; they do not incorrectly add 260 unit capacitors to `TOP`. During later integration, `EDGE_BIAS` must connect to a quiet fixed bias.

Original x coordinates and common-centroid bit assignments remain unchanged. To satisfy spacing for 1.18 µm via4 landings, 1.60 µm-wide M5, and interrow M4 routing, y pitch increases from 4.54 µm to 6.00 µm, a 32.1586% increase.

## Why these are not false connections from matching labels

This round used four independent levels of evidence:

- A small representative 4-MIM tile first validates M3/M4/via4/M5 port access, with DRC=0, unique LVS match, and a real R/C network extracted in a fresh Magic process.
- The complete-layout extracted netlist individually retains 4356 MIMs per side. The audit directly compares both extracted terminals of every MIM against the frozen original assignment CSV, rather than trusting summary counts or the same generator's claims.
- Each P/N side has only 15 nets, and the differential top has only the expected 30 ports; bit weights, TOP, and EDGE_BIAS connectivity in all raw netlists match the reference. A disconnected wire creating an extra node would fail these direct comparisons.
- Independent KLayout readback of final GDS confirms exactly two top-level side cells, exactly 4356 MIMs per side, and all 30 top-level physical port labels.

Netgen logs state that MIM models are compared as two-terminal black boxes, so LVS establishes **matching instance types, counts, pins, and network topology**. Actual MIM geometry comes from the verified SKY130 PCell and is separately constrained by Magic DRC and KLayout GDS readback. Netgen merging the 4356 same-net parallel MIMs into 14 groups is only a comparison optimization; raw extracted-netlist and CSV audits still check all instances individually.

## Core evidence

| Object | MIM count | Port/net count | Magic DRC | Independent LVS | RC extraction |
|---|---:|---:|---:|---|---|
| Representative tile | 4 | 3 | 0 | Unique match | 9 R, 11 C |
| P side | 4356 | 15 | 0 | Unique match | 13,105 R, 8,855 C |
| N side | 4356 | 15 | 0 | Unique match | 13,105 R, 8,855 C |
| Differential top | 8712 | 30 ports | 0 | Unique match | 26,210 R, 17,710 C |

All final `.res.ext` files are nonempty: representative tile 1168 bytes, P side 1,608,389 bytes, N side 1,607,456 bytes, differential top 3,433,086 bytes. These R/C counts prove an extracted network exists. Sums of resistor or capacitor entries are not equivalents for a particular end-to-end path and cannot directly establish settling time or INL.

## Area and routing resources

| Item | Result |
|---|---:|
| Routed pitch | x = 6.00 µm, y = 6.00 µm |
| Single-side readback bounding box | 431.60 µm × 422.50 µm |
| Differential top readback bounding box | 893.20 µm × 422.50 µm |
| Differential top macro area | 377,377 µm² = **0.377377 mm²** |
| Contiguous row runs per side | 140 |
| M5 trunks per side | 24 |

Physical resources are an M3 TOP mesh, M4 C1 escapes/row buses/peripheral buses, real via4, and M5 trunks. Area belongs only to the current passive differential CDAC; reference switches, sampling switches, comparator, reference buffers, digital controller, and frontend are excluded.

## Why early `.res.ext` files were empty

The first representative-tile attempt ran `extresist all` immediately within the same Magic process that built the hierarchical layout. That process retained the wrong hierarchical extraction root, could not find the flattened parent cell's `.ext`, and produced no resistor network. Complete failure output is retained in `probe_artifacts/attempt_in_process_extresist_root_failure.log`.

The repair moves RC extraction into a fresh Magic process, with each process handling one explicit root; it neither fabricates empty files nor lowers conditions. `extract_probe_rc.tcl`, `extract_rc.tcl`, and `extract_top_rc.tcl` all use this boundary. All four final `.res.ext` files are nonempty, and SPICE contains positive R/C values.

## Retained failures

| Failure | Evidence | Repair |
|---|---|---|
| First internal wide M3 trunk violates `capm.11`, 194 violations per side | `artifacts/attempt1_capm11_194_per_side.log` | Move TOP joining to a verified boundary slot and narrow vertical M3 to 0.30 µm |
| Second run loads old `.mag`, accumulating old geometry and retaining 194 violations | `artifacts/attempt2_stale_mag_replayed_194_per_side.log` | Delete only cells named by this generator before generation, then rebuild completely |
| DRC=0 but B0/DUMMY are not ports | `artifacts/attempt3_drc0_missing_b0_dummy_ports.log` | Physically extend each peripheral bus to the common pin x coordinate |
| Sides correct, but top extracts only two ports | `artifacts/attempt4_drc0_side_lvs_ready_top_ports_missing.log` | Add parent-level M3/M4 landings below every top label |
| Same-process RC extraction produces no resistor network | `probe_artifacts/attempt_in_process_extresist_root_failure.log` | Extract an explicit flattened root in a new Magic process |

## Key files and access

- `artifacts/cdac_diff_routed.gds`: final differential routed GDS; open with KLayout.
- `artifacts/cdac_diff_routed.mag`: Magic top; the same directory contains both side cells and `mim_unit.mag`.
- `artifacts/cdac_side_p_routed.gds`, `artifacts/cdac_side_n_routed.gds`: independent P/N macros.
- `artifacts/cdac_diff_routed_flat_rc.spice`: complete differential flattened RC PEX netlist.
- `artifacts/cdac_diff_routed_flat_rc.res.ext`: complete differential Magic resistor-extraction intermediate evidence.
- `artifacts/top_lvs.rpt`, `artifacts/side_p_lvs.rpt`, `artifacts/side_n_lvs.rpt`: raw LVS reports.
- `artifacts/magic_full.log`: raw P/N/top DRC log.
- `artifacts/klayout_readback.json`: independent GDS hierarchy, instance, and port readback.
- `qualification.json`: final machine audit, all checks, limitations, area, and key-file hashes.
- `probe_artifacts/`: preliminary representative-tile MAG/GDS/LVS/PEX and failure evidence.

Without installing EDA tools, open the two PNGs in this README, `qualification.json`, and LVS reports to inspect results. For interactive geometry, open `artifacts/cdac_diff_routed.gds` in KLayout; for electrical connectivity, open the PEX netlist in a text editor or SPICE tool.

## Reproduction and tests

Physical tools use fixed offline container `sky130-v2-resume-20260910`, with PDK `/foss/pdks/sky130A`. Run these commands from the repository root, executing physical tools sequentially so multiple processes do not edit the same cells:

```bash
# 1. Generate real-routing Tcl and an independent reference netlist from the frozen CSV
python3 v2/physical/cdac_route_20260911/generate_routed_cdac.py

# 2. Run the representative tile first, then extract its RC independently
docker exec sky130-v2-resume-20260910 bash -lc \
  'magic -dnull -noconsole -rcfile /foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc /repo/v2/physical/cdac_route_20260911/probe_routes.tcl > /repo/v2/physical/cdac_route_20260911/probe_artifacts/magic.log 2>&1'
docker exec sky130-v2-resume-20260910 bash -lc \
  'cd /repo/v2/physical/cdac_route_20260911/probe_artifacts && netgen -batch lvs "cdac_route_probe_flat.lvs.spice cdac_route_probe_flat" "reference.spice cdac_route_probe_flat" /foss/pdks/sky130A/libs.tech/netgen/sky130A_setup.tcl lvs.rpt -json > netgen.log 2>&1'
docker exec sky130-v2-resume-20260910 bash -lc \
  'magic -dnull -noconsole -rcfile /foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc /repo/v2/physical/cdac_route_20260911/extract_probe_rc.tcl > /repo/v2/physical/cdac_route_20260911/probe_artifacts/rc_extraction.log 2>&1'

# 3. Generate complete P/N/top layouts and run Magic DRC/extraction
docker exec sky130-v2-resume-20260910 bash -lc \
  'magic -dnull -noconsole -rcfile /foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc /repo/v2/physical/cdac_route_20260911/artifacts/generate_routed_cdac.tcl > /repo/v2/physical/cdac_route_20260911/artifacts/magic_full.log 2>&1'

# 4. Run P, N, and top-level Netgen LVS separately in artifacts/
docker exec sky130-v2-resume-20260910 bash -lc \
  'cd /repo/v2/physical/cdac_route_20260911/artifacts && netgen -batch lvs "cdac_side_p_routed_flat.lvs.spice cdac_side_p_routed_flat" "cdac_side_p_routed_flat.reference.spice cdac_side_p_routed_flat" /foss/pdks/sky130A/libs.tech/netgen/sky130A_setup.tcl side_p_lvs.rpt -json > side_p_netgen.log 2>&1'
docker exec sky130-v2-resume-20260910 bash -lc \
  'cd /repo/v2/physical/cdac_route_20260911/artifacts && netgen -batch lvs "cdac_side_n_routed_flat.lvs.spice cdac_side_n_routed_flat" "cdac_side_n_routed_flat.reference.spice cdac_side_n_routed_flat" /foss/pdks/sky130A/libs.tech/netgen/sky130A_setup.tcl side_n_lvs.rpt -json > side_n_netgen.log 2>&1'
docker exec sky130-v2-resume-20260910 bash -lc \
  'cd /repo/v2/physical/cdac_route_20260911/artifacts && netgen -batch lvs "cdac_diff_routed.lvs.spice cdac_diff_routed" "cdac_diff_routed.reference.spice cdac_diff_routed" /foss/pdks/sky130A/libs.tech/netgen/sky130A_setup.tcl top_lvs.rpt -json > top_netgen.log 2>&1'

# 5. Extract side and differential top RC in separate new Magic processes
docker exec sky130-v2-resume-20260910 bash -lc \
  'magic -dnull -noconsole -rcfile /foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc /repo/v2/physical/cdac_route_20260911/extract_rc.tcl > /repo/v2/physical/cdac_route_20260911/artifacts/rc_extraction.log 2>&1'
docker exec sky130-v2-resume-20260910 bash -lc \
  'magic -dnull -noconsole -rcfile /foss/pdks/sky130A/libs.tech/magic/sky130A.magicrc /repo/v2/physical/cdac_route_20260911/extract_top_rc.tcl > /repo/v2/physical/cdac_route_20260911/artifacts/top_rc_extraction.log 2>&1'

# 6. Independently read back with KLayout and export evidence and label-free display images
docker exec sky130-v2-resume-20260910 bash -lc \
  'cd /repo/v2/physical/cdac_route_20260911 && python3 render_klayout.py > artifacts/klayout_render.log 2>&1'

# 7. Audit all existing evidence and run regression tests without rerunning physical tools
python3 v2/physical/cdac_route_20260911/qualify.py
python3 -m unittest v2/physical/cdac_route_20260911/test_routed_cdac.py -v
```

`qualify.py` does not pass evidence merely because files exist. It parses DRC/LVS, ports, raw MIM terminals, CSV counts, RC components, `.res.ext`, GDS readback, PNG dimensions, and key-file hashes.

## Unfinished work not established by this directory

- No integration of reference-selection switches, sampling switches, comparator, reference distribution/buffering, digital SAR controller, frontend, or biasing.
- No reference-droop, settling, INL/DNL, noise, SNDR, or full-ADC post-layout simulation completed with this RC PEX.
- No EM/IR, antenna, density/fill, coupling-corner, or reliability sign-off.
- No Cadence use or replacement of the future school Cadence/verification-rule closed loop.

This directory completes an independently reviewable, practically integrable **passive differential CDAC physical macro** in the new project, not a complete ADC or finished chip.
