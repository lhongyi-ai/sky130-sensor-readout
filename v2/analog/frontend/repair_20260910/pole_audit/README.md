# Native closed-loop pole audit of the complete transistor frontend

## Result: two bounded attempts completed, but unsuitable for stability qualification

The fixed source is `../results/20260910T062811944809Z_cascoded_tail_g16/candidate.spice`, SHA256:

`564f4776c4c61872de63648816ef5aaf51555769edeca326042f287880ae1a3c`

One native `.pz` run each at gains 1 and 16 was performed in ngspice 47 without redesigning or removing circuit devices. Each was limited to 120 seconds and completed within seconds. **The current audit conclusion is governed by [qualification.json](qualification.json); the raw returned root list is not automatically treated as the real circuit's poles.**

| Nominal configuration | Native reported roots | Entries with positive real part | Nonfinite progress values |
|---|---:|---:|---|
| G=1 | 649 | 245 | Log contains `Reference value: nan` |
| G=16 | 668 | 614 | Log contains `Reference value: nan` |

These are **counts of entries reported by the native algorithm**, not confirmed physical right-half-plane pole counts. The large root counts and nonfinite progress values indicate numerical anomalies requiring investigation. They do not alone establish hundreds of real unstable modes; equally, they cannot simply be discarded to claim stability.

Section 1.2.4 of the [official ngspice manual](https://ngspice.sourceforge.io/docs/ngspice-manual.pdf) explicitly states that PZ uses numerical search and may miss roots or return too many in larger circuits. No per-root residual, linear-system eigenvector, condition-number, or independent-algorithm audit has been completed here. The final status is therefore:

`NATIVE_CLOSED_LOOP_PZ_ATTEMPT_COMPLETE_NUMERICAL_QUALIFICATION_INCOMPLETE`

## Circuit and measurement definition

- TT, 1.8 V, 27 °C, zero differential input, and 0.9 V input common mode.
- A 350 Ω sensor source resistor per side.
- The original complete transistor circuit, real biasing, and common-mode feedback, without opening any feedback loop.
- PDK `frontend_r R=2600` isolation resistors per side.
- The original PDK MIM helper circuit for 4 pF filtering per side.
- Each side's static ADC load uses equivalent replication `m=4096 mult=4096` of 4096 MIM cells sized 3×3 µm, nominally 81.28512 pF. The load was neither removed nor replaced by a small capacitor.
- `pz fp 0 fp 0 cur pol` injects small-signal current into one output and observes voltage at that same port, measuring poles of the closed-loop driving-point impedance. This asymmetric port generally couples both differential and common modes and is less likely than purely symmetric differential observation to miss fully symmetric common-mode dynamics.
- A single input/output port still cannot guarantee controllability and observability of every internal bias and common-mode state. Pole-zero cancellation, degenerate states, and numerical root-search limitations must remain explicit.

The real sampling switches do not switch in this test. It is a closed-loop small-signal experiment with a large static acquisition-phase load, and **cannot replace sampling/hold switched-load transients, large-signal behavior, power-up, or PVT verification**.

## Preservation and reproduction

Both native experiments retain their circuits, source snapshots, operating points, complete console output, and ASCII root files:

- `results/20260910T064346Z/g1/`
- `results/20260910T064427Z/g16/`

The G1 native simulation finished writing data and printed `ngspice-47 done`, but the subsequent parser failed on positive-exponent text before the process return code was saved. Only offline parsing was repaired afterward, with no simulation rerun. The G1 return code is therefore recorded as unknown with an explicit reason; the G16 return code is 0. The original G16 `summary.json` is a mechanical initial root-sign count. `audited_summary.json` and top-level `qualification.json` provide the audited conclusion incorporating method limitations.

```sh
python3 /repo/v2/analog/frontend/repair_20260910/pole_audit/analyze.py
python3 -m unittest discover -s /repo/v2/analog/frontend/repair_20260910/pole_audit -p 'test_*.py'
```

The 5 tests cover exponent-sign parsing, NaN diagnostics, refusal to treat positive real parts as automatically confirmed instability, refusal to treat only negative real parts as automatically confirmed stability, and rejection of empty results. This round contains only two circuit simulations, with no further solver-parameter attempts.

Additional tool incident: an initial interactive-help query without an X server produced a graphical-interface error. That was not taken as evidence that `.pz` was unsupported. The official manual was consulted and actual batch PZ commands verified capability. Tool capability and numerical credibility of the circuit-pole results are separate issues.
