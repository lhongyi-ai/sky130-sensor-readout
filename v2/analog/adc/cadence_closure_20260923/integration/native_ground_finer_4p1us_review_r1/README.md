# Native ground source: executed, still incomplete

**GROUND_REPRESENTATION_INCOMPLETE_NO_REPAIR.** The native zero-volt ground source
was actually bound and used, but did not resolve the numerical problem.
Both attempts reached their 300-second budget with real exit 124 and SPECTRE-25
external-stop errors. Their PSF files are syntactically complete prefixes, not
completed 0–4.1 us simulations.

| Actual evidence | Original VAMS ground | Native zero-volt ground |
| --- | ---: | ---: |
| Last saved time | **4.062500225443528 us** | **4.062828137323451 us** |
| Saved rows including initial DC | 12,342 | 12,686 |
| Errors / warnings / notices | 1 / 160 / 129 | 1 / 165 / 140 |
| LTE ignored warnings | 85 | 90 |
| AHDLLINT-8014 | 71 | 72 |
| AHDLLINT-8007 | 3 | 3 |
| AHDLLINT-8012 | 1 | 0 |
| Newton rejects | 1,118 | 1,209 |
| LTE rejects | 75 | 85 |
| Recovery notices | 121 | 132 |
| Minimum accepted step | 0.238782 fs | 0.530212 fs |

The native version advances about 0.328 ns farther into the same initial
SAMPLE_CMD transition, still before the later known CONV/ADC worst events.
This small increase in progress is not a successful numerical repair.

## Binding, voltage and source integrity

All actual input hashes match the frozen candidate. Both actual headers confirm
the same finer profile: reltol=1e-8, vabstol=1e-10 V, iabstol=1e-15 A,
maxstep=0.5 ns, gear2only, lteratio1, cthresh1p and the same environment.

The actual log records ground-fixture portbind creation/use and names the
instantiated `p2_ams_reset1.ground_ref.VGND:p` in the solver. Inventory changes
only by one native vsource. All 673 expanded BSIM4 instances, 105 capacitors,
68 resistors and other counts remain unchanged. The previously audited named
VSS connection and global-zero negative terminal are frozen in the input.

For every saved time in both records, **vss=0 V**, VDD=1.8 V, VCM=0.9 V and
reference sources=1.1/0.7 V exactly. The evidence does not indicate a floating
ground or wrong source value. No PDK or physical device was changed.

## Failure follows the branch constraint

The original largest printed solution-failure category is VAMS `vss_flow`
(15,457 iteration lines); the native version instead names `ground_ref.VGND:p`
(16,619). Comparator/phase MOS body sbnode/dbnode residual failures persist in
both cases. These counts are printed iteration diagnostics, not independent
failure events or proof of a unique physical root cause. Moving the same explicit
zero-volt branch between representations did not remove the ill-conditioned
constraint or solve the run.

The common-prefix cross-representation TP−TN difference is only 3.610443 pV, but
the common domain ends at 4.062500225443528 us. It ends before the later difficult
events and is not a precision-convergence pair. The original full-time gate remains
**NOT_RUN_INCOMPLETE**, with no ADC qualification.

## Correction and preservation

An earlier prose summary/README incorrectly called 4.062500033593080 us the
original finer endpoint; it is the time of a partial error peak. The actual endpoint
is **4.062500225443528 us**, already correctly recorded in the original machine
`review.json` and unchanged raw data. This addendum corrects that prose without
rewriting the frozen previous report. The incomplete outcome is unchanged.

`review.json` preserves both raw/input/log hashes, actual headers, inventory,
voltage ranges, full warning lists and printed failure counters. The CSV retains
the complete common-prefix comparison without alignment, deletion or synthetic
completion. This local review launched no EDA and changed no original evidence.
