# Real Transistor Circuits and SAR RTL Integration

This directory uses ngspice XSPICE `d_cosim` and Verilator to execute the original synthesizable `rtl/sar_controller.v`. Another software SAR algorithm does not replace the digital controller. See HDL co-simulation in the [Official ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf) for the interface method.

## Three different levels of evidence

1. `qualify_cosim.py --vdd 1.62` (also run at 1.8 and 1.98): the ADC is an ideal test fixture, verifying only logic ports, polarity, and continuous 100 kS/s timing. It cannot establish analog ADC correctness.
2. `qualify_phases.py`: a nonoverlapping phase circuit built from real SKY130 MOS, resistors, and MIM; 45 process/voltage/temperature combinations checked independently, retaining actual loads, all waveforms, and source snapshots.
3. `run_adc_cosim.py`: continuous conversions with real ADC and original RTL, optionally adding an explicitly selected frozen frontend. Defaults to the real phase circuit; `--phase-source ideal` is only for retained control experiments.

Examples (inside the container):

    python3 /repo/v2/integration/qualify_cosim.py --vdd 1.8
    python3 /repo/v2/integration/run_adc_cosim.py --input-v 0.123

The new bottom-plate-sampling/isolation-preamplifier candidate uses explicit arguments without overwriting the original ADC:

    python3 /repo/v2/integration/run_adc_cosim.py \
      --adc-wrapper /repo/v2/analog/adc/adc_analog12_bottom_preamp.spice \
      --adc-subckt adc_analog12_bottom_preamp \
      --adc-preamp /repo/v2/analog/adc/adc_preamp.spice

`--frontend` must specify the frontend file under test. `--gain` is 1, 4, or 16; input argument `--input-v` denotes the desired differential ADC voltage after ideal amplification, and actual sensor stimulus is automatically divided by gain. Source impedance remains between the sensor and frontend and must not disappear when the frontend is added.

Frontend isolation resistance must be explicitly set with `--frontend-riso` according to the frozen experiment; differing source defaults must not silently change load conditions. For example, the reviewed FDDA5 snapshot uses 2200 Ω per side. FDDA10 currently has common-mode oscillation and must not be connected and declared qualified using short-code tolerances.

`candidates/20260908T045601001817Z/` preserves a combined snapshot of low-threshold reference switches, real preamplification, and four-MOS compensated top-plate clamps. This candidate completed only one full conversion at input 0.123 V each at nominal and SS/1.62 V/−20 °C, both yielding 2677. Its manifest remains `UNQUALIFIED_INTEGRATION_CANDIDATE`. Runs must explicitly supply that directory's wrapper, blocks, and preamp, plus separate `--extra-include` arguments for its reference-switch and sampling-switch files; other revisions must not be mixed in. The snapshot generator replaces only the two top-plate clamps. Compensation transistors must connect to held node B; A/B cannot be swapped.

A logic-bridge report needs more than PASS: it must match hashes of the current controller, interface wrapper, and bridge script, as well as supply and simulation backend. Source changes require requalification.

`--reference-r` and `--reference-c-nf` describe external reference/common-mode source impedance and external decoupling, defaulting to 1 Ω and 10 nF each. `--source-r` is 0/350/1000 Ω per terminal, and `--input-cm-offset-mv` is −50/0/50 mV. References remain ±0.2 V relative to VDD/2.

Reference conditions are explicitly distinguished: default `--reference-cm-mode tracking` gives VREF±=VDD/2±0.2 V; `fixed` keeps external references at 1.1/0.7 V while input common mode remains VDD/2. They agree nominally and differ as supply changes. The original plan specifies only nominal references; this external interface condition must ultimately be frozen or both covered. Failure in one mode cannot directly be attributed to the circuit in another mode. Some early standalone ADC reference-branch diagnostics use fixed mode.

Large-circuit simulations explicitly save required observation nodes rather than keeping all internal waveforms in memory. `--solver sparse`/`klu` changes only the numerical solver, not the circuit, conversion count, stimulus, or error thresholds. Timeouts are separately marked incomplete; partial correct output cannot imply a complete pass. Old timeout reports remain unchanged.

## Known interpretation limits

- Short integration tests usually contain only three conversions per input. The 2 LSB raw-code tolerance is a smoke gate for connection/polarity/timing errors, not a relaxation of INL, calibration-residual, or SNDR targets.
- Verilator interface-log `$realtime` may display zero. Conversion intervals are measured from data_valid rising edges in SPICE waveforms; zero log timestamps cannot prove timing.
- Digital level bridges remain ideal interfaces and exclude digital standard-cell power/delay. Real digital-macro physical timing and power have separate reports; they must ultimately be integrated under consistent top-level conditions, without combining best values.
- MOS/capacitors/resistors use the real PDK, but this directory is currently schematic-level. Reference transient current and net supplied energy are directly integrated; this is not final full-chip power acceptance.
- New power analysis integrates only complete conversion cycles between two data_valid rising edges. A single conversion lacks enough complete cycles, so no average power is produced. Early short-window diagnostic values are retained but must not be interpreted as full-cycle power.
- The currently qualified flow has not established complete inclusion of large-signal random device noise in the dynamic comparator. Noiseless transient FFT, continuous-preamplifier `.noise`, or artificially injected independent random sources cannot individually establish full ADC/system SNDR. The relevant time-varying noise method needs further qualification; final Cadence verification remains required.
- Icarus co-simulation hangs, old phase controls, old frontend/ADC failures, and every source snapshot are retained. Use timestamped `summary.json` files to judge specific candidates; a `latest` file does not mean every revision passes.
