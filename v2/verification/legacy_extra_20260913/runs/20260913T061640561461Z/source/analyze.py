"""Measurements from actual OCEAN CSV exports. Standard library only.

Simulation completion and performance qualification are intentionally separate.
Original ngspice results are frozen evidence, never fabricated Cadence results.
"""
import cmath
import csv
import json
import math
from pathlib import Path

def curve(out,name):
    with (out/(name+'.csv')).open() as f:
        rows=[(float(r['x']),complex(float(r['real']),float(r['imag']))) for r in csv.DictReader(f)]
    if not rows or any(not math.isfinite(z) for x,y in rows for z in [x,y.real,y.imag]): raise ValueError('Missing/nonfinite curve '+name)
    if any(b[0]<=a[0] for a,b in zip(rows,rows[1:])): raise ValueError('Non-increasing axis '+name)
    return rows

def ratio(a,b):
    if len(a)!=len(b) or any(x!=y for (x,_),(y,_) in zip(a,b)): raise ValueError('Mismatched axes')
    if any(abs(v)==0 for _,v in b): raise ValueError('Zero AC stimulus')
    return [(x,va/vb) for (x,va),(_,vb) in zip(a,b)]

def ac_metrics(rows):
    db=[20*math.log10(max(abs(y),1e-300)) for _,y in rows]
    phase=[]
    for _,y in rows:
        p=math.degrees(cmath.phase(y))
        if phase: p+=360*round((phase[-1]-p)/360)
        phase.append(p)
    crossings=[]
    for i in range(len(rows)-1):
        if (db[i]>=0>db[i+1]) or (db[i]<0<=db[i+1]):
            t=-db[i]/(db[i+1]-db[i])
            f=10**(math.log10(rows[i][0])+t*math.log10(rows[i+1][0]/rows[i][0]))
            crossings.append(dict(frequency_hz=f,direction='down' if db[i]>db[i+1] else 'up',phase_deg=phase[i]+t*(phase[i+1]-phase[i])))
    down=[x for x in crossings if x['direction']=='down']
    return dict(gain_dB=db[0],phase_low_deg=phase[0],crossings=crossings,
                ugb_MHz=down[0]['frequency_hz']/1e6 if down else None,
                pm_deg=180+down[0]['phase_deg'] if down else None)

def crossing(rows,level,start,end,up):
    for (t,a),(u,b) in zip(rows,rows[1:]):
        if t<start or u>end: continue
        a=a.real;b=b.real
        if (a<=level<b if up else a>=level>b): return t+(u-t)*(level-a)/(b-a)
    raise ValueError('Required step crossing not found')

def step_metrics(vin,vout):
    result={}
    for tag,up,start,end,target in [('rise',True,1e-6,3.02e-6,1.2),('fall',False,3.02e-6,5e-6,.8)]:
        t0=crossing(vin,1.0,start,1.02e-6 if up else 3.04e-6,up)
        # Match the original Day 4 20-80% sampled least-squares fit exactly.
        fitstart,fitstop=(1e-6,2.2e-6) if up else (3e-6,4.2e-6)
        low,high=(.88,1.12) if up else (1.12,.88)
        window=[(t,v.real) for t,v in vout if fitstart<=t<fitstop]
        first=next((i for i,(_,v) in enumerate(window) if (v>=low if up else v<=low)),None)
        if first is None: raise ValueError('Missing first slew threshold')
        last=next((i for i,(_,v) in enumerate(window) if i>=first and (v>=high if up else v<=high)),None)
        if last is None: raise ValueError('Missing second slew threshold')
        pts=window[first:last+1]
        if len(pts)<5: raise ValueError('Insufficient slew-fit samples')
        if any((b[1]-a[1])*(1 if up else -1)<-1e-6 for a,b in zip(pts,pts[1:])): raise ValueError('Nonmonotonic slew fit')
        tx=sum(x for x,y in pts)/len(pts);vy=sum(y for x,y in pts)/len(pts)
        slope=sum((x-tx)*(y-vy) for x,y in pts)/sum((x-tx)**2 for x,y in pts)
        result['sr_'+('pos' if up else 'neg')+'_V_per_us']=abs(slope)*1e-6
        tail=[(t,v.real) for t,v in vout if t0<=t<end]
        bad=[i for i,(t,v) in enumerate(tail) if abs(v-target)>.004]
        settled=None
        if tail and (not bad or bad[-1]<len(tail)-1):
            settled=((tail[bad[-1]+1][0] if bad else t0)-t0)*1e6
        result[tag+'_settling_us']=settled
        result[tag+'_overshoot_mV']=max(0,max((v-target)*(1 if up else -1) for _,v in tail))*1e3
    result['worst_settling_us']=max(result['rise_settling_us'],result['fall_settling_us']) if None not in [result['rise_settling_us'],result['fall_settling_us']] else None
    return result

def op(out,job):
    with (out/'op.csv').open() as f: values={r['name']:float(r['value']) for r in csv.DictReader(f)}
    if any(not math.isfinite(x) for x in values.values()): raise ValueError('Nonfinite scalar operating point')
    with (out/'op_devices.csv').open() as f: devices=[{k:(v if k=='device' else float(v)) for k,v in r.items()} for r in csv.DictReader(f)]
    expected={'M1','M2','M3A','M3B','M4A','M4B','M5','M6','M7A','M7B','M8','M9','M10'}
    if len(devices)!=13 or {d['device'] for d in devices}!=expected or any(not math.isfinite(v) for d in devices for k,v in d.items() if k!='device'): raise ValueError('Incomplete/nonfinite device OP')
    pmos={'M3A','M3B','M4A','M4B','M7A','M7B','M8','M9'}
    margins={d['device']:(-d['vds'] if d['device'] in pmos else d['vds'])-abs(d['vdsat']) for d in devices}
    groups={name:{key:sum(d[key] for d in devices if d['device'] in names) for key in ['ids','gm','gds']}
            for name,names in [('M3',['M3A','M3B']),('M4',['M4A','M4B']),('M7',['M7A','M7B'])]}
    return dict(power_uW=-(values['VDD']-values['VSS'])*values['ivdd']*1e6,
                parallel_group_operating_points=groups,
                dc_nodes=values,device_saturation_margin_V=margins,min_saturation_margin_V=min(margins.values()),
                all_devices_saturated=all(x>0 for x in margins.values()))

def analyze(out,job):
    out=Path(out);a=job['analysis'];cell=job['cell']
    m=dict(status='REVIEW_REQUIRED',criteria={},notes=[])
    if cell=='p1b_tb_res':
        v=curve(out,'TEST');i=curve(out,'VTEST_p')
        if len(v)!=101 or len(i)!=101: raise ValueError('Expected 101 resistor DC points')
        r=[z.real/(-j.real) for (x,z),(_,j) in zip(v,i) if x>=.01 and j.real!=0]
        if not r: raise ValueError('No nonzero resistor current')
        mean=sum(r)/len(r);variation=(max(r)-min(r))/abs(mean)
        m.update(resistance_ohm=mean,variation_fraction=variation,cdf_resistance_ohm=979.33)
        m['criteria']={'positive_resistance':mean>0,'linear_within_1pct':variation<=.01,'within_5pct_of_CDF':abs(mean/979.33-1)<=.05}
    elif cell=='p1b_tb_mim':
        adm=ratio([(x,-y) for x,y in curve(out,'VTEST_p')],curve(out,'TEST'))
        caps=[z.imag/(2*math.pi*f) for f,z in adm if 1e3<=f<=1e6]
        if not caps: raise ValueError('No MIM AC band')
        c=sum(caps)/len(caps)
        m.update(capacitance_F=c,cdf_capacitance_F=34.6223e-15)
        m['criteria']={'positive_capacitance':c>0,'within_5pct_of_CDF':abs(c/34.6223e-15-1)<=.05}
    elif cell=='p1b_tb_rc':
        y=curve(out,'VOUT');v=curve(out,'VIN')
        t0=crossing(v,.05,0,2e-9,True);t63=crossing(y,.1*(1-math.exp(-1)),t0,4e-9,True)
        m.update(tau_s=t63-t0,cdf_tau_s=979.33*34.6223e-15)
        m['criteria']={'tau_within_10pct_of_CDF':abs((t63-t0)/(979.33*34.6223e-15)-1)<=.1}
    else:
        m.update(op(out,job))
        m['criteria'].update(power_nonnegative=m['power_uW']>=0,power_le_600uW=m['power_uW']<=600,devices_saturated=m['all_devices_saturated'])
        if a=='ac':
            vo=curve(out,'VOUT');vp=curve(out,'VINP');vn=curve(out,'VINN')
            if cell=='p1b_tb_ac':
                diff=[(x,p-n) for (x,p),(_,n) in zip(vp,vn)]
                metrics=ac_metrics(ratio(vo,diff))
                m.update(gain_dB=metrics['gain_dB'],ac_unity_frequency_MHz=metrics['ugb_MHz'],ac_gain_crossings=metrics['crossings'])
                m['criteria']['gain_ge_50dB']=m['gain_dB']>=50
            elif cell=='p1b_tb_loop':
                m.update(ac_metrics(ratio([(x,-y) for x,y in vo],vn)))
                m['criteria'].update(single_downward_crossing=len(m['crossings'])==1 and m['crossings'][0]['direction']=='down',
                    correct_low_frequency_sign=abs(m['phase_low_deg'])<10,
                    pm_ge_55deg=m['pm_deg'] is not None and m['pm_deg']>=55,
                    ugb_ge_5MHz=m['ugb_MHz'] is not None and m['ugb_MHz']>=5)
                m['notes'].append('Legacy single-loop return ratio only; not a frontend multiloop stability certificate.')
            else:
                stimulus=vp if cell=='p1b_tb_cm' else curve(out,'VSS' if cell=='p1b_tb_psrrm' else 'VDD')
                response=ratio(vo,stimulus)
                at1k=min(response,key=lambda r:abs(math.log10(r[0]/1e3)))
                m['transfer_1k_dB']=20*math.log10(abs(at1k[1]));m['notes'].append('CMRR/PSRR requires differential gain at same frequency and operating point; transfer is not rejection.')
        elif a=='step':
            m.update(step_metrics(curve(out,'VINP'),curve(out,'VOUT')))
            m['criteria'].update(sr_pos_ge_2=m['sr_pos_V_per_us']>=2,sr_neg_ge_2=m['sr_neg_V_per_us']>=2,
                 settling_le_1p5us=m['worst_settling_us'] is not None and m['worst_settling_us']<=1.5)
        elif a=='noise':
            for signal in ['out','in']:
                rows=curve(out,signal);m[signal+'_noise_1k_exported']=min(rows,key=lambda r:abs(math.log10(r[0]/1e3)))[1].real
            m['notes'].append('Verify Spectre noise result units in ViVA; no ADC switched-noise qualification or numeric noise pass threshold.')
        elif a=='swing':
            rows=curve(out,'VOUT');m['output_min_V']=min(v.real for _,v in rows);m['output_max_V']=max(v.real for _,v in rows)
            m['notes'].append('Forward DC transfer only; headroom, saturation and hysteresis require review.')
    if m['criteria']: m['status']='PASS' if all(m['criteria'].values()) else 'FAIL'
    if a in ['noise','swing'] or cell in ['p1b_tb_cm','p1b_tb_psrrp','p1b_tb_psrrm']:
        if m['status']!='FAIL': m['status']='REVIEW_REQUIRED'
    m['notes'].append('Old OTA limits are Day 4 limits; they are not the newer frontend/ADC specification.')
    m['notes'].append('Cadence OTA uses explicit width mapping in size_mapping.json; original ngspice device sizes are preserved separately and are not identical.')
    # Compare only named same-condition historical metrics. Preserve historical failures verbatim.
    ref=Path(__file__).parent/'reference/pvt_summary.csv'
    if job['id'].startswith('P'):
        with ref.open() as f: old=next((r for r in csv.DictReader(f) if r['point_id']==job['point']),None)
        if old:
            m['historical_pass_fail']=old['pass_fail'];m['comparison']={}
            keys={'op':['power_uW'],'ac':['gain_dB','power_uW'],'loop':['ugb_MHz','pm_deg','power_uW'],
                  'step':['sr_pos_V_per_us','sr_neg_V_per_us','worst_settling_us']}[job['id'].split('_',1)[1]]
            for key in keys:
                if key in m and m[key] is not None:
                    oldvalue=float(old[key]) if old[key] else None
                    m['comparison'][key]=dict(cadence=m[key],ngspice=oldvalue,difference=m[key]-oldvalue if oldvalue is not None else None)
    return m
