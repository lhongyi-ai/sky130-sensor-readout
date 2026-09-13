# SAR controller: open-source digital implementation

This directory implements the existing `v2/rtl/sar_controller.v` without changing
its interface. It is only the **digital controller**, not the analog converter.

## Reproduce

In the project's pinned IIC-OSIC-TOOLS image, from the repository root:

```sh
PDK_ROOT=/foss/pdks python3 v2/digital/run.py
```

The script performs Yosys synthesis to SKY130 HD cells, compiles the PDK's
functional cell models with the **unchanged** independent SAR testbench, then
runs OpenSTA at TT 25°C 1.80 V, SS 100°C 1.60 V, FF −40°C 1.95 V.
These characterized digital library corners are **not** the planned 45-point
analog PVT matrix. The PDK stays outside the repository; relevant input hashes
and generated evidence are retained in `results/validation.json`.

`run.py` returns failure for missing evidence or negative pre-layout timing
slack even if functionality passes. A working ideal testbench is not a timing
pass. Conversely, a pre-layout hold failure can be repaired by the clock-tree
and delay-cell insertion stages; inspect the separately generated routed result.

## Timing contract

- 1.6 MHz external clock: 625 ns period, 50% duty cycle.
- Digital command inputs: latest arrival 100 ns after the previous rising edge.
- Comparator result: latest arrival 250 ns after the falling edge. This is an
  **interface requirement**, not measured analog comparator performance.
- Output loads: 50 fF per port, representing a gate/switch-driver input. The
  controller does not directly drive the CDAC capacitance in this model.
- `comparator_evaluate` is a combinational phase output; its clock-to-output
  propagation is bounded to 10 ns. Analog reset/evaluation nonoverlap and
  glitch-free integration still require transistor-level verification. Only
  the inapplicable synchronous hold check at this analog phase output is
  excluded; all real data/register hold checks remain enabled.
- 1 ns clock uncertainty applies to setup and hold. Asynchronous reset assertion
  is excluded from synchronous data STA; reset release must be synchronized by
  the surrounding system. Recovery/removal for arbitrary release is not proven.

The exhaustive test uses a held integer-code comparator, has zero gate delay,
and does **not** test metastability, comparator kickback, analog noise, ADC INL,
ADC ENOB or silicon behavior.

## Physical implementation

The companion flow is `v2/physical/digital/run.sh`, using the installed
LibreLane/OpenROAD/Magic/Netgen stack and the existing SKY130 PDK. Reports there
must be read separately: mapped cell area is not the macro rectangle, and
standalone controller DRC/LVS is not full-chip DRC/LVS.

Official flow references:
[LibreLane PDK handling](https://librelane.readthedocs.io/en/stable/usage/about_pdks.html),
[configuration reference](https://librelane.readthedocs.io/en/latest/reference/configuration.html).
