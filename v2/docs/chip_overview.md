# What chip is this project actually building?

This is a SKY130 chip core combining a programmable analog frontend and an analog-to-digital converter for low-frequency differential sensors. It converts the small voltage difference produced by a sensor into numbers a computer can process. The operational amplifier is one module within it, no longer the entire project.

The signal path is: **External sensor differential voltage → programmable gain of 1/4/16 → sampling and 12-bit SAR ADC → raw digital code → external software calibration.**

## 1. Why is it needed?

For example, a suitable external pressure or strain sensor has already converted a physical change into a small voltage difference between two wires. A computer cannot directly interpret that voltage accurately: the signal may be too small, and circuit errors and noise are present. This chip core handles amplification, sampling, and digitization.

The chip does not contain sensing elements such as a pressure diaphragm or strain gauge, and does not provide bridge excitation. Converting the digital voltage into newtons, pascals, or other physical units also requires the external sensor's own transfer relationship and calibration.

## 2. What does each part do?

| Module | Plain-language explanation | What actually needs to be designed |
|---|---|---|
| Differential programmable frontend | Selects gain according to sensor signal size | Transistor amplifier, resistive feedback, gain switches, common-mode feedback, biasing, and startup |
| Sampling circuit | Temporarily remembers the voltage at a specified instant | MOS switches, charge-storage capacitors, nonoverlapping timing, and sampling drive |
| Capacitor DAC | Produces candidate voltages for ADC comparisons | Binary-weighted MIM capacitors, reference switching, parasitics, and matching layout |
| Comparator | Answers whether the input is above or below the current candidate value | Amplification/regeneration, output holding, offset, noise, and kickback control |
| SAR digital controller | Asks 12 successive comparison questions to determine the bits | Synthesizable Verilog, handshake/reset/gain latching, and standard-cell physical implementation |
| External calibration software | Corrects fixed zero and scale errors | Fixed linear coefficients for each gain, independent validation, and retention of raw data |

Common-mode feedback controls the average voltage of the two output wires to prevent both from drifting toward a supply rail. Biasing sets suitable transistor operating currents. The startup circuit prevents the bias circuit from remaining in a nonoperating state after power-up. Along with signal amplification, these determine whether the chip works.

## 3. A concrete example

Suppose both sensor terminals are around 0.9 V, but the positive terminal is 1 mV above the negative terminal. With gain 16 selected, the target differential ADC input is 16 mV.

The ADC target range is −0.4 to +0.4 V, divided into 4096 codes, each approximately 195.3125 µV wide. Zero differential input is therefore near midpoint code 2048, and 16 mV corresponds to approximately code 2130. External software then uses the stored coefficients for that gain to correct zero and scale errors.

This is an ideal example explaining the target transfer relationship, not a promise of actual chip error, noise, or resolving ability. A 12-bit output does not imply 12-bit effective accuracy; the project's nominal actual-accuracy target is approximately 10.5 ENOB.

Sensor full scale is ±25 mV at gain 16, ±100 mV at gain 4, and ±400 mV at gain 1. An oversized signal still overloads the circuit, and software calibration cannot recover lost information.

Gain 1 still performs useful work. It accommodates sensor signals that are already relatively large, avoiding saturation of the frontend, sampler, or ADC at gains 4 or 16, while still providing differential drive, common-mode control, isolation, and low-impedance drive of the real sampling capacitors. Together, the three settings allow the same chip to handle both very small and larger signals; gain 1 need not provide additional voltage amplification.

## 4. Intended performance — still targets

- Input signal bandwidth DC–5 kHz, with 100,000 output results per second.
- External 1.6 MHz clock; 16 cycles per conversion, with 4 for acquisition and 12 for bit decisions.
- Nominal 1.8 V supply, with verification at 1.62/1.80/1.98 V, −20/27/85 °C, and five process corners.
- ADC differential full scale of 0.8 Vpp and 12-bit offset-binary raw codes.
- Full-chain SNDR of at least 65 dB nominally and at least 62 dB over specified process/voltage/temperature combinations; core power no more than 2 mW nominally and 3 mW across the combinations.
- Default sensor source impedance of 350 Ω per terminal; also check 0 Ω, 1 kΩ, and ±50 mV input common-mode deviation.

The complete definitions remain those in the [Frozen specification](../config/spec.json) and original plan. A few passing points for any module cannot replace these overall acceptance conditions.

## 5. What is inside the chip, and what is outside?

Inside the chip core: frontend, bias and startup circuits, sampling switches, capacitor DAC, comparator, phase circuit, and SAR control logic.

Outside the chip: sensor, power supply, reference and common-mode voltages, clock source, a device receiving parallel data, and a computer or microcontroller running calibration. Nominal references are 0.7/1.1 V, with a 0.9 V common-mode reference. Simulations must specify these sources' impedances and external decoupling rather than assuming unlimited reference drive.

The first version has no SPI, processor, automatic gain control, on-chip self-calibration, complete antialiasing filter, tapeout, pads/ESD, package, or test board. External inputs must satisfy the bandwidth and level conditions.

## 6. How should the current work be described?

It is currently a design and module-level verification project for a SKY130 sensor-readout chip core. It already includes real device circuits, a digital controller layout, and short full-chain conversions, going beyond an ideal model. However, the complete chip has not passed all accuracy, voltage/temperature, mismatch, and top-level parasitic acceptance tests.

Native schematics, complete core layout, DRC/LVS, parasitic extraction, and matched-condition post-layout simulation must ultimately be completed in Cadence. Before fabrication and actual measurements, it cannot be described as a taped-out or silicon-measured chip. See [Implementation status](status.md) for the latest completion status and failures.
