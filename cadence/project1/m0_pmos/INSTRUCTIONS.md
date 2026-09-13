# PMOS DC test package v0.1.0

Creates independent project1/tb_pmos_dc/schematic; stops if any cell with that name already exists. The NMOS circuit is retained. This package generates topology only; set PDK dimensions through the property window. The original NMOS generation method has run in the user's environment; this PMOS circuit still awaits Linux execution.

## 1 Upload and generate

Upload project1_pmos_dc_v0.1.0.zip to ~/cadence_skywater/ and run in the Linux terminal:

```bash
cd ~/cadence_skywater
unzip -n project1_pmos_dc_v0.1.0.zip
```

Run in Cadence CIW:

```lisp
load("/home/compute/l.hongyi/cadence_skywater/project1_handoff/m0_pmos_v0_1/create_tb_pmos.il")
```

Expect P1_PMOS_TOPOLOGY_CREATED; inspect CIW diagnostics. Completed generation does not establish circuit-check or simulation success. Preserve errors verbatim; do not repeatedly delete and rebuild a same-name cell.

In Library Manager, open project1 → tb_pmos_dc → schematic and press f to fit all.

## 2 Check the circuit and set dimensions

The PMOS source and bulk connect to VS=1.8 V; the drain connects to VD=0.9 V; the gate connects to VG=1.8-VSG.
Thus VSD=0.9 V; as VSG rises from 0 to 1.8 V, the actual gate voltage falls from 1.8 V to 0 V. The variable is VSG, not the NMOS test's VGS. All three supply negative terminals are grounded.

M0 should be sky130_fd_pr_main/pfet_01v8 (standard threshold). Select M0, press q, and edit these properties in order: l=0.5u, fingers=1, m=1, fw=5u (use w if only w is editable). Press Tab after each edit and confirm that final w and fw are both 5u. Do not fill simW, simM, areas, or perimeters manually; let PDK callbacks update them. Click OK and inspect the parameters again.

Click the green Check and Save toolbar checkmark and confirm there are no connectivity errors. Do not rerun the generator.

## 3 Open and configure ADE L

From the current PMOS schematic, choose Launch → ADE L. Confirm the title includes tb_pmos_dc; do not change configuration in the old NMOS ADE window.

- Variables → Copy From Cellview: VSG=0.
- Temperature: 27°C.
- Setup → Model Libraries: retain the school-selected sky130.lib.spice, section=tt, as in the successful NMOS test; do not add it twice.
- Analyses → Choose: dc, Design Variable=VSG, Start=0, Stop=1.8, Linear, Step Size=0.01, Enabled checked.
- Outputs → To Be Plotted → Select on Design: click M0's bottom drain pin (the PMOS drain is below in this circuit), then press Esc. The signal should be /M0/D; a net name alone means voltage was selected.

## 4 Export and check the netlist, then run

Choose Simulation → Netlist → Create, then Display. Return the netlist for review first; successful generation alone does not establish acceptance.

Expected electrical relationships (node names may differ; this is a review illustration, not a handwritten replacement simulation netlist):

```text
parameters VSG=0
M0 (D G S S) pfet_01v8 w=5u l=500n ... m=1
VS (S 0) vsource dc=1.8
VD (D 0) vsource dc=0.9
VG (G 0) vsource dc=1.8-VSG
```

Confirm actual D G S B terminal order, common source/bulk node, w/l/m, derived geometry, tt, 27°C, and the 181-point sweep. Equivalent dimension expressions are acceptable.

After review, click the green Run button. Under the convention that current entering a terminal is positive, /M0/D should be negative during normal PMOS conduction. Its magnitude increases with VSG; it need not equal the NMOS value of 1.129 mA. Negative current alone is not a failure.

## 5 Save and return

Choose Session → Save State and name it pmos_dc_tt_first. Preserve PSF data in the run directory and return this run's netlist, curve screenshot, and spectre.out. If the NMOS environment's default directory convention is retained, the log is usually ~/simulation/tb_pmos_dc/spectre/schematic/psf/spectre.out; use the actual run path.

Pass criteria: normal termination, no unexplained model/convergence errors, 181 operating points, correct dimensions and connections, and reasonable current polarity and trend. Passing this minimal PMOS DC test does not qualify mismatch, noise, PVT, full M0, or the OTA.
