#!/usr/bin/env python3
"""Fresh 3um-only central-channel layout candidate, with fixed binary assignment."""
import sys
sys.dont_write_bytecode=True
import collections,datetime,hashlib,importlib.util,json,shutil,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
SRC=HERE.parent/'cdac_route_20260911/generate_routed_cdac.py'
s=importlib.util.spec_from_file_location('route_frozen',SRC);old=importlib.util.module_from_spec(s);s.loader.exec_module(old)
GAP=36.0
CHANNEL={'B0':198.,'B1':200.,'B2':202.,'B3':204.,'B4':222.,'B5':224.,'DUMMY':226.}
LOW=list(CHANNEL);OUTSIDE={net:-24.8-3.2*i for i,net in enumerate(LOW)}
PERIPH={net:y+GAP for net,y in old.PERIPHERY_Y.items()}

def cy(row):return row*6+(GAP if row>=33 else 0)
def uy(unit):return int(unit['row'])*6+GAP/2 if unit['net'] in {'B0','DUMMY'} and unit['electrical'] else cy(int(unit['row']))
def by(run):
 if run['net']=='B0':return 207.  # external landing; lower channel tracks shifted down2um
 if run['net']=='DUMMY':return 219.
 if run['net'] in LOW and run['row']==33:return cy(33)-3
 return cy(run['row'])+3

def rect(l,x1,y1,x2,y2):
 assert x2>x1 and y2>y1,(l,x1,y1,x2,y2)
 return f'rectangle {l} {x1:.3f} {y1:.3f} {x2:.3f} {y2:.3f}'
def pin(n,i,l,x,y):return f'pin {n} {i} {l} {x-.2:.3f} {y-.2:.3f} {x+.2:.3f} {y+.2:.3f}'
HEADER=['set out [file dirname [info script]]','cd $out','snap internal','drc off',
'proc rectangle {layer x1 y1 x2 y2} {box values ${x1}um ${y1}um ${x2}um ${y2}um; paint $layer}',
'proc via45 {x y} {rectangle metal4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle via4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle metal5 [expr {$x-0.80}] [expr {$y-0.80}] [expr {$x+0.80}] [expr {$y+0.80}]}',
'proc pin {name number layer x1 y1 x2 y2} {box values ${x1}um ${y1}um ${x2}um ${y2}um; label $name center $layer; port make $number; port class bidirectional; port use signal}']

def build_side(side,rows):
 cell='c3gap_'+side.lower();lines=HEADER+['load '+cell+' -silent','box values 0 0 0 0'];runs,trunks=old.build_route_plan(rows)
 for u in rows:
  row,col=int(u['row']),int(u['col']);lines +=[f'getcell mim_unit child 0 0 parent {col*6:.3f}um {uy(u):.3f}um; identify X{side}_r{row:02d}_c{col:02d}_{u["net"]}']
 # Full-width M3 row bridges remove the inherited large-M3 notch condition.
 for row in range(1,65):lines +=[rect('metal3',3.57,cy(row)-1.7,386.43,cy(row)+1.7)]
 lines +=[rect('metal3',386.12,cy(1),386.42,cy(64))]
 # Additional TOP access for the two center units whose original center offsets are retained.
 for u in rows:
  if u['electrical'] and u['net'] in {'B0','DUMMY'}:
   x=old.x_c2(int(u['col'])); y1,y2=sorted([cy(int(u['row'])),uy(u)])
   lines +=[rect('metal3',int(u['col'])*6-2.43,y1,int(u['col'])*6+2.43,y2)]
 for u in rows:
  if not u['electrical']:
   c=int(u['col']);y=uy(u);lines +=[rect('metal4',old.x_c1(c)-.2,y-.2,old.x_c2(c)+.2,y+.2)]
 lines +=[rect('metal3',-2.43,-1.7,392.43,1.7),rect('metal3',-2.43,cy(65)-1.7,392.43,cy(65)+1.7),rect('metal3',-2.43,-1.7,2.43,cy(65)+1.7),rect('metal3',387.57,-1.7,392.43,cy(65)+1.7)]
 index={(int(u['row']),int(u['col'])):u for u in rows}
 for run in runs:
  row=run['row'];ybus=by(run);xanchor=run['anchor_x']
  for col in range(run['start_col'],run['end_col']+1):
   x=old.x_c1(col);y=uy(index[(row,col)]);lines +=[rect('metal4',x-.2,min(y,ybus)-.2,x+.2,max(y,ybus)+.2)]
  xs=[old.x_c1(run['start_col']),old.x_c1(run['end_col']),xanchor]
  lines +=[rect('metal4',min(xs)-.2,ybus-.2,max(xs)+.2,ybus+.2),f'via45 {xanchor:.3f} {ybus:.3f}']
 # High bits keep peripheral trunks; low bits use short internal segments to the channel.
 for net in old.NETS_DESC:
  nr=[r for r in runs if r['net']==net]
  if net in LOW:
   yc=CHANNEL[net];xe=OUTSIDE[net];xs=sorted(set(r['anchor_x'] for r in nr))
   for x in xs:
    yy=[by(r) for r in nr if r['anchor_x']==x]+[yc]
    lines +=[rect('metal5',x-.8,min(yy)-.8,x+.8,max(yy)+.8),f'via45 {x:.3f} {yc:.3f}']
   lines +=[rect('metal4',min([xe]+xs)-.2,yc-.2,max([xe]+xs)+.2,yc+.2),f'via45 {xe:.3f} {yc:.3f}',rect('metal5',xe-.8,yc-.8,xe+.8,PERIPH[net]+.8)]
   endpoints=[xe]
  else:
   endpoints=trunks[net]
   for x in endpoints:
    yy=[by(r) for r in nr if r['anchor_x']==x]
    lines +=[rect('metal5',x-.8,min(yy)-.8,x+.8,PERIPH[net]+.8)]
  y=PERIPH[net];lines +=[rect('metal4',min(endpoints+[old.PIN_X])-.2,y-.2,max(endpoints+[old.PIN_X])+.2,y+.2)]
  for x in endpoints:lines +=[f'via45 {x:.3f} {y:.3f}']
 lines +=[pin('TOP',1,'metal3',old.x_c2(1),cy(1))]
 for idx,net in enumerate(old.NETS_DESC,2):lines +=[pin(net,idx,'metal4',old.PIN_X,PERIPH[net])]
 lines +=[pin('EDGE_BIAS',15,'metal3',old.x_c2(0),0),f'save {cell}','select top cell','expand','drc on','drc style drc(full)','drc check','drc catchup',f'puts "CANDIDATE_DRC_COUNT {side} [drc list count total]"',f'puts "CANDIDATE_DRC_DETAILS {side} [drc listall why]"',f'gds write {cell}.gds','drc off',f'flatten {cell}_flat',f'load {cell}_flat',f'save {cell}_flat','extract all','ext2spice lvs',f'ext2spice -o {cell}.lvs.spice','ext2spice cthresh 0','ext2spice rthresh 0',f'ext2spice -o {cell}.cap.spice','quit -noprompt']
 return lines

def moment(rows):
 out={}
 for net in old.NETS_DESC:
  group=[u for u in rows if u['electrical'] and u['net']==net]
  prev=[(int(u['col'])*6,int(u['row'])*6) for u in group];new=[(int(u['col'])*6,uy(u)) for u in group]
  def calc(xy):
   n=len(xy);x=sum(p[0] for p in xy)/n;y=sum(p[1] for p in xy)/n
   return dict(count=n,cx_um=x,cy_um=y,central_xx_um2=sum((p[0]-x)**2 for p in xy)/n,central_yy_um2=sum((p[1]-y)**2 for p in xy)/n,central_xy_um2=sum((p[0]-x)*(p[1]-y) for p in xy)/n)
  before,after=calc(prev),calc(new)
  assert after['count']==(1 if net=='DUMMY' else 1<<int(net[1:]))
  assert after['cx_um']==before['cx_um'] and after['cy_um']-before['cy_um']==GAP/2
  out[net]={'before':before,'candidate':after,'first_moment_offset_preserved':True,'second_moments_not_claimed_preserved':True}
 return out

def main():
 run=HERE/'full_candidate'/('run_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]);run.mkdir(parents=True)
 unit=HERE.parent/'cdac_route_20260911/artifacts/mim_unit.mag';shutil.copyfile(unit,run/'mim_unit.mag')
 positions={};moments={}
 for side in ('P','N'):
  rows=old.read_rows(side);positions[side]=[{**u,'x_um':int(u['col'])*6,'y_um':uy(u)} for u in rows];moments[side]=moment(rows)
  (run/(side.lower()+'.tcl')).write_text('\n'.join(build_side(side,rows))+'\n')
  cell='c3gap_'+side.lower();ref=[f'.subckt {cell}_flat TOP '+ ' '.join(old.NETS_DESC)+' EDGE_BIAS']
  for u in rows:
   net=u['net'] if u['electrical'] else 'EDGE_BIAS';top='TOP' if u['electrical'] else 'EDGE_BIAS';ref +=[f'X{side}_r{u["row"]:02d}_c{u["col"]:02d}_{u["net"]} {net} {top} sky130_fd_pr__cap_mim_m3_1 w=3 l=3']
  ref+=['.ends'];(run/(cell+'.reference.spice')).write_text('\n'.join(ref)+'\n')
 (run/'placement.json').write_text(json.dumps(positions,indent=2)+'\n');(run/'geometric_moments.json').write_text(json.dumps(moments,indent=2)+'\n')
 meta={'status':'GENERATED_UNVERIFIED','source_generator_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'source_MIM_sha256':hashlib.sha256(unit.read_bytes()).hexdigest(),'MIM_scope':'historical open3x3 only','MIM_body_and_binary_counts_unchanged':True,'routing_change':'36um center channel; seven low-net M4 horizontal tracks and externalM5 aggregation; full-width M3 bridge fill to repair actual full-DRC notches' ,'upper_half_translation_um':36,'B0_DUMMY_translation_um':18,'channel_y_um':CHANNEL,'outside_trunk_x_um':OUTSIDE,'first_moments_preserved_up_to_common_18um_y_translation':True,'second_moments_changed_and_retained_in_report':True,'estimated_side_bbox_um':[-44.8,-1.7,410.8,456.8],'estimated_differential_area_um2':941.2*458.5,'formal_ADC_PEX_allowed':False,'school4x4_layout':False,'static_INL_DNL_pass':False}
 (run/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n');print(run)
if __name__=='__main__':main()
