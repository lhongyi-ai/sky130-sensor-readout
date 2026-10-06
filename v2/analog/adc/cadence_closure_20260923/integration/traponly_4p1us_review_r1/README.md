# Traponly 4.1 us precision-pair review

Status: **SHORT_DOMAIN_NUMERICAL_FAIL**. This local review does not change the
original 0.05 LSB all-time gate, the PDK, the circuit, or any frozen results.
No EDA simulation was launched by this review.

Evidence: `../../runs/task_20260924T071725254673Z/design/{baseline,strict}`.
Both Spectre processes finished with exit 0 and cover 0 through 4.1 us, including
the initial DC sample. The wrapper qualification exit is 2 because this deliberately
short diagnostic completes no conversion; it is not an ADC qualification pass.

## Identity and actual settings

All submitted input hashes match. The 741 native primitives, original SAR RTL,
interfaces, stimulus, sequence and bound native circuit match the frozen v4 files.
Between baseline and strict, only the original requested precision profile differs.
Both PSF headers verify Spectre 21.1.0.132.isr1, `method=traponly`,
`relref=sigglobal`, conservative, `lteratio=10`, 27 C and unchanged gmin/cmin.
Neither input overrides `cthresh`.

| Actual setting | Baseline | Strict |
| --- | ---: | ---: |
| reltol | 1e-6 | 1e-7 |
| Voltage absolute tolerance | 1e-8 V | 1e-9 V |
| Current absolute tolerance | 1e-13 A | 1e-14 A |
| Maximum step | 2 ns | 1 ns |
| Accepted transient steps | 4,503 | 9,882 |
| Raw rows including initial DC | 4,504 | 9,883 |

## Original four-channel check

The union contains 14,365 accepted output times. Each run is linearly interpolated
only to the other run's accepted times. There is no time shift, edge exclusion or
cropping within the 0–4.1 us diagnostic domain. These interpolation-based differences
do not independently separate waveform error from event timing and interpolation
error. The original threshold is **9.765625 uV**.

| Channel | Maximum absolute baseline/strict difference | Result |
| --- | ---: | --- |
| CDAC TP−TN | 344.021465 uV at 4.07507947660431 us | FAIL |
| RP | 2.076841 nV | Within limit |
| RN | 1.518799 nV | Within limit |
| VCM | 0 V | Within limit; ideal source limits evidential value |

The CDAC error is 35.23 times the limit. On one common comparison grid spanning
the old gear2 v4 and new traponly pairs, the old 0–4.1 us peak is 854.868994 uV:
the traponly peak is approximately 59.8% smaller, but remains a failure.
In the same local CONV window, 4.06315–4.06335 us, the maximum instead worsens
from 9.902133 uV to 12.514675 uV. This is not a uniform improvement.

The old full-record prefixes have the same physical configuration but fewer saved
diagnostic quantities and a different diagnostic context. Treat that comparison as
a same-domain diagnostic, not proof of a strictly isolated execution change.
The old full two-frame 14.374 mV peak occurs outside this short domain and must not
be used as the comparison denominator to claim global improvement.

## Warnings and numerical ringing

| Diagnostic | Baseline | Strict |
| --- | ---: | ---: |
| Spectre end summary | 0 errors / 2 warnings / 197 notices | 0 errors / 80 warnings / 1,026 notices |
| AHDLLINT-8007 | 2 | 3 |
| AHDLLINT-8014 | 0 | 71 |
| SPECTRE-16266, LTE ignored | 0 | 6 |
| LTE rejected steps | 95 | 309 |
| Newton rejected steps | 4 | 147 |
| Device rejected steps | 2 | 2 |
| Recovery steps | 1,351 | 1,418 |
| Minimum accepted step | 4.91836 fs | 0.305136 fs |
| Printed `trapezoidal ringing` mentions | 339 | 1,234 |

Both logs explicitly report trapezoidal ringing and recommend `method=trap`.
The strict log also says **1,378 notices suppressed**. The printed mention count
is neither the total number of numerical events nor a unique event count; suppressed
notices cannot simply be added to that count. Ringing annotations involve internal
body nodes in the comparator reset/logic, phase drivers and switch control logic.
This is the simulator's numerical ringing diagnosis, not proof of a physical
circuit oscillation. Strict LTE-ignore warnings remain real unresolved evidence.

The two amsspice parse warnings for unused `res_generic_nd/pd` are preserved
separately in the complete warning list; they are not part of the Spectre end-summary
warning totals. No warning is automatically waived by this report.

## Decision and artifacts

Do not promote this option to the two-frame or twelve-frame qualification campaign
on the strength of this probe. The original two-frame failure is retained. The
short test produces zero completed frames and zero SAR decisions, as expected.
Root controls any subsequent single-factor experiment; none is launched here.

`review.json` contains input/raw/log hashes, actual headers, all warning lines,
diagnostic statistics and same-domain comparisons. The CSV retains all union-grid
differences. `report_sha256.json` freezes this report and analysis artifacts.
