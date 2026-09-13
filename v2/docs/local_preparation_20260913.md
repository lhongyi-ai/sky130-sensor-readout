# Local Progress and School Delivery Preparation: 2026-09-13

Corresponding legacy OTA characterization, new frontend diagnostics, continuous ADC conversion, and reusable layout assembly were actually executed locally. **The complete chip has not passed acceptance, and no new frontend installation package was released to the school in this round.** Existing school environment and legacy OTA data are retained as handoff evidence; this preparation does not overwrite the original school library.

## The legacy OTA's 32 items

32/32 corresponding local ngspice tests completed, plus two differential references. They use the 13 MOS dimensions and diffusion geometries already exported by the school and cannot be described as new school Spectre runs. Nominal gain differs from the school value by approximately 0.000011 dB and power by approximately 0.000018 µW; the maximum relative difference across five shared operating-point fields for the 13 MOS devices is approximately 0.0001934%.

- CMRR: 71.324 dB, passing the legacy threshold.
- PSRR+ / PSRR−: 36.331 / 36.099 dB, below 45 dB.
- ICMR: 0.8–1.2 V on a 0.1 V grid, not covering 1.3 V; not a continuous boundary measurement.
- Loop and step tests pass at 1/2 pF; extended-load PM at 10/20 pF is 53.767°/40.554°, below 55°. Extended loads must not be confused with the original mandatory 1/2/5 pF range.
- Noise at 1 kHz: 401.152 nV/√Hz; integrated from 10 Hz to 1 MHz: 52.300 µV RMS. Report-only, with 26 noise-model warnings retained.

Common-mode/supply tests and the original differential test have different DC bias, so additional differential references at matching bias were run before calculating rejection ratios. An automatic absolute-gain PASS cannot override an ICMR relative-gain failure. A DC follower sweep is not presented as an independent output-swing test.

[Complete reproduction report, raw data, and entry point](../verification/legacy_extra_20260913/README.md). The 32 school-side extra items and formal review still await school raw results; the previous three PVT settling failures remain unchanged.

## New frontend

Continued using same-source `dynamic_20260911/candidate_06.spice`, without changing the circuit or assembling results across candidates.

After adding current/voltage dual injection, the previous high-frequency differential upward recrossing of 0 dB disappears, indicating that the old measurement method omitted reverse transmission. Minimum local differential PM across acquisition/hold and three gains is approximately 74.22°. However, the coupled-loop reference system's right-half-plane pole count and internal modes unobserved by ports are still not reliably verified, so formal full multiloop stability has not passed.

Six static-noise diagnostics across three gains and acquisition/hold states were actually executed. They cannot replace sampled random-noise acceptance. Comparison with the legacy FDDA10 113 µV budget is diagnostic only; differing filters and sampling states cannot directly establish new-version noise PASS/FAIL. The 45-point PVT run has not started because the stability prerequisite remains unmet.

A local reference for a small G4 DC/AC trial was added so future native school designs can first undergo a small comparison. This is still not a migration package proven by school execution. [Complete frontend record](../analog/frontend/qualification_20260913/README.md), [Minimum school migration comparison](../analog/frontend/qualification_20260913/CADENCE_CANARY.md). This round had 26 real launches, including 6 fully retained noise-export failures; 6 method/evidence checks pass. The main task verified 415 delivery-file hashes and corrected the migration document's OCEAN path using the latest school `site.json`.

## ADC

Added 12 continuous frames using the real transistor circuit, repaired bridge, and original SAR RTL, with a 122 µs simulation record. The baseline run took 393.553 s; all 144/144 comparator decisions, 12 sets of data-bus/RTL-log/comparator codes, and 50 handshake checks agree. Inputs cover positive/negative near-full-scale, both sides of zero, and new code centers. Results are 5, 4090, 2047, 2048, 100, 3995, 1601, 3000, 1907, 2203, 2557, 3311.

A stricter review using the same stimulus also completed: tolerances tightened 10-fold, maximum step reduced from 2 ns to 1 ns, elapsed time 839.944 s, exit code 0; all 12 frame codes, 144 real decisions, and 50 handshake checks still agree.

**The complete numerical-waveform convergence gate fails, so reliable continuous conversion and full ADC acceptance remain unfinished.** Maximum CDAC difference is approximately 48.393 mV on the union of accepted time points and approximately 4.077 mV on a common 1 ns grid, both above 0.05 LSB = 9.765625 µV. Predecision differences are only approximately 13.38 nV, which cannot override substantial differences across the full waveform. Raw points, edges, and local diagnostics from both runs are retained; identical codes do not justify changing solver settings or releasing all-code runs.

The same model also confirmed that the KLU matrix solver can complete an operating point in 3.021 s, exit code 0. This is a new computational path for further verification, without a conclusion of transient speedup or passing numerical equivalence.

[Complete ADC results and resumable entry point](../analog/adc/qualification_20260913/README.md). 13 related tests pass, and the main task independently verified 76 delivery-file hashes. All-code static progress is currently 0/131,073; the 16,384-point spectrum and at least 200 system mismatch samples remain unexecuted. Existing local CDAC/comparator statistics cannot be added together as complete ADC mismatch acceptance.

School migration has a separately demonstrated architecture risk: the current digital-bridge binary is ARM64 Linux and cannot directly be treated as executable on school machines. The school side must check CPU architecture, supply a bridge matching the target architecture, and qualify loading and short conversion. Passing continuous conversion in the local container does not prove school-bridge compatibility.

## Layout and top-level post-layout simulation

Generated a real local assembly GDS with one differential CDAC, two four-transistor sampling switches, and one digital macro. KLayout readback passes, and Magic reports geometry DRC=0 for the unrouted assembly; 148 existing-evidence/port/hash checks and 7 false-pass-prevention checks pass.

A CDAC substrate port was found and explicitly exposed in a new simulation-adapter copy to prevent a floating internal substrate. The digital macro SPICE is only an LVS topology view with R=C=0; actual SPEF/SDF/gate-level timing interfaces or fresh extraction are required. It cannot serve as analog RC post-layout simulation.

Physical layouts for the frontend, comparator/preamplifier, reference network, and clock/drivers are missing, as is intermacro routing. Full-core LVS, PEX, and performance post-layout simulation were not executed. All 135 rows in the three-gain ×45-PVT readiness matrix are NOT_RUN; the post-layout readiness gate correctly refuses release.

[Local GDS, images, and complete preparation record](../physical/core_integration_20260913/README.md).

## School Linux delivery reliability

The user explicitly requested fewer errors discovered only after repeated uploads. This round incorporates that into new-version release conditions:

1. Freeze the school's demonstrated Python 3.6.8, IC618, and Spectre 21 environment contract; deliver local NumPy/ngspice tools separately from school entry points.
2. Use a complete versioned package, manifest checks, and a single entry point; test installation, reruns, failure exits, and recovery in clean directories and paths containing spaces, without requiring successive temporary patches.
3. Check environment and dependencies first; verify pins, CDF parameters, actual stimulus, and operating-point data fields from native exports. A SKILL function without execution evidence does not pass merely because parentheses balance.
4. First run a small school-side trial with a local reference; save model/netlist/package hashes and raw logs. That evidence must match the same package before batch tasks start.
5. Record environment, simulation, export, and performance failures separately; old successful records cannot replace the newest failure, and recovery must not overwrite old data.

Existing reliability regression reran: 4 launcher tests, 7 export/install/rollback tests, and 5 pipeline-failure scenarios pass. The new package gate additionally passes 13 synthetic tests, rejecting corruption/mixed revisions/incorrect hashes, CRLF, Python 3.6 incompatibility, and stale/simulated field evidence, and checking real log errors and completion markers bound to the same package hash. Even exit code 0 does not release a run with logged errors or missing actual export files. Packages containing native modules must also declare the target architecture, match ELF headers, and supply school-side module-loading records; an ARM local bridge cannot be included in an x86 target package.

Some tests use simulated OCEAN/Virtuoso, proving entry-point logic rather than actual school-tool execution. Python 3.6 compatibility has currently been checked at the syntax level; that runtime is unavailable locally. The new completion-marker protocol has not yet been executed by a new school entry point, so batch release remains denied. Hashes bind content, not authenticate school provenance; field logs still need substantive review.

[New-package release tool and tests](../../cadence/project1/reliability_20260913/PACKAGE_GATE_README.md), [Existing launch/recovery regression record](../../cadence/project1/reliability_20260913/regression.json). This round neither requested reupload of the old OTA package nor claimed reliable school-side batch execution of the new frontend.

## Order of continued work

Compare the legacy OTA school extra items once raw results return; close formal stability and sampled noise for the new frontend before freezing same-revision 45-PVT; resolve ADC numerical convergence and the computational path before releasing all-code, long-record, and system-mismatch runs; after freezing modules, complete missing analog layouts, intermacro routing, full DRC/LVS/PEX, and finally unified top-level post-layout simulation.

These are the actual remaining conditions. No chip specification changes, and completed preparation is not equated with completed design acceptance.
