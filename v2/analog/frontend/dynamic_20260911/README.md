# Non-Cadence frontend dynamic closure (2026-09-11)

## Conclusion

This round advanced the frontend from oscillation under real sampling and excessive gain-16 settling error to a substantially improved
transistor-level candidate that uses the external `VCM` reference. With one source version at
TT / 1.8 V / 27 °C, `candidate_06.spice` passed all of the following at gains 1, 4, and 16 simultaneously:

- An 81-point static scan and independent-point errors after three-point external linear calibration;
- Acquisition settling with 4096 real SKY130 MIM cells per side and four-MOS sampling switches;
- Quiet-reference-window ringing, output common mode, device operating regions, and frontend power;
- Full-input-range endpoint checks with external `VCM` at 0.85 V and 0.95 V.

However, it **is not yet a qualified frontend**. The final formal loop audit found that phase margin at the first
0 dB crossing is insufficient to prove the multiloop result. The stage gate therefore prevented starting the 45 PVT combinations.
The authoritative final status is `qualification.json`, not the optimistic status text emitted by the original script for diagnostic 8.

## Plain-language explanation of the changes

The frontend acts like an adjustable-gain amplifier ahead of the ADC. It must amplify the sensor's small differential voltage
while holding the average of the two output voltages near `VCM`. The previous version had two strong automatic
average-control loops, like two people turning the same steering wheel aggressively; oscillation at approximately 2.9 MHz kept growing.

The final candidate from this round makes three changes:

1. The first stage directly controls matched loads from the average output, without adding a high-gain intermediate loop.
2. The output stage adds a low-gain `CMS−VCM` error stage with real resistor degeneration, so `VCM` actually
   enters the circuit rather than appearing only in the port name.
3. Miller capacitance changes from 16 pF to 8 pF per side, and the tested assembly's isolation resistance changes from 1.8 kΩ to
   1.5 kΩ, allowing gain 16 to settle within the 2.476847754 µs acquisition window.

The original 1.2 kΩ zero-setting resistor, implemented with a 0.35 µm-wide resistor, had an illegal calculated length of approximately 0.241 µm.
This round uses a 0.69 µm-wide high-resistance polysilicon device with an approximately 0.855 µm length. The 1.5 kΩ isolation resistor is approximately
0.543 µm long. Both exceed the 0.5 µm PCell minimum length. This is parameter-legality checking only,
not evidence that a frontend layout has been drawn or that DRC/LVS passed.

## Nominal results from the same candidate

The following thresholds were not relaxed: 48.828125 µV for acquisition error and error 30 ns after sampling, 4.8828125 µV peak-to-peak in the quiet
reference window, and a 1.85 mW frontend power budget.

| Gain | Maximum static independent-point residual | Maximum acquisition error | Maximum error 30 ns after sampling | Maximum reference-window peak-to-peak | Average power |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.029642 LSB | 1.892 µV | 1.637 µV | 1.321 nV | 0.702 mW |
| 4 | 0.019548 LSB | 1.743 µV | 1.441 µV | 1.180 nV | 0.698 mW |
| 16 | 0.041138 LSB | 10.262 µV | 11.182 µV | 1.132 nV | 0.698 mW |

The maximum nominal transient output-common-mode errors are approximately 13.94, 14.58, and 14.69 mV. With external `VCM` set to
0.85 V and 0.95 V, the maximum output-common-mode tracking errors over the full input range are 36.56 mV and
5.21 mV respectively, both within the current 50 mV endpoint limit. These are not PVT results.

## Why phase margin still cannot be signed off

Diagnostic 8 used test-only zero-DC voltage sources to inject each gain's outer differential loop, first-stage
common-mode loop, and output common-mode loop. The real sampling switches remained on, with 4096 MIM cells per side.
At the first downward 0 dB crossing:

- Apparent differential phase margins at the three gains were 86.38°, 84.86°, and 83.30°;
- Apparent output-common-mode phase margins were 123.53°, 123.19°, and 123.00°.

These values exceed 60°, but the original script missed two disqualifying findings:

- The differential curves cross 0 dB **upward** again at approximately 74.8, 47.1, and 38.9 MHz. The first downward
  crossing alone cannot represent the complete Nyquist behavior.
- The first-stage common-mode scalar return ratio has approximately −180° low-frequency phase at gains 1 and 4, but approximately
  0° at gain 16. With mutually coupled loops, this sign inconsistency invalidates continued use of a single-loop phase-margin formula.

Therefore, the original `LOOP_STABILITY_PASS` in `diagnostics/08.../summary.json` is
explicitly superseded by `qualification.json`. Continuing requires a multiloop return-difference/generalized Nyquist
audit, or a redesign with one well-defined output-common-mode loop, followed by renewed dynamic and stability gates.

## Evidence retained from eight diagnostics

- 01: legal resistors plus large common-mode compensation capacitors failed numerically at the first reset edge.
- 02: fixing artificial numerical breakpoints revealed that the large-capacitor approach oscillates to the supply rails.
- 03: unconditional resistive restoration removed ringing, but the bias pushed the first stage toward the upper rail.
- 04: correcting the bias moved the circuit to another saturated operating point.
- 05: direct common-mode sensing passed static checks at all three gains and dynamics at gains 1/4, while gain 16 failed at approximately 90 µV.
- 06: 8 pF Miller capacitance plus legal 1.5 kΩ isolation passed dynamics at all three gains, but `VCM` was not yet in the loop.
- 07: adding the low-gain `CMS−VCM` error stage passed three-gain dynamics and ±50 mV VCM endpoint checks.
- 08: loop injection produced complete raw curves; auditing found the original automatic pass to be a false positive.

The runner-path problem occurred before ngspice started and is stored in `setup_failures/`; it was not presented as
a real circuit experiment. All actual diagnostics used one worker, and each directory retains candidate snapshots,
testbenches, raw data, logs, configuration, summaries, and a SHA-256 manifest.

## Viewing the current evidence

- Candidate circuit: `candidate_06.spice`
- Final conservative status: `qualification.json`
- Best complete dynamic evidence: `diagnostics/07_20260911T085157880653Z_candidate_06/`
- Formal raw loop evidence: `diagnostics/08_20260911T085257873008Z_candidate_06_loops/`
- Rebuildable status: `python3 build_qualification.py`
- Evidence regressions: `python3 -m unittest -v test_evidence.py`

All results are pre-layout results from open-source SKY130/ngspice. They are not native Cadence schematics or
frontend DRC/LVS/PEX, do not include qualified transistor transient noise, and do not establish full-ADC SNDR.
