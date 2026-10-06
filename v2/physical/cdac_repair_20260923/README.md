# Independent diagnosis of routed CDAC linearity failure

An independent BFS/42-digit Decimal analysis reconstructed resistance-connected components and the full charge matrix from the original RC netlist. It did not import the earlier union-find analyzer or modify historical geometry/results.

The source has8712 MIM,26210 R and17732 C with no duplicate device names. Thirty-one components correspond to30 declared ports plus VSUBS. All8192 active MIM units remain;520 edge dummies have both terminals on EDGE_BIAS and zero differential contribution. The matrix is symmetric, row sums are zero and nonnegative capacitor edges are preserved.

All4096 codes reproduce maximum abs(INL)=3.562071LSB, DNLmin=−3.854472LSB and255 nonpositive transitions. TOP–bit coupling totals are identical before/after RC segmentation. The failure therefore is not explained by duplicate segment counting, missing suffixes, port merging or incorrect unit count in this analyzer.

B4–B11 binary carries have negative incremental weight, with counts128+64+32+16+8+4+2+1=255. B3 still has DNL−0.963083LSB, below−0.9, so merely removing nonpositive transitions is insufficient. Small-bit TOP coupling does not scale with unit weight. Exact carries, matrices and mathematical sensitivities remain adjacent.

This diagnoses the public extraction network, not its physical process coefficients or school4µm result. Later actual layout rerouting is in `../cdac_closure_20260923/`; sensitivity calculations are not re-extracted layouts.
