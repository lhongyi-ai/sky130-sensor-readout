# Architecture

**Status:** Architecture selected; the Day 2 M1–M5 first-stage SPICE block is
implemented and characterized. M6/M7, compensation, the loaded complete OTA,
and its authoritative Xschem schematic are not yet verified.

## 1. Signal path

```text
VINP/VINN
    |
    v
M1/M2 NMOS differential pair ---> M3/M4 PMOS mirror load ---> VX
    |                                                          |
M5 tail <--- VBN <--- MB diode NMOS <--- IREF                  |  Day 2 boundary
                                                               |
                                                  [complete OTA not yet verified]
                                                               |
                                                               v
                              M6 common-source stage ----> VOUT
                                      ^                      |
                                      |                      |
                              M7 PMOS current load            |
                                      |                      |
                                      +---- CC [and RZ] <----+
```

The diagram is functional, not a transistor-level schematic. The M1–M5 and MB
connections have been verified in the Day 2 SPICE block; M6/M7 orientation and
compensation polarity still require complete-OTA implementation and checking.

## 2. Blocks and responsibilities

### M1/M2 — NMOS differential input pair

- converts differential input voltage into signal current;
- largely sets input transconductance, input-referred noise, and UGB;
- participates in the lower limit of the input common-mode range;
- uses matched dimensions and bias conditions.

In the implemented Day 2 polarity, M1 senses `VINN`, M2 senses `VINP`, and
`VX` is an inverting first-stage output. Each device uses
`W/L = 16.83798/0.5 µm`.

### M3/M4 — PMOS current-mirror active load

- converts the differential branch currents to a single-ended first-stage
  output at `VX`;
- provides high incremental load resistance and first-stage gain;
- mirror mismatch and compliance affect gain and systematic imbalance.

Day 2 implements each M3/M4 side as two explicit `25/0.5 µm` PFETs in
parallel, for 50 µm total width per side. Explicit units avoid relying on the
PDK subcircuit multiplier hierarchy.

### M5 — NMOS tail-current source

- sets total input-stage current;
- finite output resistance affects common-mode gain and CMRR;
- its saturation headroom constrains the low end of ICMR.

Day 2 uses `W/L = 25.8754/0.8 µm`. At the nominal first-stage operating point,
M5 carries 38.0713829 µA and has 0.1160701611 V saturation margin.

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

The implemented Day 2 tail-bias branch forces 10 µA through diode-connected
NMOS MB (`W/L = 8.08605/0.8 µm`) to generate `VBN = 0.658036427 V`; M5 mirrors
that bias into the first stage. This verifies the tail branch only. The
second-stage PMOS bias required by M7 is still to be implemented.

## 3. Day 2 first-stage checkpoint

At TT/1.8 V/27 °C and `VCM = 0.9 V`, the two input branches are symmetric at
19.0356918 µA each, the tail node is 0.214664546 V, and
`VX = 0.792073469 V`. The block has 36.2697407 dB differential gain at 1 Hz
and 45.524514446 MHz first-stage 3 dB bandwidth.

The formal first-stage-only ICMR is **0.76–1.24 V**. The 0.8 V point passes,
but 1.3 V fails: its minimum M1–M5 saturation margin is still positive at
0.163156821 V, while gain has fallen 4.2908617 dB relative to 0.9 V. Therefore
the failure mechanism is high-common-mode gain loss, not loss of the tracked
devices' model saturation condition.

The selected M3/M4 sizing is an area/bandwidth compromise. Compared with the
legal explicit-parallel 179.4248 µm/side, `L = 0.8 µm` iteration, it reduces the
channel-area proxy from 331.0868 to 94.0071 µm² and increases first-stage 3 dB
bandwidth from 13.106718 to 45.524514446 MHz, while reducing gain from 38.2056 to
36.2697 dB. Neither block covers the required 1.3 V high end.

## 4. Named nodes and interfaces

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

## 5. Design sequence

1. **Complete:** characterize individual NFET/PFET devices in the installed PDK.
2. **Complete:** validate current mirrors and compliance ranges.
3. **Complete:** build M1–M5 with the diode-connected MB/M5 tail-bias mirror.
4. **Complete with documented high-end ICMR failure:** verify first-stage bias,
   gain, symmetry, and common-mode range.
5. Add M6/M7 and establish a valid quiescent output point.
6. Add `CC`, create the loop-gain bench, and tune nominal stability.
7. Add `RZ` only when supported by measured loop-gain evidence.
8. Complete nominal characterization and the 13-point core PVT matrix.

## 6. Explicitly out of scope

- bandgap or precision on-chip reference design;
- output buffer or rail-to-rail input stage;
- local-mismatch Monte Carlo or yield analysis;
- full-chip layout, parasitic extraction, and post-layout simulation;
- tapeout, fabrication, packaging, and laboratory measurement.

Partial matched-block layout plus DRC/LVS is optional after schematic-level
completion and does not change the claims above.
