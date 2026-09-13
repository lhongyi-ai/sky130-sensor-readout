#!/usr/bin/env python3
"""Build deterministic native-design descriptions from the frozen Day 4 source."""
import hashlib
import json
import re
import shutil
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent
VERSION = '1.0.4'

def put(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def inst(name, cell, nets, props=None, lib='analogLib', pins=None):
    if pins is None:
        pins = ['PLUS', 'MINUS']
    return dict(name=name, lib=lib, cell=cell, terminals=dict(zip(pins, nets)), props=props or {})

def build():
    ref = ROOT / 'reference'
    ref.mkdir(exist_ok=True)
    authority=BASE if (BASE/'reference_manifest.json').is_file() else ROOT
    manifest = json.loads((authority / 'reference_manifest.json' if authority==BASE else ref/'reference_manifest.json').read_text())
    for item in manifest['sources']:
        src = authority / item['snapshot']
        assert hashlib.sha256(src.read_bytes()).hexdigest() == item['sha256'], src
        if src.resolve()!=(ref/src.name).resolve(): shutil.copyfile(src, ref / src.name)
    if authority==BASE: shutil.copyfile(BASE / 'reference_manifest.json', ref / 'reference_manifest.json')
    source = (ref / 'ota_subckt.spice').read_text()
    ota = []
    mapping=[]
    for line in source.splitlines():
        if not line.startswith('XM'):
            continue
        f = line.split()
        values = dict(x.split('=') for x in f[6:])
        original_w=Decimal(values['W'])
        migrated_w=original_w.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
        width=format(migrated_w.normalize(),'f')
        names=['M7A','M7B'] if f[0]=='XM7' else [f[0][1:]]
        unit_width=format((migrated_w/len(names)).normalize(),'f')
        assert Decimal(unit_width)<=50, 'Per-instance width exceeds observed school limit'
        mapping.append(dict(device=f[0][1:],original_w_um=str(original_w),cadence_w_um=width,
            instances=names,unit_w_um=unit_width,
            delta_um=str(migrated_w-original_w),relative_change=float((migrated_w-original_w)/original_w),
            length_um=values['L'],fingers=1,m=1,
            evidence='M8 width 7.22u accepted in returned diagnostic' if f[0]=='XM8' else 'Pending Linux CDF validation'))
        for name in names:
            ota.append(inst(name, f[5].replace('sky130_fd_pr__', ''), f[1:5],
                        dict(w=unit_width+'u', fw=unit_width+'u', l=values['L']+'u',
                             fingers='1', m='1'), 'sky130_fd_pr_main', ['D','G','S','B']))
    assert len(ota) == 13
    put('size_mapping.json',dict(policy='Explicit migration choice: widths rounded to 0.01 um; not a claimed PDK minimum grid.',
        source='reference/ota_subckt.spice',evidence='reference/p1_m8_diagnose.txt',devices=mapping))
    table=['# 原尺寸与 Cadence 迁移尺寸','',
           '原始源码不变。下列宽度是本次明确选择的迁移尺寸；0.01 µm 不是从单个 M8 样本推导出的工艺最小网格。所有回调和导出网表仍须严格匹配这些目标值。','',
           '| 器件 | 原 W / µm | 迁移 W / µm | 差值 / µm | 相对变化 |','|---|---:|---:|---:|---:|']
    for row in mapping:
        table.append('| {device} | {original_w_um} | {cadence_w_um} | {delta_um} | {percent:.6f}% |'.format(percent=row['relative_change']*100,**row))
    table+=['','M7 的迁移总宽度 72.2 µm 分成 M7A、M7B 两个并联 PMOS，每个 W=36.1 µm、L=0.8 µm、fingers=m=1；各自 D/G/S/B 均与原 M7 对应端相连。学校报告已确认单指上限 50 µm。分拆后分别生成扩散几何，寄生参数不保证与单实例一致，需在仿真中对照。',
            '仅 M8 的 7.22 µm 已有独立学校 CDF 诊断证据；本版所有实例仍待 Linux 验证。最大总宽度相对调整小于 0.05%，不代表性能差异已验证。旧 ngspice 与新 Cadence 对照必须同时考虑尺寸映射、并联分拆和模型版本差异。','']
    (ROOT/'尺寸映射.md').write_text('\n'.join(table))
    ota += [inst('RZ1','res',['VX','NCC'],{'r':'2k'}), inst('CC1','cap',['NCC','VOUT'],{'c':'3p'})]
    ports = ['VDD','VSS','VINP','VINN','VOUT','VBP']
    cells = {'p1b_ota_legacy_r4':dict(ports=ports, instances=ota)}
    # Keep native PDK defaults for the first R/C qualification; never invent a resistance/area formula.
    cells['p1b_tb_res'] = dict(ports=[], instances=[
        inst('R0','res_high_po_0p35',['TEST','VSS','VSS'],lib='sky130_fd_pr_main',pins=['PLUS','MINUS','B']),
        inst('VTEST','vdc',['TEST','VSS'],{'vdc':'VTEST','acm':'1'}),
        inst('VSSSUP','vdc',['VSS','0'],{'vdc':'0'})])
    cells['p1b_tb_mim'] = dict(ports=[], instances=[
        inst('C0','cap_mim_m3__base',['TEST','VSS'],lib='sky130_fd_pr_main'),
        inst('VTEST','vdc',['TEST','VSS'],{'vdc':'0.9','acm':'1'}),
        inst('VSSSUP','vdc',['VSS','0'],{'vdc':'0'})])
    cells['p1b_tb_rc'] = dict(ports=[], instances=[
        inst('R0','res_high_po_0p35',['VIN','VOUT','VSS'],lib='sky130_fd_pr_main',pins=['PLUS','MINUS','B']),
        inst('C0','cap_mim_m3__base',['VOUT','VSS'],lib='sky130_fd_pr_main'),
        inst('VIN','vpulse',['VIN','VSS'],dict(val0='0',val1='0.1',delay='1n',rise='1p',fall='1p',width='5n',period='10n')),
        inst('VSSSUP','vdc',['VSS','0'],{'vdc':'0'})])
    for mode in ['op','ac','loop','step','cm','psrrp','psrrm','noise','swing']:
        a = [inst('VSSSUP','vdc',['VSS','0'],{'vdc':'0','acm':'1' if mode=='psrrm' else '0'}),
             inst('VDD','vdc',['VDD','0' if mode=='psrrm' else 'VSS'],{'vdc':'VDD','acm':'1' if mode=='psrrp' else '0'}),
             inst('IREF','idc',['VBP','VSS'],{'idc':'10u'}),
             inst('RLOAD','res',['VOUT','VSS'],{'r':'100k'}),
             inst('CLOAD','cap',['VOUT','VSS'],{'c':'CL'})]
        closed = mode in ['op','step','swing']
        a += [inst('XOTA','p1b_ota_legacy_r4',['VDD','VSS','VINP','VOUT' if closed else 'VINN','VOUT','VBP'],lib='project1',pins=ports)]
        if mode=='step':
            a += [inst('VINP','vpulse',['VINP','VSS'],dict(val0='0.8',val1='1.2',delay='1u',rise='20n',fall='20n',width='2u',period='5u'))]
        else:
            amp = '0.5' if mode=='ac' else ('1' if mode in ['cm','noise'] else '0')
            a += [inst('VINP','vdc',['VINP','VSS'],{'vdc':'VCM','acm':amp})]
        if mode in ['ac','loop']:
            a += [inst('VTEST','vdc',['VTEST','VSS'],{'vdc':'0','acm':'0.5' if mode=='ac' else '1','acp':'180' if mode=='ac' else '0'}),
                  inst('LBREAK','ind',['VOUT','VINN'],{'l':'1G'}),
                  inst('CBREAK','cap',['VTEST','VINN'],{'c':'1G'})]
        elif not closed:
            a += [inst('VINN','vdc',['VINN','VSS'],{'vdc':'VCM','acm':'1' if mode=='cm' else '0'})]
        cells['p1b_tb_'+mode] = dict(ports=[],instances=a)
    for c in cells.values():
        for i, obj in enumerate(c['instances']):
            obj['xy'] = [(i % 4)*4, -(i // 4)*5]
    put('design.json',dict(version=VERSION, library='project1',cells=cells))
    day4 = json.loads((ref/'day4_manifest.json').read_text())
    # Freeze all original PVT raw evidence, not just the nominal curves.
    original=BASE.parents[1]/'results/raw/day4/pvt'
    if not original.is_dir(): original=ref/'pvt_raw'
    (ref/'pvt_raw').mkdir(exist_ok=True)
    evidence={}
    for point in day4['pvt_points']:
        for mode in ['op','diff_ac','loop','transient']:
            src=original/(point['point_id']+'_'+mode+'.tsv')
            text=src.read_text()
            if day4['manifest_sha256'] not in text: raise ValueError('Raw evidence lacks frozen manifest '+str(src))
            if src.resolve()!=(ref/'pvt_raw'/src.name).resolve(): shutil.copyfile(src,ref/'pvt_raw'/src.name)
            evidence['pvt_raw/'+src.name]=hashlib.sha256(src.read_bytes()).hexdigest()
    (ref/'raw_evidence_manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    jobs = []
    def job(name,bench,analysis,point=None,**extra):
        p = point or dict(point_id='P01',process='tt',vdd_v=1.8,temp_c=27)
        jobs.append(dict(id=name,cell='p1b_tb_'+bench,analysis=analysis,corner=p['process'],temp=p['temp_c'],
                         params=dict(VDD=p['vdd_v'],VCM=.9,CL=5e-12,VTEST=0),point=p['point_id'],**extra))
    job('res_dc','res','res_dc',group='passives')
    job('mim_ac','mim','ac',group='passives')
    job('rc_step','rc','rc_step',group='passives')
    for p in day4['pvt_points']:
        for mode in ['op','ac','loop','step']:
            job(p['point_id']+'_'+mode,mode, 'ac' if mode=='loop' else mode,p,group='nominal' if p['point_id']=='P01' else 'pvt')
    for mode in ['cm','psrrp','psrrm','noise','swing']:
        job('nom_'+mode,mode,'noise' if mode=='noise' else ('swing' if mode=='swing' else 'ac'),group='extra')
    for cl in [1,2,10,20]:
        for mode in ['loop','step']:
            job('load_%dp_%s'%(cl,mode),mode,'ac' if mode=='loop' else mode,group='extra')
            jobs[-1]['params']['CL']=cl*1e-12
    for n in range(19):
        job('icmr_%02d'%n,'ac','ac',group='extra')
        jobs[-1]['params']['VCM']=n*.1
    put('jobs.json', jobs)
    # A compact SKILL literal is a generated input, not evaluated Python code.
    def il(x):
        if isinstance(x,str): return json.dumps(x)
        if isinstance(x,list): return 'list('+ ' '.join(il(v) for v in x)+')'
        return str(x)
    records = []
    for name,c in cells.items():
        objs = [[o['name'],o['lib'],o['cell'],o['xy'],list(map(list,o['terminals'].items())),list(map(list,o['props'].items()))] for o in c['instances']]
        records.append([name,c['ports'],objs])
    (ROOT/'design.il').write_text('; Generated by build.py from frozen reference.\np1bDesign='+il(records)+'\n')
    put('local_status.json',dict(status='LOCAL_PREPARED_LINUX_NOT_RUN',version=VERSION,
        cell_count=len(cells),job_count=len(jobs),qualification='No Cadence pass is claimed by this package.'))

if __name__ == '__main__': build()
