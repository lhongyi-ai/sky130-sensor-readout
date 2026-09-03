# Architecture

**Status:** Compact M1–M10 two-stage architecture and 3 pF + 2 kΩ compensation
are frozen. Day 4 completed the 13-point core-PVT and nominal characterization
campaign. Day 5 retains this architecture after rejecting nominal-only geometry
reconnaissance as an insufficient basis for promotion.

## 1. Signal path

```text
VINP/VINN
    |
    v
M1/M2 NMOS differential pair ---> M3/M4 PMOS mirror load ---> VX
    |                                                          |
M5 tail <--- VBN <--- M10 diode NMOS <--- M9 PMOS              |
                                           ^                   |
IREF ---> M8 diode PMOS ---> VBP -------------+                v
                              M6 common-source stage ----> VOUT
                                      ^                      |
                                      |                      |
                              M7 PMOS current load            |
                                      |                      |
                                      +---- 3 pF + 2 kΩ <----+
```

The diagram is functional, not a placed layout. The same compact dimensions are
cross-checked in the selected parameters, retained summaries, and raw loop/
transient evidence.
The final editable source is
[`schematics/two_stage_ota.sch`](../schematics/two_stage_ota.sch), with a
[rendered review figure](../results/plots/final_two_stage_ota_schematic.png).

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

Day 3 uses M6 `W/L = 8.83907427/0.5 µm` and M7
`W/L = 72.2005/0.8 µm`. At the nominal operating point, M6 sinks
83.2666517 µA, M7 sources 92.2666438 µA, and the 100 kΩ-to-VSS load takes
approximately 9 µA at `VOUT = 0.899999206 V`.

### CC and RZ — frequency compensation

- `CC` connects between `VOUT` and `VX` to create Miller pole splitting;
- increasing `CC` generally improves stability but reduces UGB and can affect
  slew rate;
- the selected Day 3 network is `CC = 3 pF` in series with `RZ = 2 kΩ`.

The 3 pF capacitor alone gave only 33.2236432° phase margin. The selected
resistor moves the nominal result to 69.0829108°, a 35.8592675° improvement,
with UGB changing from 17.2553341 to 16.745448 MHz. The 3 pF/1 kΩ candidate is
retained as a hard-limit failure at 52.2886533° phase margin.

### Bias network

- an external `IREF` avoids expanding the five-day scope into reference design;
- MOS mirrors generate tail and second-stage currents;
- ideal current sources may be used only for early block isolation, not for the
  final reported design under test.

Day 3 uses one 10 µA external reference. Diode-connected PMOS M8 establishes
`VBP`; matched PMOS M9 feeds diode-connected NMOS M10 at `VBN`, which biases
M5. M8/M9 use `W/L = 7.22005/0.8 µm`; M10 uses
`W/L = 8.08605/0.8 µm`. M7 shares `VBP`. At nominal, M8 carries
9.99999882 µA, while M9/M10 carry 9.99144222/9.9914427 µA.

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

## 4. Day 3 nominal complete-OTA checkpoint

The complete nominal signal path is present with the frozen 5 pF || 100 kΩ load
to VSS. The selected circuit produces 67.6747747 dB open-loop gain,
16.7454480155 MHz UGB, 69.0829107715° phase margin, and 270.536967 µW
quiescent power. A direct unity follower gives 8.20202918/11.51994781 V/µs
positive/negative slew and 0.07475 µs worst 1% settling for the 0.8↔1.2 V
test. SR follows the frozen monotonic 20–80% least-squares method using 62/47
rising/falling samples. Settling is referenced to the input 50% crossings at
1.01 µs rising and 3.03 µs falling.

Loop gain is measured with a DC-closed/AC-open break at the feedback input. A
1 GH inductor preserves `VOUT`-to-`VINN` DC feedback; a 1 GF coupling capacitor
injects the 1 V AC test source while isolating it at DC. The return ratio is
`T = -V(VOUT)/V(VINN)`. Its -0.00682757215° low-frequency phase is near zero,
which validates the recorded sign convention.

All M1–M10 model saturation checks pass at this nominal point; M5 is the
limiting device with 0.1161336635 V margin. Day 4 independently correlates the
nominal metrics and extends the same architecture across the frozen PVT and
nominal-characterization benches.

## 5. Day 4 architecture-level closure

The shared Day 4 OTA subcircuit exposes `VDD` and `VSS` explicitly. All NMOS
sources/bulks, the ideal `IREF` return, and `RL`/`CL` returns use `VSS`; PMOS
bulks use `VDD`. This prevents a supply-rejection bench from accidentally
shorting an implicit ground to the perturbed negative supply.

At every PVT point, the architecture passes the six core hard limits. The
worst values are 65.5351 dB A0 and 14.5527 MHz UGB at P08, 66.2452° PM and
302.710 µW at P13, 7.97766 V/µs SR+ at P06, and 11.1958 V/µs SR- at P08.
The return-ratio bench retains the validated 1 GH/1 GF DC-closed/AC-open loop
break and finds one non-boundary downward 0 dB crossing at every point.

The nominal characterization exposes the architecture’s actual tradeoffs:

- CMRR is 71.3222 dB at 1 kHz and passes.
- PSRR+ and PSRR- are 36.3313 and 36.2510 dB, respectively, so both fail the
  45 dB hard limit. The ideal external bias and finite current-source output
  resistances are part of this schematic-level behavior.
- The complete-OTA ICMR is 0.76–1.22 V. The low endpoint passes, but the upper
  end does not include the required 1.3 V.
- Bidirectional offset-inverting sweeps establish 0.18–1.63 V output swing,
  which covers the required 0.3–1.5 V interval.
- CL=1/2/5 pF gives 94.1626°/86.2882°/69.0829° PM, with no sustained or growing
  oscillation in the associated follower transients.
- Input-referred noise is 401.170 nV/√Hz at 1 kHz and 52.3016 µV RMS integrated
  from 10 Hz to 1 MHz; no noise pass limit is defined.

P06, P07, and P13 additionally record `SETTLING_NOT_REACHED` under the frozen
absolute ±4 mV band. Settling is a nominal-only metric; this information is
retained without adding it to the six-metric PVT gate.

## 6. Day 5 architectural decision

The formal optimization is the Day 3 addition of a 2 kΩ series resistor to the
3 pF Miller capacitor. It raises PM from 33.2236° to 69.0829° while changing
UGB from 17.2553 to 16.7454 MHz. The selected network received the complete
Day 4 characterization campaign and passed the six-metric core-PVT gate.

Longer-channel `first_stage_l2`/`first_stage_l3` and `m7_l2` variants were
screened only at nominal in a 32-run, 48-TSV audited campaign. They remain
rejected reconnaissance. `first_stage_l2` improves PSRR+/- to
72.419/67.315 dB, but lowers PM to 61.524° and worsens the Day 4-equivalent
1 Hz ICMR gain delta at 1.3 V from -4.935 dB to -7.361 dB (-2.425 dB). It
increases the total channel-area proxy to 2.195× and lacks a full PVT rerun.
`first_stage_l3` and `m7_l2` fail the nominal 55° PM hard limit. The
architecture therefore remains unchanged for reporting.

## 7. Named nodes and interfaces

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

## 8. Design sequence

1. **Complete:** characterize individual NFET/PFET devices in the installed PDK.
2. **Complete:** validate current mirrors and compliance ranges.
3. **Complete:** build M1–M5 with the diode-connected MB/M5 tail-bias mirror.
4. **Complete with documented high-end ICMR failure:** verify first-stage bias,
   gain, symmetry, and common-mode range.
5. **Complete at nominal:** add M6/M7 and establish a valid quiescent output.
6. **Complete at nominal:** add `CC`, implement the DC-closed/AC-open loop
   break, and tune nominal stability.
7. **Complete at nominal:** select `RZ = 2 kΩ` from the retained compensation
   sweep.
8. **Complete:** nominal characterization and the 13-point core PVT matrix;
   retain PSRR± and high-end ICMR failures.
9. **Complete:** package the Day 5 report while keeping the core-PVT-qualified
   baseline; no nominal-only reconnaissance result is promoted.

## 9. Explicitly out of scope

- bandgap or precision on-chip reference design;
- output buffer or rail-to-rail input stage;
- local-mismatch Monte Carlo or yield analysis;
- full-chip layout, parasitic extraction, and post-layout simulation;
- tapeout, fabrication, packaging, and laboratory measurement.

Partial matched-block layout plus DRC/LVS is optional after schematic-level
completion and does not change the claims above.
