# Ground-reference declaration: prepared, not run by this reviewer

The only circuit-description change from `native_ref_finer_4p1us_r1/finer` is:

```diff
   electrical vdd,vss,ip_source,in_source,inp,inn,rp_source,rn_source,rp,rn,vcm;
+  ground vss;
...
-    V(vss) <+ 0.0;
```

All remaining source contributions, native reference RC, 741-device chip,
original RTL, stimuli, settings, save list and execution wrapper are byte-identical.
There is no added native zero-volt source, resistor, capacitor, noise, IC or leakage.

## Verified language basis and hypothesis

The official [Accellera Verilog-AMS LRM 2.4, §3.6.4](https://www.accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf#page=58)
defines grounding for a net already declared with a continuous discipline and
identifies it with the circuit's global reference node. The example uses
`electrical gnd; ground gnd;` (printed page 43, PDF page 58).
Here vss is already electrical before its ground declaration. This standard
syntax has been checked; this package's school compilation remains unverified.

The prior native voltage-source replacement kept an explicit ground-branch
unknown: failure moved from VAMS `vss_flow` to native `VGND:p` rather than being
resolved. This new representation declares the reference node directly, removing
that redundant ideal-branch unknown while preserving the zero potential condition.
It is a targeted numerical hypothesis from actual diagnostics, not proof that
grounding is the sole cause. Body-node and other source-current failures may remain.

The ground declaration is a continuous electrical reference, not a digital constant
or floating pin. All ideal source assumptions remain unchanged. The earlier native
reference-resistor thermal-noise distinction remains; no ADC noise result is claimed.

## Frozen execution contract

Input folder: `finer/`. Its manifest, SHA256SUMS, `single_factor.diff` and
`preparation_audit.json` preserve provenance. Expected actual settings remain
reltol=1e-8, vabstol=1e-10 V, iabstol=1e-15 A, maxstep=0.5 ns, gear2only,
lteratio=1, cthresh=1p, sigglobal, conservative, TT/27 C and stop=4.1 us.

Only root schedules the single isolated school task with the already verified
container and tool PATH. From a fresh copy of `finer/`:

```bash
sha256sum -c SHA256SUMS
bash run.sh 300
```

Check actual compilation, grounding/alias evidence, unchanged non-ground devices
and source potentials, absence of both explicit ground-flow branches, actual
settings, complete time domain and all numerical warnings. If the global-ground
alias no longer appears as a separate saved `vss` trace, verify its actual alias
mapping rather than treating an unexplained missing trace as success. The original
save list is deliberately preserved so this remains a two-line input change.

Timeouts, missing bindings or incomplete raw data remain failures. Qualification
exit 2 is expected for a completed short diagnostic with zero completed conversions.
Compare first at the same finer precision to isolate representation, and then use
a same-representation precision pair if it warrants one. Keep the original full-time
four-channel 9.765625 uV gate and all LTE warnings; this short test cannot qualify
two-frame/12-frame ADC accuracy.
