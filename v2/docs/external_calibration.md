# External Calibration Data Input

Calibration runs in computer software, not on the chip. Inputs may be raw conversion codes from the behavioral model, ngspice, or later Spectre simulations; the import tool does not automatically endorse their level of physical evidence.

CSV files must contain these columns: `instance_id,sample_id,gain,vdd_v,temperature_c,raw_code,sensor_input_v`.
`sample_id` must be unique within the file; `raw_code` is a raw integer from 0 to 4095; `gain` is 1, 4, or 16.
`sensor_input_v` is the difference between the two sensor-terminal voltages. It must be known for calibration/validation and may be blank in normal application.
Only valid outputs after acquisition/conversion has settled may be exported; reset-period or invalid codes must not be included.

From the repository root:

```sh
python3 v2/scripts/calibrate.py fit nominal_training.csv frozen_coefficients.json
python3 v2/scripts/calibrate.py apply raw_samples.csv corrected_samples.csv --coefficients frozen_coefficients.json
python3 v2/scripts/calibrate.py validate independent_holdout.csv holdout_report.json --coefficients frozen_coefficients.json
```

- For each instance and gain, fit only at 1.8 V / 27 °C, using at least 4096 samples at each of −80%, 0, and +80% full scale.
- Reject training if any individual sample reaches an endpoint code; averaging must not hide saturation.
- Validation points must be independent of training points, with at least 2048 samples each. The nominal mean-residual target is ≤1 LSB, and ≤4 LSB at other voltage/temperature conditions.
- The same instance/gain must use the original coefficients across voltage/temperature conditions, without refitting. The tool rejects substitution of coefficients from another instance or gain.
- Outputs retain raw codes, unrounded/unclipped calibrated codes, and converted input voltage. Software does not hide overrange or drift.
- Existing output files are not overwritten; choose a new filename for the next experiment.

Passing every tested point proves only the results for that set of inputs. The full 45 combinations, three gains, noise, dynamic accuracy, mismatch, and post-layout simulation require separate evidence and cannot be replaced by a calibration report.
