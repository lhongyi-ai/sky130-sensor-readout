# Day 5 isolated optimization reconnaissance

This directory compares the frozen Day 4 OTA against three deliberately
bounded geometry changes. It is an engineering tradeoff screen, not a second
production selection flow.

Run the complete 32-deck experiment from the repository root:

```bash
experiments/day5/run.sh
```

The script uses the project-pinned IIC-OSIC Docker image for both simulation
and analysis, regenerates every corrected SPICE deck and raw result, and then
rebuilds the CSV audit tables and `assessment.md`. The generated
`day5_manifest.json` binds the baseline to the
current Day 3 selected-parameter JSON, the retained Day 3 compensation
before/after table, the Day 4 manifest, the pinned PDK identity, and the exact
workflow sources. Its deterministic hash is stamped into all generated SPICE
decks, all 48 raw TSVs, and all nine result CSVs.

The run exits unsuccessfully unless all of these contracts pass:

- the exact 32-deck, 32-log, 32-exit-record, and 48-TSV file sets;
- exact row, column-name/order, finite-value, and declared frequency/time-grid
  checks (including scale zero for operating-point files);
- exactly one non-boundary downward UGB crossing per loop curve;
- the strict Day 4 slew-rate and one-percent settling definitions;
- Day 4-equivalent 1-Hz gain plus M1–M10 saturation-margin checks at all three
  ICMR checkpoints; and
- baseline A0, UGB, and PM agreement with the selected Day 3 compensation
  evidence.

The runner is fail-closed. Before starting, it snapshots the last outputs. Any
failed generation, simulation, or audit is copied under `failed_runs/` with its
decks, logs, exit records, and TSVs before the last output snapshot is restored.
Four first-attempt testbench/model-bin errors remain under
`retained_failures/attempt1` as permanent provenance.

The production decision is recorded in `decision_summary.csv`: keep the frozen
Day 4 baseline. The nominal-only `first_stage_l2` candidate is retained as a
rejected tradeoff because its PSRR improvement comes with lower phase margin,
worse high-end ICMR, and substantially greater device area without a PVT rerun.
No Day 5 candidate may be promoted from this nominal screen. Promotion would
require the complete Day 4 campaign again: all 13 PVT points for the core
metrics, slew rate, and M1–M10 operating points; strict nominal P01 one-percent
settling plus the Day 4 transient status at the remaining PVT points; the
121-point continuous ICMR; bidirectional output swing; CMRR/PSRR curves; input
noise; 1/2/5-pF load stability; and the complete Day 4 integrity audit.
