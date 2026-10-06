# Adaptive trap 4.1 us pair: numerical gate still fails

Status: **SHORT_DOMAIN_NUMERICAL_FAIL**. The tool-recommended `method=trap`
reduces printed numerical ringing but does not solve the original full-domain
precision disagreement. No threshold, source, circuit, PDK or old result changed.

Evidence: `../../runs/task_20260924T073009937369Z/design/{baseline,strict}`.
Both simulations actually exit 0 and complete 0–4.1 us, including initial DC.
Both PSF files end normally. The wrapper qualification exit 2 is expected for
this short diagnostic: zero frames and zero SAR decisions are completed by then.

## Frozen input and actual configuration checks

Returned manifests equal the prepared manifests, all input hashes agree, and
the physical netlist, RTL, interfaces and stimulus equal frozen v4. Both actual
headers report Spectre 21.1.0.132, **method=trap**, conservative, sigglobal,
lteratio=10, 27 C and the original gmin/cmin. No cthresh override is present.
The baseline/strict inputs differ only by the original precision profile.

| Actual setting | Baseline | Strict |
| --- | ---: | ---: |
| reltol | 1e-6 | 1e-7 |
| vabstol | 1e-8 V | 1e-9 V |
| iabstol | 1e-13 A | 1e-14 A |
| maxstep | 2 ns | 1 ns |
| Accepted steps | 4,479 | 9,785 |
| Raw rows including initial DC | 4,480 | 9,786 |

## Unchanged four-channel numerical gate

All 14,244 times in the accepted-time union are retained. The other run is
linearly interpolated at each accepted time; there is no time shift, excluded
switch edge or cropped interval within 0–4.1 us. The threshold remains
**0.05 LSB = 9.765625 uV**. This metric includes event-timing/interpolation effects;
it does not isolate intrinsic waveform error independently.

| Channel | Maximum absolute baseline/strict difference | Result |
| --- | ---: | --- |
| TP−TN | **344.418245 uV**, at 4.075079474424275 us | FAIL, 35.27 times limit |
| RP | 2.224074 nV | Within limit |
| RN | 1.629924 nV | Within limit |
| VCM | 0 V | Within limit; ideal-source limitation |

The same-domain old gear2 peak is 854.868994 uV. The previous traponly result is
344.021465 uV, so adaptive trap leaves essentially the same worst error as
traponly. In the fixed local CONV window, 4.06315–4.06335 us, adaptive trap gives
9.405620 uV, compared with old gear2 9.902133 uV and traponly 12.514675 uV.
That local improvement does not replace the all-time failure later in the record.
The old full two-frame worst event is outside this diagnostic and is not used
to claim a global reduction. Old gear2 prefixes also have fewer diagnostic saves;
their comparison is a same-domain diagnostic, not exact execution equivalence.

## Full warning and recovery evidence

| Actual log count | Baseline | Strict |
| --- | ---: | ---: |
| End summary | 0 errors / 1 warning / 10 notices | 0 errors / 55 warnings / 20 notices |
| AHDLLINT-8007 | 1 | 3 |
| AHDLLINT-8014 | 0 | 47 |
| SPECTRE-16266, LTE ignored | 0 | 4 |
| SPECTRE-16780, LTE relaxed | 0 | 1 |
| LTE rejects | 107 | 305 |
| Newton rejects | 4 | 107 |
| Device rejects | 2 | 2 |
| Recovery steps | 1,336 | 1,374 |
| Minimum accepted step | 5.580499 fs | 0.303710 fs |
| Printed trapezoidal-ringing mentions | 33 | 38 |

The printed ringing counts decrease from traponly's 339/1,234 to 33/38. These
are annotation counts, not unique or exhaustive event counts. Unlike traponly,
neither new log has the final ringing recommendation or suppressed-notice lines;
ringing annotations still exist internally. Strict still explicitly ignores or
relaxes LTE. Neither reduction in messages nor absence of an end notice establishes
numerical correctness or physical circuit stability.

The two amsspice unused-library parse warnings remain preserved separately from
the Spectre totals. All warning lines, actual headers and raw/input/log hashes
are retained in `review.json`. No warning is automatically waived.

## Decision

Do not promote this diagnostic to two-frame/12-frame accuracy qualification.
The original failures remain. This analysis launched no EDA and changed no raw
evidence. `analyze.py`, the full union-grid CSV and `report_sha256.json` make the
local calculation reproducible; the parser handles both singular and plural
error/warning summaries.
