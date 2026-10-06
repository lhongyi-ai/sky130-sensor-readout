# CAPM multiport control specification

Status: SPEC_ONLY / NOT_RUN. Freeze geometry, port positions, substrate treatment, material definitions, process version and reference uncertainty before physical qualification. Do not infer a dedicated dielectric from area density or invent missing values.

Controls comprise isolated 4×4/4×8/8×8 µm devices; fixed-core lead extensions; contact count/position variants; same-layer neighbors at several legal separations; independent M2/M5 routes; and matched blanks. Keep a documented substrate/reference terminal. These variations separate functional capacitance, external lead RC, contact ownership and neighbor/substrate coupling.

Drive each independent port with unit AC while other nonreference ports are zero, measuring currents into the network to form each Y column. Preserve all signed terms. Report Re(Y), Im(Y)/ω, substrate constraints, Maxwell-matrix symmetry/charge conservation/semidefiniteness and lossy-network reciprocity/passivity. Do not silently symmetrize or clip invalid eigenvalues. Reconstruct differential/common-mode/neighbor responses and compare with direct excitations.

Assign every functional C, internal metal/contact R, external lead, substrate and neighbor term to explicit shared reference planes. Retain model-only, bounded-extraction-only and assembled-network results. Physical accuracy requires an independent applicable reference with uncertainty and an ADC-budget-based tolerance fixed before comparison. Solver convergence, KCL and sensible distance trends are necessary but insufficient. Arrays follow only after these controls pass.
