# Common-point pair: no demonstrated improvement

Both actual 741-device ADC/RTL diagnostics reached 4.1 µs, with no complete conversion. Baseline/strict used identical models/stimuli and gear2only/sigglobal, with effective reltol 1e−6/1e−7, Vabs 1e−8/1e−9 V, Iabs 1e−13/1e−14 A and maxstep 2/1 ns.

The saved domains begin at 2/1 ns, so neither covers the requested t=0 boundary. Of 2001 requested common times, baseline/strict matched 1997/1976 and both matched only 1974. Natural accepted points were retained. Strict explicitly reported a skipped breakpoint around 4.06328 µs and an LTE relaxation on another phase NFET around 4.07479 µs.

Complete common-domain TP−TN differences remained approximately 854.989 µV, compared with approximately 854.869 µV previously. Dense requested times did not establish an improvement or eliminate model/body recovery. Local small errors and near-time matches do not qualify the missing domain or all requested solve points.

The repaired analyzer changes only numpy-to-Python scalar conversion at JSON serialization. Original failure snapshots and raw results are preserved. The resulting analysis exit 2 denotes actual completeness failure. Evidence: `review.json` and the adjacent input/history records.
