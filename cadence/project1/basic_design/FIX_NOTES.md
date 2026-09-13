# v1.0.4: M7 exceeds the single-finger width limit

The actual school callback explicitly reported that fw=72.2u exceeded the 50u maximum and was clamped to 50u. The original generator correctly stopped; accepting a narrowed M7 would change the design, so the dimension check must not be skipped.

This version explicitly splits M7 into two independent parallel PMOS devices: M7A and M7B, each W=fw=36.1 µm, L=0.8 µm, fingers=1, and m=1, retaining a total width of 72.2 µm. Each instance's D/G/S/B connects to VOUT/VBP/VDD/VDD respectively. No additional multiplier of 2 is set, to avoid double-counting. Existing parallel units of M3/M4 remain unchanged; the OTA contains 13 actual MOS instances.

PDK callbacks calculate diffusion geometry separately for the two instances. Under the currently checked single-finger geometry relationship, total area stays equal, but the summed perimeter of each diffusion terminal is 0.53 µm larger than for one instance. This split must not be described as fully parasitically equivalent; its impact requires later simulation comparison.

Netlist audits check that both instances exist and have correct dimensions and bulk connections. Operating points are exported separately, ids/gm/gds are aggregated for M7, and saturation margins remain checked per device. Missing M7B, an incorrect multiplier, or missing results cause failure. All generated target MOS single-finger widths are now no greater than 50 µm; this limit comes from the school error and does not validate other process rules.

The new OTA is named `p1b_ota_legacy_r4`, with testbench references updated accordingly. Older versions and diagnostic cells are retained.

## Instructions

Upload `project1_basic_design_v1.0.4.zip` to `~/cadence_skywater/` and run in the Linux terminal:

```bash
cd ~/cadence_skywater
unzip -n project1_basic_design_v1.0.4.zip
cd project1_handoff/basic_design_v1_0_4
python3 run.py prepare
```

Paste the entire printed `p1bRoot=... load(...)` line into Cadence CIW. After `P1B_ALL_CREATED` appears, run from the new directory:

```bash
python3 run.py run --group passives
```

If an error occurs, return the CIW contents and the new directory's cdf_values.tsv and create_status.txt. Do not delete old cells or ignore parameter clamping. Local checks of this package cannot replace actual school execution.
