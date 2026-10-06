# Historical v3 AMS entry

v3 retained the complete 741-device native circuit, original RTL and stimuli. It only changed testbench `$fatal` handling to explicit display/finish markers compatible with the actual school Verilog mode. Selected saves matched 74 actual voltage nodes, including the trial bus. This changes stored outputs, not the solved circuit or accepted-time record.

The actual v3 compilation/binding succeeded, but reset release reached extreme time-step recovery; it did not establish conversion or convergence qualification. v4 subsequently used sigglobal based on the independent comparator diagnostic and retained all other circuit/stimulus/profile inputs.

Baseline global requests were reltol=1e−5, 10 nV, 100 fA and 2 ns; strict 1e−6, 1 nV, 10 fA and 1 ns. Actual conservative-preset values must be read from the logs. The original failures and historical 12-frame preparation remain intact. Current complete two-frame baseline and strict failure results are documented in `../../RESULTS.md` relative to this directory's parent integration scope; consult the top-level ADC RESULTS report.
