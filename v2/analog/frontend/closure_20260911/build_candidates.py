#!/usr/bin/env python3
"""Explicit physical headroom corrections, never an automated parameter search."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'repair_20260910/results/20260910T062811944809Z_cascoded_tail_g16/candidate.spice'
BASE_SHA='564f4776c4c61872de63648816ef5aaf51555769edeca326042f287880ae1a3c'


def once(source,before,after):
    if source.count(before)!=1:raise ValueError('Expected one marker: '+before)
    return source.replace(before,after)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name',choices=['headroom_a','headroom_b','headroom_c'],required=True)
    args=p.parse_args()
    if hashlib.sha256(BASE.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Baseline changed')
    s=BASE.read_text()
    s,n=re.subn(r'^(X[PN][1-6] D[PM] I[PM] TAIL VSS )sky130_fd_pr__nfet_01v8( L=2 W=800)$',
                r'\1sky130_fd_pr__nfet_01v8_lvt\2',s,flags=re.MULTILINE)
    if n!=12:raise ValueError('Expected 12 real LVT input instances')
    s=once(s,'XT0 TS BN VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=312\nXT1 TS BN VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=312',
           '\n'.join(f'XT{i} TS BN VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=624' for i in range(4)))
    s=once(s,'XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=1',
           'XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=5\n'
           '* Dedicated same-L tail mirror reference, lower inversion density.\n'
           'XBNTBIAS BNT BP VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=10\n'
           'XBNTD BNT BNT VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=44')
    for side,drains in [('P','NPC NNC'),('N','NNC NPC')]:
        s=once(s,f'XERR{side} IN{side} FB{side} {drains} BN BT VSS fdda_error_pair',
               f'XERR{side} IN{side} FB{side} {drains} BNT BT VSS fdda_error_pair')
    s=once(s,'XCASBP BCASC BP VDD VDD sky130_fd_pr__pfet_01v8 L=1 W=1\n'
           'XNCASA BCASC BCASC BCASM VSS sky130_fd_pr__nfet_01v8 L=1 W=8\n'
           'XNCASB BCASM BCASM VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=8',
           '* Physical midpoint of VDD and external VCM, not an ideal internal source.\n'
           'XRCBH VDD BCASC VSS frontend_r100k\n'
           'XRCBL BCASC VCM VSS frontend_r100k')
    for side in ('P','N'):
        s=once(s,f'XO{side} OUT{side} X{side} VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=105',
               f'XO{side} OUT{side} X{side} VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=10')
    if args.name in ('headroom_b','headroom_c'):
        s=once(s,'XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=5',
               'XBTD BT BT VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=3.5')
        s=once(s,'XCCM CMCTL VSS frontend_c1p','XCCM CMCTL VSS frontend_c4p')
    if args.name=='headroom_c':
        s=once(s,'XCMT CMTAIL BN VSS VSS sky130_fd_pr__nfet_01v8 L=1 W=192',
               '* CM tail is 0.4 times each error-pair tail, using identical current density.\n'
               'XCMT CMTS BNT VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=499.2\n'
               'XCMT1 CMTS BNT VSS VSS sky130_fd_pr__nfet_01v8 L=2 W=499.2\n'
               'XCMTC0 CMTAIL BT CMTS VSS sky130_fd_pr__nfet_01v8 L=1 W=320\n'
               'XCMTC1 CMTAIL BT CMTS VSS sky130_fd_pr__nfet_01v8 L=1 W=320')
        s=once(s,'XFFN OUTN CMSENSE frontend_c1p',
               'XFFN OUTN CMSENSE frontend_c1p\n'
               '* 100k||100k to outputs plus 50k/15 to VCM gives 1/16 DC error sensing.\n'
               '* Two 1 pF feedforward cells plus 30 pF to VCM preserve that AC ratio.\n'
               'XRCMATT CMSENSE VCM VSS frontend_r R=3333.333333333333\n'+
               '\n'.join(f'XCMATT{i} CMSENSE VCM frontend_c1p' for i in range(30)))
    s=f'* closure_20260911 {args.name}: unqualified physical candidate.\n'+s
    target=HERE/'candidates'/f'{args.name}.spice'
    target.parent.mkdir(exist_ok=True)
    if target.exists():raise FileExistsError('Candidates are immutable: '+str(target))
    target.write_text(s)
    metadata={'name':args.name,'baseline_sha256':BASE_SHA,'source_sha256':hashlib.sha256(s.encode()).hexdigest(),
              'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'changes':['PDK LVT input gates improve low-input source/tail headroom.',
                         'Four W624/L2 bottom tails per error pair, same-L W44/L2 reference at ~5.5 uA; target mirror ratio 56.7.',
                         'Real BT diode W5/L1 lowers cascode gate; no ideal internal bias source.',
                         'Two 100kohm PDK resistor strings set BCASC midpoint between VDD and externally specified VCM.',
                         'Output NMOS W10/L2 raises first-stage gate/drain voltage at approximately the existing output bias current.'],
              'risks':['Potential output-stage gm and phase-margin reduction.',
                       'LVT noise and leakage not inherited from standard-Vt baseline.',
                       'Reference source loading and bias startup need later qualification.',
                       'No assumed static, stability, noise, power or PVT pass.']}
    if args.name in ('headroom_b','headroom_c'):
        metadata['changes'] += ['BT diode W3.5, not W5: raise middle tail node to improve bottom-tail output resistance.',
                                'CMCTL compensation uses four actual 1 pF MIM cells instead of one.']
    if args.name=='headroom_c':
        metadata['changes'] += ['CM tail bottom W998.4/L2 total, upper W640/L1 total: exactly 0.4 geometric scale of an input error-pair tail at identical BNT/BT bias.',
                                'CM error attenuator uses real 100k output strings and 3333.333ohm shunt to external VCM, with 2pF/30pF corresponding capacitive division.',
                                'Intended common-mode crossover reduction from measured 1.804MHz toward 0.3MHz; no assumed stability pass.']
    target.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':main()
