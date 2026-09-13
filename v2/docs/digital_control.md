# SAR Digital Controller: Executable Preparation, Not a Completed ADC

This module is the digital controller RTL for a 12-bit synchronous SAR. It does not include a transistor comparator, sampling switches, CDAC, standard-cell mapping, or physical layout. It cannot establish completion of M5 or prove ADC noise, INL, DNL, power, or effective resolution.

## Interface contract

The design file is `v2/rtl/sar_controller.v`, written in synthesizable Verilog-2005. All control requests are processed on the rising edge of `clk`. `rst_n` is an asynchronous active-low reset: it immediately cancels conversion, clears output data and metadata, and masks sampling and comparator evaluation. Physical implementation must also address synchronized reset release and recovery/removal timing.

| Signal | Contract |
|---|---|
| `clk` | External 1.6 MHz clock; digital behavioral tests use 50% duty cycle |
| `start` / `gain_sel[1:0]` | Requests are accepted when `ready=1` and gain is valid; `00=1`, `01=4`, `10=16`; `11` rejects the request |
| `ready` / `busy` | `busy = !ready` indicates **request backpressure**, not a busy flag for all analog activity. All `start` requests are ignored when `busy=1`. During reset, `ready=0` |
| `gain_latched[1:0]` | Latched when a request is accepted; external gain changes are ignored during conversion |
| `sample_en` | Acquisition request for four consecutive full clock cycles |
| `trial_code[11:0]` | Current CDAC trial code; proceeds from MSB to LSB, with the comparator determining whether to retain or clear each bit |
| `comparator_evaluate` | Active only during the low clock half-cycle of the 12 decision cycles; forced inactive during reset |
| `comparator_bit` | Sampled on the rising edge; `1` means the held differential input is at least the current DAC trial level, retaining the trial bit; equality retains the bit |
| `data[11:0]` / `data_valid` | Offset-binary raw code; on completion, `data_valid` is high for one full cycle, and data is held until the next completion or reset |
| `data_gain[1:0]` | Updated with `data`, identifying the gain of **the frame just completed**; used to select the correct calibration coefficients |

`ready` indicates that a request can be accepted on the **next rising edge**. It is high while idle and during the final decision cycle. Thus `busy=0` during the final decision cycle even though analog comparison has not finished. Use sampling/comparison control signals to determine analog activity; `!busy` does not mean that the analog circuit is quiescent.

Relative to the initial plan, `ready` is an explicit handshake addition that eliminates interframe idle cycles, and `data_gain` is a metadata addition that prevents mismatched calibration coefficients during continuous conversion. The rule that requests are ignored when `busy=1` is unchanged.

The input protocol requires `start` and `gain_sel` to satisfy setup/hold conditions at the acceptance edge. Holding `start` high requests continuous conversion, starting subsequent conversions at eligible boundaries. Reserved gain `11` does not trigger conversion, produce a new error code or valid data, or clear existing data.

## Exact timing: 16 full cycles, without a 17th idle cycle

Let E0 be the rising edge that accepts the request:

| Interval/edge | Operation |
|---|---|
| E0 | Accept request, latch gain, assert sampling request |
| E0–E4 | Four full acquisition cycles, totaling 2.5 µs |
| E4 | End acquisition and set MSB trial code `0x800` |
| E4–E5 | First decision cycle: CDAC settling/comparator reset in the high half-cycle, comparison request in the low half-cycle |
| E5–E15 | Sample decisions from MSB through bit 1 and update the next trial bit |
| E15–E16 | Bit 0 decision; `ready=1`, `busy=0`, allowing preparation of the next frame request |
| E16 | Complete the frame and publish `data`, `data_gain`, and the valid pulse; a valid request can simultaneously start the next frame |

Continuous-request acceptance edges are therefore E0, E16, E32, and result edges are E16, E32, E48, satisfying `1.6 MHz / 16 = 100 kS/s`. When E16 simultaneously updates data and starts a new frame, `data_gain` belongs to the previous frame and `gain_latched` to the new frame.

### Timing requirements not yet physically verified

`comparator_evaluate` is a combinational **phase-control output**, not a gated clock for RTL registers. In ideal digital timing, state and trial code change only on rising edges, with evaluation in the following low half-cycle.

This does not prove that the real circuit is glitch-free, nonoverlapping, or has sufficient reset or comparison-regeneration time. Each half of the 625 ns period is nominally 312.5 ns; clock skew, switch-control delay, CDAC settling, comparator reset/regeneration, and register setup time must be deducted. Dedicated phase drivers and timing constraints, followed by transistor-level and physical-parasitic verification, are still required. Reset deassertion must satisfy synchronization constraints.

## Reproducible digital tests

Run `python3 v2/tests/rtl/run.py` from the repository root. This entry point uses only the Python standard library and installed Icarus Verilog, places compilation artifacts in a temporary directory, and cleans them automatically. Standard output is a JSON validation record. Missing tools produce status `blocked` and exit code 2; an unexecuted test is not treated as a pass.

Test file `v2/tests/rtl/tb_sar_controller.sv` uses SystemVerilog test syntax, while the RTL under test remains Verilog-2005. For Icarus Verilog, run the following from the repository root; generated files go to a temporary directory rather than the design directory:

```sh
rtl_test_dir=$(mktemp -d /tmp/sky130-sar-rtl.XXXXXX)
iverilog -g2005 -Wall -s sar_controller -o "$rtl_test_dir/design.vvp" v2/rtl/sar_controller.v
iverilog -g2012 -Wall -s tb_sar_controller -o "$rtl_test_dir/test.vvp" v2/rtl/sar_controller.v v2/tests/rtl/tb_sar_controller.sv
vvp "$rtl_test_dir/test.vvp"
```

Success prints a statistics line beginning with `PASS sar_controller:`; failure prints the reason and exits with nonzero status. Tests use a fixed pseudorandom sequence for reproducibility:

- Exhaustively visit all 4096 ideal quantization codes, covering retention/rejection of every bit, endpoints, and codes around zero differential input; interleave the three gain settings.
- Independently schedule and check 4 full acquisition cycles, 12 decision cycles, and exactly 16 cycles of latency; compare final and per-bit trial codes each time.
- Test 32 frames with no idle gaps, changing external input and gain together to verify that old-data/new-gain metadata are not confused.
- Apply 4096 cycles of deterministic random requests, gains, and inputs; ignore all requests during backpressure.
- Apply asynchronous reset separately in all 16 acquisition/decision intervals, checking cancellation, no residual valid pulse, and subsequent recovery.
- Reject reserved-gain starts both while idle and at completion boundaries, without disrupting normal completion of the previous frame.
- Check output-data retention, valid-pulse width, comparator evaluation during the low half-cycle, and reset masking.

The test comparator implements only “acquired ideal integer code ≥ trial code.” It does not model reference-voltage amplitudes, comparator noise/offset, metastability, CDAC mismatch, sampling-settling error, gain circuitry, or distortion. This all-code sweep proves **digital search and protocol behavior**, not that the physical ADC has no missing codes or achieves 12-bit accuracy.

### Results of this digital validation

Icarus Verilog 13.0 completed Verilog-2005 design compilation and testing: 687,790 assertion checks, 4,400 accepted frames, 4,384 completed frames, and 16 reset-canceled frames; 2,293 requests ignored during backpressure, 74 reserved-gain requests rejected, and 124 coincident completion/new-request edges. Digital RTL validation passes; physical timing and analog ADC verification remain unfinished.
