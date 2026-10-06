#!/usr/bin/env python3
"""Generate isolated M5-location controls using ONLY frozen open 3x3 MIM.

Change only the x position of one independent M5 aggressor. Never edits a PDK,
original array, weights, model or limits. Each run has a new retained directory.
"""
import datetime,hashlib,json,shutil,uuid
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
SOURCE=HERE.parent/'cdac_route_20260911/artifacts/mim_unit.mag'

def main():
 run=HERE/'controls'/('run_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:8]);run.mkdir(parents=True)
 shutil.copyfile(SOURCE,run/'mim_unit.mag')
 header=['set out [file dirname [info script]]','cd $out','snap internal','drc off',
 'proc rectangle {layer x1 y1 x2 y2} {box values ${x1}um ${y1}um ${x2}um ${y2}um; paint $layer}',
 'proc via45 {x y} {rectangle metal4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle via4 [expr {$x-0.59}] [expr {$y-0.59}] [expr {$x+0.59}] [expr {$y+0.59}]; rectangle metal5 [expr {$x-0.80}] [expr {$y-0.80}] [expr {$x+0.80}] [expr {$y+0.80}]}',
 'proc pin {name number layer x y} {box values [expr {$x-0.1}]um [expr {$y-0.1}]um [expr {$x+0.1}]um [expr {$y+0.1}]um; label $name center $layer; port make $number; port class bidirectional; port use signal}']
 cases=[]
 for label,xagg in [('inside',11.27),('outside',-10.0)]:
  cell='p1cdac3_m5_'+label;lines=header+['load '+cell+' -silent','box values 0 0 0 0']
  for row in range(1,33):
   y=row*6
   for col in range(1,5):
    x=col*6;lines+=[f'getcell mim_unit child 0 0 parent {x}um {y}um; identify X_r{row:02d}_c{col:02d}',f'rectangle metal4 {x-.93:.3f} {y-.2:.3f} {x-.53:.3f} {y+3.2:.3f}']
   lines += [f'rectangle metal3 3.570 {y-1.7:.3f} 26.430 {y+1.7:.3f}',f'rectangle metal4 -4.000 {y+2.8:.3f} 23.470 {y+3.2:.3f}',f'via45 -4 {y+3}']
  lines += ['rectangle metal3 26.120 6.000 26.420 192.000','rectangle metal5 -4.800 8.200 -3.200 195.800',f'rectangle metal5 {xagg-.8:.3f} 9.000 {xagg+.8:.3f} 201.000','pin TOP 1 metal3 8.17 6','pin BIT 2 metal5 -4 195',f'pin AGG 3 metal5 {xagg} 200',f'save {cell}','select top cell','expand','drc on','drc style drc(full)','drc check','drc catchup',f'puts "CONTROL_DRC_COUNT {label} [drc list count total]"',f'puts "CONTROL_DRC_DETAILS {label} [drc listall why]"',f'gds write {cell}.gds','drc off',f'flatten {cell}_flat',f'load {cell}_flat',f'save {cell}_flat','extract all','ext2spice lvs',f'ext2spice -o {cell}.lvs.spice','ext2spice cthresh 0','ext2spice rthresh 0',f'ext2spice -o {cell}.cap.spice','quit -noprompt']
  (run/(label+'.tcl')).write_text('\n'.join(lines)+'\n')
  refs=[f'.subckt {cell}_flat TOP BIT AGG']+[f'X{i} BIT TOP sky130_fd_pr__cap_mim_m3_1 w=3 l=3' for i in range(128)]+['.ends']
  (run/(cell+'.reference.spice')).write_text('\n'.join(refs)+'\n')
  cases.append({'case':label,'cell':cell,'MIM_count':128,'MIM_W_L_um':[3,3],'aggressor_x_um':xagg,'aggressor_y_um':[9,201],'aggressor_width_um':1.6,'aggressor_area_um2':307.2,'expected_ports':['TOP','BIT','AGG'],'changed_parameter':'aggressor x coordinate only','TOP_row_fill_width_um':3.4})
 manifest={'status':'GENERATED_NOT_YET_EXTRACTED','source_MIM':str(SOURCE.relative_to(ROOT)),'source_MIM_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'scope':'Open-PDK3x3 historical layout control only. Not school4x4.','hypothesis':'Moving a long M5 conductor off the array reduces TOP coupling, with all other geometry, conductor area and circuit topology unchanged.','cases':cases,'required_readback':['actual DRC','all128 MIM dimensions/terminals','AGG conductor retained as distinct extracted port','TOP-BIT function and parasitic terms','TOP-AGG, BIT-AGG and AGG-substrate coupling'],'limitations':['Open Magic physical coefficients are not independently silicon-qualified','No dynamic switches/noise/reference impedance','AGG is independently driven to isolate its coupling; not a complete array reroute'],'formal_ADC_PEX_allowed':False}
 (run/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print(str(run))
if __name__=='__main__':main()
