# ADC numerical diagnosis and retained controls

All original numerical failures, input hashes and actual exit states are preserved. No PDK model patch, artificial leakage, cmin, prerecorded decision, time alignment or removed switching edge is used to obtain qualification. Prepared inputs and completed simulation runs are distinct states.

## Comparator and solver controls

Adding diagnostic output left the original strict waveform VALUE bytes unchanged, while revealing 144 convergence-recovery LTE ignores, nine discontinuity relaxations and 64 internal resistor bsource warnings. Setting ltethstep=0 replaced the nine printed relaxation events with additional LTE-ignore counts; it did not remove recovery dependence. Robust discontinuity handling used lteminstep=1e−14 and printed 1000 warnings with another 4084 suppressed, so it was rejected.

A sigglobal comparator control reduced printed LTE relaxations to one and passed reset/hold/five real decision checks. The preamplifier full-domain difference from the old strict configuration was about 8.85 µV, while fast logic edges still differed by millivolts. This independent comparator test cannot qualify the complete ADC. Count limits and suppressed messages are retained.

## Complete actual ADC

The 741-device circuit and original RTL produced two frames, codes 5/4090, 24 actual comparator decisions and the additional reset-abort checks. The complete source-defined domain is [0,30.9475 µs]. Strict timed out at 27.8243761974 µs and retained 20 LTE relaxations. Complete-common-prefix TP−TN difference reached 14.374193 mV with 399 over-threshold intervals. Approximate 1.492 ps CONV timing sensitivity explains the instantaneous scale, not an equivalent conversion error or PASS.

The domain comes from frozen source timing, not the simulator's last saved point. Raw tail records remain auditable. Comparison uses the union of actual accepted times, including every edge, with no extrapolation. Identical source/configuration contracts and actually tightened tolerances are required. TP−TN, RP, RN and VCM must each remain within 9.765625 µV over the complete required domain, with normal finish and reset/protocol checks. Decision-instant agreement is supplementary evidence.

## Mode-boundary evidence

The first phase PFET probe saved int_b/dbnode/sbnode, actual reversed state and four terminal currents. During one 201.302 fs step, external VDS reversed and int_b changed by −449.092 µV. Added saves preserved all 4951 original times and 76 common voltages exactly. Terminal KCL consistency and temporal association do not prove model physical accuracy or a bug.

Eight independent single-device transient controls completed with zero errors/warnings, but did not reproduce the original complete-ADC warning. Eight DC sweeps contained 14,408 actual points; one-sided charge slopes repeated under precision, direction and grid controls. Total/intrinsic-named Q aliases were identical despite nonzero saved overlap fields, so their semantics remain unresolved. Sentinel model-option exports are not resolved options.

Seven actual external-port AC controls, 287 points, also showed left/right response changes. These are only the D-driven column of a three-terminal admittance matrix with S/B tied, not a full capacitance matrix or independent silicon reference. Spectre 25 retained the first-phase warning and skipped the requested internal save, so version switching did not establish a repair.

## Failed short-window alternatives

- cthresh-only original ADC: 854.441 µV.
- traponly / adaptive trap: 344.021 / 344.418 µV, with ringing and LTE warnings retained.
- Original VAMS reference with tighter LTE: timed out at 4.06328 µs.
- Reduced 654-device phase/load circuit: strict skipped the input edge; it omitted 87 preamp/comparator devices and did not reproduce the same warning.
- Half-sine reduced stimulus: edge gap disappeared, four body-node LTE relaxations remained, and difference was 1.128 mV. It changes the stimulus and is not an equivalent repair.
- Equivalent native reference R/C: Newton rejections fell 218→11 and LTE ignores 5→0, but difference remained 854.569 µV. This equivalence is deterministic transient only; native resistor noise needs separate treatment.
- Native R/C with tighter LTE: complete short-domain difference 182.974 µV, with 23 LTE ignores and four relaxations. Finer attempts did not complete the domain.

These experiments help separate mechanisms but none passes the original gate. See the top-level [RESULTS](../RESULTS.md), individual review directories and their JSON for exact channels, domains, source hashes and logs. Analysis fixtures check missing data, narrow peaks, shifts, incomplete domains and PSF field semantics; local test passes are not EDA qualification.

Next work should establish a reproducible full-load diagnostic and supported model/solver explanation, then verify a justified repair on the complete two-frame/reset comparison. Twelve-frame and long campaigns remain gated. Formal MIM/ADC PEX remains independently incomplete.
