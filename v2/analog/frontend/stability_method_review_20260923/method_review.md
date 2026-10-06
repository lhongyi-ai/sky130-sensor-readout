# Four-channel frontend stability: implementable return-difference experiment and qualification limits

This independent method review is dated September 23, 2026. It did not operate LinuxLab, change circuits or run Cadence. Status: **METHOD_PROPOSED / GLOBAL_STABILITY_NOT_QUALIFIED**. The derivation and checks concern linear algebra, not qualification of the school frontend.

## Conclusion

Four **closed-loop series-voltage injections, measuring all four injection-branch currents**, can construct an exact characteristic-determinant ratio relative to a specified finite-series-resistance reference network. Original MOS devices, parasitics and bidirectional loading are retained; neither zero gate current nor unilateral signal flow is assumed.

Those four AC runs alone do not establish global stability. The complete right-half-plane (RHP) state count of the reference and the low/high-frequency Nyquist contour closure are also required. The reference still contains all active devices and **cannot be assumed stable**. Existing PZ uses a fixed-frequency equivalent for frequency-dependent BSIM4 quantities, so the existing 104 approximate poles cannot automatically supply that evidence.

Native STB remains useful for required local differential/common-mode margins, listing every crossing. STB and the determinant ratio are different quantities; the determinant must not be converted into an arbitrary global phase margin.

## 1. Fix four physical cuts

Use the existing device connections in `p2fe_c06_stb_school_r1`. An independent copy replaces three STB probes with four ideal independent voltage sources while retaining the 133 core objects.

| Channel | A: driving side | B: receiving gate side |
| --- | --- | --- |
| p | XPGA_SUMPOS | DM_INP, MIP gate |
| n | XPGA_SUMNEG | DM_INN, MIN gate |
| c1 | XPGA_XOTA_NCM | CM1_GATE, both PMOS load gates |
| c2 | XPGA_XOTA_CMG | CM2_GATE, both NMOS output-load gates |

Each source has positive terminal A, negative terminal B and `dc=0`. Define `e=v(A)-v(B)` and `i=I(VINJ)` positive from A to B. Here i is current **through the injection source**, not its sign-reversed delivered current. Set one source to AC=1 per run and the other three to AC=0. The original nonzero VINP/VINN AC stimuli must also be zero, as must every external independent AC signal. Closing the four zero-DC sources must preserve exact equivalence to the native circuit.

Measure `Y_C[:,j]=i/e_j` in siemens, retaining all eight A/B voltages for direction/equivalence checks. C denotes the original closed circuit. Keep all four rows/columns and off-diagonal coupling, rather than only differential response to differential excitation.

## 2. Exact determinant identity

Write the complete small-signal MNA, excluding only those four connection constraints, as K(s), including existing ideal-source constraints and internal device states. B is the four-branch incidence matrix; unknowns are internal variables x and branch currents i:

```text
M_C(s) [x;i] = [0;e]
M_C(s) = [ K(s)   B ]
         [ B^T    0 ]

U = [0; I4],     J = [0 I4]
Y_C(s) = J M_C(s)^(-1) U
```

Replace each ideal connection with a positive finite resistance `R=diag(Rp,Rn,Rc1,Rc2)`, linearized at the same operating point. Branch constraints become `B^T x − R i = u`:

```text
M_R = M_C − U R J
F_R/C = det(M_R)/det(M_C) = det(I4 − R Y_C)
D_C/R = det(M_C)/det(M_R) = 1/F_R/C
```

This follows directly from the matrix determinant lemma. K(s) may be nonsymmetric and include cross-capacitance and reverse transmission; no loading is discarded. R defines the reference system explicitly; the original system remains R=0. Do not choose R to obtain an attractive curve. Record it and cross-check different values.

Four AC runs of the reference give `Y_R=J M_R^(-1)U` and permit independent checks:

```text
Y_R = (I4 − Y_C R)^(-1) Y_C
D_C/R = det(I4 + R Y_R)
(I4 − R Y_C)(I4 + R Y_R) = I4
```

The matrix identity is stronger than comparing determinants alone. It exposes incorrect port direction/units, unintended AC excitation, operating-point drift and wrong currents. Prefer linear solves, slogdet and SVD over explicit inversion. Record high condition numbers.

**Sign unit check:** for a test network `G || C`, injection-source current is `i=−(G+sC)e`. Thus `F_R/C=1+R(G+sC)`, with reference pole `s=−(1+RG)/(RC)` in the left half-plane. Reversing that sign would incorrectly classify a passive circuit as unstable.

## 3. Build the reference network

Use `A — resistor(Rk) — X — voltage_source(Udc+u) — B`, with current positive A→B. Read original closed-loop current I0k and fix `Udc=−Rk*I0k`; the original operating point then satisfies zero total voltage drop. This fixed DC compensation has AC=0, with injection superimposed on it. For the first single-point numerical experiment, `[100,100,1000,1000] Ω` is an initial value, not a circuit-design component or stability guarantee. Repeat at 0.1× and 10× to check count consistency.

Measure DC equivalence using all node voltages, MOS id/gm/gds/capacitances and major branch currents. A different DC solution or significantly different linearized model invalidates application of the identity to those matrices. Matching output voltage alone is insufficient. Relate numerical equivalence tolerances to DC solve precision and operating-point sensitivity.

The reference is not simply all loops open: resistors still transmit signals, and internal loops and bidirectional interactions remain. Its change is explicit and implementable with ordinary elements, but the RHP count cannot be inferred from topology alone.

## 4. Use a power-consistent differential/common-mode basis

Start with physical injections and transform afterward to differential mode, input common mode, CM1 and CM2. Define `e=S u`:

```text
S = [[1/2, 1],[-1/2, 1]] ⊕ I2
u = [e_p−e_n, (e_p+e_n)/2, e_c1, e_c2]^T
j = S^T i = [(i_p−i_n)/2, i_p+i_n, i_c1, i_c2]^T
Y_modal = S^T Y_physical S
R_modal = S^(-1) R_physical S^(-T)
```

This preserves `e^T i=u^T j` and the determinant ratio. Halving input common-mode current, or changing the voltage basis without transforming R, gives the wrong coupled return difference. For `Rp=Rn=r`, modal resistances are differential `2r` and common-mode `r/2`.

## 5. Return difference and the missing RHP-count evidence

Let Z_C and Z_R count finite RHP characteristic roots of the **complete linear systems**, including algebraic multiplicity, rather than poles visible in one input/output transfer function. On a positively oriented (counterclockwise) closed RHP contour Γ:

```text
W = Δarg D_C/R(Γ)/(2π) = Z_C − Z_R
Z_C = Z_R + W
```

The fixed orientation here follows the imaginary axis from +jΩ to −jΩ, then the right semicircle back to +jΩ. Reversing frequency traversal requires reversing the winding convention. Stability requires Z_C=0 and no imaginary-axis roots. If the reference has one RHP pole, a stable original system requires W=−1, not zero.

Hidden modes can occur in both systems and cancel from D. For example, a shared `(s−3)` factor unexcited/unobserved by these ports is invisible in D. Zero winding alone therefore cannot rule out hidden unstable modes. The complete reference-state count supplies the missing information. Cuts need not cover every graph-theoretic loop, but uncovered dynamics cannot be assumed stable.

Two acceptable approaches to reference counting are:

1. Obtain the complete finite-dimensional rational small-signal state description, including internal states such as NQS. Count reference generalized eigenvalues while checking singular matrices, infinite algebraic roots, cancellation options and numerical convergence; alternatively count an equivalent complete characteristic determinant in the complex s-plane.
2. Construct a provably stable reference by exactly nulling all active gain while retaining necessary passive/internal dynamic terms, then continuously restore controlled sources to obtain a normalized determinant. Ordinary external gate clamping is not device gain nulling. This requires native tool support or a verified complete linear model; a few constant gm/gds/C values cannot be substituted for BSIM4 while claiming the original model.

The present PZ warning means its pole count applies to a fixed-frequency approximation. Agreement across frequency settings, precision and gmin is sensitivity evidence, not proof that frequency-dependent dynamics are absent. Read effective model options and supported model behavior to determine whether the warning corresponds to enabled dynamics. Do not disable features merely to remove the warning. Without the complete count, retain `REFERENCE_RHP_COUNT_UNVERIFIED`.

## 6. Nyquist endpoints and numerical qualification

- Extend positive frequencies by conjugate symmetry only after verifying a real-coefficient model and fixed operating point. Retain complex matrices, not only magnitude/phase screenshots.
- Compute/check finite D(0). Poles/zeros at the origin or imaginary axis require explicit indentation/counting rules. Imaginary-axis modes fail internal stability; starting at 0.01 Hz does not bypass them.
- Do not close finite high-frequency endpoints with an arbitrary straight line. D need not tend to one; the series-R reference can change DAE constraints and infinite-root structure. D tends to zero in the passive RC example above. Obtain the high-frequency order q and leading term `c*s^q` from the complete model and verify the asymptote on the right semicircle, whose phase contribution is qπ. Direct complex-s determinant evaluation permits sampling that actual semicircle. A visually flat AC tail is insufficient.
- Start with a broad grid and refine small singular values, small |D|, fast phase changes and every crossing. A suggested phase increment below 10°, with bisection checks, is a sampling strategy, not a stability target. Also check curve proximity to the origin within each segment to avoid missing narrow windings.
- Compare at least two grid densities, endpoint extensions, precisions and R values. Record both matrix-identity errors, condition numbers, minimum singular values, contour phase residual and final integer count. An unstable integer estimate remains numerically unresolved.
- Report all STB 0 dB/critical-phase crossings, directions and PM/GM definitions. No crossing means not applicable, not automatic margin success. The required ≥60° remains an additional local condition; determinant distance cannot replace it. Singular values also depend on normalization, so fix the power basis and units.

## 7. Minimum experiment sequence and stopping conditions

1. Freeze the native 133-object netlist. Build four zero-drop sources and verify contraction, DC and ordinary-AC equivalence.
2. At TT, 1.8 V, 27°C, gain=4 and a fixed acquisition-on operating point, run the four AC columns and save Y_C plus complete source/node values.
3. Build finite-R references with fixed DC compensation from that operating point. Verify DC equivalence, run reference columns, and check matrix identities and modal-basis invariance.
4. First verify acquisition and counting using single-transistor/passive-RC and synthetic stable, unstable and hidden-unstable examples. Included code validates the algebra locally; Spectre acquisition is not yet validated by these checks.
5. Obtain complete reference RHP counts and frequency-contour closure. If only fixed-frequency PZ is available, report a completed return-difference experiment with global stability still incomplete. Steps 1–4 alone cannot pass M2.
6. After closing the method chain, apply it to the same frozen version across gains, acquisition/hold states, prescribed PVT, operating points, asymmetry and mismatch. Fixed-state small-signal stability does not establish periodically switched stability. Real sampling, startup, overload and steps remain required, with periodic operating-point/Floquet/PSTB evidence if necessary.

## 8. Invalid shortcuts

- **Clamp receiving gates to AC ground and read driving-side voltage:** this changes gate-capacitance and reverse-current loading. Without retained current reaction and a determinant derivation, it is not the original return difference.
- **Restore connection with a unity VCVS:** its input draws no current, and receiving-side current returns through its output source rather than the driving node. Equal DC voltage does not make it a wire; full bidirectional port constraints must be established.
- **Multiply four STB traces:** conditional return ratios with other loops closed are not an ordered factorization against a shared known reference, so their product is not the complete characteristic determinant.
- **Use the old det(K)/det(Yee+Yff) and assume zero reference RHP poles:** the old code correctly marks the reference unverified. Active-reference and hidden-mode factors remain unresolved after Schur elimination; renaming status cannot qualify it.
- **Combine approximate QZ zero-RHP count with STB PM≥60°:** if QZ uses only a fixed-frequency approximation, this still does not prove full stability of the original frequency-dependent model.

## Sources and local checks

Tian et al. define return difference through characteristic-determinant ratios and distinguish bidirectional loop algorithms from device gain nulling. Their conditions do not automatically hold for arbitrary multiple loops. [Author's original paper](https://kenkundert.com/docs/cd2001-01.pdf), [IEEE DOI](https://doi.org/10.1109/101.900125). The finite-series-R matrix formulas above are independently derived from the stated complete MNA; Spectre STB is not claimed to output this matrix directly.

Installed stb_help.txt and pz_help.txt were reviewed and their limits summarized, without redistributing licensed documentation. The native STB netlist and older run_multiport.py were independently examined. Input hashes and synthetic checks are recorded here.

`verify_rank_update.py` checks 71 nonsymmetric four-port MNA cases, determinant identities, bidirectional inverse relations, modal invariance, passive signs, Nyquist orientation and hidden-unstable counterexamples. Output is `synthetic_method_checks.json`. These checks do not count as actual frontend qualification.
