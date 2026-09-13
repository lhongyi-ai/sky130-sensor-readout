# Interrupted integration matrix — not a passing regression

The initial 13-case matrix used the frozen standard-threshold-reference,
bottom-sampling + preamp candidate. It was stopped on 2026-09-08 UTC after
repeated wall-clock timeouts, while device-level reference/sampling revisions
were still being investigated. Correct partial raw codes are not completion.

Eight cases returned incomplete/timeout results. Two further cases (100-ohm
reference and −50 mV input common-mode offset) were deliberately interrupted.
Three queued cases (+50 mV common-mode and 0/1000-ohm source) were not run.
All emitted logs, source snapshots and partial results are retained.

The original parent process had a 510-second child deadline. The child runner
was subsequently extended to a 900-second SPICE deadline. The old parent could
not inherit this code change; its queue and exactly its two worker/NGSPICE
process pairs were terminated to avoid an orphan process or ambiguous state.
The updated matrix source now has a longer outer deadline. Do not claim the
old directory was rerun with that revised program.

Next qualification must use explicit frozen sources and tested phase loads,
then repeat all required cases. This interruption does not reduce the project
specification or turn a three-frame debug test into full ADC signoff.
