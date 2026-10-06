# Single-PFET mode-boundary diagnostic inputs

This historical preparation isolates the actual phase-output pfet_01v8, TT/27°C, W/L=32 µm/150 nm, m=1, with original junction geometry and S/B tied to 1.8 V. No PDK/body-network parameters change.

A continuous cosine stimulus around D=1.8 V matches the measured local drain slope −4.27529 V/ns and gate slope +8.74090 V/ns, with gate approximately 0.916425553 V at reversal. The 29.3930 ps period and four cycles are a model-isolation condition, not the ADC operating frequency or a replay of its complete history.

Matched, static-gate, slow_10x and finite_1ohm controls distinguish gate variation, slew and source-impedance effects. Their ideal sources remove the free output/load loop; 1 Ω is not a measured real driver resistance. Actual terminal voltages must be checked.

```sh
python3 verify_inputs.py
bash run_case.sh matched baseline 120
bash run_case.sh matched strict 120
```

Use separate immutable result directories and verify actual effective tolerances, observed fields, hashes and full accepted-point comparisons. Source configuration does not imply execution; actual eight-run results are in `../mode_boundary_matrix_review_v1/`. These tests cannot grant ADC or PEX PASS.
