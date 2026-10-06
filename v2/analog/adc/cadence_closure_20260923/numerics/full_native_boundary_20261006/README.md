# Complete native first-edge boundary control — October 6, 2026

The 654-device reduction omitted 87 preamp/comparator instances and could not establish reproduction of the complete ADC warning. This control keeps **all 693 ADC and 48 phase instances**, including the complete reset connection and those 87 instances. Native device records are retained byte for byte. The source-native SHA-256 must be supplied explicitly and is checked before preparation.

The original saved short-domain run contains 4,951 points. Before creating a deck, the builder checks every one against the analytically defined reset release at 1.885 us, the first sample-command edge at 4.0625 us, constant input/reference sources, zero EVAL and all twelve zero trial bits. Both edges retain the original linear 1 ns ramp. A changed reset, trial bit, port order, instance count, native hash or incomplete reference aborts preparation. No comparator outcome is replayed.

This is a **pure Spectre boundary diagnosis**, not an original-RTL conversion. Native source R/C is deterministically equivalent to the original bench equations; it adds thermal noise absent from those original VAMS equations, so noise equivalence is not claimed. PWL and AMS event handling may differ, and must be measured rather than assumed.

Run baseline and strict profiles serially in separate retained directories. The local analyzer compares all accepted-time unions with the original AMS baseline and with each other, including TP−TN, RP, RN, VCM, reset, sample command and phase/comparator signals. Missing edge quarters and incomplete runs remain explicit failures. No time alignment, edge deletion, extrapolation or lower numerical threshold is allowed. The original 9.765625 uV criterion remains unchanged.

```sh
python3 -m unittest test_build test_analysis
python3 build.py --native /path/to/frozen/reset1_native_bound.scs \
  --native-sha256 ORIGINAL_NATIVE_SHA256 \
  --reference /path/to/original/adc_closure_tran.tran.tran \
  --model /path/to/authorized/sky130.lib.spice --output prepared
```

The original raw reference, licensed simulator and installed PDK are local prerequisites and are not published. Fresh output directories are required. A short-domain success would authorize a diagnostic comparison with the full original-RTL run; it cannot itself qualify two frames, reset interruption, twelve frames, noise or PEX.

## Repair sequence

1. Establish complete-load boundary reproduction, and retain every numerical warning and source edge.
2. Resolve effective body-network/terminal-charge semantics or obtain a supported model/simulator explanation. Single-transistor or DC/AC evidence alone does not establish a model defect.
3. Test one justified solver, interface or circuit change at a time. Reject ringing, skipped edges, timeout prefixes and unproven noise equivalence.
4. Return to the unchanged SAR RTL and real comparator. Complete two frames and reset-abort at both accuracy levels, then the full original-domain comparison. Only that qualification enables twelve frames and the long campaigns.

The MIM physical coupling references and internal/external RC boundary remain separate prerequisites; `formal_ADC_PEX_allowed=false`.

Actual execution and failures are recorded in [RESULTS.md](RESULTS.md) and [review.json](review.json).
