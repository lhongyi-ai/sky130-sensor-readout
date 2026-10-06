"""Prepare immutable noise-control inputs. This module never launches a simulator."""
from pathlib import Path
import argparse, hashlib, json, math, re
ROOT=Path(__file__).resolve().parent
K_B=1.380649e-23

def sha(data):return hashlib.sha256(data if isinstance(data,bytes) else data.encode()).hexdigest()
def read_config():return json.loads((ROOT/'config.json').read_text())
def theory(c):
    t=c['temperature_c']+273.15;r=c['ideal_rc_resistance_ohm'];cap=c['nominal_capacitance_f'];tau=r*cap
    return dict(temperature_k=t,k_b_j_per_k=K_B,R_ohm=r,C_f=cap,tau_s=tau,fc_hz=1/(2*math.pi*tau),
      one_sided_white_psd_v2_per_hz=4*K_B*t*r,white_asd_v_per_sqrt_hz=math.sqrt(4*K_B*t*r),
      single_ended_variance_v2=K_B*t/cap,single_ended_rms_v=math.sqrt(K_B*t/cap),
      differential_independent_variance_v2=2*K_B*t/cap,differential_independent_rms_v=math.sqrt(2*K_B*t/cap),
      ideal_hard_cutoff_variance_fraction={str(int(f)):2/math.pi*math.atan(2*math.pi*f*tau) for f in c['noise_bandwidths_hz']})
def timing(c,n,warm):
    period=1/c['sample_rate_hz'];tr=c['clock_rise_s'];tf=c['clock_fall_s'];delay=c['clock_delay_s']
    width=c['acquisition_midpoint_duration_s']-(tr+tf)/2
    assert width>0
    phases={'pre_open':delay+tr+width-c['preswitch_guard_s'],
      'post_open':delay+tr+width+tf+c['postfall_guard_s'],
      'late_hold':delay+period-c['latehold_before_next_rise_s']}
    rows=[dict(cycle=j,phase=phase,time_s=j*period+offset) for j in range(warm,warm+n) for phase,offset in phases.items()]
    rows.sort(key=lambda x:x['time_s'])
    assert all(rows[i]['time_s']<rows[i+1]['time_s'] for i in range(len(rows)-1))
    return dict(period_s=period,pulse_width_s=width,phase_offsets_s=phases,samples=rows,stop_s=(warm+n+1)*period)
def options(c,tight=False):
    return f"simOptions options temp={c['temperature_c']:g} tnom=27 reltol={c['reltol']/(2 if tight else 1):g} vabstol={c['vabstol_v']/(2 if tight else 1):g} iabstol={c['iabstol_a']/(2 if tight else 1):g}\nsaveOptions options save=selected\n"
def clocks(c):
    tm=timing(c,1,0);d=c['clock_delay_s'];tr=c['clock_rise_s'];tf=c['clock_fall_s'];v=c['vdd_v']
    return (f"VACQ (ACQ 0) vsource type=pulse val0=0 val1={v:g} delay={d:g} rise={tr:g} fall={tf:g} width={tm['pulse_width_s']:g} period={tm['period_s']:g}\n"
      f"VACQB (ACQB 0) vsource type=pulse val0={v:g} val1=0 delay={d:g} rise={tr:g} fall={tf:g} width={tm['pulse_width_s']:g} period={tm['period_s']:g}\n")
def circuit(c,kind,model):
    h='simulator lang=spectre\nglobal 0\n'
    if kind.startswith('tg') or kind=='mim_ac':h+=f'include "{model}" section={c["model_section"]}\n'
    h+=f'VCM (VCM 0) vsource dc={c["vcm_v"]:g}\nVDD_SRC (VDD 0) vsource dc={c["vdd_v"]:g}\n'
    if kind=='mim_ac':
      return h+'VCAP (CM 0) vsource dc=0 mag=1\nXCM (CM 0) cap_mim_m3_1 l=4u w=4u m=4096\n'
    h+=clocks(c)
    for side in ('P','N'):
      node='H'+side
      if kind=='rc':h+=f'R{side} (VCM {node}) resistor r={c["ideal_rc_resistance_ohm"]:g}\nC{side} ({node} 0) capacitor c={c["nominal_capacitance_f"]:g}\n'
      else:
        # Model aliases and junction geometry below come from a school-native netlist;
        # their source hash is frozen separately. Four MOS include the existing proxy's dummy devices.
        h+=f'RS{side} (VCM F{side}) resistor r={c["source_resistance_ohm"]:g}\n'
        h+=f'X{side}N ({node} ACQ F{side} 0) nfet_01v8_lvt w=4u l=150n as=1.06p ad=1.06p ps=8.53u pd=8.53u m=1\n'
        h+=f'X{side}P ({node} ACQB F{side} VDD) pfet_01v8_lvt w=8u l=350n as=2.12p ad=2.12p ps=16.53u pd=16.53u m=1\n'
        h+=f'X{side}ND ({node} ACQB {node} 0) nfet_01v8_lvt w=2u l=150n as=530f ad=530f ps=4.53u pd=4.53u m=1\n'
        h+=f'X{side}PD ({node} ACQ {node} VDD) pfet_01v8_lvt w=4u l=350n as=1.06p ad=1.06p ps=8.53u pd=8.53u m=1\n'
        h+=f'XC{side} ({node} VCM) cap_mim_m3_1 l=4u w=4u m=4096\n'
    return h+'ic HP=0.9 HN=0.9\n'
def build(out,model,profile):
    assert not out.exists(), 'Refuse to overwrite prepared inputs'
    assert not any(x in model for x in ('"','\n','\r')), 'Unsafe model path'
    c=read_config();out.mkdir(parents=True);jobs=[]
    def add(j,body):
      d=out/j['id'];d.mkdir();(d/'input.scs').write_text(body)
      j.update(status='NOT_RUN',qualification='NOT_EVALUATED',input_sha256=sha(body),input_file=j['id']+'/input.scs')
      jobs.append(j)
    # .noise is used ONLY to validate an LTI resistor's units and analytical PSD.
    body=circuit(c,'rc',model)+options(c)+'save HP HN\nrc_single (HP 0) noise start=1 stop=100G dec=40\nrc_diff (HP HN) noise start=1 stop=100G dec=40\n'
    add(dict(id='rc_analytic_noise',kind='rc_noise',analysis='noise'),body)
    body=circuit(c,'mim_ac',model)+options(c)+'save CM VCAP:p\nmim_ac ac start=1k stop=100M dec=20\n'
    add(dict(id='mim_capacitance_ac',kind='mim_ac',analysis='ac'),body)
    n=c['pilot_samples'] if profile=='pilot' else c['production_samples'];warm=c['pilot_warmup_cycles'] if profile=='pilot' else c['production_warmup_cycles']
    configs=[(60e6,False,False)] if profile=='pilot' else [(f,False,False) for f in c['noise_bandwidths_hz']]+[(60e6,True,False),(60e6,False,True)]
    seeds=c['seeds'][:1] if profile=='pilot' else c['seeds'];tm=timing(c,n,warm)
    for kind in ('rc','tg'):
      for f,tight,colored in configs:
        if kind=='rc' and colored:continue
        base=f'{kind}_f{int(f/1e6)}_'+('tight' if tight else 'base')+('_colored' if colored else '_white')
        common=circuit(c,kind,model)+options(c,tight)+'save HP HN ACQ ACQB\n'
        maxstep=c['tight_maxstep_s'] if tight else c['base_maxstep_s']
        # Explicit computed strobes: no interpolation of an off/on edge into held samples.
        st=' '.join(f'{r["time_s"]:.12g}' for r in tm['samples'])
        common_tran=f'tran tran stop={tm["stop_s"]:.12g} maxstep={maxstep:g} errpreset=conservative compression=no strobeoutput=strobeonly strobetimes=[{st}]'
        twin=base+'_off'
        for seed in [None]+seeds:
          tag='off' if seed is None else 's'+str(seed);ident=base+'_'+tag
          noise=' noisefmax=0' if seed is None else f' noisefmax={f:g} noisefmin={(c["colored_companion_fmin_hz"] if colored else f):g} noisescale=1 noiseseed={seed}'
          j=dict(id=ident,kind=kind,analysis='tran',noise_enabled=seed is not None,noise_mode='colored' if colored else 'white_control',noisefmax_hz=f if seed else 0,bandwidth_family_hz=f,noisefmin_hz=c['colored_companion_fmin_hz'] if colored else f,seed=seed,maxstep_s=maxstep,tight=tight,twin_job=twin,common_input_sha256=sha(common+common_tran),n_samples=n,warmup_cycles=warm,timing=tm,profile=profile)
          add(j,common+common_tran+noise+'\n')
    manifest=dict(version=c['version'],status='NOT_RUN',simulation_launched=False,scope=c['scope'],profile=profile,config_sha256=sha((ROOT/'config.json').read_bytes()),generator_sha256=sha(Path(__file__).read_bytes()),model_path=model,model_section=c['model_section'],theory=theory(c),jobs=jobs)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--model',required=True);p.add_argument('--profile',choices=['pilot','production'],default='pilot');a=p.parse_args()
    m=build(a.output.resolve(),a.model,a.profile);print(json.dumps(dict(prepared_jobs=len(m['jobs']),status='NOT_RUN',output=str(a.output))))
