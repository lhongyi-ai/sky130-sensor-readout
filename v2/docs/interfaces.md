# Interfaces and Data Definitions

## Analog boundary

The final core is planned to use VINP/VINN, VDD/VSS, VREFP/VREFN, and VCM.
The behavioral-model input is VINP−VINN in V; output full scale is −0.4 to +0.4 V.
References and common mode are externally supplied voltages; no on-chip bandgap reference is included.
At nonnominal VDD, the plan is VCM=VDD/2, VREFP=VCM+0.2 V, and VREFN=VCM−0.2 V to preserve 0.8 V differential full scale; device-voltage limits and switch functionality still need verification.

12-bit LSB = 0.8/4096 = 195.3125 µV. Input-referred LSB is additionally divided by frontend gain.
Each conversion threshold is −0.4+k×LSB; a value exactly at a threshold takes the upper code.
The voltage at a code center is (code+0.5)×LSB−0.4. Calibration uses code-center coordinates to avoid hiding a half-LSB offset.
The model ADC saturates to endpoint codes outside the range, but frontend supply clipping/overload recovery is not modeled.

## Digital interface

| Signal | Meaning |
|---|---|
| clk | External 1.6 MHz; current ideal-clock tests use 50% duty cycle |
| rst_n | Asynchronous active-low reset; cancels unfinished conversion and clears output-valid state |
| start | Accepted when ready=1; holding it high requests continuous conversion |
| gain_sel | 00→1, 01→4, 10→16; 11 rejects the request |
| ready / busy | Complements; busy indicates request backpressure, not internal analog activity |
| gain_latched | Gain currently being processed or just accepted |
| sample_en | High for 4 full acquisition cycles |
| trial_code | 12-bit trial code for subsequent CDAC switch decoding; not actual analog-switch waveforms |
| comparator_evaluate | Requests comparator evaluation in the latter half of a decision cycle; physical implementation remains to be verified |
| comparator_bit | Comparison result: 1 retains the current trial bit; 0 clears it; sampled at the documented rising edge |
| data_valid | High for one cycle when the conversion completes |
| data / data_gain | Raw code and gain of the same completed frame, held until the next completion/reset |

In the final decision cycle, ready=1, so a new frame can be accepted at the edge completing the old frame.
At that point data_gain belongs to the old frame and gain_latched already belongs to the new frame; external calibration must use data_gain.
An invalid gain_sel neither cancels the old frame being completed nor starts a new one.

## External calibration

The three inputs for each gain are −80%, 0, and +80% of its permitted amplitude; retain the mean and standard deviation of 4096 settled samples at each point.
The coefficient file records instance, gain, nominal voltage/temperature, training points, slope, intercept, and error.
Validation uses an independent grid from −90% to +90%, excluding all training points, with 2048 samples averaged per point.
Floating-point calibration results are neither clipped nor rounded again; raw 12-bit data are always retained.

To demonstrate the limitations of fixed calibration, the experiment additionally injects +100 µV of input-offset drift while retaining the original coefficients.
This is a synthetic sensitivity test, not real SKY130 drift at a particular temperature.

## Result statuses

- LOCAL_MODEL_AND_DIGITAL_TESTS_PASS: local model and RTL tests pass.
- PARTIAL_PDK_FEASIBILITY_NOT_VERIFIED: M2 has not fully passed.
- NOT_RUN_REQUIRES_TRANSISTOR_MODEL: the test matrix is defined but has no real-circuit results.
- SYNTHETIC / BEHAVIORAL: valid only for budget and analysis-method verification.

These statuses must not be automatically promoted to POST_LAYOUT, PVT_PASS, MISMATCH_PASS, or SILICON_MEASURED.
