# CDAC static-linearity verification after parasitic extraction (2026-09-11)

## Conclusion

The real capacitance network extracted from the final differential CDAC layout has been used for static charge-redistribution calculations across **all 4096 codes**. The method and inputs are valid, but the current layout's linearity **did not pass**:

- Differential endpoint INL: `−3.5621 to +3.5621 LSB`, against a target of `±1.5 LSB`;
- Differential endpoint DNL: `−3.8545 to +0.3243 LSB`, against a target of `−0.9 to +1.5 LSB`;
- **255 adjacent-code transitions reverse direction**, failing both monotonicity and the necessary condition for no missing codes;
- The worst reverse transition occurs at `2047 → 2048`;
- After endpoint normalization, the maximum P/N difference is only `0.01057 LSB`. This shows good left/right mirroring, but both sides reproduce the same systematic parasitic error, which differential subtraction cannot cancel.

The machine-readable conclusion is in [`qualification.json`](qualification.json), with status:

`CDAC_PEX_STATIC_LINEARITY_FAIL_NONMONOTONIC`

This is not a failure of the simulation program. The analysis ran to completion and passed input, connectivity, matrix, and file-hash checks. The failure lies in **the current physical capacitor weights themselves**.

## What the displayed image represents

The black-background image is neither a transistor schematic nor a complete chip. It shows the **layout of the differential capacitive DAC (CDAC)**, a passive module within the SAR ADC:

- The large rectangle on the left is the P-side capacitor array;
- The large rectangle on the right is the N-side capacitor array;
- Every small square is a real SKY130 MIM capacitor;
- The dense colored lines are metal and vias connecting capacitors to `TOP`, `B11…B0`, `DUMMY`, and `EDGE_BIAS`;
- Together the sides contain 8,712 physical MIM capacitors: 8,192 active capacitors and 520 edge-protection dummies;
- This layout has achieved DRC=0, a unique LVS match, and RC extraction in the open-source flow, which does not automatically establish qualified analog performance.

Original layout presentation images with no obscuring text are available at:

- [`../../../physical/cdac_route_20260911/artifacts/cdac_diff_routed_display_no_labels.png`](../../../physical/cdac_route_20260911/artifacts/cdac_diff_routed_display_no_labels.png)
- [`../../../physical/cdac_route_20260911/artifacts/cdac_routing_detail_display_no_labels.png`](../../../physical/cdac_route_20260911/artifacts/cdac_routing_detail_display_no_labels.png)

These PNGs hide text only in presentation copies; the GDS and electrical connectivity remain unchanged.

## Why linearity can fail after DRC/LVS passes

Think of the CDAC as a balance with twelve binary weights:

- B0 should contribute 1 unit;
- B1 should contribute 2 units;
- B2 should contribute 4 units;
- …;
- B11 should contribute 2048 units.

DRC checks only whether geometry violates manufacturing rules. LVS checks whether intended connections, device counts, and nets agree. Neither guarantees that parasitic capacitance from metal wiring preserves the exact `1:2:4:…:2048` ratio.

In the current results, lower-bit nets acquire relatively larger additional TOP coupling. For example, on the P side:

| Port | Effective TOP coupling |
|---|---:|
| B0 | 27.89023 fF |
| B1 | 55.94460 fF |
| B2 | 98.23780 fF |
| B3 | 182.90650 fF |
| B4 | 351.84180 fF |

When the code carries from `...01111` to `...10000`, B3…B0 are removed simultaneously and B4 is added. The current B4 increment is too small to compensate for removing all four low bits, so the output moves backward. This pattern repeats every 16 codes, producing 255 reverse transitions.

## How the PEX results were obtained

The final inputs are three frozen, unmodified RC PEX netlists:

- Differential top level: [`../../../physical/cdac_route_20260911/artifacts/cdac_diff_routed_flat_rc.spice`](../../../physical/cdac_route_20260911/artifacts/cdac_diff_routed_flat_rc.spice)
- P side: [`../../../physical/cdac_route_20260911/artifacts/cdac_side_p_routed_flat.rc.spice`](../../../physical/cdac_route_20260911/artifacts/cdac_side_p_routed_flat.rc.spice)
- N side: [`../../../physical/cdac_route_20260911/artifacts/cdac_side_n_routed_flat.rc.spice`](../../../physical/cdac_route_20260911/artifacts/cdac_side_n_routed_flat.rc.spice)

Analysis steps:

1. Read the differential top level's 30 real ports: `TOP`, `B11…B0`, `DUMMY`, and `EDGE_BIAS` for each of P and N.
2. Audit 26,210 extracted resistor segments, confirming that every internal metal node ultimately reaches exactly one correct port, with no floating islands or accidental shorts between ports.
3. In the static limit of infinite settling time, collapse finite resistances within each net to ideal wires. Resistance affects finite-time settling but does not change the final static capacitance ratios.
4. Read all extracted capacitors. The netlist actually contains 17,710 positive values with an `f` suffix, 20 positive values with a `p` suffix, and 2 explicit zeros; this analysis does not omit the `p` suffix.
5. For each 3 µm × 3 µm MIM, use the nominal intrinsic capacitance of `19.845 fF` previously measured and frozen in the same SKY130 environment for this project; add the extracted metal capacitance.
6. Calculate from TOP charge conservation:

   `ΔV_TOP = Σ(C_TOP,j × ΔV_j) / ΣC_TOP,j`

7. Apply the current code to P and its 12-bit complement to N; keep `DUMMY` and `EDGE_BIAS` fixed without switching.
8. Calculate outputs for every code from 0…4095, then compute endpoint INL, DNL, monotonicity, and the necessary condition for no missing codes.

All 12 code-driven TOP couplings agree exactly, term by term, between the independent P/N netlists and the differential top-level netlist. The top level adds only approximately `0.0003/0.0004 fF` of extra fixed TOP capacitance. This cross-check avoids reliance on a single file.

## Result plots: text separated from curves, with no overlapping annotations

Legends are outside the plotting area, and numerical annotations are not placed on curves.

![P, N, and differential INL and differential DNL for all 4096 codes](results/static_linearity.png)

The next plot separates each bit's error relative to ideal binary weighting. The P and N bars almost overlap, indicating that common routing parasitics dominate rather than left/right mismatch.

![Bit-weight errors after parasitic extraction](results/bit_weight_error.png)

## Auditable files

- [`results/all_4096_codes.csv`](results/all_4096_codes.csv): P output, N complemented-code output, differential output, INL, and DNL to the next code for each code.
- [`results/bit_weights.csv`](results/bit_weights.csv): intrinsic MIM capacitance, extracted additions, effective totals, and weight errors for B0…B11.
- [`results/capacitance_pairs.csv`](results/capacitance_pairs.csv): capacitance sources and totals between each pair of real ports.
- [`results/port_capacitance_matrix_fF.csv`](results/port_capacitance_matrix_fF.csv): a 31 × 31 symmetric pairwise-port-capacitance matrix covering 30 interfaces and substrate `VSUBS`, with a 0 diagonal; this is not a Maxwell matrix with negative diagonal terms.
- [`qualification.json`](qualification.json): input hashes, output hashes, algorithm scope, all thresholds, and final numerical values.
- [`analyze.py`](analyze.py): source for parsing, matrices, 4096-code calculation, CSV output, and plotting.
- [`test_cdac_pex_linearity.py`](test_cdac_pex_linearity.py): 11 regressions covering a small ideal binary circuit, sign direction, carry failure, real ports, suffix parsing, matrix symmetry, and input/output hashes.

## Test results

Run:

```bash
cd /Users/stanley/Documents/ChatGPT/Analog\ Circuit\ Project/sky130-two-stage-ota
python3 v2/analog/adc/cdac_pex_linearity_20260911/analyze.py
python3 -m unittest v2/analog/adc/cdac_pex_linearity_20260911/test_cdac_pex_linearity.py -v
```

Current result: `11/11 tests passed`.

The small ideal binary network returns numerical zero for both INL and DNL. Deliberately underweighting B4 makes the test detect a negative carry at `15 → 16`. These tests validate the matrix, direction, and fault detection rather than merely hard-coding answers for the final data.

## Recommended repair sequence

The current layout should not be inserted directly into the complete ADC and declared a 12-bit pass. A reasonable next round is:

1. Use `bit_weights.csv` for parasitic-aware redistribution of unit counts/compensation capacitors, first correcting the carry margin between B4 and the four low bits;
2. Alternatively, adopt a redundant/trimmable CDAC architecture with margin to absorb wiring parasitics;
3. Complete DRC, LVS, and RC PEX again after rerouting;
4. First repeat this directory's all-4096-code static check and confirm monotonicity and INL/DNL passes;
5. Then add real reference switches, interconnect R, and reference-source impedance for finite-time settling, followed by comparator, noise, SAR timing, and complete-ADC verification.

## Explicitly incomplete work

- No complete-ADC pass has been proven, and the 255 reverse transitions are not presented as a measured missing-code count for the final ADC;
- Dynamic RC settling, reference droop, switch nonlinearity, comparator behavior, noise, and SNDR have not been calculated;
- A single nominal MIM result has not been treated as a mismatch/process-corner result;
- Cadence has not been used, and future Cadence/university-rule closure has not been replaced;
- There are no silicon or laboratory measurements.

This stage advances from correct layout connectivity to discovering a systematic linearity problem through real parasitics that must be corrected, with all evidence retained for independent recalculation.
