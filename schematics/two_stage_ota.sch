v {xschem version=3.4.8RC file_version=1.3
* SKY130A two-stage Miller-compensated OTA.
* Schematic-level design only; the load and loop-break elements are external.
}
G {}
K {}
V {}
S {}
F {}
E {}
T {SKY130A 1.8-V TWO-STAGE MILLER-COMPENSATED OTA CORE} 110 -980 0 0 0.7 0.7 {layer=4}
T {Frozen Day 3 sizing; schematic-level simulation only} 110 -945 0 0 0.4 0.4 {layer=4}
T {Single-ended first stage} 590 -900 0 0 0.4 0.4 {layer=4}
T {Second stage + compensation} 1130 -900 0 0 0.4 0.4 {layer=4}
T {Single-IREF bias} 160 -900 0 0 0.4 0.4 {layer=4}
T {M3 = M3A || M3B; M4 = M4A || M4B (each unit W/L = 25/0.5 um)} 585 -250 0 0 0.3 0.3 {layer=4}
T {IREF: external 10-uA sink from IREF/VBP to VSS} 145 -250 0 0 0.3 0.3 {layer=4}
T {RZ = 2 kohm; CC = 3 pF; path VX -> RZ -> NCOMP -> CC -> VOUT} 1080 -250 0 0 0.3 0.3 {layer=4}
T {Nominal external load (not in core): 100 kohm || 5 pF from VOUT to VSS} 1040 -205 0 0 0.3 0.3 {layer=4}
N 120 -850 1490 -850 {lab=VDD}
N 120 -150 1490 -150 {lab=VSS}
N 190 -690 320 -690 {lab=IREF}
N 280 -720 280 -690 {lab=IREF}
N 490 -690 490 -460 {lab=VBN}
N 430 -460 490 -460 {lab=VBN}
N 430 -460 430 -430 {lab=VBN}
N 430 -430 450 -430 {lab=VBN}
N 630 -760 630 -730 {lab=NMIR}
N 630 -730 670 -730 {lab=NMIR}
N 740 -760 740 -730 {lab=NMIR}
N 740 -730 780 -730 {lab=NMIR}
N 670 -470 1015 -470 {lab=TAIL}
N 840 -470 840 -330 {lab=TAIL}
N 540 -500 630 -500 {lab=VINN}
N 885 -500 975 -500 {lab=VINP}
N 1260 -690 1400 -690 {lab=VOUT}
N 1340 -690 1340 -430 {lab=VOUT}
N 1400 -690 1490 -690 {lab=VOUT}
N 1140 -660 1140 -610 {lab=NCOMP}
C {devices/title.sym} 160 -40 0 0 {name=TITLE author="SKY130 two-stage OTA project"}
C {devices/ipin.sym} 885 -500 0 0 {name=pVINP lab=VINP}
C {devices/ipin.sym} 540 -500 0 0 {name=pVINN lab=VINN}
C {devices/opin.sym} 1490 -690 0 0 {name=pVOUT lab=VOUT}
C {devices/iopin.sym} 120 -850 0 1 {name=pVDD lab=VDD}
C {devices/iopin.sym} 120 -150 0 1 {name=pVSS lab=VSS}
C {devices/ipin.sym} 190 -690 0 0 {name=pIREF lab=IREF}
C {devices/lab_pin.sym} 320 -750 0 0 {name=lM8S lab=VDD}
C {devices/lab_pin.sym} 320 -720 0 0 {name=lM8B lab=VDD}
C {devices/lab_pin.sym} 490 -750 0 0 {name=lM9S lab=VDD}
C {devices/lab_pin.sym} 490 -720 0 0 {name=lM9B lab=VDD}
C {devices/lab_pin.sym} 490 -400 0 0 {name=lM10S lab=VSS}
C {devices/lab_pin.sym} 490 -430 0 0 {name=lM10B lab=VSS}
C {devices/lab_pin.sym} 450 -720 0 1 {name=lM9G lab=IREF}
C {devices/lab_pin.sym} 490 -580 0 0 {name=lVBN lab=VBN}
C {devices/lab_pin.sym} 670 -790 0 0 {name=lM3AS lab=VDD}
C {devices/lab_pin.sym} 670 -760 0 0 {name=lM3AB lab=VDD}
C {devices/lab_pin.sym} 670 -730 0 0 {name=lM3AD lab=NMIR}
C {devices/lab_pin.sym} 780 -790 0 0 {name=lM3BS lab=VDD}
C {devices/lab_pin.sym} 780 -760 0 0 {name=lM3BB lab=VDD}
C {devices/lab_pin.sym} 780 -730 0 0 {name=lM3BD lab=NMIR}
C {devices/lab_pin.sym} 960 -790 0 0 {name=lM4AS lab=VDD}
C {devices/lab_pin.sym} 960 -760 0 0 {name=lM4AB lab=VDD}
C {devices/lab_pin.sym} 920 -760 0 1 {name=lM4AG lab=NMIR}
C {devices/lab_pin.sym} 960 -730 0 0 {name=lM4AD lab=VX}
C {devices/lab_pin.sym} 1070 -790 0 0 {name=lM4BS lab=VDD}
C {devices/lab_pin.sym} 1070 -760 0 0 {name=lM4BB lab=VDD}
C {devices/lab_pin.sym} 1030 -760 0 1 {name=lM4BG lab=NMIR}
C {devices/lab_pin.sym} 1070 -730 0 0 {name=lM4BD lab=VX}
C {devices/lab_pin.sym} 670 -500 0 0 {name=lM1B lab=VSS}
C {devices/lab_pin.sym} 670 -530 0 0 {name=lM1D lab=NMIR}
C {devices/lab_pin.sym} 1015 -500 0 0 {name=lM2B lab=VSS}
C {devices/lab_pin.sym} 1015 -530 0 0 {name=lM2D lab=VX}
C {devices/lab_pin.sym} 840 -470 0 0 {name=lTAIL lab=TAIL}
C {devices/lab_pin.sym} 840 -300 0 0 {name=lM5B lab=VSS}
C {devices/lab_pin.sym} 840 -270 0 0 {name=lM5S lab=VSS}
C {devices/lab_pin.sym} 1300 -720 0 1 {name=lM7G lab=IREF}
C {devices/lab_pin.sym} 1340 -750 0 0 {name=lM7S lab=VDD}
C {devices/lab_pin.sym} 1340 -720 0 0 {name=lM7B lab=VDD}
C {devices/lab_pin.sym} 1300 -400 0 1 {name=lM6G lab=VX}
C {devices/lab_pin.sym} 1340 -400 0 0 {name=lM6B lab=VSS}
C {devices/lab_pin.sym} 1340 -370 0 0 {name=lM6S lab=VSS}
C {devices/lab_pin.sym} 800 -300 0 1 {name=lM5G lab=VBN}
C {devices/lab_pin.sym} 1140 -720 0 0 {name=lRZP lab=VX}
C {devices/lab_pin.sym} 1140 -635 0 0 {name=lNCOMP lab=NCOMP}
C {devices/lab_pin.sym} 1140 -550 0 0 {name=lCCM lab=VOUT}
C {sky130_fd_pr/pfet_01v8.sym} 300 -720 0 0 {name=M8
L=0.8
W=7.22005
nf=1 mult=1
model=pfet_01v8
spiceprefix=X}
C {sky130_fd_pr/pfet_01v8.sym} 470 -720 0 0 {name=M9
L=0.8
W=7.22005
nf=1 mult=1
model=pfet_01v8
spiceprefix=X}
C {sky130_fd_pr/nfet_01v8.sym} 470 -430 0 0 {name=M10
L=0.8
W=8.08605
nf=1 mult=1
model=nfet_01v8
spiceprefix=X}
C {sky130_fd_pr/pfet_01v8.sym} 650 -760 0 0 {name=M3A
L=0.5
W=25
nf=1 mult=1
model=pfet_01v8
spiceprefix=X}
C {sky130_fd_pr/pfet_01v8.sym} 760 -760 0 0 {name=M3B
L=0.5
W=25
nf=1 mult=1
model=pfet_01v8
spiceprefix=X}
C {sky130_fd_pr/pfet_01v8.sym} 940 -760 0 0 {name=M4A
L=0.5
W=25
nf=1 mult=1
model=pfet_01v8
spiceprefix=X}
C {sky130_fd_pr/pfet_01v8.sym} 1050 -760 0 0 {name=M4B
L=0.5
W=25
nf=1 mult=1
model=pfet_01v8
spiceprefix=X}
C {sky130_fd_pr/nfet_01v8.sym} 650 -500 0 0 {name=M1
L=0.5
W=16.83798
nf=1 mult=1
model=nfet_01v8
spiceprefix=X}
C {sky130_fd_pr/nfet_01v8.sym} 995 -500 0 0 {name=M2
L=0.5
W=16.83798
nf=1 mult=1
model=nfet_01v8
spiceprefix=X}
C {sky130_fd_pr/nfet_01v8.sym} 820 -300 0 0 {name=M5
L=0.8
W=25.8754
nf=1 mult=1
model=nfet_01v8
spiceprefix=X}
C {sky130_fd_pr/pfet_01v8.sym} 1320 -720 0 0 {name=M7
L=0.8
W=72.2005
nf=1 mult=1
model=pfet_01v8
spiceprefix=X}
C {sky130_fd_pr/nfet_01v8.sym} 1320 -400 0 0 {name=M6
L=0.5
W=8.83907427
nf=1 mult=1
model=nfet_01v8
spiceprefix=X}
C {devices/res.sym} 1140 -690 0 0 {name=RZ1 value=2k m=1}
C {devices/capa.sym} 1140 -580 0 0 {name=CC1 value=3p m=1}
