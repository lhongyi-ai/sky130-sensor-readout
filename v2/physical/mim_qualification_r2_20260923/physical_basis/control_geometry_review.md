# Ordinary-interconnect control geometry review

Static expansion of seven SKILL layout calls matched the independent JSON geometry and pin definitions exactly. All rectangles lie on a 5 nm grid; pins are inside the specified M3/M4 metal. None of these controls contains CAPM.

M3/M4 lines are 1 µm wide with nominal lengths 10/50 µm, but pin centers are separated by 9.98/49.98 µm. The narrow 0.02 µm pin regions can add spreading/meshing effects. Do not require a fivefold absolute resistance ratio or treat these controls as calibrated sheet-resistance measurements.

The via fixtures have one cut, four parallel cuts or two series cuts connected through M4 without a bypass. Total port resistance includes metal access and spreading, so it is not simply one-quarter or twice the one-via total.

PVS regards both labels as one conductive net. QRC must retain distinct physical endpoints connected through finite resistances; a single alias with no measurable A–B network cannot pass temperature testing. This review was static only; actual subsequent r2 network results are separate.
