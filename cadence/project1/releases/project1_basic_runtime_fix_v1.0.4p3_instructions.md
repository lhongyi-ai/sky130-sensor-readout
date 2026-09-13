# Legacy OTA operating-point export fix 1.0.4p3

## What this test measures and where it failed

P01_op measures static bias, supply power, and whether all 13 MOS devices occupy the required operating regions for the legacy OTA at TT / 1.8 V / 27°C. Spectre converged in 11 iterations with 0 errors, 0 warnings, and 3 notices; output was 0.900012033 V and supply current 151.015357 µA, corresponding to approximately 271.827642 µW supply power.

Device-data export failed because the school model has another internal MOS hierarchy. For example, the actual saved device name is `XOTA.M1.msky130_fd_pr__nfet_01v8`, whereas the old script read `XOTA.M1`. Consequently, op_devices.csv contained only a header and all 65 parameter reads were empty. The old OCEAN input executed commands individually and still wrote COMPLETE after errors; Python's final missing-data check correctly retained FAIL / NOT_RUN.

The fault was in the generated result-reading script. It is not a confirmed transistor operating-region failure, nor does it mean simulation did not run.

## Changes in this version

- Use the 13 internal MOS names already present in the returned PSF; select dcOpInfo and check available device names before reading.
- Export ids, gm, gds, vds, and vdsat, together with the original device name for each row.
- Perform all steps within one protected export operation; any error immediately returns a nonzero exit status. Python checks error logs, 13 data rows, finite values, and mappings in addition to COMPLETE.
- Create an independent recovery record from existing PSF and re-export P01_op. Copy and preserve original PSF and input hashes without changing the failed original attempt; do not rerun Spectre for this P01_op.
- Circuit, dimensions, compensation values, stimuli, simulation options, and performance thresholds remain unchanged.

The log's bad pivoting messages are numerical-solver notices; this run still converged. The notices are fully preserved for subsequent review alongside device operating points and AC/step results. Simulation options were not changed to remove the notices.

## Upload once and run one continuation entry

1. Upload `project1_basic_runtime_fix_v1.0.4p3.zip` to `~/cadence_skywater/` on Linux.
2. Run these three lines in order in the **Linux terminal**. No CIW load or schematic rebuild is needed:

```bash
cd ~/cadence_skywater
unzip project1_basic_runtime_fix_v1.0.4p3.zip
bash project1_handoff/basic_runtime_fix_v1_0_4p3/continue_nominal.sh
```

This entry performs: install fix → review the three existing passive datasets (without resimulation) → recover P01_op export from existing PSF → if it passes, continue with P01_ac, P01_loop, and P01_step → automatically collect.

Expect `P1_RUNTIME_PATCH_APPLIED: 1.0.4p3`, followed by `P1_PASSIVES_RECHECK_PASS`. Successful recovery displays `P01_op PASS PASS RESUMED_EXPORT ...`. When entering the nominal group, P01_op displays ALREADY_ATTEMPTED because it skips the just-recovered successful result, then runs the other three tests.

Failure at any step stops subsequent tests and automatically packages available results. Download the new ZIP at the final printed path and return it to this task, preserving terminal text. Do not repeat the same entry merely because FAIL appeared; analyze that report first.

If installation fails before the run stage, the entry will not collect a report from an incomplete installation; return the error text directly. Old scripts are saved in `patch_backups/v1_0_4p3/`. Old 1.0.4p2 data, schematics, and all failure records are retained.

## Validation status and references

Local checks include: all 13 internal device names exist in the actual PSF; the old “error + COMPLETE + exit code 0” case is rejected; missing rows, nonnumeric values, and incorrect device mappings remain rejected; recovery calls only OCEAN and preserves original PSF and failures; installation and rollback; the original package's 17 regression tests; and passive-data review.

There is no local OCEAN/SKILL runtime; numerical unit tests of recovery use synthetic fixtures and were not used to declare an OTA pass. Actual device parameters and saturation-region status still await this school export.

API references: [Cadence engineer's example using selectResult, outputs, and getData to read operating-point structures](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/36112/getting-report-into-a-list); [Cadence explanation of errset and exit(1)](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/59814/how-to-get-exit-code-0-when-there-is-a-skill-error-in-a-skill-script/1399235). Internal MOS names come from this returned file, without guessing names in other process libraries.
