# Pulse-source parameter repair v1

In this report, OCEAN generated the netlist normally, and the netlister reported 0 errors / 0 warnings. However, RC `VIN` was exported as `type=pulse val0=0 val1=0`, lacking the expected levels and timing; strict parameter checking intercepted it before simulation.

The basic-package generator had written Spectre output parameter names directly into `analogLib/vpulse` instances. The correct mapping is:

| Schematic CDF property | Spectre output parameter | RC input VIN | OTA step input VINP |
|---|---|---:|---:|
| v1 | val0 | 0 | 0.8 |
| v2 | val1 | 0.1 | 1.2 |
| td | delay | 1n | 1u |
| tr | rise | 1p | 20n |
| tf | fall | 1p | 20n |
| pw | width | 5n | 2u |
| per | period | 10n | 5u |

The first school probe report already recorded these seven analogLib/vsource names; [Cadence's official vpulse-property explanation](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/18773/may-i-use-some-skill-function-to-edit-a-component-cdf-in-my-current-design) also explicitly uses `v1`. The script still checks that all seven parameters exist in the actual school `vpulse` CDF before modifying anything; missing fields or conflicting values stop execution.

## Keep the MIM command on one line

MIM did not run this time: the launcher was executed alone without arguments, and `run --job ...` was then treated as another Linux command.

Copy this complete line into the Linux terminal; do not press Enter after `.sh`:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job mim_ac --retry
```

## Repair the two generated pulse sources

1. Upload `p1_fix_pulses_v1.il` to `/home/compute/l.hongyi/cadence_skywater/`. This is a single SKILL file requiring no extraction.
2. If schematic windows for `p1b_tb_rc` or `p1b_tb_step` are open, save and close those two editing windows first. Keep the main Virtuoso CIW window open.
3. Run the following line in the **bottom input field of Cadence CIW**, not in the Linux terminal:

```lisp
load("/home/compute/l.hongyi/cadence_skywater/p1_fix_pulses_v1.il")
```

Expect two `P1_PULSE_SOURCE_SAVED` messages, followed by:

```text
P1_PULSE_REPAIR_DONE: 2 sources saved. Next rerun native audits; NOT A SIMULATION PASS.
```

The script only changes the seven correct CDF properties of `project1/p1b_tb_rc/VIN` and `project1/p1b_tb_step/VINP`. At both locations, it first checks package ownership markers, vpulse master, old stimulus values, and actual CDF fields. It retains old properties and before/after readback logs, does not touch MOS devices, process R/C, wiring, or library definitions, does not execute MOS/PAS callbacks, and does not rebuild circuits.

Completed readback, checking, and saving do not establish a simulation pass; subsequent native-netlist audits still validate every level and timing parameter. If the script errors, return the complete CIW text and `basic_design_v1_0_4/runs/p1_pulse_repair_v1.log`; do not rerun or delete cells yet.

## Rerun RC and return results

After the repair-complete marker appears, return to the **Linux terminal** and run:

```bash
bash ~/cadence_skywater/p1_school_run_v1.sh run --job rc_step --retry
bash ~/cadence_skywater/p1_school_run_v1.sh collect
```

Return the new report ZIP. The repair log is under runs/ and is automatically included. Expect VIN in the new native RC netlist to contain `val0=0 val1=0.1 delay=1n rise=1p fall=1p width=5n period=10n`; field order may differ. The original incorrect netlist and failure status remain unchanged.

Model review has already shown that the old resistor CDF threshold is inapplicable; the original RC time-constant gate also still requires confirmation against actual MIM and process parasitics. This file does not relax those gates or declare incomplete passive or OTA simulations passed.

Local validation includes SKILL parenthesis/string checks, agreement of both pulse sources and all 14 values with the frozen design, confirmation that the reported incorrect netlist is rejected, and checker regression with correct level/timing netlists. Actual SKILL execution still awaits school Cadence validation.
