# Fixed-I precision-control review

**Result: INCOMPLETE, no numerical repair established.** The real fixed-I run returned 124 after its 300 s bound. Its last saved point is **4.063283615652629 µs**, not the worst-error timestamp. The requested 4.1 µs transient and original four-channel numerical gate remain incomplete; no ADC or long-campaign approval follows.

## Controlled change and identity

Relative to the original completed strict profile, actual relative tolerance tightens from 1e-7 to 1e-8, voltage absolute tolerance from 1e-9 to 1e-10 V, and maximum step from 1 ns to 0.5 ns. **Current absolute tolerance stays at the original strict 1e-14 A (10 fA).** Relative to the prior failed finer profile, only the requested current absolute tolerance changes from 1 fA back to 10 fA. This review has a dedicated analyzer with explicit 10 fA checks; it does not reuse the previous utility's 1 fA assertion.

All source and returned manifest hashes match; all non-control files are byte-identical across the three runs. Native 741-device chip, original RTL, source waveforms, native external reference fixture, method gear2only, lteratio=1, cthresh=1 pF, sigglobal, temperature and inventory are unchanged. Actual PSF headers verify the stated tolerances and 0.5 ns maximum step. The deterministic reference-fixture comparison still does not establish noise equivalence to the older VAMS resistive contributions.

## Actual run evidence

| Property | Original strict 10 fA | Finer 1 fA | New finer, fixed 10 fA |
|---|---:|---:|---:|
| Process exit | 0 | 124 | 124 |
| Last saved time (µs) | 4.1 | 4.062500225443528 | 4.063283615652629 |
| Saved rows | 20,403 | 12,342 | 17,470 |
| Final errors / warnings / notices | 0 / 103 / 59 | 1 / 160 / 129 | 1 / 166 / 146 |
| LTE ignored warnings | 23 | 85 | 81 |
| LTE relaxed warnings | 4 | 0 | 6 |
| Newton rejected steps | 332 | 1,118 | 1,026 |
| LTE rejected steps | 836 | 75 | 550 |
| Recovery notices | 49 | 121 | 136 |

New-run warning classification: AHDLLINT-8014 ×71; SPECTRE-16266 ×81; AHDLLINT-8007 ×7; SPECTRE-16780 ×6; AHDLLINT-8012 ×1. All complete warning lines are retained in `review.json`. SPECTRE-25 reports external termination, consistent with the bounded runner's exit 124. PSF has a valid END marker, but that closes a partial transient; it does not imply time-domain completion. No malformed row was removed or filled.

The new run progresses **0.7833902091 ns** beyond the prior 1 fA attempt, but again stalls near a switching event. Its last four recovery messages report time 4.06328 µs and attempted step 199.9e-21 s. The independent actual minimum accepted-step statistic is 9.540217e-17 s; these are different quantities.

The most frequently printed failed-solution quantity remains the VAMS top-level `vss_flow` (13,489 iteration lines), followed by `vdd_vss_flow` (2,232). Comparator body-node residues persist: XCORE_XPN:sbnode 3,088 lines and XCORE_XPP:sbnode 3,062. Counts refer to repeated printed Newton iterations and do not prove unique causes or independent failure events. Restoring 10 fA did not eliminate the underlying difficulties and does not establish a roundoff floor.

## Common-prefix comparisons only

The original threshold remains **9.765625 µV (0.05 LSB)**. Every saved accepted point from either run within the overlapping interval is retained in the union grid; missing counterpart values use linear interpolation. No time alignment, edge exclusion, threshold change or extrapolation is used.

- Original strict → new fixed-I: domain **0–4.063283615652629 µs**, 25,572 union points. Maximum CDAC differential difference **0.207816238905 µV**, at **4.063263912835218 µs**. RP 59.0036908 pV, RN 55.6058533 pV, VCM zero.
- Failed finer 1 fA → new fixed 10 fA: domain **0–4.062500225443528 µs**, 20,938 union points. Maximum CDAC difference **0.162258421627 nV**. This isolates current-tolerance sensitivity only on the already available earlier prefix.

These prefixes are within the threshold, but **neither covers the requested full time domain**. Original strict's known later numerical error peak is outside this new finer run's saved interval. There are no complete frames or SAR decisions in these short probes. The experiment does not independently establish convergence with respect to absolute-current tolerance, the original two-frame numerical gate, 12-frame operation, noise, linearity, or mismatch.

## Provenance and correction

Actual inputs/results: `../../runs/task_20260924T081825369891Z/design/finer/`. Comparison inputs/results: `../../runs/task_20260924T074416052775Z/design/strict/` and `../../runs/task_20260924T075605661855Z/design/finer/`. `review.json` includes raw/log/input hashes, actual headers, inventories, warnings and complete comparison statistics; the two CSV files preserve union-grid differences.

The frozen fixed-I input manifest's purpose sentence repeated **4.062500033593 µs**, the earlier partial-difference peak timestamp, as though it were the prior finer endpoint. The correct raw-derived prior finer endpoint is **4.062500225443528 µs**. This report explicitly corrects the interpretation while preserving the frozen input unchanged.

No EDA was run by this review. No additional parameter search was prepared. Any further numerical intervention needs new circuit/model-specific evidence, not the partial-prefix closeness from this timeout.
