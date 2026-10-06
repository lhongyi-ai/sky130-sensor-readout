# Actual ten-nanosecond input-edge control

The native ADC/phase circuit was unchanged. SAMPLE_CMD rise/fall changed1→10ns and delay to4.058µs, preserving its4.063µs half-rail time. The actual8µs run completed but retained minimum-step recovery and LTE relaxation, so numerical qualification failed.

The internal NL peak changed only1.92445→1.92261V and TOPB remained approximately1.91463V. Slower external input did not eliminate internal switching difficulty. No initial-state, leakage or prerecorded-comparison shortcut was added.

The actual school tool rejected reltol on the tran line with SFE-106 and ignored it. Both logged profiles actually used reltol1e−6, Vabs10nV, Iabs100fA and maxstep2ns. Later inputs remove the invalid analysis parameter and specify requests in options, then verify realized settings. Original failed inputs/logs remain intact.
