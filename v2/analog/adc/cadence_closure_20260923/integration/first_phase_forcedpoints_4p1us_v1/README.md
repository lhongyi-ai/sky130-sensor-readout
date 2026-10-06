# Common-time first-phase diagnostic preparation

This package preserved the actual ADC, original RTL, native phase/load network and tolerances while requesting common solve points near the first acquisition transition. The goal was to distinguish interpolation from actual solver/edge sensitivity, not to remove accepted points or change the acceptance domain.

The analyzer initially failed to JSON-encode a numpy Boolean. The repair converts only JSON-boundary scalar types to equal-valued Python scalars; the failed snapshot, traceback and hashes remain in `json_boundary_fix_history/`. It does not change waveforms or thresholds.

Later analysis in `../../numerics/first_phase_commonpoints_pair_review_v2/` shows missing exact requested points, a skipped breakpoint and an additional body-node LTE relaxation. The test did not establish numerical improvement and is not an accepted repair. Preserve all natural accepted points and both complete-domain and explicitly partial diagnostics.
