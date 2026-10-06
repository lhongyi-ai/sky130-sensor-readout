# Complete public 3×3µm central-channel candidate

The complete new candidate ran public Magic full DRC, Netgen LVS, top-level C extraction and all4096 static codes. P/N/top DRC=0/0/0 and each LVS matched uniquely. The original frozen failure is retained.

| Metric | Original | New candidate |
| --- | ---: | ---: |
| Maximum abs(INL), LSB | 3.562071 | 0.327237 |
| Minimum DNL, LSB | −3.854472 | −0.177832 |
| Maximum DNL, LSB | +0.324300 | +0.171533 |
| Nonpositive transitions | 255 | 0 |
| Differential area, mm² | 0.377377 | 0.4315402 |

Area rises14.3525%, with941.2×458.5µm bounds. A36µm central channel separates the upper/lower array; central B0/dummy move18µm. Low-weight routes use short M5 segments into separate M4 tracks, then peripheral M5 collection. Actual DRC exposed thin-M3 bridge notches, which were repaired geometrically without editing the rules.

The calculation uses the full actual extracted C network and frozen19.845fF unit characterization with ideal settled references. No parasitic deletion/rescaling or changed weights/calibration is used. This public3µm candidate is not the school4µm migration, complete RC dynamic simulation or standalone actual ADC full-code test. Formal PEX remains incomplete.
