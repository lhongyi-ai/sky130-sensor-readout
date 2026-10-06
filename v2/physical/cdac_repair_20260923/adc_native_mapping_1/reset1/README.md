# reset1 native implementation and numerical limits

The new native ADC schematic/symbol has693 devices:631 MOS,32 process resistors and30 parameterized MIM, with27 ports including RST_N. CDF readback, all693 exported objects, both-view ports and schematic zero-error/zero-warning checks passed. Old fix1 remains intact.

Fourteen real CMOS devices implement RST_B=NOT(RST_N), S_BAR=BN OR RST_B and R_BAR=BP AND RST_N. Reset forces Q0/QB1; release leaves decisions to actual StrongARM/buffers/holding NAND. The added BP/BN loads are asymmetric and require timing/noise/precision review.

The87-device comparator fixture's first150ns snapshot was too early and failed; the real S/R path activated near166ns. A second9.2µs fixture using the original312.5ns evaluation window passed five real positive/negative decisions, hold/precharge and EVAL-high reset. A stricter same-input run also passed those functional checks, but both retained five printed LTE warnings.

Actual tolerance tightening was tenfold, maxstep2→1ns. Full-union PREP−PREN difference40.006µV and common1ns-grid22.308µV exceed the9.765625µV diagnostic threshold; selected decision-instant agreement cannot waive this. Fast-latch nodes differed much more due partly to edge-time sensitivity.

This fixture has ideal TN/TP and no actual CDAC/RP/RN/VCM network; the original complete-ADC physical gate was NOT_RUN at this historical point. Subsequent integration and actual two-frame results are separate. Native, functional, numeric and PEX states must not be conflated.
