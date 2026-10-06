# School MIM/public SKY130A cross-check

The unchanged school MIM GDS was checked locally using the existing public-tool container, not school PVS/Quantus. Its CAPM marker is 89:44, but bottom/contact/top layers are 69:20/69:44/70:20. The current public structure expects 70:20/70:44/71:20 for M3/via3/M4.

Magic merged PLUS/MINUS on the original school geometry. KLayout zero violations did not prove electrical compatibility. Independent synthetic positive/negative geometry controls and rule inspection showed that public MIM checks and device extraction exist, but cannot be applied by matching only cell names or a CAPM marker.

Actual bridge/CIW read-only access and database queries succeeded. No school PDK, original layout, netlist or result was changed. Current Cadence MIM qualification requires consistent structure, mapping, port order and supported recognition/extraction configuration.

Sources: [public DRC](https://github.com/efabless/mpw_precheck/blob/main/checks/tech-files/sky130A_mr.drc), [Magic technology](https://github.com/RTimothyEdwards/open_pdks/blob/master/sky130/magic/sky130.tech). This historical cross-check is not complete-core PEX or foundry signoff.
