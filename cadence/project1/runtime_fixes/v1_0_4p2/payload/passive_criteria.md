# M0 passive-device review criteria V1

Applies only to the current frozen basic package at TT, 27°C, tnom=27°C: the 0.35 µm × 0.35 µm process resistor, 4 µm × 4 µm MIM capacitor, and original 0→0.1 V RC test. Legacy OTA and new-frontend specifications remain unchanged.

## Reason for correction

The old resistor criterion treated the CDF-displayed 979.33 Ω as the actual constant resistance throughout the voltage sweep. The old RC criterion directly used 979.33 Ω × 34.6223 fF. The public model includes voltage dependence and terminal parasitic capacitances; neither old criterion reflected the actual model.

This version reanalyzes completed Spectre data and creates an independent review.json. Original status.json, metrics.json, netlists, waveforms, failures, and environment-block records are all preserved. RECHECK PASS reviews prior actual data; it does not imply another simulation run.

## Model sources and scope

- [Resistor model](https://raw.githubusercontent.com/google/skywater-pdk-libs-sky130_fd_pr/main/cells/res_high_po/sky130_fd_pr__res_high_po_0p35.model.spice): 589.99 Ω contact term, 1112.41 Ω/µm body-resistance term, and their voltage coefficients; both ends have parasitic capacitance to bulk.
- [TT resistor/capacitor parameters](https://raw.githubusercontent.com/google/skywater-pdk-libs-sky130_fd_pr/main/models/r%2Bc/res_typical__cap_typical.spice): area capacitance density 1.06e-4 F/m² and edge capacitance density 5.04e-11 F/m. This geometry gives 0.3286045 fF per end.
- [MIM model](https://raw.githubusercontent.com/google/skywater-pdk-libs-sky130_fd_pr/main/cells/cap_mim_m3/sky130_fd_pr__cap_mim_m3_1.model.spice): capacitance and two series resistances; model capacitance has no voltage coefficient and its temperature coefficient is zero.

Coefficients come directly from the model and were not fitted to the returned RC waveform. C uses the frozen CDF value of 34.6223 fF, independently validated by MIM AC testing. School dependency files corresponding to the public model have not been individually hash-verified, so this is migration qualification for this environment and geometry, not certification of the entire PDK.

## Three sets of criteria

1. Resistor: check the 101-point sweep axis, voltage, current sign, and finite values; compare every point's current with the voltage-dependent model equation using tolerance 1 pA + 1e-4 × reference current, retaining the numerical budget of the earlier independent review. Retain the CDF value for explanation, but no longer require agreement within 5% or force the physical model to behave as an ideal linear resistor.
2. MIM: 1081 frequency points from 1 Hz to 1 GHz, 120 points per decade; extract capacitance from 1 kHz to 1 MHz and retain the original threshold of positive capacitance within CDF ±5%; measurement-band flatness 1e-4; high-frequency extracted series resistance must be 0–1 Ω as an additional condition for the RC approximation.
3. RC: retain the original input pulse, 10 ns duration, and maximum 0.5 ps step; check the full input waveform, output range, and high/low plateaus; compare both rising 63.2% and falling 36.8% delays with the model reference.

For an ideal step, let A=0.1 V and C_total=C_MIM+C_res_output. The reference delay is

`t63 = C_total × integral[0..1] R(A × exp(-s)) ds`.

Use Simpson integration with 1024 segments; the reference includes nonlinear R and the output-terminal parasitic. The ideal voltage source drives the input-terminal parasitic, which is not included in the output load. The reference neglects ≤1 Ω MIM series resistance and the finite 1 ps rise time. Both rising and falling delay tolerances are 0.5%, sufficient to cover these small terms and sample-interpolation error.

Also integrate resistor-model current over the complete VIN/VOUT curves to check `C_total × ΔVOUT = integral I_R dt`. The output-equivalent residual limit is 250 µV (0.25% of step amplitude), covering the series-resistance approximation, trapezoidal integration, and simulation tolerances. This is not an ADC settling-error specification. All metrics must pass simultaneously; missing data, incorrect stimulus, incomplete breakpoints, or incorrect waveforms cannot pass solely on one crossing time.

## Result reuse and stage entry

Use only the latest retained attempt for each test; do not skip a latest failure to seek the best earlier result. Review rechecks native topology, all parameters, actual analysis inputs, normal log termination, export-complete markers, and all data, and verifies input/netlist hashes.

Accept only frozen 1.0.4p1 data or current 1.0.4p2 data. All three tests must share top-level model hashes and configuration, matching the current Linux model entry. If models, data, configuration, or the latest attempt change, the old review can no longer qualify the OTA entry gate.

All three reviews must pass before entering the nominal legacy OTA group. Original OTA operating-point, AC, loop, step, and PVT thresholds remain unchanged. This patch creates no cells and modifies no devices, connections, or school PDK files.
