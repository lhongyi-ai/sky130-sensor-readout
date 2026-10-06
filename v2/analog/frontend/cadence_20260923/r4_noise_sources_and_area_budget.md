# r4 noise sources and conditional area budget

Actual G16 HP−HN noise integrated over 1 Hz–50 kHz was 249.248 µV rms; using 6.103515625 Hz as the lower bound gave 239.895 µV. Approximately 89.86% of band-limited variance came from MOS flicker components, with the input pair contributing 80.65% of total variance.

The total `out` field is ASD in V/√Hz; nested device contributions are PSD in V²/Hz. Total ASD is squared before integration. Device subcomponents sum to their total, and device totals sum to out² without double counting. Six actual files closed to approximately 10⁻¹⁵ relative error. Five independent parser fixtures passed.

| Gain | HP−HN 1 Hz–50 kHz, µV rms | HP−HN 1 Hz–100 MHz, µV rms |
| --- | ---: | ---: |
| 1 | 28.869 | 46.998 |
| 4 | 72.888 | 121.838 |
| 16 | 249.248 | 388.374 |

For the specified −1 dBFS sine, approximately 252.084 mV rms signal and a 65 dB target imply about 141.757 µV total noise-plus-distortion budget. This continuous-time, fixed-switch, lumped-load calculation is not actual switched ADC noise, folding or SNDR. Calibration cannot remove time-varying flicker noise.

Area scaling is a conditional design experiment: increased device area also changes model, OP, capacitance and transfer functions. Detailed bands, contributors and predictions: `r4_noise_and_temperature_independent_review.json`; analysis: `review_r4_noise.py`.
