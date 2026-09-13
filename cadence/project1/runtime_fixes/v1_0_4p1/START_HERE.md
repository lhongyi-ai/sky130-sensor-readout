# Basic-design runtime patch 1.0.4p1

This patch applies to `basic_design_v1_0_4` after schematics such as `p1b_ota_legacy_r4` have been generated. It only updates the runtime entry point; it does not execute SKILL or change the `project1` library, device dimensions, or test thresholds. Do not repeat `load(create.il)`.

## Confirmed cause

School OCEAN returned `native/p1b_tb_res/spectre/schematic/netlist/input.scs` within this run's directory. The `netlist` file in the same directory contains the top-level circuit; `ihnl/cds0/netlist` is an internally generated file. The old script recursively searched for all files of the same name and incorrectly stopped when it found two.

The new entry point parses the absolute path returned by OCEAN in `netlist_return.txt`, verifies it remains inside this independent run directory, and uses the top-level `netlist` beside that `input.scs`. It does not select by modification time, file size, or search order; all existing connectivity, port, model, and parameter checks continue. It also preserves `native_input.scs` and `native_selection.json`, recording the selection basis and input hashes.

## Upload and install (entirely in the Linux terminal)

1. Upload `project1_basic_runtime_fix_v1.0.4p1.zip` to `~/cadence_skywater/`, alongside the original complete ZIP.
2. Run in the terminal that already has the Cadence environment and license address configured:

```bash
cd ~/cadence_skywater
unzip -n project1_basic_runtime_fix_v1.0.4p1.zip
cd project1_handoff/basic_design_v1_0_4
bash ../basic_runtime_fix_v1_0_4p1/apply.sh
```

Expect `P1_RUNTIME_PATCH_APPLIED: 1.0.4p1`. Repeating installation with intact files displays `P1_RUNTIME_PATCH_ALREADY_APPLIED`; either marker allows continuation.

The installer checks original-package and patch hashes, saves the original `run.py` and manifest to `patch_backups/v1_0_4p1/`, and finally updates the manifest to the runtime-patch version. It does not modify your `site.json`, existing statuses, or waveforms. If `P1_RUNTIME_PATCH_STOPPED` appears, return the complete output and do not continue testing.

## Rerun process resistor/capacitor tests

Still in the `basic_design_v1_0_4` folder and the same terminal, run:

```bash
bash p1_run.sh run --group passives --retry
```

`p1_run.sh` removes `LD_LIBRARY_PATH` before starting system Python and saves its value; the runner restores it only when launching OCEAN/Spectre subprocesses. Parent Python no longer inherits Cadence's Python library path throughout execution. Existing PATH, CDSHOME, and license-location environment settings still come from the current terminal; this patch does not install software or configure license services.

This command runs resistor DC, MIM AC, and RC step sequentially. Every attempt writes to a new results directory. Each test prints:

```text
job_name  tool_status  performance_status  [error_message]  results_directory
```

Only actual `PASS PASS` output establishes completion and satisfaction of current thresholds. `ENV_BLOCKED NOT_RUN` means no acceptable result has yet been obtained; `FAIL` or `REVIEW_REQUIRED` requires log analysis. Prior failure records remain visible and do not become passes.

View the summary and package results:

```bash
bash p1_run.sh summary
bash p1_run.sh collect
```

Return the `project1_basic_report_*.zip` printed by the terminal. It includes new selection records, original top-level input, run logs, PSF, CSV, statuses, and the original-runner backup manifest, excluding the full PDK or rule library.

After all three process R/C tests actually pass, the remaining original flow keeps its entry points, with only the launcher changed:

```bash
bash p1_run.sh run --group nominal
bash p1_run.sh run --group pvt
bash p1_run.sh run --group extra
```

Local checks validate only path selection, argument forwarding, environment isolation, installation safeguards, and existing analysis behavior; this patch still awaits actual school Linux execution. OCEAN netlist-generation success does not establish Spectre resistor/capacitor simulation success.
