# lteratio=1 partial failure review

**PARTIAL_TIMEOUT_NOT_QUALIFIED.** Tightening LTE alone did not produce a complete
precision pair. This review does not edit inputs, raw files, the PDK or thresholds.
No EDA run or smaller-lteratio retry was launched/prepared.

Evidence: `../../runs/task_20260924T072218194124Z/design/{baseline,strict}`.
Both actual headers confirm Spectre 21.1.0.132, gear2only, lteratio=1, sigglobal,
conservative, 27 C, and the original actual precision profiles (reltol 1e-6/1e-7;
maxstep 2 ns/1 ns). All manifest input hashes match.

| Actual evidence | Baseline | Strict |
| --- | ---: | ---: |
| Simulator wrapper exit | 0 | 124, 180-second limit |
| Qualification wrapper exit | 2, short probe | 124 |
| Last saved time | 4.1 us | 4.063280441059132 us |
| Complete saved voltage rows | 9,114 | 8,634 |
| End summary | 0 errors / 5 warnings | 1 error / 102 warnings |
| LTE rejects | 349 | 230 |
| Newton rejects | 5 | 977 |
| Recovery steps | 1,914 | 441 |

Strict ended with `SPECTRE-25`, reporting external stop by user/farm, consistent
with the actual timeout exit 124. It advanced beyond the earlier observed 4.06309 us
but remained in Newton/recovery difficulty around 4.06328 us. The final recovery
attempt reports a 199.9e-21 s attempted step and `sbnode` residual problems. This
attempted step is not the minimum accepted step: the diagnostic summary reports
5.519267e-17 s as the strict minimum accepted step.

Strict warning counts are 75 AHDLLINT-8014, 8 AHDLLINT-8007,
18 SPECTRE-16266 (LTE ignored), and 1 AHDLLINT-8012. Baseline has
3 AHDLLINT-8007 and 2 SPECTRE-16780 (LTE temporarily relaxed). All warning and error
lines are retained in `review.json`; no numerical warning is waived.

The actual strict PSF contains an END marker and its saved voltage rows parse
completely and monotonically. Thus its bytes need no repair, but its **time domain
is incomplete**. No row is filled, deleted or synthesized to reach 4.1 us.
The common saved domain 0–4.063280441059132 us gives TP−TN maximum difference
1.129105 uV; RP/RN are below 0.332 nV, and ideal VCM agrees exactly. These are
partial statistics only: they end inside the difficult phase transition and do
not include the later worst events. They do not constitute the original full
0–4.1 us check, a two-frame pass, or evidence that tightening LTE fixes the ADC.

`analyze.py`, `review.json` and `partial_common_domain_differences.csv` provide
reproducible local analysis. The first local summary parser expected plural
“errors” and missed “1 error”; its initial report/script are preserved under
`summary_parser_history/`. The corrected report records the actual singular-error
summary without changing any input or observed waveform.
