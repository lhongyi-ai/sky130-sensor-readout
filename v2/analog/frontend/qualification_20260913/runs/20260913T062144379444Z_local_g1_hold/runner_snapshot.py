#!/usr/bin/env python3
"""Frozen, serial and append-only frontend qualification diagnostics.

The bilateral Tian two-injection calculation is a local diagnostic. Its outputs
are never promoted to complete multiloop signoff. The assembled circuit is
unchanged at DC; each local probe leaves all other physical loops closed.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, os, re, signal, subprocess, time
import numpy as np

HERE=Path(__file__).resolve().parent
NG='/foss/tools/ngspice/bin/ngspice'
LIB='/foss/pdks/sky130A/libs.tech/combined/sky130.lib.spice'
MODES=('dm','input_cm','stage1_cm','output_cm')
SOURCES=('candidate_06.spice','sampling_switch.spice','adc_blocks.spice')

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x): Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def rep(s,a,b):
    if s.count(a)!=1: raise ValueError(a)
    return s.replace(a,b,1)

def instrument(source):
    s=rep(source,'.subckt rd_fdota INP INN OUTP OUTN VDD VSS VCM','.subckt rd_fdota INP INN OUTP OUTN VDD VSS VCM params: NV=0 NI=0 OV=0 OI=0')
    s=rep(s,'XMLP N1 NCM VDD VDD','VTESTNCM NCM_GATE NCM dc 0 ac {NV}\nITESTNCM VSS NCM_GATE dc 0 ac {NI}\nXMLP N1 NCM_GATE VDD VDD')
    s=rep(s,'XMLN N2 NCM VDD VDD','XMLN N2 NCM_GATE VDD VDD')
    s=rep(s,'XCMS DS CMS CS VSS','VTESTOCM CMS_ERROR CMS dc 0 ac {OV}\nITESTOCM VSS CMS_ERROR dc 0 ac {OI}\nXCMS DS CMS_ERROR CS VSS')
    s=rep(s,'.subckt sky130_v2_switchable_pga VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1','.subckt sky130_v2_switchable_pga VINP VINN OUTP OUTN VDD VSS VCM SEL0 SEL1 params: DV=0 DI=0 CV=0 CI=0 NV=0 NI=0 OV=0 OI=0')
    s=rep(s,'XOTA SUMPOS SUMNEG OUTP OUTN VDD VSS VCM rd_fdota','VTESTP I_SUMPOS SUMPOS dc 0 ac {DV*.5+CV}\nVTESTN I_SUMNEG SUMNEG dc 0 ac {-DV*.5+CV}\nITESTD I_SUMNEG I_SUMPOS dc 0 ac {DI}\nITESTCP VSS I_SUMPOS dc 0 ac {CI*.5}\nITESTCN VSS I_SUMNEG dc 0 ac {CI*.5}\nXOTA I_SUMPOS I_SUMNEG OUTP OUTN VDD VSS VCM rd_fdota NV={NV} NI={NI} OV={OV} OI={OI}')
    return s

def base(gain,state,source='candidate_06.spice',corner='tt',vdd=1.8,temp=27):
    return [f'* Frozen candidate_06: G{gain}, {state}',f'.lib {LIB} {corner}',f'.include {source}', '.include adc_blocks.spice','.include sampling_switch.spice',f'.temp {temp}', '.options reltol=1e-6 abstol=1e-14 vntol=1e-9 chgtol=1e-18 itl1=300 itl2=300 method=gear maxord=2',f'VDD VDD 0 {vdd}',f'VCM VCM 0 {vdd/2}',f'VINP VINP 0 {vdd/2} ac .5',f'VINN VINN 0 {vdd/2} ac -.5',f'VACQ ACQ 0 {vdd if state=="acquire" else 0}',f'VACQB ACQB 0 {0 if state=="acquire" else vdd}',f'VSEL0 SEL0 0 {vdd if gain==4 else 0}',f'VSEL1 SEL1 0 {vdd if gain==16 else 0}']

def dut(tag='',params=''):
    t=tag
    return [f'RSP{t} VINP IP{t} 350',f'RSN{t} VINN IN{t} 350',f'XPGA{t} IP{t} IN{t} OP{t} ON{t} VDD 0 VCM SEL0 SEL1 sky130_v2_switchable_pga {params}',f'XRIP{t} OP{t} FP{t} 0 rd_hr R=1500',f'XRIN{t} ON{t} FN{t} 0 rd_hr R=1500',f'XCFP{t} FP{t} 0 rd_c4p',f'XCFN{t} FN{t} 0 rd_c4p',f'XTGP{t} FP{t} HP{t} ACQ ACQB VDD 0 rd_sampling_tgate',f'XTGN{t} FN{t} HN{t} ACQ ACQB VDD 0 rd_sampling_tgate',f'XCP{t} HP{t} VCM adc_mim_bank COUNT=4096',f'XCN{t} HN{t} VCM adc_mim_bank COUNT=4096',f'RLEAKP{t} HP{t} VCM 1g',f'RLEAKN{t} HN{t} VCM 1g']

def control():return ['.control','set noaskquit','set num_threads=1','set wr_singlescale','set wr_vecnames','set numdgt=15','set filetype=ascii']
def end():return ['quit','.endc','.end']

def local_deck(gain,state):
    lines=base(gain,state,'injections.spice')
    lines=[x.replace(' ac .5',' ac 0').replace(' ac -.5',' ac 0') for x in lines]
    vec=[]; defs=[]
    for mode in MODES:
        for inj in ('v','i'):
            tag=f'_{mode}_{inj}'; p='xpga'+tag; o=p+'.xota'
            key={'dm':'D','input_cm':'C','stage1_cm':'N','output_cm':'O'}[mode]+inj.upper()
            lines+=dut(tag,f'{key}=1')
            if mode=='dm':
                ve=f'(v({p}.i_sumpos)-v({p}.i_sumneg))'; vf=f'(v({p}.sumpos)-v({p}.sumneg))'; current=f'(-i(v.{p}.vtestp)+i(v.{p}.vtestn))/2'
            elif mode=='input_cm':
                ve=f'(v({p}.i_sumpos)+v({p}.i_sumneg))/2'; vf=f'(v({p}.sumpos)+v({p}.sumneg))/2'; current=f'(-i(v.{p}.vtestp)-i(v.{p}.vtestn))'
            else:
                gate,node,dev=('ncm_gate','ncm','vtestncm') if mode=='stage1_cm' else ('cms_error','cms','vtestocm')
                ve=f'v({o}.{gate})';vf=f'v({o}.{node})';current=f'-i(v.{o}.{dev})'
            for name,expr in [('ve',ve),('vf',vf),('if',current)]:
                k=mode+'_'+inj+'_'+name
                defs += [f'let {k}={expr}',f'let {k}_r=real({k})',f'let {k}_i=imag({k})']
                vec += [k+'_r',k+'_i']
    lines+=control()+['op','ac dec 120 1 1g']+defs+[f'wrdata response.dat {" ".join(vec)}']+end()
    return '\n'.join(lines)+'\n',['frequency']+vec

def noise_deck(gain,state):
    lines=base(gain,state)+dut()+control()+['op','wrdata op.dat v(op) v(on) v(fp) v(fn) i(vdd) i(vcm)','ac dec 120 1 1g','let gain=mag(v(fp)-v(fn))','wrdata gain.dat gain','noise v(fp,fn) VINP dec 120 1 1g','setplot noise1','wrdata noise_density.dat onoise_spectrum inoise_spectrum','setplot noise2','print all','write noise_integrated.raw all']+end()
    return '\n'.join(lines)+'\n',None

def pz_deck(gain,state):
    lines=base(gain,state)+dut()+control()+['op','wrdata op.dat v(op) v(on) v(fp) v(fn) i(vdd) i(vcm)','pz fp 0 fp 0 cur pol','print all','write poles.raw all']+end()
    return '\n'.join(lines)+'\n',None

def crossing(f,z):
    db=20*np.log10(abs(z)); ph=np.unwrap(np.angle(z))*180/np.pi
    ph-=360*np.round(ph[0]/360);out=[]
    for k in np.where(db[:-1]*db[1:]<0)[0]:
        a=-db[k]/(db[k+1]-db[k]); p=ph[k]+a*(ph[k+1]-ph[k])
        out.append({'frequency_hz':float(f[k]*(f[k+1]/f[k])**a),'phase_deg':float(p),'phase_margin_deg':float(180+p),'direction':'down' if db[k]>0 else 'up'})
    return {'low_frequency_gain_db':float(db[0]),'low_frequency_phase_deg':float(ph[0]),'unity_crossings':out,'min_distance_to_minus_one':float(np.min(abs(1+z)))}

def analyze_local(folder,cols):
    d=np.loadtxt(folder/'response.dat',skiprows=1,ndmin=2)
    if d.shape[1]!=len(cols) or not np.isfinite(d).all() or abs(d[-1,0]/1e9-1)>1e-9:raise ValueError('Invalid AC span/data')
    idx={x:i for i,x in enumerate(cols)}
    def v(key):return d[:,idx[key+'_r']]+1j*d[:,idx[key+'_i']]
    result={}; export=[d[:,0]];headers=['frequency_hz']
    for mode in MODES:
        A=v(mode+'_i_if');B=v(mode+'_v_if');C=v(mode+'_i_ve');D=v(mode+'_v_ve')
        den=2*(B*C-A*D)+A-D+1
        t=(2*(A*D-B*C)-A+D)/den
        raw=-v(mode+'_v_vf')/D
        if not np.isfinite(t).all():raise ValueError('Nonfinite bilateral ratio')
        result[mode]={'tian_bilateral_local_diagnostic':crossing(d[:,0],t),'old_voltage_ratio_diagnostic':crossing(d[:,0],raw),'minimum_formula_denominator_abs':float(min(abs(den))),'complete_multiloop_signoff':False}
        export += [t.real,t.imag,raw.real,raw.imag];headers += [mode+'_'+k for k in ('tian_real','tian_imag','old_real','old_imag')]
    np.savetxt(folder/'local_return_ratios.csv',np.column_stack(export),delimiter=',',header=','.join(headers),comments='')
    return {'loops':result,'status':'BILATERAL_LOCAL_DIAGNOSTICS_COMPLETE','formal_stability_gate_pass':False}

def analyze_noise(folder,gain):
    d=np.loadtxt(folder/'noise_density.dat',skiprows=1,ndmin=2)
    if d.shape[1]!=3 or not np.isfinite(d).all() or abs(d[-1,0]/1e9-1)>1e-9 or np.min(d[:,1:])<0:raise ValueError('Invalid noise span/data')
    f=d[:,0];density=d[:,1]
    def integral(hi):
        mask=f<hi; x=np.r_[f[mask],hi];y=np.r_[density[mask],np.interp(hi,f,density)]
        return float(np.sqrt(np.trapezoid(y*y,x)))
    # Fixed per-gain calibration is taken only from matching frozen candidate.
    old=json.loads((HERE.parent/'dynamic_20260911/qualification.json').read_text())
    if old['candidate_sha256']!=sha(HERE/'candidate_06.spice'):raise ValueError('Calibration source hash mismatch')
    gain_data=old['gains'][str(gain)]
    return {'status':'STATIC_NOISE_DIAGNOSTIC_COMPLETE','output_rms_v':{str(hi):integral(hi) for hi in (5000,50000,1000000000)},'calibration_record':{k:v for k,v in gain_data.items() if 'calib' in k},'provisional_output_budget_v':113e-6,'static_budget_diagnostic_pass':integral(1e9)<=113e-6,'sampled_noise_signoff':False,'gain_reference_source_sha256':old['candidate_sha256']}

def run(kind,gain,state,timeout):
    folder=HERE/'runs'/f'{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}_{kind}_g{gain}_{state}';folder.mkdir(parents=True)
    for name in SOURCES:(folder/name).write_bytes((HERE/name).read_bytes())
    (folder/'runner_snapshot.py').write_bytes(Path(__file__).read_bytes())
    if kind=='local':(folder/'injections.spice').write_text(instrument((HERE/'candidate_06.spice').read_text()))
    deck,cols={'local':local_deck,'noise':noise_deck,'pz':pz_deck}[kind](gain,state)
    (folder/'bench.spice').write_text(deck)
    if cols:save(folder/'columns.json',cols)
    result={'kind':kind,'gain':gain,'sampler_state':state,'corner':'tt','vdd_v':1.8,'temperature_c':27,'candidate_sha256':sha(HERE/'candidate_06.spice'),'complete_frontend_qualified':False,'formal_stability_gate_pass':False,'single_worker':True}
    save(folder/'config.json',result)
    env=dict(os.environ,SPICE_USERINIT_DIR='/foss/pdks/sky130A/libs.tech/ngspice',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    start=time.monotonic(); timed=False
    with (folder/'console.txt').open('w') as out:
        p=subprocess.Popen([NG,'-b','-o','simulator.log','bench.spice'],cwd=folder,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        try:p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed=True;os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
    log=(folder/'simulator.log').read_text(errors='replace') if (folder/'simulator.log').exists() else ''
    result.update(returncode=p.returncode,timed_out=timed,elapsed_s=time.monotonic()-start)
    (folder/'exit_code.txt').write_text(str(p.returncode)+'\n')
    errors=[x for x in log.splitlines() if re.search(r'error|timestep too small|singular matrix|iteration limit|overflow|nan|\binf\b',x,re.I)]
    result['simulator_diagnostics']=errors[:50]
    result['status']='TIMEOUT_INCOMPLETE' if timed else 'SIMULATOR_FAILURE' if p.returncode or errors or 'ngspice-47 done' not in log else 'COMPLETE'
    if result['status']=='COMPLETE':
        try:
            if kind=='local':result.update(analyze_local(folder,cols))
            elif kind=='noise':result.update(analyze_noise(folder,gain))
            else:
                num=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
                roots=[{'real_per_s':float(m[0]),'imag_per_s':float(m[1]) if m[1] else 0.} for m in re.findall(r'pole\(\d+\)\s*=\s*('+num+r')(?:\s*,\s*('+num+r'))?',log)]
                result.update(status='PZ_REQUIRES_RESIDUAL_AND_MODE_COMPLETENESS_AUDIT',reported_poles=roots,reported_rhp_count=sum(x['real_per_s']>0 for x in roots),eigenmode_completeness_verified=False)
        except Exception as e:result.update(status='ANALYSIS_FAILURE',analysis_error=str(e))
    save(folder/'summary.json',result)
    save(folder/'manifest.json',{'files':{p.name:{'sha256':sha(p),'size_bytes':p.stat().st_size} for p in sorted(folder.iterdir()) if p.is_file() and p.name!='manifest.json'}})
    print(json.dumps({'folder':str(folder),'status':result['status'],'elapsed_s':result['elapsed_s']}),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['local','noise','pz']);ap.add_argument('--gains',type=int,nargs='+',default=[1,4,16]);ap.add_argument('--states',nargs='+',choices=['acquire','hold'],default=['acquire','hold']);ap.add_argument('--timeout',type=float,default=120);a=ap.parse_args()
    for g in a.gains:
        for state in a.states:
            result=run(a.kind,g,state,a.timeout)
            if result['status'] in ('SIMULATOR_FAILURE','TIMEOUT_INCOMPLETE','ANALYSIS_FAILURE'):raise SystemExit(1)
