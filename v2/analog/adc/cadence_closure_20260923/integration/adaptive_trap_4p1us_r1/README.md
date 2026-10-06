# Adaptive trap diagnostic: prepared, not run

This is one bounded 0–4.1 us experiment with the same 741-device full ADC,
original RTL and physical stimulus. It changes only the integration method to
`method=trap` relative to the original no-cthresh gear control. It does not combine
the failed cthresh or lteratio=1 variants. The two precision profiles are unchanged.

## Verified recommendation

The actual Spectre 21.1.0.132 traponly logs contain this notice in both profiles:

> Trapezoidal ringing is detected during tran analysis.
> Please use method=trap for better results and performance.

Baseline xrun.log lines 1818–1820 and strict lines 8525–8527 are retained with their
hashes in `tool_recommendation_evidence.json`. The locally captured installation
help defines `traponly` as using the trapezoidal rule almost exclusively, whereas
`trap` is an advanced method using all three integration methods. The help also
warns about point-to-point trapezoidal ringing and numerical damping from Gear
or backward Euler. Thus the recommendation is specifically `trap`, not `traponly`
and not an assurance of physically correct results.

## Frozen identities and expected observations

`preparation_audit.json` proves that the physical files, original controller,
interfaces, stimulus and run wrapper are byte-identical to the validated traponly
package. Removing the explicit method from the baseline control reproduces the
actual original gear-control file byte-for-byte. The strict reference differs only
by the original requested tolerances and maximum step. Each profile contains a
single-factor diff, manifest and SHA256SUMS.

| Expected actual setting | Baseline | Strict |
| --- | ---: | ---: |
| Integration method | trap | trap |
| reltol after conservative preset | 1e-6 | 1e-7 |
| vabstol | 1e-8 V | 1e-9 V |
| iabstol | 1e-13 A | 1e-14 A |
| Maximum step | 2 ns | 1 ns |
| relref | sigglobal | sigglobal |
| lteratio, unmodified default | 10 | 10 |
| Stop | 4.1 us | 4.1 us |

The actual returned PSF headers and log must confirm these settings. Save settings
preserve all accepted times and previously verified diagnostic nodes; no forced
timepoint window, output-only strobe, time alignment or edge exclusion is added.

## Root-controlled execution

Upload into a new isolated school directory, using the same configured container
and Xcelium PATH as the preceding verified run. Do not invoke both profiles in
parallel. Inside each profile's fresh folder:

```bash
sha256sum -c SHA256SUMS
bash run.sh 180
```

The wrapper deliberately retains its original full-sequence qualification check;
for a successful short probe, `simulator_exit_code.txt` should be 0 and
`qualification_exit_code.txt` 2 because no complete frame is expected by 4.1 us.
Read both files; do not treat exit 2 alone as a simulator failure or change the
wrapper to report an ADC pass. A timeout or malformed/incomplete PSF remains
partial evidence. Preserve all outputs and the real exit status.

Compare all accepted baseline/strict points on the original four channels
(TP−TN, RP, RN, VCM) without shifting or excluding switch edges. The limit remains
0.05 LSB = 9.765625 uV. Report all LTE/recovery/ringing notices, including suppressed
notice counts, separately from functional markers. This probe can test whether
the tool-recommended adaptive method reduces the observed numerical ringing and
cross-profile error. It cannot prove full two-frame/12-frame operation, linearity,
noise, mismatch or ADC accuracy; the prior failures remain retained.
