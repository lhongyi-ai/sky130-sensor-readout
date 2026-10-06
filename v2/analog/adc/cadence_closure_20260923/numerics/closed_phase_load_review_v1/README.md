# Reduced closed phase/load result: not repaired

The native reduced circuit contains 654 devices and 104 direct CONV gate loads. It retains real phase/output switching but omits 87 preamplifier/comparator devices, so it is not equivalent to the full ADC. Baseline/strict used gear2only/sigglobal with tenfold effective tolerance tightening and maxstep 2/1 ns.

Both reached 4.1 µs, with 4572/7958 saved points and 1/5 warnings. Strict reached recovery at the command edge, reduced the step to about 2e−19 s and skipped a breakpoint. Its raw points jumped from 4.0625 to 4.0645 µs across the entire 1 ns input rise. Exact source values at saved points do not prove that the edge was solved.

Full accepted-time differences were command 0.9 V, CONV 1.012019 V, TP−TN 193.630 mV, RP 14.5548 µV and RN 5.1778 µV. They remain failure evidence, not credible conversion-error estimates from a resolved edge.

The warning named a different device from the original CONV PFET, so the original same-node warning was not reproduced. The baseline also differed from the original full probe by 23.089 mV on TP−TN. All exact contexts remain in `review.json` and `provenance.json`; no time alignment, removed edge or relaxed gate was used.
