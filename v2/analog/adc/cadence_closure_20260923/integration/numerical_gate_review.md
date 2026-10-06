# Independent full-ADC numerical gate review

The source-frozen two-frame measurement domain is [0,30.9475 µs]. Baseline finished normally and saved through 30.9476920795 µs; strict timed out at 27.8243761974 µs. Complete qualification cannot be assigned to their common prefix. Tail records remain separately auditable.

Both runs use the same 741 devices, original RTL and stimuli, gear2only/sigglobal/conservative/lteratio=10. Actual tolerances are baseline reltol=1e−6, Vabs=1e−8 V, Iabs=1e−13 A, maxstep=2 ns; strict 1e−7, 1e−9 V, 1e−14 A and 1 ns. Baseline/strict retain 2/20 LTE-relaxation warnings.

The worst TP−TN difference is 14.3741931607 mV at 16.5862427375 µs, with 399 contiguous over-threshold accepted-point intervals. CONV's half-rail transition differs by approximately 1.49210 ps, while the local differential slope is approximately 9.6293 mV/ps. This explains the scale of a fixed-time edge difference; it does not turn the failed 9.765625 µV gate into PASS or establish an equivalent ADC conversion error.

Residual errors persist beyond the instantaneous peak. Pre-EVAL and pre-capture differences are very small and explain equal codes, but remain supplementary observations. Do not align time, remove edges, waive LTE recovery or replace complete finish/reset checks with two codes.

Evidence: the frozen domain contract, full-domain comparison and event-attribution JSON in `../numerics/`. No circuit, model, threshold or historical result was changed by this review.
