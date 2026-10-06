#!/usr/bin/env python3
"""New candidate only: explicit global-reset gates, original fix1 untouched."""
import copy,hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent; R=D.parent
base=json.loads((R/'adc_school_r1_fix1_objects.json').read_text());objs=copy.deepcopy(base);changes=[]
for o in objs:
 for block,old,new in [('XSET','XADC_XCMP_BN','XADC_XCMP_S_BAR'),('XRESET','XADC_XCMP_BP','XADC_XCMP_R_BAR')]:
  if o['name'] in ['XADC_XCMP_'+block+'_XP1','XADC_XCMP_'+block+'_XN1']:
   assert o['nets']['G']==old;o['nets']['G']=new
   o['mapping_notes'].append('reset1: retention latch input receives physical global-reset gating; normal Boolean function preserved.')
   changes.append(dict(instance=o['name'],terminal='G',before=old,after=new))
assert len(changes)==4
new=[]
def mos(name,pol,w,d,g,s):
 cell=pol+'fet_01v8';bulk='VSS' if pol=='n' else 'VDD';ww=str(w)
 x={'name':'XADC_XCMP_'+name,'originalpath':'reset1/'+name,'kind':'mos','library':'sky130_fd_pr_main','cell':cell,'view':'symbol','source_parameters':{'W':ww,'L':'0.15','NF':'1','MULT':'1'},'original_model':'sky130_fd_pr__'+cell,'source_location':{'file':'reset1/build_reset1.py','role':'NEW_REAL_GLOBAL_RESET_LOGIC'},'mapping_notes':['Added actual PDK static CMOS gate; not part of frozen original ADC.'],'props':{'w':ww+'u','fw':ww+'u','l':'0.15u','fingers':'1','m':'1'},'mapped_parameters':{'W':ww,'L':'0.15','NF':1,'M':1},'nets':{'D':d,'G':g,'S':s,'B':bulk}}
 new.append(x)
def inv(n,a,y):
 mos(n+'_XP','p',2,y,a,'VDD');mos(n+'_XN','n',1,y,a,'VSS')
def nand(n,a,b,y):
 mid='XADC_XCMP_'+n+'_MID'
 mos(n+'_XP1','p',2,y,a,'VDD');mos(n+'_XP2','p',2,y,b,'VDD')
 mos(n+'_XN1','n',2,y,a,mid);mos(n+'_XN2','n',2,mid,b,'VSS')
def nor(n,a,b,y):
 mid='XADC_XCMP_'+n+'_MID'
 mos(n+'_XN1','n',2,y,a,'VSS');mos(n+'_XN2','n',2,y,b,'VSS')
 mos(n+'_XP1','p',4,mid,a,'VDD');mos(n+'_XP2','p',4,y,b,mid)
inv('XRSTB','RST_N','XADC_XCMP_RST_B')
nor('XSOR_XNOR','XADC_XCMP_BN','XADC_XCMP_RST_B','XADC_XCMP_S_NOR')
inv('XSOR_XINV','XADC_XCMP_S_NOR','XADC_XCMP_S_BAR')
nand('XRAND_XNAND','XADC_XCMP_BP','RST_N','XADC_XCMP_R_NAND')
inv('XRAND_XINV','XADC_XCMP_R_NAND','XADC_XCMP_R_BAR')
assert len(new)==14;objs+=new;assert len(objs)==693 and len({o['name'] for o in objs})==693
ports=json.loads((R/'actual_ams_binding_provenance.json').read_text())['sensor_adc_candidate']['port_order']+['RST_N'];assert len(ports)==27
(D/'objects.json').write_text(json.dumps(objs,indent=2)+'\n')
(D/'delta.json').write_text(json.dumps({'status':'CANDIDATE_NOT_SIMULATED','parent_manifest_sha256':hashlib.sha256((R/'adc_school_r1_fix1_objects.json').read_bytes()).hexdigest(),'new_cell':'p2adc_core_reset1_school_r1','old_cell_untouched':'p2adc_core_fix1_school_r1','ports':ports,'changed_original_connections':changes,'added_devices':[o['name'] for o in new],'added_MOS_count':14,'count':693,'gates':{'reset_inverter':'INV n1u/p2u L.15, from adc_inv','S_BAR':'NOR2 n2u/p4u fromphase_nor + INV n1u/p2u','R_BAR':'NAND2 n2u/p2u fromadc_nand2 + INV n1u/p2u'},'load_risk':'BN formerly drove NAND2 input totalW4um, now NOR2 input totalW6um; BP continues totalW4um. Physical loading, feedthrough, delay and history must be reverified.'},indent=2)+'\n')
def skill(x):
 if isinstance(x,str):return json.dumps(x)
 if isinstance(x,list):return 'list('+' '.join(skill(i) for i in x)+')'
 if isinstance(x,int):return str(x)
 raise TypeError(type(x))
helper=(R/'create_native_fix1.il').read_text().split('\nwhen(ddGetObj')[0].replace('adc_school_r1_20260923','adc_reset1_school_r1_20260923')
cell='p2adc_core_reset1_school_r1'
ss=[helper,'when(ddGetObj("project1" "'+cell+'") error("Existing target; refuse overwrite"))','p2adcOne=p2Create("'+cell+'" list(']
for o in objs:
 cb=['fingers','l','fw','m'] if o['kind']=='mos' else (['segL'] if o['cell'].startswith('res_') else ['w','l','m'])
 ss.append(' '+skill([o['name'],o['library'],o['cell'],list(map(list,o['nets'].items())),list(map(list,o['props'].items())),cb]))
ss += [') '+skill(ports)+')','p2adcSymbol("'+cell+'" '+skill(ports)+')','p2adcOne']
(D/'create_native.il').write_text('\n'.join(ss)+'\n')
print(json.dumps({'cell':cell,'devices':len(objs),'changed_existing_gates':len(changes),'added':len(new),'ports':len(ports)}))
