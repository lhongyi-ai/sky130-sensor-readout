# Three-gain r2/r3 static review

Each version was calibrated once at −80%, zero and +80% full scale, then checked at 78 independent static points. LSB=195.3125 µV. These are analog DC residuals, not actual ADC codes, device-noise averages or full-chain calibration qualification.

| Version/gain | Maximum residual, LSB | Positive endpoint, V | Out-of-range points |
| --- | ---: | ---: | ---: |
| r2/1 | 0.09967 | 0.420789 | 4/81 |
| r2/4 | 0.47979 | 0.416306 | 4/81 |
| r2/16 | 0.33040 | 0.413658 | 4/81 |
| r3/1 | 0.05150 | 0.397242 | 0/81 |
| r3/4 | 0.45560 | 0.398535 | 0/81 |
| r3/16 | 0.31777 | 0.398852 | 0/81 |

r2 common mode was approximately 0.9145–0.9152 V; r3 was approximately 0.900164–0.900852 V. A small calibration residual cannot recover clipping beyond the ADC ±0.4 V range. r3 endpoint margins are measured, not obtained by shrinking the required input range.

The deck explicitly saved pointwise `id/vds/vdsat/region` for 13 core MOS devices. Those actual vectors are distinct from earlier repeated scalar OP exports. Exact branch, region and supply-energy records remain in the adjacent independent-review JSON and analysis programs. Static proxy results do not waive sampled-load, noise, stability or PVT tests.
