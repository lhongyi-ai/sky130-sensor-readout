# Documented Quantus distributed-network controls

The documentation review proposed isolated numerical controls, not a new process model:

```text
parasitic_reduction -enable_reduction false
filter_res -min_res 0 -merge_parallel_res false -merge_parallel_via false -remove_dangling_res false
extraction_setup -max_fracture_length 5 -max_fracture_length_unit microns
output_db -add_explicit_vias true
```

For the examined LVS flow,5µm is the documented minimum fracture length; do not invent1µm. Explicit vias separate material branches, while parallel merging and via-array grouping are different mechanisms. Removing dangling resistors may alter capacitor placement and therefore deserves an explicit control.

A second independent group disables via-array lumping and small-coupling filtering:

```text
extraction_setup -max_via_array_count 1
filter_cap -exclude_self_cap false -exclude_floating_nets false
filter_coupling_cap -coupling_cap_threshold_absolute 0 -coupling_cap_threshold_relative 0
```

Use the appropriate LVS-supported options, preserve devices/substrate/temperature mapping, and compare complete rigid rotations using port impedance as well as total C. Better same-network numerical agreement does not fill missing CAPM materials. Actual subsequent results remain in the parent r3 report.
