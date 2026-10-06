# Actual external-port AC mode-boundary control

Seven actual school runs at D−SB=−20/−5/−1/0/+1/+5/+20 µV each completed with zero errors/warnings and one notice. Each has 41 frequency points from 1 kHz to 10 MHz, 287 total. The same fixed PFET, geometry, bias, strict DC profile and model hashes were retained; all 13 actual trace fields exist and are finite.

Only D is driven by normalized AC=1+j0 V; G and tied S/B are AC zero. Device current is the negative source current, and `Y_kD=I_device_k/V_D`. Signed `Im(Y)/(2πf)` is an effective response coefficient, not necessarily a separate physical capacitor. This is only the D column of a three-port admittance matrix, not a full matrix; S+B cannot be separated by this fixture.

The near-zero left/right changes at 1 kHz are approximately −11.16981 fF on D, +4.86825 fF on G and +6.30158 fF on tied S/B. The external AC response therefore confirms a branch difference beyond raw-Q naming alone. Port/current consistency remains a numerical check, not physical/silicon validation.

Actual DC bias differs from request by at most 1.40e−16 V, and the actual reversed states agree with the DC controls. Saved currents have limited printed precision; long displayed decimals do not imply equal physical accuracy. Full tables, signs, frequency dependence and provenance remain in the adjacent JSON records. No supported model defect/repair or complete ADC convergence is established.
