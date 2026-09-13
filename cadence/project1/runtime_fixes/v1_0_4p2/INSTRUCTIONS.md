# Basic-device review and legacy OTA entry: 1.0.4p2

This package corrects the old resistor and RC acceptance criteria. It only updates local runtime/analysis scripts, reads existing actual results, and writes separate review records. No CIW load, cell recreation, or rerun of completed passive simulations is required.

## What the earlier tests and changes addressed

| Test | What it establishes | Existing conclusion |
|---|---|---|
| NMOS / PMOS DC | Correct dimensions, ports, model/Spectre connection, and reasonable drain current from the gate sweep | Flow has run successfully |
| Process resistor DC | Actual I–V and resistance, avoiding confusion between a displayed value and a constant model value | Measured about 1.231 kΩ; agrees with the voltage-dependent model equation |
| MIM capacitor AC | Correct compensation-capacitor units, geometry, and capacitance | About 34.62225 fF at TT/27°C and 0.9 V bias; this test passed |
| RC step | Correct pulse-source parameters, charge/discharge behavior, transient data, and time units | Pulse source repaired; model reference 42.9836 ps, measured about 42.9852 ps |

Repeated revisions mainly arose from three issues: incorrect CDF fields/functions in the generator; a terminal launch environment differing from the already-open Cadence session; and ideal R/C criteria unsuitable for actual process models in the analyzer. These are migration-tool and criteria problems, not a requirement for repeated manual circuit tuning by the user.

Device mapping did occur earlier: some MOS widths were adapted to school CDF precision, and M7 was split into two parallel 36.1 µm devices because of the 50 µm single-finger maximum. Original dimensions, differences, and parallel mappings remain recorded; performance impact must be checked at the OTA stage. This package does not change those dimensions further.

## Step 1: upload and install the correction package

Upload `project1_basic_runtime_fix_v1.0.4p2.zip` to `~/cadence_skywater/` on Linux.

Run the following in order in the **Linux terminal**, pressing Enter once per line:

```bash
cd ~/cadence_skywater
unzip project1_basic_runtime_fix_v1.0.4p2.zip
bash project1_handoff/basic_runtime_fix_v1_0_4p2/apply.sh
```

Expected: `P1_RUNTIME_PATCH_APPLIED: 1.0.4p2`. If already installed, `ALREADY_APPLIED` appears.

Installation remains in the original `project1_handoff/basic_design_v1_0_4/`, with the version updated in the manifest. Old scripts are backed up to `patch_backups/v1_0_4p2/`; original simulation directories, site.json, schematics, and create.il remain unchanged. If a conflict or hash mismatch appears, preserve and return the text; do not delete original files.

## Step 2: review the three existing datasets

Run this complete line in the **Linux terminal**:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh recheck-passives
```

This command neither starts Spectre nor operates on schematics. It checks native netlists, analysis inputs, logs, waveforms, and hashes, then recalculates metrics.

Expected:

```text
res_dc RECHECK PASS original PASS FAIL
mim_ac RECHECK PASS original PASS PASS
rc_step RECHECK PASS original PASS FAIL
P1_PASSIVES_RECHECK_PASS ...
```

`original ... FAIL` is the preserved result under the old criteria; the new review is stored separately in `runs/passive_reviews/<time>/review.json`. Proceed only after all three pass.

If STOPPED or FAIL appears, run collect at the end of this document and return the results and terminal text; repeating the same simulations is unnecessary.

## Step 3: nominal legacy OTA tests

After the review passes, run in the **Linux terminal**:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --group nominal --retry
```

This starts actual execution of the four nominal legacy OTA tests:

1. `P01_op`: static bias, device operating regions, and power.
2. `P01_ac`: low-frequency gain and open-loop frequency response.
3. `P01_loop`: feedback-loop crossings, bandwidth, and phase margin.
4. `P01_step`: closed-loop step, slew rate, and settling time.

Conditions are TT / 1.8 V / 27°C. The program runs sequentially; a tool-execution or performance-criteria failure stops the flow and preserves results. Original PVT entry points remain available; return these four results for review before proceeding to remaining conditions. Success here does not establish that the new frontend or ADC meets specifications.

## Finally: package results for return

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

Download the new generated ZIP and return it to this task. It includes the new passive review and all prior failure records.

## Local validation and remaining scope

The patch passed 11 local checks, including the original package's 17 regression tests. Checks covered review of actual returned data, rejection of incorrect data, prevention of reuse after evidence changes, repeated installation, conflict stops, and rollback on failure. Linux runtime files were checked for Python 3.6 syntax compatibility.

This patch has not yet executed at the school; the local review uses actual Spectre CSV files you returned. Model-file dependencies at every level, statistical models, noise, PVT, legacy OTA performance, and physical verification each retain their own acceptance requirements and cannot be inferred to pass from basic tests.

Full criteria, formulas, and sources are in `payload/passive_criteria.md`.
