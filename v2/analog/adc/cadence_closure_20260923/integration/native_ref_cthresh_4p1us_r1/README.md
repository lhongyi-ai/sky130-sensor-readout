# External reference representation control — PREPARED_NOT_RUN

Only the external reference fixture changes representation, keeping original chip741 devices, RTL, stimulus, voltage sources, 350ohm inputs and 1ohm/10nF per reference. Four old VAMS branch contributions are removed, not retained in parallel. No IC, leakage, Cmin, PDK parameter, method, tolerance or gate change. Compared with completed cthresh1p pair, only R/C representation changes. Compare against original without cthresh only as a two-step diagnostic, never claim it is a single-factor comparison.

Reason: cthresh exact alternate stamping applies to primitive capacitors; we have not verified whether it gives such a stamp to original VAMS ddt(10nF*V) contributions. This is a test of numerical conditioning at very small time steps. Native subckt equation I=(Vsource−Vref)/1ohm; Q=10nF*(Vref−Vss). No reference impedance or bandwidth improvement is claimed.

School execution must verify exactly two RREF/CREF pairs, no surviving old four contributions, cthresh=1p, DC voltages, raw domain and all original numerical criteria. This short diagnostic has zero completed frames, not full ADC qualification.

Independent static audit passed; school binding/actual counts still pending. Equivalence here is deterministic transient only: native resistor noise differs from the prior noiseless VAMS expression and requires separate treatment before noise qualification.
