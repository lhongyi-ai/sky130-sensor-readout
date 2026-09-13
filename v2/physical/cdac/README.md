# 12-bit Differential CDAC Physical Assignment

This converts circuit weights for **8192 total 3 µm × 3 µm MIM units** across the ADC's two sides into reproducible two-dimensional placement input. It is not final layout, and correct arrangement is not presented as passing DRC/LVS/PEX.

## What is complete at this level

- Each side has 64 × 64, or 4096, electrically connected unit capacitors.
- The program automatically checks the count `B11…B0 + DUMMY = 4096`.
- Every capacitor in `B11…B1` has a same-net mirror partner about the array center, so these banks have geometric centroids exactly at the array center.
- The single-unit `B0` and electrical `DUMMY` occupy a mirrored pair near the center; together they are common-centroid.
- An outer ring of edge dummies, excluded from the 4096 electrical total, reserves space to reduce edge-environment differences.
- The N side is locally mirrored relative to P to support later differential-symmetric top-level placement.

![CDAC placement assignment](cdac_assignment.svg)

Generate or review:

    python3 v2/physical/cdac/generate_assignment.py
    python3 -m unittest v2/physical/cdac/test_assignment.py -v

Machine-readable results are in `assignment_summary.json`; two CSV files record each unit's net, coordinates, and electrical-array membership.

## What cannot yet be claimed

The current 4 µm pitch is a prerouting estimate. Top plates, 24 bit bottom-plate wires, reference switches, shielding, and supplies must still be added, followed by SKY130-rule DRC, LVS, parasitic extraction, and performance regression. Geometric arrangement does not establish passing spatial-gradient, mismatch, noise, or reference-droop performance.
