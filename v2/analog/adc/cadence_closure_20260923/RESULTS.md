# Run results: two-frame functionality and reset pass; numerical qualification remains open

## September 24 continuation: actual LinuxLab execution

The existing SSH connection was used to run school Spectre/Xcelium and Cadence/PVS. Inputs were frozen locally and returned evidence was analyzed. Earlier versions, failures and the original PDK were preserved; no manual upload was required.

| Independent control | Verified result | Conclusion |
| --- | --- | --- |
| Single transistor: matched slopes, fixed gate, ten-times-slower stimulus and finite source impedance, each at two precision settings | Eight actual runs completed with zero errors and zero warnings. Internal body-node and terminal-current sensitivity remained; model hashes were unchanged. | The original full-ADC warning was not reproduced. A model defect is not established. |
| Original ADC, changing only large-capacitor numerical representation through cthresh | Complete 0–4.1 µs difference: 854.441 µV | FAIL |
| Original ADC, traponly / adaptive trap | Differences: 344.021 / 344.418 µV; ringing and integration warnings retained | FAIL; not adopted as a repair |
| Original VAMS reference, tightening only LTE | Strict run timed out at 4.06328 µs before reaching 4.1 µs | A low difference over a partial interval cannot qualify the run. |
| Reduced 654-device circuit retaining actual phase generation and switch loading | Strict run skipped the input edge; warnings named different devices | The original same-node warning was not reproduced; this cannot replace ADC qualification. |
| Reduced circuit with a half-sine input edge | Edge skipping disappeared; four body-node LTE warnings remained and the difference was 1.128 mV | Stimulus shape matters, but this is not a complete repair. |
| Original ADC with equivalent native reference R/C | Strict Newton rejections decreased from 218 to 11, LTE ignores from 5 to 0; difference remained 854.569 µV | Solver behavior improved; waveform comparison failed. Equivalence applies to deterministic transient behavior; noise requires separate accounting. |
| Native reference R/C with further LTE tightening | Complete short-window difference decreased to 182.974 µV; strict run still had 23 LTE ignores and 4 relaxations | A 78.6% reduction, still above 9.765625 µV; subsequent finer runs did not finish the short window. |

Each peak uses its stated complete time domain and the same absolute time. Edges were retained and traces were not phase-aligned. Results from different reduced circuits or stimuli are not presented as precision improvements in the original ADC.

Evidence: [single-transistor controls](numerics/mode_boundary_matrix_review_v1/README.md), [reduced circuit with actual loading](numerics/closed_phase_load_review_v1/README.md), [smooth edge control](numerics/closed_phase_load_halfsine_review_v1/README.md), [native reference R/C](integration/native_ref_cthresh_4p1us_review_r1/README.md), and [tighter LTE](integration/native_ref_lte1_4p1us_review_r1/README.md). Public BSIM4 references support investigation of derivatives near zero VDS, but no confirmed applicable repair was found: [primary-source review](numerics/bsim4_public_mode_review.md).

The physical work created a native 2×2 control structure using school 4 µm MIM capacitors. Each of three cases ran 279 ordinary DRC checks and 9 project MIM checks with zero results. The normal case was LVS MATCH; a cross-row open and a bottom-plate short were both MISMATCH. Each case contained four actual functional capacitors and zero black boxes. Actual GDS, ports and geometry were reviewed. [Physical audit](../../../physical/cdac_closure_20260923/school4um_preparation/access_2x2_r2/README.md). Disabled rules are excluded from coverage. These results do not qualify PEX physical accuracy.

The short tests did not qualify a new complete two-frame precision run, 12 frames, long records, or formal PEX.

Further strict controls did not produce a valid repair. Finer current tolerance, an equivalent native zero-volt ground source, a direct global-ground declaration, and tightening other settings while retaining the original strict current tolerance all failed to complete the short window. Exits and partial waveforms remain recorded; small pre-timeout differences cannot qualify the run. Compilation confirmed that the ground declaration removed one node, but the difficulty moved to other driver branches and internal MOS body nodes. It cannot be attributed solely to one ground representation.

The single-transistor static diagnostic completed eight sweeps: two precisions, wide and fine ranges, and both sweep directions, totaling 14,408 points. All runs had zero errors and zero warnings, with matching input and before/after PDK hashes. Raw charge showed repeatable slope differences on the two sides of source/drain mode reversal; forward/reverse and precision controls agreed. A finite charge jump and a model defect have not been proved. Saved total and intrinsic charge fields were equal point by point, and exported effective-model selectors included sentinel values. These interpretation limits are retained in the [static charge report](numerics/static_charge_review_v1/README.md).

External small-signal port controls also completed: seven biases, each with 41 frequency points from 1 kHz to 10 MHz, all with zero errors and zero warnings. External responses showed a branch difference: at drain/source biases of −1 / +1 µV, the 1 kHz gate effective response was −16.3231 / −11.4548 fF. The observation therefore extends beyond raw-Q field naming, but does not establish a model defect or explain every full-ADC failure. Current signs and KCL were checked against actual text-printing precision; rounding residuals were not treated as physical errors. [Actual AC report](numerics/ac_boundary_review_v1/README.md), [independent port review](numerics/ac_port_cross_review_v1/README.md).

Learning check: displacement current depends on charge variation with time. For a single transistor with other biases fixed, `I≈(dQ/dVD)·dVD/dt` describes the local contribution of drain-voltage change. Charge can approach continuity while its slope changes. The actual ADC also has gate, internal-body and other coupling terms; this expression does not replace the complete model. Port checks use `Y=I/V` and `Ceff=Im(Y)/(2πf)` to examine external response. They are an additional observation, not proof of process accuracy.

## School-native ADC and original RTL

The actual native reset1 design contains 693 ADC devices and 48 phase-generation devices, together with the original `sar_controller.v`. Each input has 350 Ω source impedance. The 1.1 / 0.7 V reference sources each use 1 Ω and 10 nF decoupling. VCM is 0.9 V. Conditions are TT / 27°C / 1.8 V with a 1.6 MHz external clock.

Two complete frames and a reset interruption during the third frame were executed:

| Differential input | Actual raw code | Ideal offset-binary interval code | Output gain tag |
| --- | ---: | ---: | ---: |
| −0.399 V | 5 | 5 | 0 |
| +0.399 V | 4090 | 4090 | 2 |

All 24 Q/QB decisions came from the actual comparator, with no prerecorded decisions. The 670 online protocol checks and offline actual S/R, Q/QB and reset-waveform checks passed. Executed cases included ignoring starts while busy, rejecting the reserved gain code, assigning data_gain correctly when completion and new acceptance share an edge, and interrupting conversion with reset during EVAL. Gain tags belong to the independent ADC interface; this fixture does not contain the three-gain analog frontend.

The baseline finished in approximately 331 seconds with zero Spectre errors and two automatic LTE-relaxation warnings. Its status is `FUNCTIONAL_PASS_PRECISION_NOT_QUALIFIED`. The original evidence directory is `runs/task_20260924T050345927509Z/`; `review.json` contains the complete offline review. Original school runs remain local-only in this publication.

Strict precision v4 reached its 900-second limit, with actual exit 124. Its two codes were again 5 / 4090, but the reset-interruption test was incomplete. All 20 LTE-relaxation warnings and 159 notices were retained. SSH exit 255 was recorded separately from the simulator exit; the retained evidence was subsequently recovered.

The full common-prefix diagnostic failed. TP−TN reached a maximum difference of 14.374193 mV at 16.5862427 µs, just after second-frame acquisition. RP/RN differences were approximately 0.936 µV, and VCM difference was zero. Edges were neither removed nor aligned. This is not a 73.6-LSB ADC conversion error: it is the node-waveform difference between two numerical configurations at the same absolute time. The worst interval was approximately 188 ps wide, with a CONV rising-edge timing difference of about 1.492 ps. Residuals remained at tens of µV after the peak; approximately 32.59 ns later, the interval through 100 ns was below the limit. The 24 pre-EVAL differences were at most 63.02 pV and pre-capture differences at most 191.94 pV. Those observations support equal codes, but do not waive the full-domain FAIL.

The numerical threshold remains a maximum difference of 9.765625 µV for TP−TN, RP, RN and VCM. An independent v5 diagnostic changed only the relative convergence reference from sigglobal to allglobal, according to installed Spectre help. This changes the KCL residual history reference. Devices, models, gmin/cmin, input, tolerances and the original threshold were unchanged. V5 again passed function/reset checks but retained two LTE-relaxation warnings and did not solve the numerical problem. A v5 strict run was not started.

A subsequent 4.1 µs short probe saved local gates and primitive internal-body nodes in the same actual ADC, with 76 voltage channels. Near the first warning, the final CONV PFET body node changed by approximately −449.1 µV within an accepted step of 201.3 fs, while external VDS crossed zero and gate voltage remained continuous. This locates a body-network / source-drain mode-reversal event, but does not establish a PDK or solver defect. The short probe reached stop without completing conversion protocol qualification.

The installed Spectre 25.1 / Xcelium 25.03 combination ran the same short probe. It still reported LTE relaxation at the same location and rejected saving internal int_b. Classification of its 26 warnings and cross-version waveform checks are in [the version-25 review](numerics/version25_probe_review.md). The independent 87-device comparator retained functional success in the newer tool, with extremely small-step Newton recovery. Reduced warning counts were not treated as numerical qualification.

A 4.1 µs baseline/strict pair with requested common solver time points completed, with both simulator exits zero. Baseline had no Spectre warnings; strict retained LTE relaxation and explicitly skipped a breakpoint. Of 2001 requested points, 1974 exact common points were actually saved. Their direct CDAC differential difference was 11.6048 µV, above 9.765625 µV. Across the actual common domain [2 ns, 4.1 µs], the maximum difference was 854.989 µV, versus 854.869 µV for the old configuration over the same domain. There was no improvement. This short-domain result cannot be compared with the 14.374 mV peak at 16.586 µs to claim improvement. [Complete evidence review](numerics/first_phase_commonpoints_pair_review_v2/README.md).

The analysis program's NumPy-boolean JSON serialization defect was fixed; its original program and traceback were retained. Raw waveforms and qualification conclusions were unchanged. An additional 4.1 µs body-network / reversal / terminal-current probe completed with zero errors and two warnings. All added observations were actually saved. Its 76 shared voltage channels and time grid matched the earlier probe point by point, showing that additional observation did not change this trajectory. Near the first warning, external signed VDS crossed zero, reversed changed from 1 to 0, and int_b, dbnode and sbnode changed simultaneously. This identifies an event for controlled model/solver reproduction, but temporal coincidence does not prove a model defect. Saved PFET OP vds is folded internally and cannot replace external CONV−VDD. Approximate four-terminal current balance establishes port self-consistency only. [Neighbor points, metadata and figure](numerics/body_network_probe_review/README.md). Twelve-frame and longer tests remain gated.

Waveform figure: [full numerical-difference localization](numerics/full_adc_numerical_failure.png).

## Parallel array progress

The older public 3×3 µm complete differential array was rerouted and extracted. Public Magic full DRC returned zero at three hierarchy levels and Netgen matched at all three. The 8712 MIM bodies and binary weights were unchanged. Static 4096-code analysis gave maximum |INL| of 0.327237 LSB and DNL of −0.177832…+0.171533 LSB, with no reverse transition. Area increased by 14.35%.

This is the established C-only extraction plus frozen functional-capacitance analysis, not actual full-code ADC simulation. It does not qualify school 4×4 µm devices, distributed R/dynamics, device noise or independent physical accuracy. Root review confirmed all 45 artifact hashes. See [the full candidate](../../../physical/cdac_closure_20260923/full_candidate/README.md).

School 4×4 µm mapping confirmed that the current ADC connects the common sampling node to the M4 top plate, while the older 3×3 candidate uses the M3 bottom plate; that layout cannot be reused directly. Three independent native access controls were created and verified in project1: p2c4_access_pair_r1, p2c4_access_open_r1 and p2c4_access_short_r1. Each ran 279 ordinary school checks and 9 project MIM checks with zero violations. Actual GDS, top-level identity and geometry were checked. The normal case extracted two 4×4 µm MIM devices with three ports and MATCH. The open retained both devices but left BITB floating; the short merged bottom plates. Both were MISMATCH, with zero black boxes in all cases. This verifies actual contact and connectivity, not parasitic accuracy.

An 8712-row bit-assignment template is prepared. Its 12 µm spacing is only control-case spacing; final pitch, biasing of 520 edge units and school-model multiplicity/statistical interfaces remain unresolved. The later 2×2 shared-M4 control is complete, as described above. See [access controls](../../../physical/cdac_closure_20260923/school4um_preparation/access_tile/README.md).

## Retained qualification gates

Complete ADC numerical convergence, 12 frames, full-code testing, long noisy records, 45 PVT conditions and 200 mismatch samples are not qualified by these results. MIM material parameters, model reference planes, RC double-counting boundaries and ordinary-interconnect resistance provenance remain incomplete. `formal_ADC_PEX_allowed=false`.

## Next evidence required

Single-transistor dynamic controls, a reduced actual switch-load circuit, bidirectional DC charge sweeps and external AC response controls have already run. The next numerical work must explain the selected model's terminal-charge definitions, source/drain direction, internal body network and associated solver difficulty, and establish an applicable supported treatment. No validated repair was found in this iteration. Existing evidence does not prove a model/tool defect and does not justify directly changing model selectors. A future attempt must start from new model/tool interpretation or a reviewable repair basis, then repeat the same actual ADC's complete two-frame/reset test and original numerical criterion before expanding to 12 frames. Every short-window failure and timeout is retained. Diagnostic materials have not been sent externally.

The 4 µm physical controls have reached the 2×2 shared-top-plate stage and passed enabled rules and connection counterexamples. Before a complete array, edge-unit biasing and the correspondence between physical units and multiplicity/statistical models must be settled. CAPM materials and independent coupling references, internal/external RC reference planes and exclusions, and the temperature/version provenance of ordinary-interconnect resistance remain unresolved. Formal ADC PEX remains unavailable as a performance claim.

Original successes, failures, timeouts, output compatibility issues and local analysis errors remain retained. This publication does not require the user to upload or load the earlier packages again.
