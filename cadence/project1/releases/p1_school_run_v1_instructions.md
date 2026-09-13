# project1 fixed school-environment entry v1

In the latest report, both MIM and RC reported `exec: virtuoso: not found` when OCEAN started. Neither netlist generation nor Spectre simulation began. Previously configured PATH and other variables applied only to that terminal session; the original `p1_run.sh` isolated Python libraries without fully restoring the school tool environment.

`p1_school_run_v1.sh` loads the previously successful environment consistently before invoking the existing `p1_run.sh`. It fixes the Virtuoso path matching IC618, CDSHOME, shared-library path, and user-confirmed license-server address, retaining Python-library isolation. These settings affect only this launch and its subprocesses; they do not change terminal startup files, system installations, process libraries, schematics, site.json, or existing run statuses.

## Upload once

Upload `p1_school_run_v1.sh` to this path on school Linux:

```text
/home/compute/l.hongyi/cadence_skywater/p1_school_run_v1.sh
```

This is a single file; no extraction, chmod, or CIW load is needed. Continue using the original `basic_design_v1_0_4` and installed 1.0.4p1 patch.

## Subsequently run from any Linux terminal

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job mim_ac --retry
bash ~/cadence_skywater/p1_school_run_v1.sh run --job rc_step --retry
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

Return both outputs and the report ZIP printed by collect. Continue evaluating tool and performance statuses separately; an entry point starting does not establish a test pass. The resistor model-consistency review is preserved separately, and the old CDF-comparison failure remains unchanged.

If the first command shows `P1_SCHOOL_ENV_STOPPED` or `ENV_BLOCKED`, return the error first rather than retrying repeatedly; the new run directory preserves actual tool logs. If tool status is PASS but performance status is FAIL, retain that result and continue collecting the other independent basic test. Correct passive criteria together after all three raw datasets are available.

Use the same entry for later queries and return packaging:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh summary
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

This entry restores only observed client configuration. The license address is not a license file or key; actual license acquisition remains controlled by the school server. Local checks for this version cover shell syntax, variable restoration in an unconfigured terminal, argument forwarding, Python/Cadence environment isolation, and subprocess exit codes. School Cadence was not run locally.
