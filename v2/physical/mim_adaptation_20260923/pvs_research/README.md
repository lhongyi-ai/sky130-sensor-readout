# Project-owned minimal PVS MIM rules

Actual PVS21.10-p044 controls produced five normal LVS MATCH results, six expected connection/dimension MISMATCH results and one 1:0 device-count case with comparison NOT RUN. All twelve LVS runs had zero black boxes. Thirteen DRC runs included seven valid geometries with zero violations and five deliberate geometric defects correctly detected; an electrical short had zero geometric DRC but was rejected by LVS.

`mim_layers.pvl` maps drawing/text datatypes, `mim_drc.pvl` implements nine limited structure checks and `mim_lvs.pvl` recognizes a two-terminal p1_mim_public_r1 device and measures w/l. M3/CAPM/via3/M4 map to 70:20/89:44/70:44/71:20. PLUS reaches the top through M4/via3; MINUS reaches M3.

Specify actual GDS/top, source CDL/top and output paths. Inspect rule results and comparison contents rather than accepting process exit 0. The CDL primitive is an LVS interface; simulation must load the functional wrapper. Size, orientation and swapped-port counterexamples prevent using a permissive black box.

These authored rules do not copy the school deck or establish full foundry coverage. Exact input/result counts and failed states: `final_runtime_audit.json`.
