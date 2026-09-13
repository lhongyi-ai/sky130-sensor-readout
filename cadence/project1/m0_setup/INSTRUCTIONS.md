# project1 native single-device circuit starter package v0.1.0

This package provides M0 circuit generation and an entry point for manual ADE validation; it is not a complete M0–M5 design package. It creates only project1/tb_nmos_dc/schematic; if any same-name cell already exists, it stops without overwriting. Local structural and connection-geometry checks have been performed on the script; actual SKILL/PDK execution remains unverified. The first run may expose school model-name or Spectre-syntax incompatibilities; preserve actual errors.

## 1 Upload and generate (Linux terminal → CIW)

Upload project1_m0_setup_v0.1.0.zip to ~/cadence_skywater/.

```bash
cd ~/cadence_skywater
unzip -n project1_m0_setup_v0.1.0.zip
```

Enter in the already-running Cadence CIW:

```lisp
load("/home/compute/l.hongyi/cadence_skywater/project1_handoff/m0_setup_v0_1/create_tb.il")
```

Expected: P1_M0_TOPOLOGY_CREATED appears in CIW. Check schCheck diagnostics; this text alone does not establish that the circuit check passed. On error, do not rerun or delete existing cells; return the CIW error text. A partial circuit may already exist in memory or the library and must be diagnosed first.

From Tools → Library Manager, open project1 → tb_nmos_dc → schematic. Press f to fit the view. Expect one M0, two DC voltage sources VD/VG, and three ground symbols. Both M0 source and bulk connect to ground; VD positive connects to the drain and negative to ground; VG positive connects to the gate and negative to ground.

## 2 Set dimensions (schematic window)

M0 initially retains PDK default dimensions and does not yet meet the test specification. Select M0 and press q to open device properties.

In order, change Length/l to 0.5u, Number of fingers/fingers to 1, Multiplier/m to 1, and Finger width/fw to 5u; press Tab after each edit to activate process callbacks. If the interface only permits editing Width/w, set Width to 5u under the one-finger condition and confirm that fw also becomes 5u. Final w and fw should both be 5u for one finger. Do not edit hidden simW/simM or enter areas/perimeters manually. If field meanings or displayed units differ, return the property window rather than guessing units.

Click OK, then press q again to confirm dimensions persisted. The school process callbacks update areas/perimeters; these still require checks in the exported netlist. Direct database dimension writes do not automatically trigger all CDF callbacks, so this version retains this manual step.
Reference: [Cadence's official explanation of CDF callbacks](https://community.cadence.com/cadence_technology_forums/f/custom-ic-skill/36448/skill-command-to-create-the-cell-view/1348670).

Inspect VD and VG separately: DC voltage should be 0.9 and VGS. Run Check and Save. Expect no connectivity errors; preserve warnings verbatim.

## 3 Configure the first DC run (Launch → ADE L from the schematic; if only Explorer is available, use its test editor)

- Setup → Simulator/Directory/Host: simulator spectre. Use a new project-results directory for every run without overwriting the previous failure. In the Linux terminal, `mktemp -d ~/cadence_skywater/project1_handoff/m0_setup_v0_1/run_XXXXXXXX` can create a separate directory; enter its printed path as ADE's Project Directory.
- Variables → Copy From Cellview: set initial VGS to 0.
- Setup → Temperature: 27°C; if menu locations differ, verify actual temperature in environment/simulation options.
- Setup → Model Libraries: add the model candidate found in the report below, with lowercase tt as Section:

```text
/project/engineering/cadence21/CDK/sky130_release_0.0.3/models/sky130.lib.spice
```

Note: the report only confirms the file exists and declares tt; it has not established that school `nfet_01v8` resolves through this entry. Preserve and record automatically configured school model entries; do not delete them or add the same file twice. If a default model configuration already exists, return that window's contents for review first.

- Analyses → Choose → dc: choose Design Variable for Sweep Variable, variable VGS, Start=0, Stop=1.8, Sweep Type=Linear, step 0.01 V. If configured by point count, use 181 points including both endpoints.
- Outputs → To Be Plotted → Select On Schematic: click the M0 drain pin to select current, or select VD positive-terminal current. VD positive-terminal current is usually negative; the NMOS absorbed current is its negative. Do not misclassify this sign as an error.

## 4 Export and check the netlist before running

In ADE, choose Simulation → Netlist → Create, then Display. Menus may vary slightly by version.
Reference: [Cadence's official netlist-generation explanation](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/42929/spectre-monte-carlo-simulation-without-ade-xl-license).

Check and save the complete input.scs, including hierarchical sub-netlists if present:

1. M0 node order is D, G, S, B; the last two are ground, and drain/gate connect correctly to VD/VG.
2. Actual w=5u, l=0.5u, m=1 (equivalent scientific notation is acceptable), not the defaults 420n/150n. Derived ad/as/pd/ps must reflect the changed width rather than retain 420n default geometry.
3. VD=0.9, VG uses VGS, the DC sweep is 0→1.8 in 0.01 steps, and temperature is 27.
4. Model include path and section=tt; record the actual device model name. School CDF defaults to nfet_01v8; do not independently replace it with another model name.

If any item is unclear, return the netlist for review first. Click Run only when connectivity and dimension configuration are correct. On undefined model/subcircuit, include, or syntax errors, save the complete log; do not replace the device with an ideal transistor or modify the PDK.

Success criteria: Spectre terminates normally, 181 valid DC points, VDS constant at 0.9 V, gate voltage 0→1.8 V, current generally increasing with gate voltage, and no NaN/Inf. This validates the environment and single device, not OTA/ADC qualification.

## 5 Return results

Return a schematic screenshot, M0 property screenshot, actual exported input.scs and hierarchical sub-netlists, spectre.out log, and Id–VGS curve screenshot. If available, export CSV from the waveform window, preserving axis and current units, and retain the original PSF directory on Linux.

You can create a separate return directory on Linux, copy the exported files into it, compress it to ZIP through the file manager, and download it. Include only this test's files, not the PDK, licenses, or entire user directory. Return failures too, without overwriting their records.

## Current status

- Supplemental probe report: 20260911T194803Z_94d70a07; internal file hashes passed.
- Native circuit generation: awaiting Linux execution.
- Model candidate/tt: found; Spectre compatibility, device-name resolution, and licensing: not run.
- M0 dimensions/derived parameters/connectivity: awaiting property callbacks and exported-netlist review.
- M1–M5: not run.
