# Independent AC port cross-check

This independent read-only analysis checks the actual seven-bias external-port AC data against source-current signs, terminal-current saves, actual drive amplitudes and DC operating conditions. It does not launch EDA or alter the original data.

With D-driven unit AC and G/tied-SB at AC zero, the observations form one admittance-matrix column. Signed cross coefficients are retained, not converted to positive independent capacitors. KCL and device/source current agreement are limited by the printed data precision and do not certify physical model accuracy.

The near-zero branch changes agree with the primary AC review. They support a local mode-boundary response investigation but do not resolve transient LTE, establish a finite charge jump or qualify the full ADC. Exact normalization, worst residuals, raw-field coverage and source hashes remain in the adjacent independent review JSON.
