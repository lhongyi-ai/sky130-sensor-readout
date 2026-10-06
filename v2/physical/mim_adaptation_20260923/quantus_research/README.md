# Quantus MIM adaptation: bounded documentation review

The examined school Quantus21.2/SKY1300.0.3 typical technology covers ordinary M1–M5/via1–via4. Its associated LVS/layer setup contains no capacitor/CAPM mapping, and the six compiled blocking groups are MOS. This is consistent with the original missing functional capacitor.

Installed documentation supports runtime layer mapping, actual LVS device/parameter inputs and device-region exclusions. Those interfaces permit isolated experiments without changing the global PDK. They do not prove that ordinary M3/M4 data correctly model the dedicated CAPM electrode, dielectric or external coupling.

The technology file hash is `14c40ca701ecd4a87dc0b6b5e754262f30becadc4c3086f0ef6807ff6b6f27ca`. Only necessary metadata and authored configuration are published, not technology/manual source. This particular review did not execute QRC, PVS or Spectre; actual later experiments are in the parent r1 report.

Preserving a functional model plus some parasitic R/C is not complete physical PEX qualification. Layer omission, unmapped-layer behavior, substrate assumptions and RC exclusion must remain explicit.
