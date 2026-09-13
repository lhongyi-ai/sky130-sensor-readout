# SAR Digital Controller Macro: Open-source Layout and Post-extraction Verification

**Status: Independent digital-macro verification passes. This does not complete the entire ADC or sensor-readout chip.**

Completed with the existing SKY130A PDK and LibreLane / Yosys / OpenROAD / Magic / KLayout /
Netgen, without Cadence or chip fabrication.

Actual receiver loading and setup/hold abstractions for the analog comparator interface are in
`results/interface_validation.json`, reconstructible from retained nine-corner extracted Liberty
using `python3 v2/physical/digital/interface.py`. Maximum receiver capacitance is 3.5 fF and
maximum setup is 3.06730 ns; the analog-side independent test contract uses 5 fF loading and
5 ns hold after capture. These loads exclude additional parasitics from future top-level analog wiring.

## Actual results

| Item | Result |
|---|---:|
| Macro rectangle | 150 × 150 µm, 22,500 µm² |
| Standard-cell area, including clock and repair cells | 3,674.77 µm² |
| Magic DRC / KLayout DRC | 0 / 0 |
| Netgen LVS | Circuits match uniquely |
| XOR difference between two GDS generation paths | 0 |
| Antenna, disconnection, maximum-capacitance/transition violations | 0 |
| Post-extraction STA | 3 digital-library corners × 3 RC corners, all passing |
| Worst setup / hold slack | +7.857665 ns / +0.139204 ns |
| Final placed-netlist functional regression | 687,790 checks, covering all 4096 codes |
| Estimated digital power under specified test load | Approximately 8.123 µW at TT 25°C 1.8 V |

Power uses zero-delay gate-level activity from the final netlist, standard-cell power models, and nominal SPEF;
all 1,028 activity pins have VCD annotation. It is not worst-workload power, analog-circuit power,
actual transistor supply current, or silicon measurement. Timing is checked separately with STA;
gate-level functional regression does not use SDF delays, so the two must not be conflated as timing simulation.

Detailed machine-verifiable conclusions are in `results/physical_validation.json`;
slacks, pass conditions, and input/artifact SHA-256 hashes are recorded for every library/RC corner.
Test coverage is retained in `results/routed_gate_validation.json`.

## Use and reproduction

From the repository root in the prepared offline EDA container:

```sh
SAR_PHYSICAL_RUN_TAG=final bash v2/physical/digital/run.sh
python3 v2/physical/digital/verify_routed.py final
python3 v2/physical/digital/summarize.py final
```

Existing runs are not overwritten automatically. Select a new run tag for reimplementation and use the
same tag in the final two commands. Complete intermediate data remain in local `runs/`, excluded from Git;
portable artifacts are in `artifacts/`, with key reports and frozen source snapshots in `evidence/`.

`artifacts/` includes GDS, LEF, DEF, ODB, SPEF, macro Liberty, SDF, Verilog netlists,
SPICE extracted netlists, and actual layout renders. They describe only this digital macro.

## Design boundaries and explained failures

- Clock period is 625 ns; output drive conditions are 50 fF per terminal. Comparator output must settle within
  250 ns after the falling edge and remain held beyond the next rising edge. Actual analog loading still needs verification.
- `comparator_evaluate` is an analog phase-control output, not a synchronous data receiver.
  A 10 ns clock-to-output propagation limit is retained, without an inapplicable synchronous hold check.
  Analog nonoverlap, narrow pulses, and comparator holding still require top-level verification.
- Asynchronous reset release must be synchronized by the upper level; recovery/removal for arbitrary release is unproven.
- The initial run's phase-output constraint double-counted 100 ns external delay inside the 10 ns propagation limit,
  causing failure; a later run exposed an inapplicable synchronous hold constraint on the phase output.
  Neither diagnosis changed RTL or waived real-register hold checks; the final run was fully rerun.
- The initial worst corner had approximately 1.4 fF of maximum-capacitance violation, eliminated by increased actual physical-repair margin.
- Original Yosys area mapping has a real pre-layout hold failure, ultimately repaired with clock-tree and
  delay cells. `v2/digital/results` retains that baseline rather than portraying it as originally passing.
- The 9 digital-library and RC corners are not the 45 process/voltage/temperature combinations required by the analog project.
- Passing open-source rule checks is not foundry production sign-off; this project excludes pads and tapeout.

See `THIRD_PARTY_NOTICE.md` for third-party standard-cell attribution and usage terms.
