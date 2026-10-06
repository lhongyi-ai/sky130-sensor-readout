# Frontend migration audit — September 23, 2026

This historical audit checked frozen local sources and evidence before native migration. candidate_06 in the dynamic and qualification directories was byte-identical, with source SHA-256 `a4ed567d6a5b1f8853124602fd3f0503118e77c751a6fc3152f772b89483a5f1`. The 415-file delivery manifest and six existing method/evidence tests passed locally; no new EDA run was performed by this audit.

Three-gain nominal static and real sampling-load controls existed, but formal stability, sampled noise and 45-PVT qualification did not. Twenty-six earlier ngspice launches included retained noise-export failures. Local dual-injection results did not establish global coupled-loop stability: reference-system RHP poles, hidden modes, closed Nyquist contour and reliable full-system roots remained unresolved. A small algebraic reconstruction residual was not a transistor Jacobian eigenvalue residual.

The proposed next step was a G4 native OP, 1 kHz AC and three-point DC canary, followed by full native netlist matching and suitable school stability methods. Later actual migration results are documented separately in `first_cadence_frontend_independent_review.md`. All frozen specifications and failures remain unchanged; this dated audit is not the current status table.
