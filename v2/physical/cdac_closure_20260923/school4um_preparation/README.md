# School 4×4µm CDAC migration preparation

Local actual-GDS/native-netlist readback checked every MIM in the693-device ADC and prepared unplaced weight-preserving templates. No new remote physical/EDA execution was performed by this preparation.

The actual ADC common sampling node uses PLUS/top. The successful old-public3µm routed array uses MINUS/bottom as common. Geometry scaling alone would therefore preserve the wrong physical access convention. Reuse allocation/routing ideas only after rebuilding the common-plate and bit-access network.

The project-owned school unit has CAPM[0,0]–[4,4]µm on89:44, M3[−0.4,−0.4]–[4.4,4.4] on70:20 and M4[0.1,0.1]–[3.9,3.9] on71:20. Its81 via3 cuts are0.2×0.2µm on70:44, pitch0.4µm. PLUS is M4 and MINUS M3. Overall envelope is4.8×4.8µm; small pin markers are connectivity tags, not calibrated RC reference planes.

Binary weights remain1…2048 plus dummy,4096 units per side. The model/RC ownership and CAPM physical gate remain unresolved. Subsequent actual two-device/2×2 access controls are documented separately; `formal_ADC_PEX_allowed=false`.
