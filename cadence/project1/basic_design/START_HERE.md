# project1 complete basic-design package v1.0.4

This package locally completes source freezing, schematic and symbol generators, basic testbenches, execution entry points, netlist checks, result analysis, and return tools. **This package has not yet run in school Cadence; passing local checks must not be treated as passing circuit simulation.** Completed independent NMOS/PMOS tests remain in their original cells without overwriting.

## Package contents

| Content | Provided by this package |
|---|---|
| Process resistor | `p1b_tb_res`: `res_high_po_0p35`, default single segment 350 nm × 350 nm, bulk at VSS, I/V test over 0–0.1 V |
| MIM capacitor | `p1b_tb_mim`: `cap_mim_m3__base`, default 4 µm × 4 µm, m=1, AC admittance and capacitance measured at 0.9 V bias |
| Process RC | `p1b_tb_rc`: small-step response of the actual process R/C above, cross-checked by time constant |
| Legacy two-stage OTA | Native `p1b_ota_legacy_r4` schematic and symbol, 13 MOS instances (M7 split into two parallel units), explicit bulk, bias, and all port connections |
| OTA testbenches | Nine total: `p1b_tb_op/ac/loop/step/cm/psrrp/psrrm/noise/swing` |
| Original PVT | Thirteen frozen conditions, each with operating-point, AC, loop, and step tests: 52 tests, distinct from the new system's 45-point PVT |
| Supplemental tests | CMRR/PSRR transfer functions, static noise, forward output sweep, 1/2/10/20 pF loads, and 19 input common-mode points; nominal 5 pF is already included in P01 |
| Evidence | Original design netlist, historical 13-point summary, and all 52 raw PVT datasets; prior failures are fully retained |
| Execution and return | `run.py`, independent directories per test; no formal simulation if the netlist fails checks; logs, waveforms, measurements, versions, and hashes are returned together |

Total: **13 cells, 1 OTA symbol, and 87 test jobs**. View the job list with `python3 run.py list`. Schematics connect devices with short wires and net labels for individual inspection; they are not imported images or Spectre text alone.

The legacy OTA retains the original baseline's ideal 2 kΩ series 3 pF compensation, ideal external 10 µA reference, and 5 pF parallel 100 kΩ load. MOS current mirrors generate its bias; the original design has no bias resistor requiring replacement. Process R/MIM area selection, precise realization of 2 kΩ/3 pF, mismatch, and layout belong to subsequent component replacement and physical implementation; the original baseline must not be silently changed during the initial comparison.

Based on the measured M8 callback, this version explicitly adapts MOS widths to 0.01 µm precision. Original dimensions remain in reference; per-device differences are in `device_size_mapping.md`. This is not a validated full-process grid; other devices still require callbacks and netlist checks. Dimension-check tolerance is not relaxed.

## 1. Upload and prepare (Linux terminal)

Upload `project1_basic_design_v1.0.4.zip` to `~/cadence_skywater/`. Run these commands in order:

```bash
cd ~/cadence_skywater
unzip -n project1_basic_design_v1.0.4.zip
cd project1_handoff/basic_design_v1_0_4
python3 run.py prepare
```

Compatible with **Python 3.6.8** in the environment report, using only the standard library; no pip or software installation is required. The extraction directory is separate from the `project1` library database. `unzip -n` does not overwrite existing uploaded files; if the same version was uploaded before, preserve the old directory first and do not mix packages.

`prepare` creates `site.json` and prints one CIW command containing the absolute path of your current directory. Default paths come from the existing environment report:

```text
OCEAN:   /project/engineering/cadence21/ic/tools/bin/ocean
Spectre: /project/engineering/cadence21/spectre/tools/bin/spectre
Model:   /project/engineering/cadence21/CDK/sky130_release_0.0.3/models/sky130.lib.spice
Working directory: ~/cadence_skywater
```

OCEAN points to the IC installation running Virtuoso rather than blindly using another ICADVM installation on PATH. This absolute OCEAN path still requires first-run confirmation on Linux; if absent, the tool explicitly reports an environment block. Correct the path in `site.json`; there is no need to upload the complete package again. Prior actual NMOS/PMOS runs validated TT at this model entry; other corners still require execution of this package.

## 2. Generate all native circuits once (Cadence CIW)

If Virtuoso is not already open, run in another terminal:

```bash
cd ~/cadence_skywater
/project/engineering/cadence21/ic/bin/virtuoso &
```

Paste the entire line printed by `prepare` into the bottom input field of the **main Virtuoso CIW window** displayed at startup. Do not paste into the schematic status bar or Linux terminal. Its form is shown below; use the actual path printed by the terminal:

```lisp
p1bRoot="/home/compute/l.hongyi/cadence_skywater/project1_handoff/basic_design_v1_0_4" load(strcat(p1bRoot "/create.il"))
```

Success markers: `P1B_ALL_CREATED` in CIW and `created.txt` in the package directory. The package's `p1b_` cells appear under Library Manager → `project1`. Open `p1b_ota_legacy_r4/schematic` and `symbol` to inspect them.

The generator attempts to call school MOS parameter callbacks to update total width, finger width, length, and diffusion geometry, avoiding individual manual entry. It checks whether callbacks changed requested dimensions. **Callbacks and SKILL APIs still require first execution validation on this installation**; errors stop the flow rather than accepting incorrect dimensions. `cdf_values.tsv` stores actual parameter readbacks.

All target names are checked before creation; any same-name cell stops generation. Repeating `load` does not overwrite existing circuits. After successful generation, proceed directly to tests without another `load`. If generation stops, preserve cells and CIW errors; do not delete the library or modify the process library. Return the error text, `create_status.txt`, and `cdf_values.tsv` so I can revise the package.

## 3. Validate process R/C with one command (Linux terminal)

```bash
cd ~/cadence_skywater/project1_handoff/basic_design_v1_0_4
python3 run.py run --group passives
```

Execution order: resistor DC → MIM AC → process RC step. The command invokes OCEAN in the background to export netlists from these native schematics. Spectre starts only after the locally written checker audits each netlist. Jobs run serially by default without requesting parallel jobs.

Per-job results: `runs/job_name/time_random_id/`.

| File | Purpose |
|---|---|
| `status.json` | Records tool-execution status separately from performance-check status |
| `native_netlist.scs`, `netlist_audit.json` | Original schematic-exported netlist and connectivity/dimension audit results |
| `input.scs` | Actual simulation input; device content comes from the native netlist, with this job's model, parameters, and analysis settings appended |
| `spectre.out`, `log_audit.json` | Original log, exit code, normal-termination checks, and warnings |
| `psf/` | Actual raw Spectre results, viewable in ViVA |
| `*.csv`, `metrics.json` | OCEAN-exported waveforms, actual measurements, and threshold evaluations |
| `ocean_netlist.log`, `ocean_export.log` | Diagnostics for netlist-generation or result-export failures |

Success requires `status=PASS` and `performance_status=PASS`. The resistor must have positive resistance and approximate linearity and is compared with its nominal CDF value; MIM capacitance must be positive and is compared with the CDF default of 34.6223 fF; RC is checked through its step time constant. The 1%/5%/10% tolerances are environment-test tolerances for this package, not process-accuracy or chip-specification guarantees. If default model and CDF values differ, preserve results and analyze why; do not directly relax thresholds to display a pass.

## 4. Four nominal legacy OTA tests (Linux terminal)

After all three process R/C tests pass, run:

```bash
python3 run.py run --group nominal
```

Runs `P01_op`, `P01_ac`, `P01_loop`, and `P01_step` in order, all at TT, 1.8 V, 27°C. Common mode remains 0.9 V. Operating-point outputs include every MOS device's current, gm, gds, VDS, and VDSAT; the measurement table also retains differences from old ngspice results.

AC: 1 Hz–1 GHz, 120 points per decade; differential input is +0.5/−0.5 V small signal, normalized by the actual differential input. The loop uses the original 1 GH/1 GF loop-break conditions and records every 0 dB crossing, its direction, and phase, rather than only the first crossing.

Step: 0.8→1.2 V, delay 1 µs, rise/fall 20 ns each, high-level width 2 µs, period 5 µs, total duration 5 µs, maximum step 0.5 ns. Retains the original **20%–80% least-squares slew rate** and ±4 mV settling time relative to the input 50% crossing. The original 13-point historical waveforms were used to check analysis consistency; historical failures do not become new passes.

This package uses stricter Spectre numerical tolerances; the school model version also differs from the original open-source PDK. Result differences therefore require explanation, and exact equality with historical results is not guaranteed.

## 5. Original PVT and supplemental tests (Linux terminal)

After nominal review, run:

```bash
python3 run.py run --group pvt
python3 run.py run --group extra
python3 run.py summary
```

PVT comprises the other 48 tests for original P02–P13; the four P01 tests already ran in the nominal stage. Circuit-performance failures during PVT allow other conditions to continue; tool failures stop execution to avoid repeated invalid runs. `summary` lists every attempt of every job, explicitly shows unrun jobs as `NOT_RUN`, and generates `attempts.csv`; it does not automatically select each job's best result.

A combined entry `python3 run.py run --group all` is also available for sequential batch execution once the initial flow has been validated. For the first run, the three groups above are recommended to locate environment problems; no additional file uploads are needed.

CM/PSRR tests output transfer functions that must be paired with differential gain at the same frequency to derive rejection ratios. Static-noise export units require initial verification in ViVA. These supplemental items show `REVIEW_REQUIRED` and cannot directly establish full acceptance, nor replace ADC switching dynamic noise, mismatch, or post-layout validation.

## 6. Interruptions, retries, and failures

Previously attempted jobs, including failures, are skipped by default and old directories are not rewritten. For example, after fixing a job:

```bash
python3 run.py run --job P01_ac --retry
```

Every `--retry` creates a new results directory. If the terminal closes, directories without a final status retain original logs; such `NOT_RUN` states are not passes. Do not manually change `status.json` to PASS. Connectivity errors, parameter errors, and abnormal diffusion geometry are reported in `netlist_audit.json` or `status.json`; circuits that fail netlist checks are not used for formal results.

`status=PASS` only means this job completed netlist auditing, Spectre execution, and result export. `performance_status=FAIL` means measured data failed test thresholds. `ENV_BLOCKED` means tools, paths, or native-netlist generation are blocked. Missing exported signals retain PSF and report failure; no zeros or fabricated measurements are substituted.

## 7. Package all results for return

Run in the same Linux directory:

```bash
python3 run.py summary
python3 run.py collect
```

The final output prints the full path to `project1_basic_report_time_id.zip`. Download that ZIP and return it to this task. It includes actual PSF data and grows with the number of runs; it excludes the full PDK, rules, and licenses. If generation failed, also return the specific CIW error text.

## Known boundaries

- This package's generator, OCEAN netlist-path behavior, model corners, result signal names, and callbacks all require first execution validation on Linux; only local implementation and checks are currently complete.
- The legacy OTA comparison is schematic-level; it excludes a process-compensation replacement at actual dimensions, layout, and DRC/LVS/PEX and does not claim they passed.
- The current package does not migrate the new frontend or ADC, replace the digital standard-cell library, or change the `data_gain` interface.
- Native cells are not automatically overwritten; version conflicts or callback errors require preserving the state and revising the package. This package reduces uploads but cannot guarantee that future revisions will be unnecessary.

## English technical summary

This bundle freezes the legacy Day 4 two-stage OTA and its 13-point PVT evidence. It provides native Cadence schematic/symbol generation, process resistor and MIM-capacitor benches, a process RC transient check, and 87 sequential simulation jobs. The legacy OTA retains the original ideal compensation and external bias reference for controlled comparison. Spectre runs use audited netlists exported from the native schematics. Every attempt retains its inputs, logs, raw results, tool provenance and measurements. Local checks are not Cadence qualification; all new SKILL/OCEAN flows remain pending execution in the school's installed environment.

## API references

The generator references official Cadence forum guidance on [symbol pin generation](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/65626/issue-skill-script-creates-schematic-and-symbol-but-ports-are-missing), [schematic generation and net labels](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/36821/schematic-creation-using-skill/1349758), [native OCEAN netlist generation](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/17473/how-to-create-netlist-using-ocean-script), and [CDF callback limitations](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/50707/changing-schematic-properties-and-callbacks/1382755); installed-version differences still require actual execution validation.
