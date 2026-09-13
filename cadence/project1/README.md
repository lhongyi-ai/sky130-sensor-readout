# project1: Cadence migration and validation

## Latest validation status: reports dated 2026-09-13 UTC

The current school execution version is `basic_design_v1_0_4` with runtime patch **1.0.4p3**. **All 87 predefined entry points have actual execution evidence; full acceptance against the original specification remains incomplete.** All 32 latest extra tests executed and exported successfully; their original labels are **13 PASS, 14 FAIL, and 5 REVIEW_REQUIRED**. Phase margins at 10/20 pF are 53.77°/40.55°, below the legacy 55° threshold. The basic package screens ICMR at ≥50 dB; review against the original requirement of no more than 3 dB degradation from nominal and the other original criteria passes only five sampled points from 0.8 to 1.2 V. The screened 0.8–1.4 V range must not be reported as fully qualified. Static-noise units have been verified: input noise at 1 kHz is 401.150 nV/√Hz, with 52.2998 µV RMS integrated over 10 Hz–1 MHz; the original specification requires reporting this quantity only.

Latest evidence: [extra-test review and next steps](reports/basic_20260913T062632Z_d7dc1ae6/extra_characterization_review.md), [complete review data](reports/basic_20260913T062632Z_d7dc1ae6/review.json), and [results plot](reports/basic_20260913T062632Z_d7dc1ae6/extra_characterization.png). The latest report ZIP SHA256 is `413e1edf9477d189f043045c2c49c17ef7900432de9b4e5962b545ee78822c27`.

The native legacy OTA passed all four nominal tests. Of 52 tests at 13 PVT points, 49 passed; P06_step, P07_step, and P13_step still fail the 1% settling requirement. The steady follower error exceeds ±4 mV; the frozen ngspice waveforms have the same issue, and the historical overall PASS did not include settling time. See the [PVT review](reports/basic_20260913T023544Z_5cc09eef/pvt_review_and_next_steps.md). Original reports and failures remain unchanged.

The user currently does not need to rerun extra tests or PVT, or rebuild the circuit. The next local supplemental package (not yet generated) must add CMRR/PSRR at the same operating point, the original fine ICMR sweep and criteria, and the original output-swing test with fixed common mode and sweeps in both directions. TT review of the default process-passive dimensions passed; statistical and physical-flow M0 capabilities remain incompletely qualified. The new frontend, ADC, layout, and full-system performance have not completed Cadence acceptance.

**The following sections are historical workflow and delivery records. Descriptions such as “not yet run” and “current latest” retain their original context; the current status is established by the section above and its linked actual evidence.**

Cadence work resumed on 2026-09-11, targeting the user-created `project1` library. The user-confirmed workflow is **prepare locally → user uploads to Linux → user executes → user returns results**. Automatic remote-desktop operation is no longer used.

## Current deliveries and next steps

- First package: [project1_probe_v1.0.0.zip](releases/project1_probe_v1.0.0.zip), for environment metadata checks only.
- User instructions: [start here](probe/START_HERE.md), with upload, extraction, terminal checks, CIW checks, and return steps.
- Local validation: [local_validation.json](releases/local_validation.json). Eight behavioral tests, Python/Shell checks, and static SKILL structure checks passed. Actual SKILL execution, device semantics, licensing, and circuit simulation remain unverified.
- The first report was received and its internal hashes agree; IC6.1.8, Spectre 21.1, and the project1 technology association were confirmed. The first version missed Spectre CDF and the top-level model entry; the supplemental probe is releases/project1_probe_v1.1.0.zip. Its report was received, identifying the sky130.lib.spice / tt model candidate; device names and Spectre compatibility still require actual tests. The next package is releases/project1_m0_setup_v0.1.0.zip: generate native topology first, then set dimensions, export the netlist, and run DC following m0_setup/INSTRUCTIONS.md.
- Second-package status: **NMOS_DC_SMOKE_PASSED_REMAINING_M0_PENDING**. Adapt native schematic/symbol, Spectre/OCEAN, mixed-signal, and physical verification after receiving reports; do not guess school PDK parameters or tool capabilities.
- M0–M5 have not run in Cadence. Completing these file packages does not complete chip or simulation acceptance.

## Continuation after receiving a report

1. Verify the report ZIP hash and run ID; distinguish the terminal PATH from the Virtuoso PATH, and check `project1` and its associated technology.
2. Establish cell/port/CDF mappings for standard/low-threshold MOS, MIM, resistors, and analog test sources. If only default values are available for legal dimensions and multiplier semantics, validate them using actual minimal M0 circuits.
3. Record “path found” separately from “actual execution passed” for `sky130_fd_sc_hd` standard cells, mixed-signal operation, true dynamic noise, and DRC/LVS/PEX; do not merge these into a single environment PASS.
4. Freeze the selected same-version design sources and evidence before creating the second package. Use the existing baseline for the legacy OTA. For the new frontend, use the candidate and hashes specified by `v2/analog/frontend/dynamic_20260911/qualification.json` as the baseline for this plan; later changes must not silently replace them. Check dependencies individually for the ADC, digital macro, sampling switches, and routed CDAC.
5. The user executes M0/M1 and returns results first, followed by frontend/ADC validation and physical closure. Formal multi-loop stability of the complete frontend remains open; an existing open-source CDAC physical PASS does not establish Cadence or full-ADC PASS.

## Current evidence

- Virtuoso 6.1.8 and Library Manager have been observed on the school remote desktop.
- The CIW log confirms successful association of `project1` with `sky130_fd_pr_main`.
- The school PDK currently references `/project/engineering/cadence21/CDK/sky130_release_0.0.3/cds.lib`.
- In the terminal `cds.lib`, project1 is at `/home/compute/l.hongyi/cadence_skywater/project1`.
- Spectre models, licensing, simulation execution, and results have not yet been verified. No cell has yet been created in project1.
- The remote connection once showed a blank screen; after reloading, noVNC reported `New connection has been rejected with reason: Authentication failed`. This is historical connection evidence. The user has chosen to operate, upload, and return results personally; remote control is no longer attempted.

## Validation sequence

1. `tb_nmos_dc`: standard-threshold 1.8 V NMOS, W=5 µm and L=0.5 µm; source and bulk grounded, VDS=0.9 V, VGS swept from 0 to 1.8 V in 10 mV steps, TT, 27°C. Record the model path and section, device parameters and units, actual Spectre version, run log, Id–VGS curve, and operating point. Original ngspice single-device data are in `reference/nfet_characterization_l0p5.tsv`.
2. Create a native schematic and symbol for the original two-stage OTA, checking instances, dimensions, port order, bulk connections, and compensation network. M3 and M4 each consist of two explicit parallel units; multiplicity must neither be omitted nor double-counted.
3. At TT/1.8 V/27°C, VCM=0.9 V, IREF=10 µA, and 5 pF ∥ 100 kΩ to VSS, run DC operating-point, gain, loop-stability, and transient tests and compare with frozen ngspice data. The original pulse is 0.8→1.2 V, delay 1 µs, rise/fall 20 ns, width 2 µs, and period 5 µs. State measurement-method differences between simulator STB and the legacy loop-break method.
4. After environment validation and the OTA comparison pass, migrate the same-version frontend and ADC candidates. After actual candidate performance validation, advance full layout, DRC, LVS, parasitic extraction, and post-layout simulation according to project gates.

## Distinguishing reference data from results

`reference/` contains byte-for-byte copies of existing local ngspice evidence, not new Cadence results.
`reference_manifest.json` records original paths, SHA-256 hashes, nominal reference values, and single-device conditions; `cadence_measurements` is null, indicating that no run has occurred.

The Day 4 original netlist port order is `VDD VSS VINP VINN VOUT VBP`; the presentation core netlist uses `VINP VINN VOUT VDD VSS IREF`. Migration must explicitly select an interface; the two must not be interchanged.

Model equivalence between the school PDK and original ngspice PDK is unconfirmed. Known legacy frontend and ADC failures remain recorded; successful Cadence connectivity cannot substitute for circuit acceptance.

## 2026-09-11: first measured NMOS DC run

The user-returned Spectre 21.1 log ended normally: 0 errors, 1 checklimitdest=psf deprecation warning, and complete dc-0 through dc-180 records covering 181 operating points at 27°C, VGS 0→1.8 V, with maximum drain current 1.129 mA. Evidence: reports/m0_nmos_20260911_152640/qualification.json. Model loading, solving, and licensing passed for this run; a numerical audit of raw waveforms is still incomplete. Only the NMOS DC smoke test passed; full M0 and M1–M5 remain unaccepted. Earlier “not run” descriptions above remain historical; this section establishes the latest NMOS status.

## PMOS delivery

releases/project1_pmos_dc_v0.1.0.zip has been generated: independent tb_pmos_dc, source/bulk at 1.8 V, drain at 0.9 V, and gate at 1.8-VSG. After setting 5u/0.5u/one finger/multiplier 1 in the CDF form, the user exports the netlist and runs following m0_pmos/INSTRUCTIONS.md. Local geometry, static structure, and package-hash checks passed; the actual PMOS run has not occurred.

## 2026-09-11: measured PMOS DC run

reports/m0_pmos_20260911_162236/qualification.json: Spectre ended normally with 0 errors, 1 checklimitdest deprecation warning, and 181 operating points. The screenshot shows /M0/D ending near -211 µA; the log's maximum current is I(VS:p)=210.8 µA and must not be treated as a directly exported drain-current value. Basic NMOS and PMOS DC flows have both run successfully. Numerical raw-waveform audits, passive-device tests, statistical qualification, and physical qualification remain pending.

## 2026-09-11: complete basic-design package

`releases/project1_basic_design_v1.0.0.zip`: one upload generates 13 native cells and the legacy OTA symbol and provides 87 serial jobs. These include process resistor/MIM/RC tests, legacy OTA operating-point/AC/loop/step tests, the original 13-point PVT sweep, and supplemental tests. Entry points and full instructions are in `basic_design/START_HERE.md`.

The original OTA retains ideal 2 kΩ/3 pF compensation and an external 10 µA reference; its results must not be mixed with results using process-passive replacements. Netlists are checked after native-schematic export; each attempt is stored independently, preserving prior failures and missing results. The 52 original raw PVT evidence files are frozen in the package. Local behavioral tests and replay of the original 13-point loop/transient measurements passed; see `basic_design/local_validation.json`. These are analysis and package checks. **This package's SKILL/OCEAN code and new circuits have not yet run on school Linux**; actual behavior of school Python 3.6.8, CDF callbacks, OCEAN paths, and output signal names requires on-site validation. Delivery does not mark full M0/M1 complete.

## Basic package v1.0.1: PAS initialization revision (latest)

The user's actual v1.0.0 run reported `PasCdfCommitValue: failed to find valid initialization data!` in the M8 fingers callback, interrupting generation before simulation. v1.0.1 calls the instance CDF formInitProc before parameter callbacks and logs initialization. The new OTA is `p1b_ota_legacy_r1`, and testbenches reference it; the interrupted cell is preserved without deletion or overwrite. The new upload is `releases/project1_basic_design_v1.0.1.zip`, using the independent directory `project1_handoff/basic_design_v1_0_1`. Thirteen local tests, script lexical checks, and extracted-dependency checks passed; the revised school Cadence execution still awaits user validation. See `basic_design/FIX_NOTES.md` for instructions.

## Basic package v1.0.2: type-check revision (current latest)

The actual v1.0.1 run reported `eval: undefined function - flonump`, interrupting CDF parameter writeback. This shows execution passed the initialization/callback code but does not establish device or overall-generation success. v1.0.2 uses `type()` checks for string/fixnum/flonum and runs a five-value-category SKILL type self-test before creating any cell. The new OTA is `p1b_ota_legacy_r2`; the two prior interrupted versions remain. Upload: `releases/project1_basic_design_v1.0.2.zip`; independent directory: `project1_handoff/basic_design_v1_0_2`. Fourteen local tests and extraction checks passed; on-site execution remains unverified. Historical ZIP files are retained without overwriting delivered versions.

## Basic package v1.0.3: adapted dimensions frozen from the M8 diagnostic (current latest)

v1.0.2 stopped at the strict M8/w check; the user subsequently saw an empty schematic. Independent diagnostic results are archived in `reports/m8_cdf_diagnostic_20260912`: PasCdfFormInit succeeded; the fw callback changed w/fw from 7.22005u to 7.22u; L=.8u and fingers=m=1 were correct; diffusion geometry updated; diagnosis and saving completed. This validates only that PMOS CDF behavior, not simulation, and is insufficient to infer the full PDK dimension grid.

v1.0.3 explicitly selects migration widths at 0.01 µm precision (per-device mapping: `basic_design/device_size_mapping.md`), retaining original sources and historical evidence. The maximum relative width change is <0.05%; performance impact still requires actual simulation. Dimension-check tolerance is not relaxed. The new OTA is `p1b_ota_legacy_r3`; per-instance state is saved and requested/actual values are logged before dimension checks. Fifteen local tests and packaging checks passed. New package: `releases/project1_basic_design_v1.0.3.zip`; directory: `project1_handoff/basic_design_v1_0_3`. School execution by the user is pending.

## Basic package v1.0.4: parallel M7 split (current latest)

The user's actual v1.0.3 run reported that M7's 72.2u single-finger width exceeded the school 50u limit and was clamped; strict checking stopped. The original error is archived in `reports/m7_width_limit_20260912`. v1.0.4 splits M7 into M7A/M7B, each 36.1u/.8u, one finger, m=1, with corresponding D/G/S/B terminals on the same nets and total width 72.2u. The complete OTA has 13 MOS devices. Operating points are read individually and ids/gm/gds are aggregated by group; saturation margins remain checked per device. Diffusion parasitics are not claimed to be fully equivalent to a single instance and require actual simulation comparison. Seventeen local tests, lexical checks of all 87 entries, and extracted-dependency checks passed. New OTA: `p1b_ota_legacy_r4`; upload: `releases/project1_basic_design_v1.0.4.zip`; directory: `project1_handoff/basic_design_v1_0_4`. On-site execution is pending. Old cells and release packages remain preserved.
