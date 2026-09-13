v {xschem version=3.4.8RC file_version=1.3
* Non-Cadence review hierarchy bound to dynamic_20260911/candidate_06.spice by manifest hash.
* ASCII-only drawing labels keep headless exports portable and legible.
}
G {}
K {}
V {}
S {}
F {}
E {}

T {SKY130 V2 SENSOR FRONT-END - SYSTEM SCHEMATIC} 90 -1335 0 0 0.76 0.76 {layer=4}
T {DIFFERENTIAL SENSOR -> G=1/4/16 PGA -> RC ISOLATION -> REAL SAR SAMPLER BOUNDARY} 90 -1265 0 0 0.40 0.40 {layer=4}
T {OPEN-SOURCE XSCHEM REVIEW VIEW | PRE-LAYOUT | NOT CADENCE | NOT A QUALIFIED FRONT-END} 90 -1205 0 0 0.31 0.31 {layer=4}

B 4 90 -1050 465 -335 {fill=false}
T {EXTERNAL SENSOR} 277 -1000 0 0 0.43 0.43 {hcenter=true layer=4}
T {Pressure-bridge example} 277 -945 0 0 0.25 0.25 {hcenter=true}
T {Millivolt differential output} 277 -905 0 0 0.25 0.25 {hcenter=true}
T {Validation source resistance} 277 -505 0 0 0.23 0.23 {hcenter=true}
T {350 ohm per side, in testbench} 277 -465 0 0 0.23 0.23 {hcenter=true}
T {VINP = VCM + Vin_diff / 2} 277 -420 0 0 0.22 0.22 {hcenter=true}
T {VINN = VCM - Vin_diff / 2} 277 -385 0 0 0.22 0.22 {hcenter=true}

B 4 650 -1080 1120 -335 {fill=false}
T {FULLY DIFFERENTIAL PGA} 885 -1025 0 0 0.43 0.43 {hcenter=true layer=4}
T {One two-input / two-output OTA} 885 -970 0 0 0.25 0.25 {hcenter=true}
T {Cross-feedback selected by real TGs} 885 -930 0 0 0.25 0.25 {hcenter=true}
T {GAIN MODES} 885 -500 0 0 0.27 0.27 {hcenter=true layer=4}
T {SEL1:SEL0 = 00 -> 1x} 885 -455 0 0 0.23 0.23 {hcenter=true}
T {01 -> 4x   |   10 -> 16x} 885 -415 0 0 0.23 0.23 {hcenter=true}
T {11 -> no feedback branch} 885 -375 0 0 0.23 0.23 {hcenter=true}
T {DETAIL PAGE: sky130_v2_switchable_pga.sch} 885 -290 0 0 0.24 0.24 {hcenter=true layer=4}

B 4 1270 -995 1545 -420 {fill=false}
T {RC ISOLATION} 1407 -945 0 0 0.38 0.38 {hcenter=true layer=4}
T {VERIFIED ASSEMBLY: 1.5 kohm / side} 1407 -900 0 0 0.21 0.21 {hcenter=true}
T {SUBCIRCUIT DEFAULT: 1.8 kohm} 1407 -865 0 0 0.21 0.21 {hcenter=true}
T {FILTER LOAD} 1407 -545 0 0 0.27 0.27 {hcenter=true layer=4}
T {4 MIM units per side} 1407 -500 0 0 0.22 0.22 {hcenter=true}
T {Subcircuit: rd_c4p} 1407 -465 0 0 0.22 0.22 {hcenter=true}

B 4 1710 -1065 2250 -350 {fill=false}
T {REAL SAR SAMPLER BOUNDARY} 1980 -1010 0 0 0.40 0.40 {hcenter=true layer=4}
T {LVT main transmission gate} 1980 -955 0 0 0.24 0.24 {hcenter=true}
T {Two shorted diffusion dummies} 1980 -915 0 0 0.24 0.24 {hcenter=true}
T {4096 SKY130 MIM units per side} 1980 -875 0 0 0.24 0.24 {hcenter=true}
T {Sampler source:} 1980 -515 0 0 0.23 0.23 {hcenter=true layer=4}
T {../dynamic_20260911/sampling_switch.spice} 1980 -475 0 0 0.21 0.21 {hcenter=true}
T {NOMINAL REAL-LOAD DYNAMIC: PASS} 1980 -405 0 0 0.30 0.30 {hcenter=true layer=4}

N 465 -790 650 -790 {lab=VINP}
N 465 -630 650 -630 {lab=VINN}
N 1120 -790 1270 -790 {lab=COREP}
N 1120 -630 1270 -630 {lab=COREN}
N 1545 -790 1710 -790 {lab=OUTP}
N 1545 -630 1710 -630 {lab=OUTN}

T {VINP} 535 -820 0 0 0.24 0.24 {hcenter=true layer=4}
T {VINN} 535 -660 0 0 0.24 0.24 {hcenter=true layer=4}
T {COREP} 1195 -820 0 0 0.22 0.22 {hcenter=true layer=4}
T {COREN} 1195 -660 0 0 0.22 0.22 {hcenter=true layer=4}
T {OUTP} 1625 -820 0 0 0.24 0.24 {hcenter=true layer=4}
T {OUTN} 1625 -660 0 0 0.24 0.24 {hcenter=true layer=4}

L 4 1310 -790 1335 -790 {}
L 4 1335 -790 1348 -810 {}
L 4 1348 -810 1372 -770 {}
L 4 1372 -770 1396 -810 {}
L 4 1396 -810 1420 -770 {}
L 4 1420 -770 1444 -810 {}
L 4 1444 -810 1457 -790 {}
L 4 1457 -790 1505 -790 {}
L 4 1310 -630 1335 -630 {}
L 4 1335 -630 1348 -650 {}
L 4 1348 -650 1372 -610 {}
L 4 1372 -610 1396 -650 {}
L 4 1396 -650 1420 -610 {}
L 4 1420 -610 1444 -650 {}
L 4 1444 -650 1457 -630 {}
L 4 1457 -630 1505 -630 {}

N 1505 -790 1545 -790 {lab=OUTP}
N 1505 -630 1545 -630 {lab=OUTN}
N 1585 -790 1585 -555 {lab=OUTP}
N 1655 -630 1655 -555 {lab=OUTN}
L 4 1560 -535 1610 -535 {}
L 4 1560 -515 1610 -515 {}
L 4 1585 -555 1585 -535 {}
L 4 1585 -515 1585 -470 {}
L 4 1630 -535 1680 -535 {}
L 4 1630 -515 1680 -515 {}
L 4 1655 -555 1655 -535 {}
L 4 1655 -515 1655 -470 {}
N 1585 -470 1655 -470 {lab=VSS}
T {VSS} 1620 -445 0 0 0.20 0.20 {hcenter=true layer=4}

B 4 90 -255 2250 -80 {fill=false}
T {AUTHORITATIVE ELECTRICAL SOURCE} 125 -215 0 0 0.28 0.28 {layer=4}
T {../dynamic_20260911/candidate_06.spice} 125 -170 0 0 0.24 0.24 {}
T {SHA-256 and port / connection audit: artifact_manifest.json} 125 -125 0 0 0.22 0.22 {}
T {STATUS: NOMINAL STATIC + REAL-LOAD DYNAMIC PASS; FORMAL MULTILOOP STABILITY NOT CLOSED} 1000 -170 0 0 0.25 0.25 {layer=4}

T {frontend_top.sch | visual review page | 2026-09-11} 90 -25 0 0 0.22 0.22 {layer=4}
