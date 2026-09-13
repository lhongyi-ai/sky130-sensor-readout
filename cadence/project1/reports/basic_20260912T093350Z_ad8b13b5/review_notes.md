# Process-resistor DC review: actual results match the model; original comparison rule is inapplicable

Run `res_dc/20260912T092706Z_31ca6c32` completed native-netlist export, connectivity and parameter checks, Spectre simulation, and waveform export. Recalculation shows that the complete returned I–V curve matches the public SKY130 resistor-model formula. The second `FAIL` in the original `PASS FAIL` arose from inapplicable CDF-value/linearity thresholds set by this package; the original report and status files remain unchanged.

## Evidence and scope

- Process device: `res_high_po_0p35`; W=L=0.35 µm, third terminal and negative terminal both connected to VSS.
- Conditions: TT, temperature and tnom both 27°C; voltage 0–0.1 V in 1 mV steps.
- Spectre: 21.1.0.132.isr1; normal termination, 0 errors, 0 warnings, and 4 notices.
- Both voltage and current CSVs have 101 points with identical point-by-point sweep axes; voltage equals the specified stimulus and DC imaginary parts are zero.
- Returned manifest hashes match the delivered 1.0.4p1 manifest; formal input, native netlist, and OCEAN top-level input hashes were checked.

Review details: [review.json](review.json); pointwise recalculation: [resistor_recalculated.csv](resistor_recalculated.csv). The recalculation program [review_resistor.py](review_resistor.py) only reads received results and writes separate review files without modifying original statuses.

## Source of the difference

The [official public model](https://raw.githubusercontent.com/google/skywater-pdk-libs-sky130_fd_pr/main/cells/res_high_po/sky130_fd_pr__res_high_po_0p35.model.spice) represents this device as a subcircuit with contact resistance, body resistance, and parasitic capacitances; its resistance formula includes voltage-correction terms. Documentation also describes the [precision-poly resistor subcircuit and contact/body structure](https://foss-eda-tools.googlesource.com/skywater-pdk/+/5a57f505cd4cd65d10e9f37dd2d259a526bc9bf7/docs/rules/device-details/res_high/index.rst). Sources were retrieved on 2026-09-12.

In the public model, contact plus body resistance without voltage correction is:

`589.99 + 0.35 × 1112.41 = 979.3335 Ω`

This agrees with the CDF-displayed 979.33 Ω. However, this low-voltage sweep requires the contact/body voltage corrections, resulting in an effective terminal resistance of approximately 1.22–1.24 kΩ. No model coefficients were fitted to the returned curve.

| Voltage | Magnitude of Spectre-exported current | Exported V/I | Public-model formula recalculation |
|---|---:|---:|---:|
| 0.010 V | 8.075425 µA | 1238.324865 Ω | 1238.324865 Ω |
| 0.050 V | 40.584573 µA | 1231.995233 Ω | 1231.995233 Ω |
| 0.100 V | 81.715817 µA | 1223.753294 Ω | 1223.753294 Ω |

The maximum relative current difference across all 100 nonzero voltage points is `4.44×10⁻¹⁶`, at floating-point rounding scale; current at zero voltage also agrees at zero. Independent recalculation reproduced the original script's mean resistance 1231.136636 Ω, 25.7121% excess over CDF, and 1.18359% resistance variation over the interval.

![Pointwise resistor simulation versus public model](resistor_review.png)

The correct environment validation for this test should therefore compare I–V against the model formula under identical conditions. The simplified CDF display value must not be treated as fixed terminal DC resistance, nor should this model be forced to satisfy a 1% linearity requirement conflicting with its own voltage characteristics. This is a design issue in the original test criteria.

This review's numerical-consistency check uses `|I−Iref| ≤ 1 pA + 0.01%×|Iref|`, corresponding to 10 times each current absolute and relative tolerance in the executed input; it does not relax the original CDF threshold to cover the observed difference. Model coefficients come from public source files and were not calibrated to measured values.

## Logs and incomplete items

Spectre notices include both terminals of an internal capacitor connected to VSS, a global ground with only one connection, and restoration of design variables after the sweep. The first two are consistent with this circuit's connectivity; there were no model-loading errors or convergence warnings. OCEAN logs also contain font, log-lock, and library-redefinition warnings, but netlist and data exports actually completed; these warnings remain in the original logs.

This conclusion is limited to agreement of the DC model response for this device and geometry at TT/27°C over 0–0.1 V. Full contents of school model-dependency files were not obtained; no claim is made of file-by-file hash identity with public versions. Original binary PSF is retained; this review uses OCEAN-exported CSV and did not independently decode PSF.

This does not establish MIM, RC, OTA, PVT, noise, layout, or full-system success. Original test files retain `performance_status=FAIL`; this directory records the model-review conclusion separately as `PASS_DC_MODEL_COMPARISON_AT_REPORTED_CONDITION`. The original runner's stage thresholds have not yet changed.

## Next step: collect MIM and RC results with the existing package

In school Linux's `basic_design_v1_0_4` folder, using a terminal with the Cadence environment configured, run in order:

```bash
bash p1_run.sh run --job mim_ac --retry
bash p1_run.sh run --job rc_step --retry
bash p1_run.sh collect
```

These two basic tests can run independently; they neither change the original resistor failure to a pass nor enter the OTA stage. Even if a test shows performance `FAIL`, preserve and return its results; if tool-launch or netlist errors occur, return the complete error information.

The current RC comparison value remains `979.33 Ω × 34.6223 fF`, omitting the resistor voltage dependence confirmed here and process-model capacitance parasitics, so its applicability also requires review. Once original MIM and RC results are available, update passive analysis and execution thresholds together to avoid piecemeal criterion changes and repeated small-patch uploads.
