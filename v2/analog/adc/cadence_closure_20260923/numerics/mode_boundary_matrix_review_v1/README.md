# Eight single-device controls

Matched-slope, static-gate, ten-times-slower and finite-1 Ω source controls were each run at baseline/strict precision. All eight runs completed with zero errors and warnings; original model hashes matched before and after.

Internal-body and terminal-current sensitivity remained. The forced source matched its analytic waveform to less than 0.9 fV at actual accepted points. In the matched pair, D/G interpolation differences were approximately 0.099/0.202 µV while int_b differed by 23.528 µV. A finite source changes actual device terminal voltages and is not a measured replacement for the real ADC driver impedance.

The original complete-ADC SPECTRE-16780 warning was not reproduced. Ideal forcing removes the closed driver/load dynamics, so these runs isolate sensitivity rather than reproduce or repair the original failure. Fast-edge interpolation peaks alone do not prove model discontinuity. All worst points and their original neighbors remain in `summary.json`.

Next diagnosis must restore the real phase generator and actual load, followed by the original complete ADC/RTL precision gate. Slower controls cannot be adopted by reducing the required ADC rate.
