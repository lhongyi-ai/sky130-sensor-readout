# Pulse-source repair v2: property-query function error fix

The v1 function `dbFindPropByName` does not exist in school Virtuoso. The error occurred within the first read-only precheck, before any pulse-parameter modification or saving. This was a repair-script error.

v2 queries existing properties using `car(setof(prop obj~>prop prop~>name==name))`, retaining package-ownership, instance-type, original-stimulus, and actual-CDF-field checks. Both testbenches are still checked before modification, and each actual CDF value is read back.

On load, v2 releases read-only references left by the old script; it stops if it encounters an editable reference, preserving potentially unsaved changes. The v1 file and log are retained. No library regeneration, process-library modification, or environment reconfiguration is required.

## Instructions

1. Upload `p1_fix_pulses_v2.il` from the same directory to `/home/compute/l.hongyi/cadence_skywater/` on Linux. It is a single file requiring no extraction.
2. If `p1b_tb_rc` or `p1b_tb_step` schematic editing windows are open, save and close both; keep Cadence CIW open. Run in the bottom CIW command field:

```lisp
load("/home/compute/l.hongyi/cadence_skywater/p1_fix_pulses_v2.il")
```

`function ... redefined` in the same CIW indicates that new function versions were loaded. A completed repair should show two `P1_PULSE_SOURCE_SAVED` messages, ending with:

```text
P1_PULSE_REPAIR_V2_DONE: 2 sources saved. Next rerun native audits; NOT A SIMULATION PASS.
```

3. After the completion marker appears, run this complete line in the **Linux terminal**:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job rc_step --retry
```

If MIM has not yet run, also execute in the Linux terminal:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job mim_ac --retry
```

Copy each command in full; do not put the arguments after `.sh` into a separate command.

4. After completion, package and return the new ZIP:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

If load produces `*Error*`, stop subsequent simulations and return the CIW error text. The log is `basic_design_v1_0_4/runs/p1_pulse_repair_v2.log`; collect includes it automatically if created. A startup stop caused by an old editable reference may occur before the new log is created, so preserve CIW text. Do not address it by deleting cells or rerunning create.il.

## Repair scope and validation

| Testbench / instance | Schematic CDF values |
|---|---|
| p1b_tb_rc / VIN | v1=0, v2=0.1, td=1n, tr=1p, tf=1p, pw=5n, per=10n |
| p1b_tb_step / VINP | v1=0.8, v2=1.2, td=1u, tr=20n, tf=20n, pw=2u, per=5u |

These correspond to Spectre val0, val1, delay, rise, fall, width, and period respectively. Original design stimulus values and netlist-review requirements are unchanged.

Local checks cover syntax parentheses/strings, the function-call inventory (which detects the actual v1 error), all 14 parameters of both sources, and rejection/correct-input regression for native-netlist review. **Cadence is unavailable locally, so these checks do not establish SKILL execution or simulation success.** Passive criteria and final performance still require actual-result review.

Property traversal references [the official Cadence forum property-reading example](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/15020/changing-cdf-property-display-value-via-skill); read-only mode and dbClose behavior reference [a Cadence engineer's IC616 example](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/30719/saving-designs-in-virtual-memory-to-disk/1338443).
