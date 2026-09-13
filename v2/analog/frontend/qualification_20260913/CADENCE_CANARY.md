# Minimal university Cadence migration checks

This directory supplies a circuit and numerical baseline already run locally, **without a new launcher or bulk schematic-generation package that has not been qualified at the university**. University operations continue using the existing working `basic_design_v1_0_4 + 1.0.4p3` environment. Do not rerun the old failed initialization, guess PATH, or overwrite existing project1 cells.

Recorded environment boundaries:

| Item | Actual local use | Existing university record |
|---|---|---|
| Solver | ngspice 47 | Spectre 21.1 |
| Solver path | `/foss/tools/ngspice/bin/ngspice` | `/project/engineering/cadence21/spectre/tools/bin/spectre` |
| Native design tool | Not used | Virtuoso IC6.1.8 |
| Model entry point | `/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice` | `/project/engineering/cadence21/CDK/sky130_release_0.0.3/models/sky130.lib.spice` |
| OCEAN | Not used | `/project/engineering/cadence21/ic/tools/dfII/bin/ocean` |
| Working directory | `/repo/v2/analog/frontend/qualification_20260913` | `/home/compute/l.hongyi/cadence_skywater` |

The university OCEAN, Spectre, model, and working-directory entries each come from the latest site report, `cadence/project1/reports/basic_20260913T023544Z_5cc09eef/received/site.json`. Its working directory is the report's `workdir`, not a subdirectory of the upload package. The actual OCEAN path includes `tools/dfII/bin` and supersedes the old path in earlier instructions. This round did not rerun the university environment. Similar model paths do not establish equivalent model versions, CDF parameters, or passive dimensions. The main task should reference the currently verified university launch script rather than deriving a path from local `/foss`.

## Interfaces and dependencies to check first

The main `sky130_v2_switchable_pga` entry point has the fixed pin order:

`VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1`

Codes are interpreted as `(SEL1, SEL0)`: 00=G1, 01=G4, 10=G16, and 11 is reserved with feedback disconnected. The first test fixes G4: SEL0=1.8 V, SEL1=0. Do not substitute the old OTA pin order or use the sample_driver default of 1.8 kΩ. The measured assembly has external 1.5 kΩ and 4 pF per side after the PGA.

Before running the minimal test, verify the following in the netlist exported natively at the university:

- Actual cells/models, four-terminal ordering, and body connections for standard NMOS/PMOS and the LVT MOS devices needed by sampling switches; W/L, finger, and m multiplication semantics, avoiding double multiplication.
- Legal CDF fields and model mappings for 0.35 µm-wide and 0.69 µm-wide high-resistance polysilicon variants. In particular, the 1.2 kΩ Miller zero-setting resistor uses a 0.69 µm device with L≈0.855177 µm; 1.5 kΩ isolation uses a 0.35 µm device with L≈0.542800 µm. The old default-resistor M0 pass does not qualify these specific dimensions.
- MIM W/L and parallel-cell semantics: 4 pF filtering, 8 pF Miller capacitance, and a real 4096-cell sampling array per side. COUNT must neither be ignored as a comment nor multiplied again.
- Actual connection of `VCM` to the `XCMR` gate; NCM/CMS/CMG sensing and regulation connections; cross-feedback on both sides and all six switched branches.
- TT model section, 1.8 V, 27°C, 350 Ω per input, and sampling switches fixed on. Ideal test stimuli are acceptable, but the internal amplifier, R/C, and switches must not be replaced by behavioral blocks.

## Completed small local baseline

Local results: `runs/20260913T062412790986Z_noise_g4_acquire/`. `bench.spice` is the actually executed netlist; `candidate_06.spice`, `sampling_switch.spice`, and `adc_blocks.spice` are dependency snapshots. `op.dat`, `ac.dat`, `dc.dat`, and logs are complete. The directory retains the caller-generated `noise` name, but its actual status is `LOCAL_G4_CANARY_COMPLETE`; no noise analysis ran.

The test performs only a G4 operating point, 1 kHz AC, and three DC points. Test sources set VINP=0.9+SW/8 and VINN=0.9−SW/8; SW takes −0.32/0/+0.32 V, so the actual differential sensor input is SW/4.

| Item | Measured local baseline |
|---|---:|
| Zero-input output common mode | 0.886288513 V |
| At 1 kHz, differential output / SW | 1.009873411 |
| At 1 kHz, differential output / differential sensor input | 4.039493645 |
| Differential output at SW=−0.32 V | −0.323151835 V |
| Differential output at SW=0 | Approximately −1.79 pV |
| Differential output at SW=+0.32 V | +0.323151835 V |

These values help detect differences in sign, multiplication, units, ports, and models. No new percentage tolerance for agreement with ngspice is imposed as a final qualification threshold. The first university step requires only the native exported netlist and actual results of this minimal test. If they differ, compare models/CDF/assembly and output reference points before deciding whether to continue with three-gain stability or PVT. The university minimal test has not run, and native schematic migration remains incomplete.
