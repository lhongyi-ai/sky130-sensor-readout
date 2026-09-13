# Accessing the analog frontend

Here, frontend means the **analog frontend circuit** connecting the pressure sensor to the SAR ADC on the chip, not a website frontend. It therefore has no URL, login page, or interactive Web UI.

The current authoritative circuit is [`dynamic_20260911/candidate_06.spice`](dynamic_20260911/candidate_06.spice). It uses SKY130 devices, provides gains of 1, 4, and 16, and drives a real SAR sampling load of 4096 MIM cells per side. It passes three-gain static and dynamic checks under nominal conditions, but formal multiloop stability, 45-PVT coverage, noise, and the physical frontend layout remain incomplete. It therefore cannot be called a qualified final frontend.

## Option 1: view the images without installing software

Open [`xschem_20260911/renders`](xschem_20260911/renders), then view:

1. [`frontend_top.png`](xschem_20260911/renders/frontend_top.png): the complete signal chain from the differential sensor through the PGA and RC isolation to the SAR sampler.
2. [`switchable_pga.png`](xschem_20260911/renders/switchable_pga.png): how feedback resistors and switches select gains of 1, 4, and 16.
3. [`rd_fdota.png`](xschem_20260911/renders/rd_fdota.png): the two-stage fully differential OTA's transistors, biasing, compensation, and two common-mode control loops.

All three images are 2400×1600 and have individually been checked for spacing between text, devices, wires, and borders. Matching SVG files are also provided, with text and lines that remain sharp when enlarged.

## Option 2: open and zoom in Xschem

Xschem is an open-source schematic tool. After installation, enter:

`/Users/stanley/Documents/ChatGPT/Analog Circuit Project/sky130-two-stage-ota/v2/analog/frontend/xschem_20260911`

Then open the pages separately:

```sh
xschem frontend_top.sch
xschem sky130_v2_switchable_pga.sch
xschem rd_fdota.sch
```

The project container `sky130-v2-resume-20260910` already has Xschem 3.4.8RC and the SKY130 environment configured. To re-export images only, enter `/repo/v2/analog/frontend/xschem_20260911` inside the container and run:

```sh
./render_headless.sh
```

These `.sch` files are readable hierarchical review drawings, not native Cadence Virtuoso schematics. Do not regenerate a netlist from them to replace the authoritative SPICE circuit.

## Option 3: inspect the actual simulated circuit

Open [`dynamic_20260911/candidate_06.spice`](dynamic_20260911/candidate_06.spice). Key hierarchy:

| Approximate line | Subcircuit | Function |
|---:|---|---|
| 63 | `rd_bias` | On-chip bias and startup |
| 73 | `rd_fdota` | Two-stage fully differential OTA, compensation, and common-mode control |
| 125 | `rd_fbbranch` | One real resistor-plus-transmission-gate feedback branch |
| 132 | `sky130_v2_switchable_pga` | Gain 1/4/16 selection and cross-feedback |
| 156 | `sky130_v2_switchable_sample_driver` | Output isolation and ADC sampling drive |

In the netlist, `X...` denotes a device or subcircuit instance; MOS `W` and `L` specify width and length. The transistors, resistors, and MIM capacitors reference physically implementable SKY130 PDK devices, not ideal op-amp blocks.

## Evidence and current limits

- Latest conclusion: [`dynamic_20260911/qualification.json`](dynamic_20260911/qualification.json)
- Frontend experiment description: [`dynamic_20260911/README.md`](dynamic_20260911/README.md)
- Xschem drawing description: [`xschem_20260911/README.md`](xschem_20260911/README.md)
- Drawing integrity and source hashes: [`xschem_20260911/artifact_manifest.json`](xschem_20260911/artifact_manifest.json)

The precise status is: **the non-Cadence frontend circuit, readable schematics, and nominal three-gain dynamic verification are accessible. Native Cadence schematics, formal multiloop stability, 45-PVT coverage, noise, frontend layout, DRC/LVS/PEX, and post-layout simulation remain incomplete.**
