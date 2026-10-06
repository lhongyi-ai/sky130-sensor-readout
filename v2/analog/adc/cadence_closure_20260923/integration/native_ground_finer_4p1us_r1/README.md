# Native ideal ground branch: prepared representation diagnostic

**PREPARED_NOT_RUN.** This package changes only the numerical representation of
the existing ideal zero-volt ground branch. It does not alter a physical component,
source value, chip pin, device model, noise source, stimulus edge or tolerance.
All previous failed and partial runs remain unchanged.

The source is `../native_ref_finer_4p1us_r1/finer`, verified against its manifest.
The input is `finer/`; the exact changes are in `single_factor_representation.diff`
and the bounded static checks in `preparation_audit.json`.

## Exact change and ground connection

The single original contribution `V(vss) <+ 0.0;` is removed. One named HDL
instance `p2_ground_fixture ground_ref(.VSS(vss))` is added. Its native Spectre
definition declares `global 0` and contains only:

```spectre
subckt p2_ground_fixture (VSS)
VGND (VSS 0) vsource dc=0 type=dc
ends p2_ground_fixture
```

The circuit's electrical `vss` is the fixture's VSS port, while the negative
terminal is the canonical simulator global ground, not a second floating port.
The chip's VSS port is unchanged; there is no HDL logic-constant connection,
direct short substituted for the branch, or additional parallel zero-volt source.
Control include/portmap/config follow the already verified reference fixture
convention. School elaboration must still verify this new one-port binding.

All remaining six voltage contributions are byte-identical: VDD, VCM, both
reference-source voltages and both dynamic inputs. Both 350-ohm input conductance
contributions, the two native reference RC fixtures, 741-device chip, original
controller/interfaces/sequence and save list are unchanged. The wrapper adds the
ground fixture to its input hash log; the launch command and timeout behavior
are otherwise unchanged.

## Hypothesis and limits

The preceding finer log repeatedly reports Newton difficulty involving the VAMS
top-level `vss_flow` unknown, sometimes with much smaller MOS body residuals.
Moving the ideal ground branch to a native voltage-source stamp tests whether
its numerical representation contributes to that difficulty. This is a matrix
representation hypothesis, not proof of a circuit or simulator defect.

The name `vss_flow` can also reflect the other retained contributions referenced
to vss. The replacement may leave that quantity and its convergence problem
present. No tolerance is loosened and no leakage, cmin, IC or artificial damping
is introduced to force an answer.

An ideal DC zero-voltage source adds no resistor or explicit noise source, so this
change preserves that branch's ideal/noiseless assumption. The *earlier* native
reference-resistor change still requires separate thermal-noise accounting; this
diagnostic does not qualify ADC noise performance.

## Unchanged finer profile and root-controlled execution

Expected actual settings remain reltol=1e-8, vabstol=1e-10 V,
iabstol=1e-15 A, maxstep=0.5 ns, gear2only, lteratio=1, cthresh=1p,
sigglobal, conservative, 27 C, TT and stop=4.1 us. These are expectations until
checked against the returned PSF/log; conservative scales the requested global
reltol=1e-7 to actual 1e-8, as established in this installation.

In a new isolated school folder, with the already verified container environment
and Xcelium PATH, root may run one bounded job from `finer/`:

```bash
sha256sum -c SHA256SUMS
bash run.sh 300
```

This preparation itself launched no EDA. Retain real simulator exit and the
separate qualification exit. A completed short run still has expected
qualification exit 2 because it completes no conversion. Do not change that into
ADC PASS.

After execution, verify: generated VSS-to-VSS inout portbind, successful native
fixture instantiation, inventory containing exactly one additional native voltage
source, zero surviving old VAMS ground contributions, vss=0 V in saved data,
unchanged other DC voltages, actual precision settings, complete 0–4.1 us time
coverage and all warnings/recovery diagnostics. Stop on duplicate/shorted-source,
floating-node, portmap or missing-save errors. A failed attempt remains evidence.

First compare this with the original **same-precision finer** run to isolate
representation. That cross-representation diagnostic alone is not a precision
convergence pair. If it improves the problem, qualification still requires a
separate same-representation pair using the original four-channel, all-time
9.765625 uV gate. No switching edge, failed point or LTE warning may be silently
excluded, and the short test cannot replace two-frame or twelve-frame ADC gates.
