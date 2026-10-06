# Isolated Quantus temperature binding

The school's exported technology uses effective temp_reference=25°C and originally lacks TC1/TC2. Consequently RCXSPIC-27104 reports that requested extraction temperature is ignored. This is missing scaling metadata, not missing base resistance.

Documented Techgen update/compilation/process-readback interfaces permit binding coefficients in an isolated project copy. Rebase the public 30°C polynomial to 25°C while preserving its temperature function; apply it once to ordinary M3/M4/via3, not to an undefined CAPM electrode. Never fill other missing material coefficients with zeros and claim coverage.

The examined documented inputs are conductor/via temp_tc1/temp_tc2, process temp_reference and process_technology temperature. Result outputs must establish actual execution, not only absence of a warning. The parent r2 report records successful controlled compilation and numerical checks.

This experiment validates the bound ordinary-interconnect temperature law. It does not explain original reference-temperature provenance or qualify absolute resistance, CAPM stack or MIM RC ownership. Installed proprietary technology/manual content remains local.
