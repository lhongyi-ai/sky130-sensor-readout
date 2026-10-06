# Ground alias: reference node removed, simulation still incomplete

**GROUND_ALIAS_INCOMPLETE_NO_REPAIR.** The prepared two-line ground declaration
was compiled and executed, but the original 0–4.1 us simulation did not complete.
No PDK, source value, precision setting, gate or frozen record was changed during
this review.

Actual returned run: `../../runs/task_20260924T081210453008Z/design/finer`.
Its real simulator/qualification exits are **137**. The task requests 300 seconds
and the unchanged wrapper uses TERM followed by KILL after 10 seconds; terminal
output explicitly reports the timeout command killed. The Spectre log contains
SPECTRE-25 external-stop and is truncated during its final audit, so there is no
complete final Spectre summary. This is consistent with timeout escalation.
There is no returned OOM evidence, and this report does not assert OOM.

## Actual time and input checks

The saved PSF has an END marker and its relevant waveform rows parse, but ends at
**4.063186272078730 us**, with 14,457 saved rows. It progressed beyond the original
finer timeout at 4.062500225443528 us, into the initial phase response, but still
before the known later worst event. A complete file ending is not a complete
simulation interval.

All hashes agree with the frozen alias package. The source differs only by adding
`ground vss;` after the electrical declaration and removing `V(vss) <+ 0.0;`.
Other source branches, reference RC, chip/RTL and settings are unchanged. Actual
headers verify reltol=1e-8, vabstol=1e-10 V, iabstol=1e-15 A, maxstep=0.5 ns,
gear2only, lteratio1, cthresh1p and the original environment.

## Grounding observations and limits

Actual circuit inventory decreases from **515 to 514 nodes**, with every device
count unchanged and no native ground vsource added. The old top-level `vss_flow`
and the native `VGND:p` are absent from the printed failed-iteration categories.
This is consistent with the legal global-reference declaration removing the
redundant node/branch. It does not establish successful numerical convergence.

The separate saved `p2_ams_reset1.vss` trace is absent after aliasing; the parser's
initial missing-trace error and source are retained in `missing_ground_trace_history/`.
The corrected review records this missing observation explicitly and **does not
fabricate a zero-voltage trace**. The declaration, successful compilation and node
count support reference-node folding, but are distinguished from a direct saved
voltage measurement or returned generated alias map. VDD, VCM and reference-source
voltages that remain saved are exactly 1.8/0.9/1.1/0.7 V throughout the saved prefix.
The separate read-only school check confirms that temporary `amsdControl.ams`
no longer exists after the run. `alias_readback_review.json` records its hash and
this limitation; no direct flattened alias inspection is claimed.

## Remaining numerical failure

The available log contains **199 warning lines**: 124 SPECTRE-16266 LTE ignores,
71 AHDLLINT-8014, 3 AHDLLINT-8007 and 1 SPECTRE-16780 LTE relaxation. These are
observed log counts, not a claimed completed end-summary total. Diagnostic output
records 1,677 Newton rejects, 144 LTE rejects and 185 recovery notices.

The largest printed solution-failure categories now are the evaluation driver's
`e_vss_flow` (12,455 iteration lines) and top-level `vdd_vss_flow` (10,106), while
comparator and phase MOS body residual failures persist. Counts refer to printed
Newton iterations, not independent events or proof that a particular remaining
source is the physical root cause. Ground declaration did not eliminate the broader
source-current/body-residual convergence problem.

The same-precision cross-representation common prefix ends at the earlier run's
4.062500225443528 us. TP−TN differs by at most 10.923428 pV there, but that domain
does not include the subsequent difficult edges. It is neither a completed
four-channel gate nor a precision-convergence pair. The original full-domain gate
remains **NOT_RUN_INCOMPLETE**, with no ADC qualification.

`review.json`, the prefix CSV and hashes preserve actual headers, warning lines,
input integrity, inventories and failure categories. No remote EDA or process
operation was performed by this reviewer.
