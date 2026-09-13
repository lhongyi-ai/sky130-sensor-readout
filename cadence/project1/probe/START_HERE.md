# project1 supplemental probe v1.1.0

The first report has been received. That version omitted Spectre CDF mapping, and numerous device files exhausted the model scan; this version corrects both issues. They were not user-operation errors.

This package only reads environment, CDF, existing symbols, and model/rule filenames and structural metadata. It does not create or modify circuits, execute PCell callbacks, install software, run simulations, or package the PDK, rule bodies, or licenses.

## 1 Upload and extract (Linux terminal)

Upload project1_probe_v1.1.0.zip to ~/cadence_skywater/ and run:

```bash
cd ~/cadence_skywater
unzip -n project1_probe_v1.1.0.zip
cd project1_handoff/probe_v1_1
bash run.sh probe
```

This directory is separate from the project1 library and first probe; do not extract into the OpenAccess library database.

## 2 Run in the already-open Virtuoso session (CIW)

The terminal prints this run's specific `load("…/load_probe.il")` command. Copy the entire line into the input field at the bottom of CIW and press Enter. Do not reuse the previous command.

CIW is the Command Interpreter Window showing startup information and logs, usually with File, Tools, Options, and Help menus at the top. Its input field is below the log area; neither the Library Manager library list nor the Linux terminal is CIW.

Success marker: `PROJECT1_PROBE_COMPLETE`. If an error occurs, preserve its text and still perform the next step to return a partial report.

## 3 Package and return (original Linux terminal)

```bash
cd ~/cadence_skywater/project1_handoff/probe_v1_1
bash run.sh collect
```

Download the `project1_report_*.zip` printed by the terminal and return it to this task. Do not resend the probe package.

## How to confirm the two items

- Device mapping: SPECTRE_CDF in the report provides model/component names, termOrder, instParameters, netlistProcedure, and propMapping; CDF_PARAMETER provides definitions including w/fw/l/fingers/m/simW/simM; SYMBOL_TERMINAL provides actual terminals. These inform generator adaptation but cannot independently establish callback behavior or simulated dimensions.
- Model entry: cadence_pdk_index.json and linux_report.json record top-level model candidates and section names. A tt field's existence does not establish model usability; Codex must still check the target-device/entry relationship.
- Final validation: generate an NMOS testbench with W=5 µm, L=0.5 µm, fingers=1, and m=1; inspect D/G/S/B, width/length, multiplier, and model include/section in the Cadence-exported netlist, then actually run Spectre DC. Licensing and model usability are established by this run's result.

Local checks can validate script structure and reporting logic; SKILL execution and school PDK behavior still require Linux-side validation. If the supplemental probe still lacks information, return the missing status rather than guessing model paths.
