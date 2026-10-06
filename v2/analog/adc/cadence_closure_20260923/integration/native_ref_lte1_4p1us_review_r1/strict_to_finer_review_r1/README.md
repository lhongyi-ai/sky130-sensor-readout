# Strict to finer: incomplete, not qualified

The new actual reltol=1e-8 run reached only **4.062500033593080 us** before its
300-second wrapper limit (real exit **124**). Spectre reports external termination
SPECTRE-25, with **1 error, 160 warnings and 129 notices**. It did not complete the
required 0–4.1 us short domain or reach the later difficult CONV transition.

Input hashes, original circuit/RTL/fixture/stimulus identity and the planned
precision-profile-only change pass. Actual header values confirm reltol=1e-8,
vabstol=1e-10 V, iabstol=1e-15 A, maxstep=0.5 ns, gear2only, lteratio=1,
cthresh=1p and the prior environment. The preserved baseline is the actual 1e-7
strict run from `task_20260924T074416052775Z/design/strict`.

The finer PSF has an END marker and parses without deleting or filling any row;
that makes its saved prefix usable, not its time domain complete. The common-prefix
TP−TN difference is 0.245583 nV, but this prefix ends at the beginning of the
SAMPLE_CMD edge, before the known worst events. It cannot be used to claim the
original full-domain gate passed or that the numerical error was repaired.

The new warnings include **85 SPECTRE-16266 LTE ignores**, 71 AHDLLINT-8014,
3 AHDLLINT-8007 and 1 AHDLLINT-8012. The full warning table remains in `review.json`.

`failure_dominance.json` retains the printed Newton-failure counts and examples.
The top-level VAMS `vss_flow` appears in 15,457 printed solution-failure lines and
is the largest such category. This supports a bounded test of the ideal ground
branch representation. These are iteration-line counts, not independent events
or proof of a physical root cause. Numerous internal MOS sbnode/dbnode residual
failures coexist. The final body residuals are a few fA; with iabstol=1 fA they
cannot simply be declared insignificant. Moving only the zero-volt ground branch
may leave aggregated `vss_flow` from other retained VAMS sources.

No PDK, tolerance, threshold or old result was changed during this analysis.
`review.json`/CSV and their original `report_sha256.json` retain the numerical
comparison. The subsequent diagnostic addendum is separately hashed in
`diagnostic_sha256.json`. The native-ground control is prepared separately and
was not launched by this reviewer.
