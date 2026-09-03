# Architecture

**Status:** Architecture selected; schematic not yet implemented or verified.

## 1. Signal path

```text
VINP/VINN
    |
    v
M1/M2 NMOS differential pair
    |
M3/M4 PMOS current-mirror load ----> VX
                                      |
                                      v
                              M6 common-source stage ----> VOUT
                                      ^                      |
                                      |                      |
                              M7 PMOS current load            |
                                      |                      |
                                      +---- CC [and RZ] <----+
```

The diagram is functional, not a transistor-level schematic. Device numbering,
drain/source orientation, and compensation polarity must be verified in the
actual schematic before simulation.

## 2. Blocks and responsibilities

### M1/M2 — NMOS differential input pair

- converts differential input voltage into signal current;
- largely sets input transconductance, input-referred noise, and UGB;
- participates in the lower limit of the input common-mode range;
- uses matched dimensions and bias conditions.

### M3/M4 — PMOS current-mirror active load

- converts the differential branch currents to a single-ended first-stage
  output at `VX`;
- provides high incremental load resistance and first-stage gain;
- mirror mismatch and compliance affect gain and systematic imbalance.

### M5 — NMOS tail-current source

- sets total input-stage current;
- finite output resistance affects common-mode gain and CMRR;
- its saturation headroom constrains the low end of ICMR.

### M6/M7 — common-source second stage and active load

- M6 provides second-stage transconductance and gain;
- M7 supplies the nominal stage current and incremental output resistance;
- their headroom constrains output swing;
- their current and `gm` influence output drive, nondominant-pole location, and
  power consumption.

### CC and optional RZ — frequency compensation

- `CC` connects between `VOUT` and `VX` to create Miller pole splitting;
- increasing `CC` generally improves stability but reduces UGB and can affect
  slew rate;
- `RZ` is omitted initially and added only if the measured loop response shows
  that zero placement is needed.

### Bias network

- an external `IREF` avoids expanding the five-day scope into reference design;
- MOS mirrors generate tail and second-stage currents;
- ideal current sources may be used only for early block isolation, not for the
  final reported design under test.

## 3. Named nodes and interfaces

| Name | Purpose |
|---|---|
| `VDD`, `VSS` | 1.8 V supply rails |
| `VINP`, `VINN` | Differential inputs |
| `VX` | First-stage high-impedance output / compensation node |
| `VOUT` | Single-ended output |
| `IREF` | External reference-current input |
| `VBN`, `VBP` | Bias nodes, if used by the implemented mirror topology |

Names must remain consistent across the schematic, testbenches, raw outputs,
parsers, plots, and documentation.

## 4. Design sequence

1. Characterize individual NFET/PFET devices in the installed PDK.
2. Validate current mirrors and compliance ranges.
3. Build M1–M5 using an ideal tail source, then replace it with the bias mirror.
4. Verify first-stage bias, gain, symmetry, and common-mode range.
5. Add M6/M7 and establish a valid quiescent output point.
6. Add `CC`, create the loop-gain bench, and tune nominal stability.
7. Add `RZ` only when supported by measured loop-gain evidence.
8. Complete nominal characterization and the 13-point core PVT matrix.

## 5. Explicitly out of scope

- bandgap or precision on-chip reference design;
- output buffer or rail-to-rail input stage;
- local-mismatch Monte Carlo or yield analysis;
- full-chip layout, parasitic extraction, and post-layout simulation;
- tapeout, fabrication, packaging, and laboratory measurement.

Partial matched-block layout plus DRC/LVS is optional after schematic-level
completion and does not change the claims above.
