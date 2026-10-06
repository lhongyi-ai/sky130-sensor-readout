# Historical global-reset design review

The original holding NAND is not reset by StrongARM precharge: both buffered inputs high retain the previous state, and the initial Q/QB solution can be metastable. Digital RTL reset alone therefore does not define the analog holding-latch state.

The proposed real-CMOS gates implement RST_B=NOT(RST_N), S_BAR=BN OR RST_B and R_BAR=BP AND RST_N before the original crossed NAND. RST_N=0 yields Q0/QB1 after propagation; RST_N=1 restores actual comparator control. Add a consistent27th reset port to schematic/symbol/export/manifest and drive it from the same external reset as the original RTL through the qualified interface.

The proposal uses14 ordinary1.8V MOS. Gate-loading/delay asymmetry, reset skew, pulse width/recovery, power ramps, EVAL-high abort, both prior states and near-clock release require actual transistor tests. No IC/nodeset/leakage or artificial perturbation may hide the initial condition. Reset values do not count as comparison bits.

A symmetric TG-mux alternative has different overlap/series-R risks and was not adopted merely for lower device count. This historical proposal is distinct from actual later reset1 implementation and results in `../reset1/README.md`; reset does not itself promise a body-node numerical repair.
