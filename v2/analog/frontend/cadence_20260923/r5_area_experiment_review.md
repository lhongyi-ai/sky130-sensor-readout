# r5 device-area experiment

Only four MOS instances and their diffusion geometry changed: input MIP/MIN total W/L 80/1→320/4 µm, eight 40 µm fingers; first-stage PMOS XMLP/XMLN 64/1→128/2 µm, four 32 µm fingers. Other 129 instances and connectivity matched. All 133 objects passed native comparison.

| Gain | r4 band noise, µV rms | r5 band noise, µV rms | r5 wideband noise, µV rms |
| --- | ---: | ---: | ---: |
| 1 | 28.869 | 11.512 | 35.982 |
| 4 | 72.888 | 30.785 | 97.784 |
| 16 | 249.248 | 108.096 | 294.015 |

Bands are 1 Hz–50 kHz and 1 Hz–100 MHz. G16 band noise improved 7.256 dB. Input-pair and first-stage-load flicker powers became 7.117% and 31.111% of r4, compared with conditional predictions 6.25% and 25%. The measured 108.096 µV exceeds the area-only prediction by 3.54%.

A separate dc_pivot_check control preserved all saved OP, AC and noise data byte-for-byte except headers, while removing a bad-pivot notice. It does not prove arbitrary solver changes harmless. Original GminDC and repeated-alter warnings remain.

r5 is not qualified: nominal G1 full-scale range is exceeded, output common mode is high and static frontend power increases by about 0.118 mW. Real ADC sampled noise and full multi-loop stability remain open. This noise reduction is not dynamic SNDR; exact contribution and operating-point details remain in the independent JSON review.
