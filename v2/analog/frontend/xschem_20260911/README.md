# Non-Cadence frontend schematic entry point (Xschem, 2026-09-11)

This directory provides a **three-level frontend schematic review package that opens in Xschem and can also be viewed directly as PNG/SVG**. It makes the current frontend candidate, interfaces, key dimensions, and evidence boundaries readable while Cadence is not yet ready.

It is not a native Cadence Virtuoso library, a layout, or a qualified final frontend. The authoritative electrical implementation is `../dynamic_20260911/candidate_06.spice`, SHA-256 `a4ed567d6a5b1f8853124602fd3f0503118e77c751a6fc3152f772b89483a5f1`; authoritative test conclusions are in `../dynamic_20260911/qualification.json`. `artifact_manifest.json` fixes these source hashes and checks ports and key netlist connections.

## Quick access

View three 2400×1600 images without installing software:

1. `renders/frontend_top.png`: differential sensor, three-gain PGA, isolation/filtering, and the real SAR sampling boundary.
2. `renders/switchable_pga.png`: six cross-feedback branches for gains 1, 4, and 16, plus gain-selection logic.
3. `renders/rd_fdota.png`: transistor signal path of the fully differential two-stage OTA, biasing, directly sensed first-stage common-mode loop, and output common-mode loop referenced to external VCM.

If Xschem is installed, open the three pages separately from this directory:

```sh
xschem frontend_top.sch
xschem sky130_v2_switchable_pga.sch
xschem rd_fdota.sch
```

These pages are hierarchical views for human review; the top page points to the two detail pages in text. To avoid misrepresentation, netlists generated from these drawings must not replace the authoritative `candidate_06.spice`.

The project container already includes Xschem 3.4.8RC. To re-export, enter this directory from a container login shell with the SKY130 environment configured and run:

```sh
./render_headless.sh
```

The script generates three 2400×1600 PNGs and three SVGs. Each format uses a separate time-limited Xschem process, and the script cleans up its virtual-display process on exit.

## Content of the three schematic levels

### 1. Top level: `frontend_top.sch`

- The external differential sensor is on the left. The 350 Ω per side is the sensor's equivalent source impedance in the test environment, not an on-chip resistor.
- The middle contains the three-gain fully differential PGA.
- Each PGA output has an isolation resistor and a filter load made from 4 MIM cells. The subcircuit's default isolation resistance is 1.8 kΩ; the tested assembly providing this round's dynamic-pass evidence uses 1.5 kΩ per side. The drawing explicitly distinguishes them.
- The real SAR sampling boundary is on the right: the main LVT transmission gate, dummy transistors with shorted diffusions, and 4096 SKY130 MIM cells per side.
- The bottom fixes the authoritative netlist path and explicitly states that nominal static and real-load dynamic checks passed while formal multiloop stability remains unresolved.

### 2. PGA page: `sky130_v2_switchable_pga.sch`

- Each sensor input passes through a 10 kΩ input resistor to the `SUMPOS/SUMNEG` summing node.
- `OUTN` feeds back to `SUMPOS` and `OUTP` to `SUMNEG`, forming complete fully differential cross-coupled negative feedback.
- Each direction has three feedback branches of 10.35 kΩ, 41.4 kΩ, and 165.6 kΩ; each branch contains a real CMOS transmission gate.
- `SEL1:SEL0=00/01/10` selects gains 1/4/16 respectively; `11` selects no branch.
- At gain 1, the circuit still converts the differential input into a controlled fully differential output, controls common mode, lowers output impedance, isolates the sensor, and drives the SAR sampling load; it is not an inactive bypass.

### 3. OTA page: `rd_fdota.sch`

- First stage: 80/1 µm NMOS differential pair `XMIP/XMIN`, 40/1 µm tail transistor `XMTAIL`, and 64/1 µm PMOS loads `XMLP/XMLN`.
- First-stage common mode: `N1/N2` each average into `NCM` through 100 kΩ and 1 pF. `NCM` directly drives the two PMOS load gates, without an additional high-gain common-mode servo.
- Second stage: 180/1 µm PMOS common-source gain devices `XMSP/XMSN` and 9/1 µm NMOS output pull-down devices `XMOP/XMON`.
- Output common mode: `OUTP/OUTN` each average into `CMS` through 100 kΩ and 1 pF. A 20/1 µm error pair compares `CMS` with external `VCM`, using 10 kΩ source degeneration, an 8/1 µm tail device, and 105 kΩ loads to generate `CMG`, which controls both output pull-down devices.
- Each Miller branch contains a legal 1.2 kΩ `high_po_0p69` resistor plus 8 MIM cells. Its calculated length is 0.855 µm, above the 0.5 µm PCell minimum. This establishes schematic-parameter audit compliance only, not existing layout or DRC/LVS completion.

## Current candidate's passing results

All three gains use the same `candidate_06.spice`. At nominal TT, 1.8 V, 27 °C:

- Maximum static residual at points excluded from the three-point calibration: gain 1, 0.029642 LSB; gain 4, 0.019548 LSB; gain 16, 0.041138 LSB.
- Maximum acquisition error with the real sampling load: gain 1, 1.892 µV; gain 4, 1.743 µV; gain 16, 10.262 µV. All three pass this round's nominal dynamic threshold.
- Average frontend VDD＋VCM supplied power: approximately 0.702 mW at gain 1, 0.698 mW at gain 4, and 0.698 mW at gain 16.
- Device operating-region checks pass at all three gains; endpoint tracking checks with external VCM at 0.85 V and 0.95 V also pass.
- Schematic dimension audits pass for two key physical resistors: the 1.2 kΩ Miller zero-setting resistor is 0.855 µm long; the test assembly's 1.5 kΩ isolation resistor is 0.543 µm long. Both meet the 0.5 µm minimum.

## Incomplete work

This candidate **cannot yet be called a fully qualified frontend**:

- At the first downward 0 dB crossing, differential phase margins are approximately 86.38°, 84.86°, and 83.30° across the three gains; output common-mode margins are approximately 123.53°, 123.19°, and 123.00°. However, each differential return ratio crosses upward through 0 dB again at approximately 38.9–74.8 MHz, and the first-stage common-mode low-frequency return sign is anomalous at gains 1 and 4.
- Existing scalar injections do not provide the coupled multiloop system's return-difference determinant or open-loop right-half-plane pole count, so the formal multiloop stability gate is failed/unresolved. The favorable first downward-crossing margins cannot be quoted alone.
- The formal stability prerequisite has not passed, so the 45 PVT conditions have not been run, and noise is not qualified.
- There are no native Cadence schematics, frontend layout, DRC, LVS, PEX, or post-layout simulation results.

Precise status: **non-Cadence schematic review views are complete. Nominal static, real-load dynamic, power, and device-region checks pass at all three gains. Formal multiloop stability, 45-PVT, noise, and physical implementation remain incomplete.**

## Rechecking the evidence

Run in this directory:

```sh
python3 build_manifest.py
python3 -m unittest -v test_xschem_delivery.py
```

Automated checks cover:

- SHA-256 consistency of `candidate_06.spice` and the two qualification records;
- Port order for the three top-level subcircuits;
- The fully differential two-stage signal path, NCM/CMG loops, Miller branches, and key W/L values;
- Six cross-feedback branches, three resistor values, isolation resistors, and filter-load connections;
- 2400×1600 dimensions of the three PNGs, XML parsing of all three SVGs, file hashes, and absence of core dumps.

## Human visual review for overlaps

All three final PNGs were individually inspected at their original 2400×1600 resolution. Review findings are recorded in this directory's `qualification.json`:

- No text overlaps other text, wires, device boxes, or module borders;
- Every feedback branch lies fully inside its own box, with clear space between the third, gain-16 branch, its border, and the main signal box;
- Modules are clearly separated, and transistor net names, dimensions, titles, and power rails are kept apart;
- There are no missing CJK-glyph boxes, replacement characters, or `MISSING SYMBOL` labels.

This is a **human visual review** of the final images, not a computational-geometry proof. Automated tests only verify that this review record is complete and that the images have not subsequently changed; they cannot independently prove that no pixel overlap can ever exist.

## Export incident record

An early attempt that omitted the full container environment and combined PNG/SVG export in one Xschem process timed out and produced a 13 MB temporary core dump. That exact temporary file was removed, and no active Xschem process remained. Final export used the configured SKY130 login environment, one bounded process per format, and virtual-display cleanup on exit. All six final images were regenerated.

Once Cadence is ready, the devices must still be rebuilt and checked in Virtuoso against the authoritative netlist, followed by a formal multiloop stability method, 45-PVT, noise, layout, DRC/LVS, PEX, and post-layout simulation. This directory does not replace that work.
