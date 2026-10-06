# Historical school MIM flow probe

The original school cap_mim_m3__base 4×4 µm schematic/layout, native export, GDS mapping and licensed verification engines were exercised. The schematic checked with zero errors/warnings; the mapped GDS had 69 boundaries, two labels and one CAPM shape.

School DRC executed 279 rule checks and returned zero results, but MIM-specific coverage was not established. School LVS extracted zero devices against one schematic capacitor and returned MISMATCH. Quantus produced ordinary parasitic R/C without a qualified functional-MIM extraction path. Tool execution did not qualify MIM.

The original cell's metal/contact structure also differs from the current public M3/CAPM/via3/M4 reference. The unchanged failure is retained; public-tool zero DRC alone did not catch its electrical incompatibility. See [cross-check](public_crosscheck_20260923/verification_report.md).

Later independent project-owned adaptation progressed geometry, LVS and functional-instance preservation; see [r1 adaptation](../mim_adaptation_20260923/README.md). Those later results do not erase this historical failure or certify complete physical PEX.
