# Native netlist checker

`audit_native_netlist.py` compares the flat Spectre body exported by Cadence SI against an independently prepared object inventory. It uses the Python standard library, does not execute netlist expressions, and refuses to overwrite an existing output.

```sh
python3 audit_native_netlist.py /absolute/path/to/netlist \
  --manifest native_canary_school_r1_objects.json \
  --output /absolute/path/to/new_native_audit.json
```

Exit 0 means the comparison passed; exit 2 means syntax or matching failed. Supply the SI netlist body, not a complete simulation deck.

Checks cover missing/extra/duplicate instances, models, terminal order, MOS finger width/length/multiplication and total width, resistor length/width and grid, MIM geometry/multiplication, ideal resistance, and source DC/AC expressions. Unknown syntax or extra scaling is rejected. Constant and SW-dependent expressions use exact rational arithmetic. Nonnegative MOS diffusion parameters are recorded, without claiming equivalence to the original single-finger layout. A CDF resistor value is provenance, not the actual model resistance.

Eleven independent fixtures and fault-injection tests passed. The first mapping probe failed because 11 sources lacked DC values; the repaired 20-device probe passed. The complete frontend requires its own audit before simulation. This checker does not qualify stability, noise, sampling, PVT or layout.
