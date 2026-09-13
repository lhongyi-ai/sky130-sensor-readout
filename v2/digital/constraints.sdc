# Units: ns and pF, as declared by the SKY130 HD Liberty library.
create_clock -name clk -period 625.0 -waveform {0.0 312.5} [get_ports clk]
set_clock_uncertainty 1.0 [get_clocks clk]
set_clock_transition 1.0 [get_clocks clk]

# Digital host inputs must arrive within 100 ns after a launching rising edge.
set_input_delay -clock clk -max 100.0 [get_ports {start gain_sel[*]}]
set_input_delay -clock clk -min 1.0 [get_ports {start gain_sel[*]}]
set_input_transition 1.0 [get_ports {start gain_sel[*] comparator_bit rst_n}]

# Comparator evaluates in the low half. Allow 250 ns from falling edge to
# decision arrival, reserving 62.5 ns for digital setup/uncertainty.
# This is an analog interface requirement, NOT measured comparator timing.
set_input_delay -clock clk -clock_fall -max 250.0 [get_ports comparator_bit]
set_input_delay -clock clk -clock_fall -min 1.0 [get_ports comparator_bit]

# Outputs drive logic/switch-driver inputs, not the CDAC capacitor directly.
# A 50 fF load is an explicit planning condition pending top-level extraction.
set_load 0.05 [all_outputs]
set_output_delay -clock clk -max 100.0 [get_ports {ready busy data_valid data[*] data_gain[*] gain_latched[*] sample_en trial_code[*]}]
set_output_delay -clock clk -min 1.0 [get_ports {ready busy data_valid data[*] data_gain[*] gain_latched[*] sample_en trial_code[*]}]

# Clock-gated phase-control output: bound each real input-to-output transition
# rather than treating it as an independent clock or falsely excluding it.
set_max_delay 10.0 -from [get_ports clk] -to [get_ports comparator_evaluate]
# Unlike a next-cycle host output, this analog phase output has no external
# synchronous setup budget. Adding that budget would subtract it a second time
# from set_max_delay. Zero external delay preserves the explicit 10 ns bound.
set_output_delay -clock clk -max 0.0 [get_ports comparator_evaluate]
set_output_delay -clock clk -min 0.0 [get_ports comparator_evaluate]
# The analog phase receiver is not a synchronous data-capture register. There
# is no same-edge data hold specification at this output. Keep its max-delay
# check, and require analog reset/evaluate nonoverlap to be tested separately.
set_false_path -hold -to [get_ports comparator_evaluate]

# rst_n is asynchronous assertion. Release must be synchronized outside macro.
# No claim is made that an arbitrarily timed release satisfies recovery/removal.
set_false_path -from [get_ports rst_n]
