# SKY130 Calibratable Sensor Readout Core — V2

**2026-09-13 update:** Work in the school's Cadence environment has resumed. Local additions include a corresponding 32-item characterization of the legacy OTA, stability/noise diagnostics for the same frontend source, 12 real continuous ADC conversion frames, a GDS assembly of real macros, and release checks for the new school package. [Results and actual unfinished work in this round](docs/local_preparation_20260913.md).

Status: The project has progressed from behavioral models to real SKY130 transistor circuits, a physical implementation of the SAR digital controller, and short closed-loop conversions with the frontend, ADC, and original RTL. The complete chip is unfinished; passing submodules cannot be combined into a claim that the system passes. Formal stability, sampling noise, all-code/long-record verification, complete core layout, and top-level parasitic acceptance for the new version remain unfinished. No new frontend school upload package was released in this round.

The legacy OTA, results, and Git history remain unchanged. All new-version files are in this directory.

2026-09-10 update: [Actual deliverables and remaining obstacles in this round](docs/non_cadence_20260910.md). Added a frontend repair candidate, resumable static verification for the real ADC, noise-tool qualification, and raw-evidence integrity checks. Work that does not require Cadence has not been mislabeled as fully complete.

## Implemented work

The list below distinguishes completed tools/code from passing circuit performance. It is not an all-checked chip acceptance checklist.

- Implemented gain settings of 1/4/16, 12-bit offset-binary output, and 100 kS/s in the model/digital interface; this is not full analog performance sign-off.
- A SAR behavioral model with actual bit-by-bit decisions, rather than an ideal quantizer standing in for all ADC behavior.
- Finite open-loop gain, offset, cubic nonlinearity, sampling-settling memory, per-sample noise, and per-comparison noise.
- Synthetic error sensitivity analysis for binary CDAC weights and the dummy capacitor; this is not SKY130 process Monte Carlo.
- Nominal three-point calibration, validation at independent input points, and retained drift failures with frozen coefficients; no hidden clipping or recalibration.
- Coherent FFT, SNDR/ENOB/SFDR/SNR/THD, endpoint INL/DNL, and separate endpoint-code reachability checks.
- Real, compilable SAR controller RTL: 4 full acquisition cycles plus 12 decision cycles, with no idle cycle between continuous requests.
- Deliberate injection of high noise, slow settling, incorrect capacitor weights, and offset drift to check whether the acceptance framework detects failures.
- Open-source PDK device qualification: 45 process/voltage/temperature single-transistor tests, 200 real mismatch instances, and seed control; separate positive and negative controls for MIM `m` / `mult` statistical scaling.
- Real frontend candidates: a fully differential two-stage PGA, CMFB, startup-equipped biasing, and PDK resistors/capacitors/gain switches. Nominal noise and dynamic settling have progressed, but the first version fails fixed-calibration voltage/temperature tests; the high-input-impedance improvement candidate is kept separately.
- Real ADC candidates: binary MIM CDAC, sampling/reference switches, a StrongARM comparator, and a holding latch; a bottom-plate-sampling candidate with a preamplifier for isolation aims to reduce parasitic effects and kickback.
- Digital controller standard-cell synthesis, placement and routing, DRC/LVS, parasitic extraction, nine-corner static timing, and all-code functional regression on the routed netlist are complete; this is a digital macro, not a complete chip layout.
- The four-MOS sampling switch has independent layout DRC/LVS and R/C extraction; 2430 finite-condition schematic/RC points pass. See the report for actual input/common-mode/source-impedance and process/voltage/temperature ranges. Complete ADC, mismatch, and random-noise coverage are still excluded.
- The R/MIM/CMOS sampling-phase generator passes all 45 independent process/voltage/temperature timing tests. The shortest measured acquisition window is approximately 2.47685 µs; the sampling circuit must settle within this real window.
- The original SAR RTL and real ADC have performed continuous closed-loop conversions; the legacy frontend at gain 16 has also been connected for short conversions. This evidence excludes the full code range, random device noise, and top-level parasitics.
- External-data import and frozen-coefficient fitting/application/independent-validation tools preserve raw codes and check sample counts, clipping, reuse of training points, and hidden refitting across voltage/temperature conditions.

## Running

Requires Python 3.12, NumPy from requirements.txt, and Icarus Verilog / vvp. Without a digital simulator, the full validation explicitly reports incomplete status rather than skipping it and returning a pass.

From the repository root:

    python3 v2/scripts/run_validation.py

Run only the system experiment:

    python3 v2/scripts/run_behavioral.py

Run only the digital logic tests:

    python3 v2/tests/rtl/run.py

These offline commands do not connect to the school server, start Cadence, download the PDK, or modify the legacy project. Separate entry points for real circuits and physical implementation are in [Open-source environment](environment/README.md), [Digital physical implementation](physical/digital/README.md), and [Mixed simulation](integration/README.md).

## Where to find results

- [Experiment report](results/behavioral_report.md): model conditions, results before/after calibration, and failure detection.
- [Model and code validation](results/validation.json): test output, source fingerprints, and legacy-protection checks; valid only for the tests listed in that report, not final analog-circuit acceptance.
- [What chip is this project building?](docs/chip_overview.md): a beginner-oriented explanation of functions, inputs/outputs, external dependencies, and completion boundaries.
- [Project-wide evidence index](results/project_evidence.json): per-item scope, source hashes, failures, and unfinished work, without a false full-chip pass.
- [Failure audit of the frozen frontend candidate](analog/frontend/results/frozen_delivery.json): DC, noise, sampling, common-mode oscillation, and fixed-calibration results for the same revision.
- [New frontend repair experiments](analog/frontend/repair_20260910/README.md): grouped by circuit revision, retaining improvements, failures, and numerically incomplete results.
- [Real ADC all-code verification framework and measured throughput](analog/adc/verification_20260910/README.md): the all-code task is unfinished; six short conversions cannot replace all-code results.
- [Random-noise tool qualification](verification/noise_20260910/README.md): correct RC noise does not imply that the SKY130 noise model matches.
- [Device qualification](environment/results/device_qualification.json), [MIM statistical-scaling qualification](environment/results/cap_multiplier_qualification.json), and [Small-layout closed loop](environment/results/physical_qualification.json).
- [Digital controller layout and parasitic verification](physical/digital/results/physical_validation.json).
- [2430-point schematic/RC regression for the independent sampling switch](physical/adc_switch/results/dummy_w4w8_rc_full.json).
- [45-point timing for the real phase circuit](integration/results/phase_qualification.json).
- [Digital logic validation](results/rtl_validation.json): all-code, reset, continuous-conversion, and other tests.
- [Frozen specification](config/spec.json): design targets separated from assumed model parameters.
- [Error budget](results/error_budget.json): units, timing, noise allocation, and candidate capacitor sizing.
- [Unexecuted corner matrix](results/qualification_matrix.csv): 45 process/voltage/temperature combinations times three gain settings; all 135 rows are NOT_RUN.
- [Stage status and next tasks](docs/status.md), [Interface description](docs/interfaces.md), and [Digital timing details](docs/digital_control.md).

## Limits on interpreting these results

The configured 86 dB open-loop gain, 5 µV input noise, 180 ns time constant, and similar values are budget assumptions, not values extracted from SKY130 circuits.
Model SNDR/ENOB describes how these assumptions combine mathematically; it cannot be presented on a resume as actual chip performance.

The original Python behavioral model does not adequately capture source-impedance loading, continuous-noise folding, reference droop, CMFB, comparator kickback, or MOS injection. Added analytical budgets and real PDK circuits check some of these factors separately, within the scope of each report. They do not retroactively upgrade the original model's numbers to actual circuit results.

Linear calibration removes only static gain and offset; normalized SNDR is essentially unchanged. A small calibrated mean residual does not establish 12-bit effective accuracy for individual conversions.
There is already evidence for 200 real mismatch samples, 45-point PVT, power, and layout at the device/some-module level. The complete frontend-plus-ADC core still lacks 200-sample coverage, 135 system combinations, full area, top-level parasitics, and noise-inclusive SNDR.

## Reproduction and dependency boundaries

behavioral_manifest.json stores SHA-256 hashes of the model/config/scripts and every result file.
validation.json stores source fingerprints including tests and RTL; it is set to RUNNING before execution, and an interrupted or failed run cannot use previous results to claim a current pass.
Model, configuration, test, and RTL fingerprints are compared before and after execution; changes during a run prevent a pass. Acceptance thresholds and fixed timing cannot be relaxed solely by changing configuration files.
Source or configuration changes require validation to be rerun. Older files may remain as historical data, but must be checked against fingerprints and authoritative status.

Only project-owned code, public dependency versions, and analysis results are stored. School accounts, licenses, and restricted PDKs are not committed, even to a private repository.
