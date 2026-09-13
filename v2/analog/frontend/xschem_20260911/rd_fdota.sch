v {xschem version=3.4.8RC file_version=1.3
* Review schematic for rd_fdota. Authoritative implementation is dynamic_20260911/candidate_06.spice.
* Device names and sizes are kept outside symbols to avoid visual collisions.
}
G {}
K {}
V {}
S {}
F {}
E {}

T {RD_FDOTA - TWO-INPUT, TWO-OUTPUT, TWO-STAGE OTA WITH CONTINUOUS CMFB} 80 -1490 0 0 0.70 0.70 {layer=4}
T {MAIN SIGNAL DEVICES USE SKY130 1.8-V MOS | BOTH COMMON-MODE LOOPS ARE EXPLICITLY IDENTIFIED} 80 -1425 0 0 0.34 0.34 {layer=4}
T {OPEN-SOURCE REVIEW VIEW | NOMINAL DYNAMIC PASS | MULTILOOP STABILITY OPEN | NOT CADENCE} 80 -1370 0 0 0.27 0.27 {layer=4}

B 4 1180 -1330 2225 -1190 {fill=false}
T {MILLER COMPENSATION PATHS} 1215 -1295 0 0 0.28 0.28 {layer=4}
T {N1 -> XRZP 1.2 kohm -> XCCP 8 MIM units -> OUTP} 1215 -1260 0 0 0.21 0.21 {}
T {N2 -> XRZN 1.2 kohm -> XCCN 8 MIM units -> OUTN} 1215 -1230 0 0 0.21 0.21 {}
T {PHYSICAL PARAMETER AUDIT: 1.2-kohm high-po_0p69 LENGTH 0.855 um >= 0.5 um: PASS} 80 -1300 0 0 0.22 0.22 {layer=4}

B 4 80 -1160 430 -520 {fill=false}
T {BIAS AND STARTUP} 255 -1110 0 0 0.38 0.38 {hcenter=true layer=4}
T {XRBN: 24-kohm high-po resistor} 115 -1040 0 0 0.22 0.22 {}
T {VDD -> XRBN -> BN} 115 -995 0 0 0.22 0.22 {}
T {XDBN: diode-connected NFET} 115 -925 0 0 0.22 0.22 {}
T {L = 1 um, W = 20 um} 115 -880 0 0 0.22 0.22 {}
T {The physical resistor forces startup.} 115 -790 0 0 0.22 0.22 {}
T {No ideal external IBIAS is used.} 115 -745 0 0 0.22 0.22 {}
T {BN is about 0.7 V at TT nominal.} 115 -655 0 0 0.22 0.22 {}
T {XRBP: BP-to-BN compatibility path = 1 Mohm.} 115 -610 0 0 0.20 0.20 {}
T {SUBCIRCUIT: rd_bias / INSTANCE: XBIAS} 115 -555 0 0 0.20 0.20 {layer=4}

T {STAGE 1 - NMOS DIFFERENTIAL PAIR WITH PMOS CURRENT-SOURCE LOADS} 500 -1160 0 0 0.30 0.30 {layer=4}
N 500 -1110 1100 -1110 {lab=VDD}
T {VDD} 470 -1138 0 0 0.24 0.24 {layer=4}

T {XMLP} 535 -1085 0 0 0.22 0.22 {layer=4}
T {PFET W/L = 64/1 um} 710 -1035 0 0 0.19 0.19 {}
B 4 600 -1060 690 -970 {fill=false}
L 4 630 -1040 630 -990 {}
L 4 650 -1040 650 -990 {}
L 4 630 -1015 650 -1015 {}
L 4 570 -1015 630 -1015 {}
N 645 -1110 645 -1060 {lab=VDD}
N 645 -970 645 -900 {lab=N1}
T {NCM} 550 -1045 0 0 0.20 0.20 {layer=4}

T {XMLN} 835 -1085 0 0 0.22 0.22 {layer=4}
T {PFET W/L = 64/1 um} 1010 -1035 0 0 0.19 0.19 {}
B 4 900 -1060 990 -970 {fill=false}
L 4 930 -1040 930 -990 {}
L 4 950 -1040 950 -990 {}
L 4 930 -1015 950 -1015 {}
L 4 870 -1015 930 -1015 {}
N 945 -1110 945 -1060 {lab=VDD}
N 945 -970 945 -870 {lab=N2}
T {NCM} 850 -1045 0 0 0.20 0.20 {layer=4}

T {XMIP} 525 -835 0 0 0.22 0.22 {layer=4}
T {NFET W/L = 80/1 um} 710 -785 0 0 0.19 0.19 {}
B 4 600 -810 690 -720 {fill=false}
L 4 630 -790 630 -740 {}
L 4 650 -790 650 -740 {}
L 4 630 -765 650 -765 {}
N 645 -900 645 -810 {lab=N1}
N 645 -720 645 -660 {lab=TAIL}
N 470 -765 600 -765 {lab=INP}
T {INP} 445 -795 0 0 0.23 0.23 {layer=4}

T {XMIN} 825 -835 0 0 0.22 0.22 {layer=4}
T {NFET W/L = 80/1 um} 1010 -785 0 0 0.19 0.19 {}
B 4 900 -810 990 -720 {fill=false}
L 4 930 -790 930 -740 {}
L 4 950 -790 950 -740 {}
L 4 930 -765 950 -765 {}
N 945 -870 945 -810 {lab=N2}
N 945 -720 945 -660 {lab=TAIL}
N 800 -765 900 -765 {lab=INN}
T {INN} 775 -795 0 0 0.23 0.23 {layer=4}

N 645 -660 945 -660 {lab=TAIL}
N 795 -660 795 -620 {lab=TAIL}
T {XMTAIL} 650 -615 0 0 0.22 0.22 {layer=4}
T {NFET W/L = 40/1 um} 900 -570 0 0 0.19 0.19 {}
B 4 750 -620 840 -530 {fill=false}
L 4 780 -600 780 -550 {}
L 4 800 -600 800 -550 {}
L 4 780 -575 800 -575 {}
L 4 720 -575 780 -575 {}
T {BN GATE} 650 -540 0 0 0.20 0.20 {layer=4}
N 795 -530 795 -470 {lab=VSS}

T {N1 NET - TO XMSP GATE} 760 -940 0 0 0.19 0.19 {layer=4}
N 645 -900 1080 -900 {lab=N1}
T {N2 NET - TO XMSN GATE} 980 -830 0 0 0.19 0.19 {layer=4}
N 945 -870 1080 -870 {lab=N2}

T {STAGE 2 - MATCHED PMOS GAIN DEVICES AND CMFB-CONTROLLED NMOS SINKS} 1240 -1160 0 0 0.30 0.30 {layer=4}
N 1200 -1110 2100 -1110 {lab=VDD}

T {XMSP} 1315 -1085 0 0 0.22 0.22 {layer=4}
T {PFET W/L = 180/1 um} 1520 -1035 0 0 0.19 0.19 {}
B 4 1390 -1060 1480 -970 {fill=false}
L 4 1420 -1040 1420 -990 {}
L 4 1440 -1040 1440 -990 {}
L 4 1420 -1015 1440 -1015 {}
L 4 1360 -1015 1420 -1015 {}
N 1435 -1110 1435 -1060 {lab=VDD}
N 1280 -1015 1390 -1015 {lab=N1}
T {N1} 1255 -1045 0 0 0.20 0.20 {layer=4}
N 1435 -970 1435 -850 {lab=OUTP}

T {XMSN} 1665 -1085 0 0 0.22 0.22 {layer=4}
T {PFET W/L = 180/1 um} 1870 -1035 0 0 0.19 0.19 {}
B 4 1740 -1060 1830 -970 {fill=false}
L 4 1770 -1040 1770 -990 {}
L 4 1790 -1040 1790 -990 {}
L 4 1770 -1015 1790 -1015 {}
L 4 1710 -1015 1770 -1015 {}
N 1785 -1110 1785 -1060 {lab=VDD}
N 1630 -1015 1740 -1015 {lab=N2}
T {N2} 1605 -1045 0 0 0.20 0.20 {layer=4}
N 1785 -970 1785 -850 {lab=OUTN}

N 1250 -850 1435 -850 {lab=OUTP}
T {OUTP} 1275 -880 0 0 0.23 0.23 {layer=4}
N 1785 -850 2070 -850 {lab=OUTN}
T {OUTN} 1990 -880 0 0 0.23 0.23 {layer=4}

T {XMOP} 1315 -785 0 0 0.22 0.22 {layer=4}
T {NFET W/L = 9/1 um} 1520 -735 0 0 0.19 0.19 {}
B 4 1390 -760 1480 -670 {fill=false}
L 4 1420 -740 1420 -690 {}
L 4 1440 -740 1440 -690 {}
L 4 1420 -715 1440 -715 {}
L 4 1360 -715 1420 -715 {}
N 1435 -850 1435 -760 {lab=OUTP}
N 1280 -715 1390 -715 {lab=CMG}
T {CMG} 1250 -745 0 0 0.20 0.20 {layer=4}
N 1435 -670 1435 -470 {lab=VSS}

T {XMON} 1665 -785 0 0 0.22 0.22 {layer=4}
T {NFET W/L = 9/1 um} 1870 -735 0 0 0.19 0.19 {}
B 4 1740 -760 1830 -670 {fill=false}
L 4 1770 -740 1770 -690 {}
L 4 1790 -740 1790 -690 {}
L 4 1770 -715 1790 -715 {}
L 4 1710 -715 1770 -715 {}
N 1785 -850 1785 -760 {lab=OUTN}
N 1630 -715 1740 -715 {lab=CMG}
T {CMG} 1600 -745 0 0 0.20 0.20 {layer=4}
N 1785 -670 1785 -470 {lab=VSS}

N 500 -470 2100 -470 {lab=VSS}
T {VSS} 470 -445 0 0 0.24 0.24 {layer=4}

B 4 500 -405 1190 -35 {fill=false}
T {STAGE-1 DIRECT-SENSE COMMON-MODE LOOP - NCM DRIVES PMOS LOAD GATES} 845 -360 0 0 0.25 0.25 {hcenter=true layer=4}
T {SENSE} 535 -300 0 0 0.20 0.20 {layer=4}
T {XRN1 / XRN2: N1,N2 to NCM, 100 kohm each} 535 -260 0 0 0.20 0.20 {}
T {XCN1 / XCN2: 1 pF each} 535 -225 0 0 0.20 0.20 {}
T {DIRECT CONTROL} 535 -170 0 0 0.20 0.20 {layer=4}
T {NCM directly drives XMLP / XMLN gates.} 535 -130 0 0 0.20 0.20 {}
T {FORMAL RETURN-SIGN AUDIT: NOT CLOSED} 535 -90 0 0 0.20 0.20 {layer=4}

B 4 1250 -405 2225 -35 {fill=false}
T {OUTPUT CONTINUOUS COMMON-MODE FEEDBACK - CMG DRIVES OUTPUT SINKS} 1737 -360 0 0 0.25 0.25 {hcenter=true layer=4}
T {SENSE} 1285 -300 0 0 0.20 0.20 {layer=4}
T {XRCMP / XRCMN: OUTP,OUTN to CMS, 100 kohm each; 1 pF feed-forward each} 1285 -260 0 0 0.20 0.20 {}
T {LOW-GAIN VCM ERROR STAGE} 1285 -215 0 0 0.20 0.20 {layer=4}
T {XCMS / XCMR: CMS vs VCM, W/L = 20/1 um; XCMT W/L = 8/1 um} 1285 -180 0 0 0.19 0.19 {}
T {XRSCS / XRSCR = 10 kohm; XRDS / XRCMG = 105 kohm} 1285 -145 0 0 0.19 0.19 {}
T {CMG drives the 9/1 output sinks; VCM = 0.9 V nominal.} 1285 -110 0 0 0.19 0.19 {}
T {FORMAL MULTILOOP STABILITY: NOT CLOSED} 1285 -78 0 0 0.19 0.19 {layer=4}

T {AUTHORITATIVE SOURCE: ../dynamic_20260911/candidate_06.spice | AUDIT: artifact_manifest.json} 80 15 0 0 0.21 0.21 {layer=4}
T {rd_fdota.sch | visual review page | 2026-09-11} 80 60 0 0 0.20 0.20 {layer=4}
