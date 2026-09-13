#!/usr/bin/env python3
"""Four-plane coupled hybrid matrix, with no assumption of a stable reference.

Ports: differential input, common input, stage-1 CM, output CM. Every original
controlled source and reverse parasitic remains. The calculated return difference
is a port-reduced diagnostic, not a complete state-space stability certificate.
"""
import numpy as np
import run_qualification as q


def expressions(p,mode):
    o=p+'.xota'
    if mode=='dm':return f'(v({p}.i_sumpos)-v({p}.i_sumneg))',f'(-i(v.{p}.vtestp)+i(v.{p}.vtestn))/2'
    if mode=='input_cm':return f'(v({p}.i_sumpos)+v({p}.i_sumneg))/2',f'(-i(v.{p}.vtestp)-i(v.{p}.vtestn))'
    gate,dev=('ncm_gate','vtestncm') if mode=='stage1_cm' else ('cms_error','vtestocm')
    return f'v({o}.{gate})',f'-i(v.{o}.{dev})'


def deck(gain,state):
    lines=[x.replace(' ac .5',' ac 0').replace(' ac -.5',' ac 0') for x in q.base(gain,state,'injections.spice')]
    defs=[];vec=[]
    for j,mode in enumerate(q.MODES):
        for inj in ('v','i'):
            tag=f'_{mode}_{inj}';p='xpga'+tag
            key={'dm':'D','input_cm':'C','stage1_cm':'N','output_cm':'O'}[mode]+inj.upper()
            lines+=q.dut(tag,f'{key}=1')
            for i,observe in enumerate(q.MODES):
                ve,ret=expressions(p,observe)
                for n,expr in [('ve',ve),('if',ret)]:
                    k=f'r{i}c{j}_{inj}_{n}'
                    defs +=[f'let {k}={expr}',f'let {k}_r=real({k})',f'let {k}_i=imag({k})']
                    vec +=[k+'_r',k+'_i']
    lines+=q.control()+['op','ac dec 120 1 1g']+defs+[f'wrdata response.dat {" ".join(vec)}']+q.end()
    return '\n'.join(lines)+'\n',['frequency']+vec


def reconstruct(A,B,C,D):
    K=np.linalg.inv(C)
    Yff=B-A@K@D;Yfe=-A@K-Yff;Yef=K@D-Yff;Yee=K-Yff-Yfe-Yef
    base=Yee+Yff;cross=Yef+Yfe
    F=np.linalg.det(K)/np.linalg.det(base)
    return K,base,cross,F


def analyze(folder,cols):
    d=np.loadtxt(folder/'response.dat',skiprows=1,ndmin=2); idx={x:i for i,x in enumerate(cols)}
    if d.shape[1]!=len(cols) or not np.isfinite(d).all():raise ValueError('Bad matrix data')
    def vec(k):return d[:,idx[k+'_r']]+1j*d[:,idx[k+'_i']]
    n=len(d); A=np.empty((n,4,4),complex);B=A.copy();C=A.copy();D=A.copy()
    for i in range(4):
        for j in range(4):
            k=f'r{i}c{j}'
            A[:,i,j]=vec(k+'_i_if');B[:,i,j]=vec(k+'_v_if');C[:,i,j]=vec(k+'_i_ve');D[:,i,j]=vec(k+'_v_ve')
    K,baseline,cross,F=reconstruct(A,B,C,D)
    normalized=np.linalg.solve(baseline,K)
    sv=np.linalg.svd(normalized,compute_uv=False)
    residual=np.linalg.norm(K-baseline-cross,axis=(1,2))/np.maximum(np.linalg.norm(K,axis=(1,2)),1e-30)
    np.savez_compressed(folder/'coupled_hybrid_matrices.npz',frequency_hz=d[:,0],A=A,B=B,C=C,D=D,closed_admittance=K,reference_admittance=baseline,cross_admittance=cross,return_difference=F)
    np.savetxt(folder/'coupled_return_difference.csv',np.column_stack([d[:,0],F.real,F.imag,abs(F),np.unwrap(np.angle(F))*180/np.pi,sv[:,-1]]),delimiter=',',header='frequency_hz,real,imag,abs,unwrapped_phase_deg,min_singular_value',comments='')
    return {'status':'COUPLED_PORT_RETURN_DIFFERENCE_COMPUTED__BASELINE_POLE_COUNT_UNVERIFIED','formal_stability_gate_pass':False,'port_count':4,'port_order':list(q.MODES),'scope':'Finite-axis Schur port model. det(K)/det(Yee+Yff). Reference can be active; no zero-RHP-pole assumption. Hidden modes and contour closure not certified.','max_reconstruction_relative_residual':float(max(residual)),'max_C_condition_number':float(max(np.linalg.cond(C))),'return_difference_low':{'real':float(F[0].real),'imag':float(F[0].imag)},'return_difference_high':{'real':float(F[-1].real),'imag':float(F[-1].imag)},'min_abs_return_difference':float(min(abs(F))),'minimum_singular_value_of_normalized_return_difference':float(sv[:,-1].min()),'finite_positive_axis_phase_change_deg':float((np.unwrap(np.angle(F))[-1]-np.unwrap(np.angle(F))[0])*180/np.pi),'reference_RHP_pole_count':None,'winding_number_qualified':False,'unobserved_internal_modes_excluded':False}

if __name__=='__main__':
    # Reuse immutable run packaging, replacing only the diagnostic generator.
    q.local_deck=deck;q.analyze_local=analyze
    for g in (1,4,16):
        for state in ('acquire','hold'):
            r=q.run('local',g,state,100)
            if r['status'] in ('SIMULATOR_FAILURE','ANALYSIS_FAILURE','TIMEOUT_INCOMPLETE'):raise SystemExit(1)
