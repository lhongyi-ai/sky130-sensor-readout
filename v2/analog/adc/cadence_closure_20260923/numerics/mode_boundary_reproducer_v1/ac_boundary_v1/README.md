# Prepared external-port AC boundary controls

This historical input package tests the same original PFET at seven independent drain biases −20/−5/−1/0/+1/+5/+20 µV around tied S/B=1.8 V, with fixed G=0.91642555277800053 V. Geometry, strict tolerances, TT/27°C and original model/body-network settings remain unchanged.

Only VD has mag=1, phase=0; VG/VS have mag=0. This is normalized linearized excitation, not a large-signal one-volt drain step. Each case requests 1 kHz–10 MHz, ten points per decade. Compute actual source-to-device current signs and the D-driven column of Y using the actual port voltage. Preserve signed cross terms and tied-S/B scope.

```sh
bash run_all.sh 60
```

Each case uses a new result directory and records source/model hashes, tool settings and exit states. Missing fields or nonfinite values are failures, not zeros. Prepared status is distinct from the later actual execution summarized in `../../ac_boundary_review_v1/`. It is neither an independent silicon reference nor ADC/PEX qualification.
