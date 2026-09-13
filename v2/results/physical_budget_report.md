# Budget Checks Informed by Real Device Data

These are analytical constraints and risk screening, not chip simulation performance.

## Feedback Network and Noise Folding

With actual resistive feedback, signal gain G differs from noise gain 1+G. Source impedance of 350 Ω per terminal both changes gain and contributes thermal noise.
The comparison below uses an ideal single pole satisfying full-scale settling in 2.5 µs and includes only input/feedback resistor noise, excluding transistor noise.
Instantaneous sampling folds noise above 50 kHz back into band; a full-Nyquist FFT must include that noise.

| Total input resistance/terminal | Gain | Feedback resistance/terminal | Resistor output noise RMS | Resistor-only SNR upper bound |
|---|---:|---:|---:|---:|
| 350 Ω | 1 | 350 Ω | 4.75 µV | 94.51 dB |
| 350 Ω | 4 | 1400 Ω | 15.01 µV | 84.51 dB |
| 350 Ω | 16 | 5600 Ω | 55.34 µV | 73.17 dB |
| 1000 Ω | 1 | 1000 Ω | 8.02 µV | 89.95 dB |
| 1000 Ω | 4 | 4000 Ω | 25.37 µV | 79.95 dB |
| 1000 Ω | 16 | 16000 Ω | 93.54 µV | 68.61 dB |
| 10000 Ω | 1 | 10000 Ω | 25.37 µV | 79.95 dB |
| 10000 Ω | 4 | 40000 Ω | 80.21 µV | 69.95 dB |
| 10000 Ω | 16 | 160000 Ω | 295.81 µV | 58.61 dB |

This motivates lower feedback resistance and joint design of sampling isolation/filtering, without establishing compliance for any new value.
Changing integration bandwidth from 50 kHz to 5 kHz alone cannot establish passing SNDR.

## MIM Capacitors and Reference Terminals

Continuous model in the frozen PDK: a 3×3 µm MIM unit is 19.845 fF; 4096 units per side are 81.28512 pF.
Bare plate area of the two arrays is 73,728 µm², not core area. Minimum-unit DRC/LVS and capacitance extraction were performed separately; the complete array still needs actual routing.
Reference terminals are loaded. The JSON retains conservative upper bounds for switched charge, instantaneous current, decoupling, and settling time; actual values must come from transient tests with source impedance.

## Still Requires Real Circuits

These calculations cannot replace transistor thermal/flicker noise, time-varying sampling noise, reference loops, comparator kickback, stability, power, or complete-layout parasitics.
