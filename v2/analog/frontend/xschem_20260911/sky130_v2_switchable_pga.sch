v {xschem version=3.4.8RC file_version=1.3
* Review page for sky130_v2_switchable_pga in dynamic_20260911/candidate_06.spice.
* Connections and values are independently checked by artifact_manifest.json.
}
G {}
K {}
V {}
S {}
F {}
E {}

T {SWITCHABLE PGA - FULLY DIFFERENTIAL CROSS-FEEDBACK} 80 -1450 0 0 0.76 0.76 {layer=4}
T {ONE OTA AND ONE SUMMING-NODE PAIR; ONLY THE PHYSICAL FEEDBACK BRANCH CHANGES} 80 -1385 0 0 0.36 0.36 {layer=4}
T {BOUND TO candidate_06.spice | NOT CADENCE | FORMAL MULTILOOP STABILITY OPEN} 80 -1330 0 0 0.29 0.29 {layer=4}

B 4 100 -1265 930 -885 {fill=false}
T {UPPER FEEDBACK BANK: OUTN -> SUMPOS} 515 -1225 0 0 0.32 0.32 {hcenter=true layer=4}
T {MODE / RESISTANCE} 145 -1165 0 0 0.21 0.21 {layer=4}
T {PHYSICAL RESISTOR + TRANSMISSION GATE} 470 -1165 0 0 0.21 0.21 {layer=4}
T {SELECT} 805 -1165 0 0 0.21 0.21 {layer=4}
T {1x   RFB = 10.35 kohm} 145 -1095 0 0 0.22 0.22 {}
T {4x   RFB = 41.4 kohm} 145 -1025 0 0 0.22 0.22 {}
T {16x  RFB = 165.6 kohm} 145 -955 0 0 0.22 0.22 {}
T {E1 / E1B} 805 -1095 0 0 0.21 0.21 {}
T {E4 / E4B} 805 -1025 0 0 0.21 0.21 {}
T {E16 / E16B} 805 -955 0 0 0.21 0.21 {}

L 4 470 -1080 495 -1080 {}
L 4 495 -1080 507 -1095 {}
L 4 507 -1095 531 -1065 {}
L 4 531 -1065 555 -1095 {}
L 4 555 -1095 579 -1065 {}
L 4 579 -1065 603 -1095 {}
L 4 603 -1095 615 -1080 {}
L 4 615 -1080 660 -1080 {}
L 4 660 -1080 695 -1100 {}
L 4 710 -1080 750 -1080 {}
L 4 695 -1100 710 -1080 {}
L 4 470 -1010 495 -1010 {}
L 4 495 -1010 507 -1025 {}
L 4 507 -1025 531 -995 {}
L 4 531 -995 555 -1025 {}
L 4 555 -1025 579 -995 {}
L 4 579 -995 603 -1025 {}
L 4 603 -1025 615 -1010 {}
L 4 615 -1010 660 -1010 {}
L 4 660 -1010 695 -1030 {}
L 4 710 -1010 750 -1010 {}
L 4 695 -1030 710 -1010 {}
L 4 470 -940 495 -940 {}
L 4 495 -940 507 -955 {}
L 4 507 -955 531 -925 {}
L 4 531 -925 555 -955 {}
L 4 555 -955 579 -925 {}
L 4 579 -925 603 -955 {}
L 4 603 -955 615 -940 {}
L 4 615 -940 660 -940 {}
L 4 660 -940 695 -960 {}
L 4 710 -940 750 -940 {}
L 4 695 -960 710 -940 {}

B 4 100 -420 930 -40 {fill=false}
T {LOWER FEEDBACK BANK: OUTP -> SUMNEG} 515 -380 0 0 0.32 0.32 {hcenter=true layer=4}
T {MODE / RESISTANCE} 145 -320 0 0 0.21 0.21 {layer=4}
T {PHYSICAL RESISTOR + TRANSMISSION GATE} 470 -320 0 0 0.21 0.21 {layer=4}
T {SELECT} 805 -320 0 0 0.21 0.21 {layer=4}
T {1x   RFB = 10.35 kohm} 145 -250 0 0 0.22 0.22 {}
T {4x   RFB = 41.4 kohm} 145 -180 0 0 0.22 0.22 {}
T {16x  RFB = 165.6 kohm} 145 -110 0 0 0.22 0.22 {}
T {E1 / E1B} 805 -250 0 0 0.21 0.21 {}
T {E4 / E4B} 805 -180 0 0 0.21 0.21 {}
T {E16 / E16B} 805 -110 0 0 0.21 0.21 {}

L 4 470 -235 495 -235 {}
L 4 495 -235 507 -250 {}
L 4 507 -250 531 -220 {}
L 4 531 -220 555 -250 {}
L 4 555 -250 579 -220 {}
L 4 579 -220 603 -250 {}
L 4 603 -250 615 -235 {}
L 4 615 -235 660 -235 {}
L 4 660 -235 695 -255 {}
L 4 710 -235 750 -235 {}
L 4 695 -255 710 -235 {}
L 4 470 -165 495 -165 {}
L 4 495 -165 507 -180 {}
L 4 507 -180 531 -150 {}
L 4 531 -150 555 -180 {}
L 4 555 -180 579 -150 {}
L 4 579 -150 603 -180 {}
L 4 603 -180 615 -165 {}
L 4 615 -165 660 -165 {}
L 4 660 -165 695 -185 {}
L 4 710 -165 750 -165 {}
L 4 695 -185 710 -165 {}
L 4 470 -95 495 -95 {}
L 4 495 -95 507 -110 {}
L 4 507 -110 531 -80 {}
L 4 531 -80 555 -110 {}
L 4 555 -110 579 -80 {}
L 4 579 -80 603 -110 {}
L 4 603 -110 615 -95 {}
L 4 615 -95 660 -95 {}
L 4 660 -95 695 -115 {}
L 4 710 -95 750 -95 {}
L 4 695 -115 710 -95 {}

B 4 100 -850 1550 -485 {fill=false}
T {MAIN DIFFERENTIAL SIGNAL PATH} 825 -815 0 0 0.33 0.33 {hcenter=true layer=4}
T {VINP} 125 -735 0 0 0.24 0.24 {layer=4}
T {10-kohm INPUT RESISTOR} 300 -780 0 0 0.20 0.20 {hcenter=true layer=4}
T {SUMPOS} 785 -735 0 0 0.22 0.22 {hcenter=true layer=4}
T {VINN} 125 -585 0 0 0.24 0.24 {layer=4}
T {10-kohm INPUT RESISTOR} 300 -630 0 0 0.20 0.20 {hcenter=true layer=4}
T {SUMNEG} 785 -585 0 0 0.22 0.22 {hcenter=true layer=4}

N 120 -700 220 -700 {lab=VINP}
L 4 220 -700 245 -700 {}
L 4 245 -700 260 -720 {}
L 4 260 -720 285 -680 {}
L 4 285 -680 310 -720 {}
L 4 310 -720 335 -680 {}
L 4 335 -680 360 -720 {}
L 4 360 -720 375 -700 {}
N 375 -700 980 -700 {lab=SUMPOS}
N 120 -550 220 -550 {lab=VINN}
L 4 220 -550 245 -550 {}
L 4 245 -550 260 -570 {}
L 4 260 -570 285 -530 {}
L 4 285 -530 310 -570 {}
L 4 310 -570 335 -530 {}
L 4 335 -530 360 -570 {}
L 4 360 -570 375 -550 {}
N 375 -550 980 -550 {lab=SUMNEG}

B 4 980 -795 1325 -505 {fill=false}
T {RD_FDOTA} 1152 -750 0 0 0.40 0.40 {hcenter=true layer=4}
T {two inputs / two outputs} 1152 -655 0 0 0.23 0.23 {hcenter=true}
T {two stages + continuous CMFB} 1152 -615 0 0 0.23 0.23 {hcenter=true}
T {DETAIL PAGE: rd_fdota.sch} 1152 -545 0 0 0.21 0.21 {hcenter=true layer=4}
N 1325 -700 1515 -700 {lab=OUTP}
N 1325 -550 1515 -550 {lab=OUTN}
T {OUTP} 1420 -735 0 0 0.24 0.24 {hcenter=true layer=4}
T {OUTN} 1420 -585 0 0 0.24 0.24 {hcenter=true layer=4}

B 4 1640 -1265 2290 -880 {fill=false}
T {REAL CMOS GAIN DECODER} 1965 -1215 0 0 0.36 0.36 {hcenter=true layer=4}
T {XI0 / XI1: inverters} 1680 -1145 0 0 0.23 0.23 {}
T {XN1 / XN4 / XN16: NAND gates} 1680 -1095 0 0 0.23 0.23 {}
T {XIE1 / XIE4 / XIE16: inverters} 1680 -1045 0 0 0.23 0.23 {}
T {SEL1:SEL0 = 00 -> E1} 1680 -975 0 0 0.23 0.23 {}
T {01 -> E4   |   10 -> E16   |   11 -> none} 1680 -925 0 0 0.23 0.23 {}

B 4 1640 -810 2290 -460 {fill=false}
T {WHY THE 1x MODE IS USEFUL} 1965 -760 0 0 0.34 0.34 {hcenter=true layer=4}
T {It converts the sensor signal to a full-differential pair.} 1680 -690 0 0 0.22 0.22 {}
T {It controls output common mode and lowers output impedance.} 1680 -640 0 0 0.22 0.22 {}
T {It also isolates and drives the switched SAR input load.} 1680 -590 0 0 0.22 0.22 {}
T {A voltage gain of one is still active signal conditioning.} 1680 -520 0 0 0.22 0.22 {layer=4}

B 4 1640 -390 2290 -40 {fill=false}
T {CANDIDATE TRUTH} 1965 -340 0 0 0.34 0.34 {hcenter=true layer=4}
T {All three nominal static modes pass.} 1680 -275 0 0 0.22 0.22 {}
T {All three real-load dynamic modes pass.} 1680 -230 0 0 0.22 0.22 {}
T {Formal multiloop stability is not closed.} 1680 -185 0 0 0.22 0.22 {}
T {45-PVT and noise are not qualified.} 1680 -140 0 0 0.22 0.22 {}
T {This drawing is not a full qualification claim.} 1680 -95 0 0 0.22 0.22 {layer=4}

T {AUTHORITATIVE SOURCE: ../dynamic_20260911/candidate_06.spice | AUDIT: artifact_manifest.json} 80 10 0 0 0.22 0.22 {layer=4}
T {sky130_v2_switchable_pga.sch | visual review page | 2026-09-11} 80 55 0 0 0.20 0.20 {layer=4}
