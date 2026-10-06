# Functional DSPF instance output control

The first actual QRC run completed but printed only parasitic R/C and commented instance endpoints. Installed Quantus documentation states that DSPF/SPEF disable_instances defaults to true and suppresses the transistor-level LVS Instance section.

Use the documented output control:

```text
output_db -type dspf -disable_instances false
```

Run in a new directory; do not manually insert an ideal capacitor or rewrite DSPF. The actual matched PVS input already contains the generic MIM device, measured dimensions and PLUS/MINUS endpoints, so output suppression is the first issue to correct.

Verify a real noncomment functional instance with the measured w/l and two endpoints connected through the extracted network. Do not bypass series parasitics. Preserve the original omitted-instance attempt. Later parent-r1 results confirm direct instance retention; this fixes output/recognition, not CAPM physics or double-counting boundaries.
