# Design notes and learning checks

The differential frontend amplifies sensor input into the ADC range while controlling output common mode near0.9V. Real PDK terminals, body connections, finger widths and native symbols were migrated and audited. The SAR samples through actual switches, changes binary-weighted bottom plates and reads the actual comparator through the original RTL.

A concrete migration failure is3×3→4×4µm school MIM legality. With4096 units per side, load changes approximately81.3→141.8pF. Old sampling, noise and layout results cannot be reused merely because interfaces have the same names. Another failure is temperature-dependent feedback TG resistance: nominal-only calibration does not recover clipped full-scale ADC input.

Thermal noise uses PSD4kTR, integrated variancekT/C and ASD squared before integration. At27°C/141.8pF, ideal single/differential RMS are approximately5.41/7.64µV. The64-sample actual TG pilot near7.54µV is a method check with retained LTE warning, not ADC noise qualification.

Increasing four MOS areas reduced G16 band noise approximately249→108µV, but changed capacitance/OP, common mode, power and conditional margins. Tradeoffs require actual sampling, complete stability and folded noise together. Global reset defines analog latch state and abort behavior; it does not repair internal-body solver sensitivity.

Learning checks: explain each block and timing phase; derive LSB/noise/feedback relationships; explain one retained failure from actual measurements; distinguish function, numerical convergence, physical extraction and silicon evidence. Current complete-core qualification remains unfinished.
