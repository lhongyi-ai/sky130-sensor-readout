#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parent;C=R.parents[2]
HELP=C/'runs/task_20260924T052808271046Z/bsim4_help.txt';SOURCE=R.parent/'cases/matched/baseline/input.scs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
helptext=HELP.read_text();source=SOURCE.read_text();device=next(l for l in source.splitlines() if l.startswith('XTEST '));assert device=='XTEST (D G SB SB) pfet_01v8 w=(32u) l=150n as=8.48p ad=8.48p ps=64.53u pd=64.53u m=(1)*(1)'
# Only documented OP fields, without inferring private internal gate/drain/source aliases.
fields=['region','reversed','vgs','vds','vbs','vgd','vdb','vgb','ids','id','ig','is','ib','gm','gds','gmbs','qg','qd','qs','qb','qjd','qjs','qgdovl','qgsovl','qgi','qdi','qsi','qbi','cgg','cgd','cgs','cgb','cdg','cdd','cds','cdb','csg','csd','css','csb','cbg','cbd','cbs','cbb','cjd','cjs','cggbo','cgdbo','cgsbo','cbgbo','cbdbo','cbsbo','cdgbo','cddbo','cdsbo']
fieldproof={}
help_lines=helptext.splitlines();op_start=next(i for i,l in enumerate(help_lines) if l=='Operating Point Parameters')
for f in fields:
 lines=[{'line_1based':i+1,'text_with_continuation':'\n'.join(help_lines[i:i+3])} for i,l in enumerate(help_lines) if i>op_start and re.match(r'^\d+\s+'+f+r'(?:\s|=)',l)]
 assert lines,f;fieldproof[f]=lines
P='XTEST.msky130_fd_pr__pfet_01v8'
base='''// Static DC mode-boundary / charge diagnostic. No transient or ADC acceptance.
simulator lang=spectre
global 0
parameters VDELTA=0
include "/opt/cadence/CDK/sky130_release_0.0.3/models/sky130.lib.spice" section=tt
VD (D 0) vsource dc=1.8+VDELTA
VG (G 0) vsource dc=0.91642555277800053
VS (SB 0) vsource dc=1.8
'''+device+'\n'
base+='saveOptions options save=selected\nsave D G SB\n'
base+=f'save {P}:int_b {P}:dbnode {P}:sbnode sigtype=node\n'
for group in [fields[i:i+8] for i in range(0,len(fields),8)]:base+='save '+' '.join(P+':'+f for f in group)+' sigtype=dev\n'
base+=f'save {P}:currents VD:currents VG:currents VS:currents sigtype=dev\n'
# These info analyses were already used in generated school native netlists. No whole-PDK models dump.
base+='element info what=inst where=rawfile\noutputParameter info what=output where=rawfile\n'
profiles={}
for profile,rel,vab,iab,wide,fine in [('baseline','1e-5','1e-8','1e-13',1e-4,1e-6),('strict','1e-6','1e-9','1e-14',5e-5,5e-7)]:
 text=base+f'simulatorOptions options temp=27 tnom=27 reltol={rel} vabstol={vab} iabstol={iab} gmin=1e-12 cmin=0 maxwarns=1000 maxwarnstologfile=1000 maxnotes=1000 maxnotestologfile=1000\n'
 sweeps={}
 for name,extent,step in [('wide',.02,wide),('fine',.001,fine)]:
  for direction,sign in [('up',1),('down',-1)]:
   analysis='dc_'+name+'_'+direction;start=-extent*sign;stop=extent*sign;signed_step=step*sign
   text+=f'{analysis} dc param=VDELTA start={start:.17g} stop={stop:.17g} lin={round(2*extent/step)} oppoint=rawfile force=none useprevic=no swpuseprevic=yes\n'
   sweeps[analysis]={'start_V':start,'stop_V':stop,'step_V':signed_step,'expected_points':round(2*extent/step)+1,'external_D_voltage':'1.8+VDELTA','direction':direction,'lin_steps':round(2*extent/step)}
 p=R/f'input_{profile}.scs';p.write_text(text);profiles[profile]={'file':p.name,'sha256':sha(p),'requested_reltol':float(rel),'vabstol':float(vab),'iabstol':float(iab),'sweeps':sweeps}
m={'id':'static_charge_v1','status':'PREPARED_NOT_RUN','scope':'DC_MODEL_BOUNDARY_DIAGNOSTIC_ONLY','full_ADC_accuracy_pass':False,'complete_ADC':False,'source_input_sha256':sha(SOURCE),'device_record':device,'gate_fixed_V':.91642555277800053,'source_bulk_V':1.8,'profiles':profiles,'documented_op_fields':fieldproof,'installed_bsim4_help':str(HELP),'installed_bsim4_help_sha256':sha(HELP),'installed_dc_help':str(C/'runs/task_20260924T075637544368Z/dc_help.txt'),'installed_dc_help_sha256':sha(C/'runs/task_20260924T075637544368Z/dc_help.txt'),'dc_sweep_syntax':'start/stop/lin from installedDChelp; positive lin stepcount avoids negative step interpretation. Explicitoppoint/rawfile, force=none,useprevic=no,swpuseprevic=yes; actual saved fields/pointcounts must be checked.','internal_body_save_evidence':'int_b/dbnode/sbnode validated in actual school Spectre21 task060914 bodyprobe; undocumented int_g/int_d/int_s not requested.','model_options_boundary':'Do not save selector names as OP when help only lists them as model/instance parameters. limited_model_metadata.py records actual filehash and selected literal selectors across bins; not proof of effective selected bin or override. instance/output info may add observed effective instance dimensions, but never dump what=models.','derivative_contract':{'axis':'external VD varied; VG/VS/externalVB fixed. Internal BP/DB/SB and possibleinternalG/D/S states solve afresh.','saved_charge_sign':'Raw signed Spectre q-values retained. Never multiply byPFETtype or reversed. No automatic source/drain renaming.','installed_intrinsic_partial_definitions':{'cgdbo':'-dQg/dVd intrinsic','cddbo':'dQd/dVd intrinsic','cbdbo':'-dQb/dVd intrinsic'},'diagnostic_comparisons':['one-sided d(qgi)/d(external VD) alongside -cgdbo','one-sided d(qdi)/d(external VD) alongside cddbo','one-sided d(qbi)/d(external VD) alongside -cbdbo'],'not_equality_test':'DCtotal derivative contains internalnode chain response and field conventions. Intrinsic partialC is not guaranteed equal to external-sweep derivative; no pass threshold assigned.','one_sided_fit_windows_abs_delta_V':[[1e-6,5e-6],[2e-6,1e-5],[5e-6,2e-5]],'fit_reporting':'Use true measured D−SB axis, centered/scaled fits, residuals and conditionnumber. Compareup/down and1/0.5uV grids. Anyintercept difference is numerical/finitewindow evidence, not an automatic physical discontinuity finding.','cross_zero_handling':'Never substitute central cross-zero derivative for branch-resolved values. Preserveexactzero, reversed enum and anynearzero modechanges.'},'limits':['DC has no dQ/dt or transient integration; a smoothDCresult cannotprove transientLTE resolved.','Chargeoutputs may include differentintrinsic/overlap/junction scopes. Keepqjd/qjs separate, and do notassert totalQclosure or addjunctioncharge twice withoutactual schema/modelcontract.','Same ideal-source fixture removes native finite impedance, dynamichistory and ADC feedback. Thisis not ADC validation.','Tool rejection or missingcharge signals must be reported; nozero filling or fabricatedcharge derivatives.']}
(R/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('PREPARED',R)
