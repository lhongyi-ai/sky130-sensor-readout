# PZ frequency-equivalent warning and model controls

The four school MOS families have literal BSIM4 version 4.5, capMod=2 and rbodyMod=1, with AC/transient NQS, gate resistance and rdsMod disabled in the examined TT bins. Bin counts are 180/108/88/48 for ordinary NMOS/PMOS and LVT NMOS/PMOS. The wrappers did not override the examined switches. Current source hashes do not reconstruct an unfrozen historical PDK snapshot.

The same r1 native netlist was evaluated with QZ, docancel=no and identical bias/gmin at 1 Hz, 1 kHz and 1 MHz. Each result had 104 poles and zero RHP poles; rightmost real parts were −218.544, −218.546 and −218.545 Hz. No substantial frequency dependence was observed in this control.

Installed PZ help describes fixed G/C approximations for devices whose equivalent parameters depend on evaluation frequency. The exact Spectre 21.1 BSIM4 warning trigger is not exposed by the examined help. Disabled NQS excludes one proposed explanation but does not establish that the warning is necessarily harmless. Body-network dynamics do not alone identify its trigger.

Retain the approximate-root limitation and the complete coupled-loop qualification gap. Metadata, source hashes and detailed frequency comparison are preserved in adjacent JSON records; no PDK source is distributed.
