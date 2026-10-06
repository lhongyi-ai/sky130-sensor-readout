# Native external reference RC with cthresh: full short-domain failure retained

**SHORT_DOMAIN_NUMERICAL_FAIL.** Native reference RC representation reduces
Newton failures and removes the printed LTE-ignore warnings in this probe,
but does not materially reduce the original four-channel precision error.

Returned evidence: `../../runs/task_20260924T073606929136Z/design/{baseline,strict}`.
Both Spectre processes exit 0 and complete 0–4.1 us; qualification exit 2 remains
expected for a diagnostic with zero completed conversions. No EDA was launched
by this review and no frozen input, raw result or acceptance criterion changed.

## Reference replacement and binding evidence

Both returned input manifests match their prepared counterparts. Static source
checks prove that exactly four VAMS current contributions were removed and exactly
two named fixture instances added: refp(SRC=rp_source, REF=rp, VSS=vss), and
refn(SRC=rn_source, REF=rn, VSS=vss). Each fixture contains RREF(SRC,REF)=1 ohm and
CREF(REF,VSS)=10 nF. The original voltage sources, other stimulus, interfaces,
RTL and 741-device native chip file are unchanged. Control changes relative to
the preceding cthresh pair are only the new include/portmap/config binding;
the wrapper only adds the fixture file to its input hash record.

The actual amsspice logs confirm creation and use of `p2_reference_fixture.pb`.
Actual inventories change exactly from 103 to 105 capacitors and 66 to 68
resistors; every other inventory count is identical, including 673 bsim4 devices.
The comparison counts internal PDK-expanded primitives, not schematic-level
instances. The returned generated portbind now independently confirms identity
mapping of SRC/REF/VSS as inout in both profiles. `fixture_binding_review.json`
closes the initial `review.json` pending-readback field using that portbind, actual
log, static named instances, inventory and DC evidence together. The temporary
flattened `amsdControl.ams` no longer existed after the run; no direct flattened
per-instance inspection is claimed and no simulation was repeated to recreate it.

Both initial saved operating points give RP=1.099999999952622 V,
RN=0.7000000000463391 V, source references 1.1/0.7 V, VCM=0.9 V and VDD=1.8 V.

This equivalence concerns **deterministic transient equations**. A native resistor
has thermal noise not present in the old noiseless VAMS conductance expression.
Future noise tests therefore require separate accounting. Whether cthresh applied
to the former VAMS ddt contribution was unverified; the new test does not prove
that it was previously absent.

## Actual numerical settings and original gate

Both PSF/log records confirm Spectre 21.1.0.132, gear2only, sigglobal,
conservative, lteratio=10, 27 C, original gmin/cmin and actual cthresh=1e-12 F.
Baseline/strict actual reltol remain 1e-6/1e-7, vabstol 1e-8/1e-9 V,
iabstol 1e-13/1e-14 A and maxstep 2/1 ns.

The 16,080-point accepted-time union retains the complete short domain.
Comparison uses interpolation on the other run's time grid, without time shifting,
edge exclusion or gate relaxation. It includes numerical timing/interpolation
effects. The unchanged threshold is **9.765625 uV (0.05 LSB)**.

| Channel | Maximum baseline/strict absolute difference | Result |
| --- | ---: | --- |
| TP−TN | **854.568911 uV**, at 4.075079409756319 us | FAIL, approximately 87.51 times limit |
| RP | 3.177909 nV | Within limit |
| RN | 2.529958 nV | Within limit |
| VCM | 0 V | Within limit; ideal source |

On the same comparison grid and complete 0–4.1 us domain, the prior VAMS-reference
cthresh pair gives 854.441006 uV: the main peak is essentially unchanged.
In the fixed local CONV window 4.06315–4.06335 us, the prior pair gives
9.772156 uV and the native RC pair 9.910975 uV; both fail the unchanged gate.
This is a single representation change relative to the cthresh pair, not a
single-factor comparison with the original no-cthresh experiment.

## Warnings and convergence

| Actual diagnostic | Baseline | Strict |
| --- | ---: | ---: |
| End summary | 0 errors / 2 warnings / 10 notices | 0 errors / 26 warnings / 11 notices |
| AHDLLINT-8007 | 1 | 3 |
| AHDLLINT-8014 | 0 | 22 |
| SPECTRE-16266, LTE ignored | 0 | 0 |
| SPECTRE-16780, LTE relaxed | 1 | 1 |
| Accepted steps | 4,952 | 11,148 |
| LTE rejected steps | 118 | 363 |
| Newton rejected steps | 4 | 11 |
| Device rejected steps | 3 | 2 |
| Recovery steps | 1,403 | 1,909 |
| Minimum accepted step | 3.416115 fs | 0.319668 fs |

The prior cthresh strict run had 84 warnings, including five LTE ignores, and
218 Newton rejects. This replacement produces real improvement in those
diagnostics. It still relaxes LTE: baseline names the final CONV driver PMOS
internal body node; strict names `adc.XADC_XN2_XNI_XP...:int_b`. All warnings
remain recorded. Neither log prints ringing or suppression lines. The two
amsspice unused-resistor-library parse warnings are separately retained rather
than conflated with Spectre's final warning totals.

The original all-time gate still fails, and this test contains no conversions.
Two-frame/12-frame accuracy, full-code linearity, noise and mismatch remain
unqualified. The report, analysis source, raw hashes and union-grid CSV preserve
the evidence without upgrading reduced warning counts into a performance pass.
