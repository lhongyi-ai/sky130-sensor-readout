# Cross-revision calibration finding

The cold/high-supply `linearity_tt_1.98_-20_g16_r1_sw` run was started by a
sequential shell command after the live candidate had already changed. Its
circuit snapshot has SHA-256
`15796319f23b6434cf9c83b886ab6edfffba4fcff0522b59f6bc0a4882723019`, whereas
the referenced nominal calibration snapshot is
`c0bf025bd17662d036ff0e8ddd2d2d33b74dbb1a6d42d8f53fd5e61d308de95c`.

Therefore its reported fixed-calibration pass is **INVALID evidence**, even
though the raw DC simulation completed. Preserve the raw files and numerical
result as a workflow failure. The hot/low-supply comparison does have identical
snapshots and remains a valid DC-only comparison (the source revision is
common-mode unstable in transient).

The G4 nominal run in this folder likewise uses the later CM-degenerated
snapshot. Its nominal DC result is not invalid merely because of the folder
name, but must be attributed to its actual source hash, not to `fdda2` shorthand.

The runner now rejects cross-revision calibration before accepting results.
All later multi-command tests must pass a frozen snapshot to `--core`.
