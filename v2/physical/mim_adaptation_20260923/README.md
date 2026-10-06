# Independent SKY130 MIM adaptation r1

Actual school Virtuoso/PVS/Quantus/Spectre experiments used new project-owned cells only, preserving old OTA/frontend/ADC, failure records and installed PDK. The structure is M3=70:20, CAPM=89:44, via3=70:44, M4=71:20; PLUS is the top electrode and MINUS the bottom.

Nine project-owned MIM checks accepted normal geometry and rejected undersize, spacing, enclosure and missing-contact cases. LVS recognized one two-port capacitor with dimensions, rejected opens/shorts/swapped plates/swapped dimensions, and used no black boxes. Small size and direction counterexamples were retained; a 1:0 device case stopped before comparison and is not a comparison PASS.

Actual three-size Spectre controls completed with zero errors/warnings: 4×4 µm=34.62225 fF, 8×8 µm=133.26225 fF, 4×8 µm=67.94225 fF. These verify model/units/ports, not silicon or extraction physical accuracy. Public KLayout/Magic controls are separately labeled.

The first Quantus DSPF omitted the functional instance. `output_db -type dspf -disable_instances false` made Quantus retain it directly, without hand-editing DSPF. Subsequent diagnostic RC simulation worked. However CAPM coupling, internal/external RC ownership and interconnect temperature treatment were not all qualified. Blocking/no-blocking results are sensitivity controls, not accurate bounds or a reason to select whichever matches a target.

Project rules are experimental, not foundry signoff. Formal ADC PEX remains false. Detailed runtime counts, hashes, raw-output scope and warnings remain in the report and research subdirectories.
