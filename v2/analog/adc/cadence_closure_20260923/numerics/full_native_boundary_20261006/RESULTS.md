# Actual complete-load boundary diagnostic — October 6, 2026

Both new runs used the school Spectre environment and the complete unchanged native bodies: 693 ADC instances plus 48 phase instances. The preamp/comparator's 87 instances and the actual reset connection are retained. This is a first-edge pure Spectre control, with zero completed SAR frames; the original RTL is not simulated here.

| Control | Baseline | Strict |
| --- | --- | --- |
| Exit code / saved domain | 0 / complete 0–4.1 us | 0 / complete 0–4.1 us |
| Accepted saved points | 4,944 | 8,818 |
| Simulator completion | 0 errors, 0 warnings | 0 errors, 11 warnings |
| Reset-edge quarter point counts | 31 / 96 / 171 / 23 | 60 / 217 / 388 / 44 |
| Sample-edge quarter point counts | 34 / 44 / 157 / 658 | **0 / 0 / 0 / 0** |
| Diagnostic integrity | Pass | **Fail: unresolved sample edge** |

Baseline versus the original AMS baseline has a maximum TP−TN difference of **7.253533 uV**, RP approximately 1.000 nV, RN approximately 0.729 nV and VCM zero. Those four short-domain signals satisfy 9.765625 uV. This is limited baseline agreement, not a repair or complete-ADC qualification. CONV differs by approximately **93.522 uV**, so agreement must not be generalized to every internal node or to identical model/solver trajectories. The baseline does not reproduce the original same-node warning.

Strict versus baseline has a retained TP−TN maximum of **140.743946 mV**, RP **13.109005 uV**, RN **5.722163 uV**, VCM zero, and sample-command difference **677.438514 mV** under the unchanged all-union-time comparison. These values span a missing native-source edge and disaster recovery; they are not ADC output-code errors or trustworthy resolved transition physics.

At 4.0625 us, strict Newton fails after shrinking the step to approximately `199.9e-21 s`, then invokes disaster recovery. No accepted points occur inside any quarter of the 1 ns sample-command ramp. Checking an ideal source only at its accepted points would report zero source error and miss this gap; the explicit edge-coverage check rejects it.

Strict additionally reports `AHDLLINT-8014` for preamp resistor internal matrix elements and `AHDLLINT-8010` for resistor conductance changes, followed by `SPECTRE-16266` for ignored LTE requirements. This is a new diagnostic association, not proof of a resistor or MOS model defect. Diagnostics must distinguish a physical/model branch transition, a solver recovery artifact and boundary event handling.

The installed top-level model-entry fingerprint matches the entry fingerprint in retained earlier summaries. This does not prove identity of every included model file. The native deck itself is unchanged byte for byte. Actual solver metadata, file hashes, warnings, edge counts and every comparison result are in [review.json](review.json). Twelve local builder/analyzer checks passed.

## Next discriminating work

1. Review accepted-step recovery around the first sample-command breakpoint. An explicit integration-point control, if supported, must retain all accepted points and the original input shape. Resampling a failed waveform onto a new grid is not a fix.
2. Build a separate control around the reported phase/preamp PDK resistor branches, preserving their relevant terminal bias and actual model. Determine whether their conductance changes predate Newton failure or follow a recovered solution. Keep the PFET body-network controls in parallel; do not infer causation from warning order alone.
3. Any model/simulator workaround must have applicable documentation or an independently validated equivalence argument. Do not delete body resistance, replace a physical resistor with an ideal resistor, add fictitious leakage or change PDK source merely to remove warnings.
4. Validate a justified change first in a complete-edge short-domain control, then return to the original RTL and actual comparator for both full two-frame profiles and reset-abort. Preserve the original full-domain 9.765625 uV gate. Only after that qualification expand to twelve frames and long campaigns.

No repair is accepted in this report. `full_ADC_numeric_qualified=false`; `formal_ADC_PEX_allowed=false`. The separate MIM physical coupling, internal/external RC reference-plane and resistance-temperature provenance requirements remain open.
