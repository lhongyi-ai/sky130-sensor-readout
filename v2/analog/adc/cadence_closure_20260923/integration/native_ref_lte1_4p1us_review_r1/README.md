# Native reference + cthresh1p + lteratio1: improvement, numerical gate fails

**SHORT_DOMAIN_NUMERICAL_FAIL.** This precision pair completes the full short
domain and reduces the original all-time error, but it is not a validated repair.
The threshold, physical circuit, original RTL and stimulus remain unchanged.

Actual evidence: `../../runs/task_20260924T074416052775Z/design/{baseline,strict}`.
Both simulations exit 0, contain normal PSF END markers and cover 0–4.1 us.
Qualification exit 2 is expected because no complete frame or SAR decision occurs
within this diagnostic. No EDA was launched by this review.

## Identity and actual settings

All returned file hashes match the manifests. Relative to the preceding native
reference/cthresh pair, the sole input change is explicit `lteratio=1` on the tran
line; its former actual value was 10. The 741-device bound chip, reference fixture,
RTL, interfaces, stimulus, source voltages, run wrapper and save list are identical.
The actual inventory and fixture portbind creation/use are unchanged. The earlier
reference binding audit is linked by hash, without claiming a new flattened
per-instance netlist inspection.

| Actual setting | Baseline | Strict |
| --- | ---: | ---: |
| Spectre | 21.1.0.132.isr1 | same |
| method | gear2only | gear2only |
| relref / errpreset | sigglobal / conservative | same |
| cthresh | 1e-12 F | same |
| lteratio | 1 | 1 |
| reltol | 1e-6 | 1e-7 |
| vabstol | 1e-8 V | 1e-9 V |
| iabstol | 1e-13 A | 1e-14 A |
| maxstep | 2 ns | 1 ns |
| Temperature | 27 C | 27 C |

Original gmin/cmin and initial-condition handling are unchanged. The reference
replacement remains equivalent only for deterministic transient equations;
native resistor noise must be accounted for separately.

## Original full-domain comparison

The accepted-time union preserves every output time and switch edge in 0–4.1 us.
There is no time shifting, edge exclusion or threshold adjustment. Linear
interpolation to the other run's accepted times retains event-timing and
interpolation contributions in the original metric. The threshold is
**0.05 LSB = 9.765625 uV**.

| Channel | Maximum absolute baseline/strict difference | Result |
| --- | ---: | --- |
| TP−TN | **182.974473 uV**, at 4.075079495857612 us | FAIL, 18.74 times limit |
| RP | 0.504361 nV | Within limit |
| RN | 0.401713 nV | Within limit |
| VCM | 0 V | Within limit; ideal-source limitation |

The preceding native-reference lteratio10 pair gives 854.568911 uV over the
same complete domain and comparison grid. Thus the maximum decreases **78.6%**.
The fixed local CONV window 4.06315–4.06335 us improves from 9.910975 uV to
1.586312 uV. That local result does not override the later all-time failure.

Unlike the earlier VAMS-reference lteratio1 trial, the new strict run completes
the requested domain. These completion and error reductions are useful evidence
for a bounded further precision diagnostic; they do not establish correctness
despite the simulator's explicit numerical relaxations.

## Numerical warnings worsen under tightening

| Actual diagnostic | Baseline | Strict |
| --- | ---: | ---: |
| End summary | 0 errors / 6 warnings / 10 notices | 0 errors / 103 warnings / 59 notices |
| AHDLLINT-8007 | 2 | 6 |
| AHDLLINT-8014 | 0 | 70 |
| SPECTRE-16266, LTE ignored | 0 | 23 |
| SPECTRE-16780, LTE relaxed | 4 | 4 |
| Accepted steps | 9,113 | 20,402 |
| LTE rejects | 361 | 836 |
| Newton rejects | 4 | 332 |
| Device rejects | 4 | 1 |
| Recovery steps | 1,903 | 1,784 |
| Minimum accepted step | 0.310791 fs | 0.033585 fs |

The preceding native-reference lteratio10 strict run had 26 warnings, zero LTE
ignores, one LTE relaxation and 11 Newton rejects. The tighter setting restores
substantial convergence difficulty even though its final saved-waveform difference
is smaller. Neither log suppresses further notices. All warning lines, including
separate amsspice unused-library parse warnings, remain in `review.json`.

## Decision and evidence

Retain the numerical FAIL and the original two-frame gate. Zero errors and
completion do not imply ADC accuracy. No full-code, twelve-frame, noise or mismatch
campaign is released by this report. Any finer-profile result must independently
check the same full domain, actual tolerances and all unresolved LTE warnings.

`analyze.py`, `review.json` and `all_accepted_union_differences.csv` retain source,
raw and log hashes plus identical-grid comparisons. No original evidence or root
status file was modified. `report_sha256.json` freezes the artifacts.

## Reusable next precision-pair review

`review_precision_pair.py` reads returned files only. Its baseline must be this
run's strict profile (actual reltol=1e-7); the new finer profile must have actual
reltol=1e-8, vabstol=1e-10 V, iabstol=1e-15 A and maxstep=0.5 ns, while preserving
native RC, cthresh1p, lteratio1, gear2 and all other inputs. The input-control audit
expects the planned `maxstep=0.5n` spelling; it does not silently rewrite decks.

From the closure directory, after the new result is downloaded:

```bash
python3 integration/native_ref_lte1_4p1us_review_r1/review_precision_pair.py \
  --baseline runs/task_20260924T074416052775Z/design/strict \
  --finer PATH_TO_NEW_RETURNED_FINER_RUN \
  --output integration/native_ref_lte1_4p1us_review_r1/strict_to_finer_review_r1
```

The output folder must be new. The analyzer checks hashes, actual headers,
completion, warning counts and every accepted output time. Malformed PSF data
is retained and reported rather than repaired; a valid partial prefix is labeled
partial and cannot pass the full domain. Meeting the waveform threshold while
LTE warnings remain is explicitly `WAVEFORM_LIMIT_MET_NUMERICAL_WARNINGS_UNRESOLVED`,
never ADC PASS. Help/import checks have run locally; the real finer analysis
remains pending its actual results.
