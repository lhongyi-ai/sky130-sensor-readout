# Historical no-reset comparator diagnostic preparation

This prepared subgraph takes all73 actual preamp/comparator devices from the audited fix1 native export, including self-bias, StrongARM, MIM, isolation buffers and holding NAND. All73 connections/parameters matched. It is not an ideal comparator and was not executed by this preparation.

TN−TP starts+1mV and changes to−1mV after6.55µs; EVAL starts5µs with625ns periods. Requested checks observe real complementary Q/QB, S/R activation, precharge and hold. Initial holding-latch state before evaluation must not count as a decision.

This is the historical no-global-reset baseline. The later reset1 fixture has87 devices and separate evidence; do not mix versions or claim that this preparation implements reset. Complete ADC/reference convergence is outside its ideal-driven input scope.
