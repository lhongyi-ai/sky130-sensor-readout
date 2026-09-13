"""Fail-closed audit of the native Spectre netlist. No substitute DUT netlists."""
import ast
import math
import re

SCALE = {'t':1e12,'g':1e9,'meg':1e6,'k':1e3,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15,'a':1e-18}
def numeric(s, variables=None):
    variables = variables or {}
    s = re.sub(r'(?i)(\d+(?:\.\d*)?|\.\d+)(meg|[tgkmunpfa])\b', lambda m: '('+m[1]+'*'+str(SCALE[m[2].lower()])+')',s)
    def calc(n):
        if isinstance(n,ast.Expression): return calc(n.body)
        if isinstance(n,ast.Num) and type(n.n) in (int,float): return n.n
        if isinstance(n,ast.Constant) and type(n.value) in (int,float): return n.value
        if isinstance(n,ast.Name) and n.id in variables: return variables[n.id]
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return (-1 if isinstance(n.op,ast.USub) else 1)*calc(n.operand)
        if isinstance(n,ast.BinOp):
            x,y=calc(n.left),calc(n.right)
            if isinstance(n.op,ast.Add): return x+y
            if isinstance(n.op,ast.Sub): return x-y
            if isinstance(n.op,ast.Mult): return x*y
            if isinstance(n.op,ast.Div): return x/y
        raise ValueError('Unsupported netlist expression: '+s)
    value=calc(ast.parse(s,mode='eval'))
    if not math.isfinite(value): raise ValueError('Nonfinite netlist value')
    return value

def parse(text):
    scopes={'TOP':{}}
    ports={}
    scope='TOP'
    for line in text.replace('\\\n',' ').splitlines():
        line=line.split('//')[0].strip()
        if not line: continue
        m=re.match(r'subckt\s+(\S+)\s*(.*)',line,re.I)
        if m:
            scope=m[1]; scopes[scope]={};ports[scope]=m[2].replace('(','').replace(')','').split();continue
        if re.match(r'ends\b',line,re.I): scope='TOP';continue
        m=re.match(r'(\S+)\s+\(([^)]*)\)\s+(\S+)\s*(.*)',line)
        if m:
            name,nets,model,props=m.groups()
            if name in scopes[scope]: raise ValueError('Duplicate instance '+name)
            kv=dict(re.findall(r'(\w+)\s*=\s*(.*?)(?=\s+\w+\s*=|$)',props))
            scopes[scope][name]=dict(nets=nets.split(),model=model,props=kv)
    return scopes,ports

MAP={'vdc':('vsource',{'vdc':'dc','acm':'mag','acp':'phase'}),
     'vpulse':('vsource',{'val0':'val0','val1':'val1','delay':'delay','rise':'rise','fall':'fall','width':'width','period':'period'}),
     'idc':('isource',{'idc':'dc'}),'res':('resistor',{'r':'r'}),
     'cap':('capacitor',{'c':'c'}),'ind':('inductor',{'l':'l'})}

def check(text, design, cell, variables):
    scopes,ports=parse(text)
    notes=[]
    def scope_check(actual,expected,netmap=None):
        netmap=dict(netmap or {})
        if set(actual)!=set(x['name'] for x in expected):
            raise ValueError('Instance set differs: '+str(sorted(actual)))
        for want in expected:
            got=actual[want['name']]
            model=want['cell']
            if want['lib']=='project1':
                if got['model'] not in scopes: raise ValueError('DUT subcircuit not exported')
                c=design['cells'][model]
                p=ports[got['model']]
                if set(p)!=set(c['ports']): raise ValueError('DUT symbol ports differ')
                wanted_nets=[want['terminals'][x] for x in p]
                scope_check(scopes[got['model']],c['instances'],{x:x for x in p})
            else:
                wanted_nets=list(want['terminals'].values())
                expected_model=MAP.get(model,(model,{}))[0]
                if model=='cap_mim_m3__base': expected_model='cap_mim_m3_1'
                if got['model']!=expected_model: raise ValueError('Model mismatch '+want['name']+': '+got['model'])
            if len(wanted_nets)!=len(got['nets']): raise ValueError('Terminal count differs')
            for wn,gn in zip(wanted_nets,got['nets']):
                if wn=='0' and gn!='0': raise ValueError('Ground not connected')
                if wn in netmap and netmap[wn]!=gn: raise ValueError('Open/reordered terminal on '+want['name']+' '+wn)
                if gn in netmap.values() and netmap.get(wn)!=gn: raise ValueError('Short between nets on '+want['name'])
                netmap[wn]=gn
            gp=got['props']
            for key,val in want['props'].items():
                if key in ('fw','fingers'): continue
                mapped=MAP.get(model,('',{}))[1].get(key,key)
                default={'phase':'0','mag':'0'}.get(mapped)
                observed=gp.get(mapped,default)
                if observed is None or not math.isclose(numeric(observed,variables),numeric(val,variables),rel_tol=1e-8,abs_tol=1e-24):
                    raise ValueError('Parameter mismatch '+want['name']+'.'+mapped+': '+str(observed)+' expected '+val)
            if model in ['nfet_01v8','pfet_01v8']:
                for key in ['as','ad','ps','pd']:
                    if key not in gp or numeric(gp[key],variables)<=0: raise ValueError('Missing geometry '+want['name']+'.'+key)
                # Single finger, school default diffusion extension 0.265 um, verified by the 5 um NMOS/PMOS exports.
                w=numeric(want['props']['w'])
                for key,expected in [('as',w*.265e-6),('ad',w*.265e-6),('ps',2*w+.53e-6),('pd',2*w+.53e-6)]:
                    if not math.isclose(numeric(gp[key]),expected,rel_tol=2e-4,abs_tol=1e-22):
                        raise ValueError('CDF geometry differs from qualified one-finger mapping '+want['name']+'.'+key)
            if model=='res_high_po_0p35':
                for key in ['w','l']:
                    if key not in gp or not math.isclose(numeric(gp[key]),350e-9,rel_tol=1e-5): raise ValueError('R default geometry mismatch')
                if 'r' not in gp or not math.isclose(numeric(gp['r']),979.33,rel_tol=1e-4): raise ValueError('R nominal CDF value differs')
                notes.append('R default 350nm x 350nm; model I/V must still be measured')
            if model=='cap_mim_m3__base':
                for key in ['w','l']:
                    if key not in gp or not math.isclose(numeric(gp[key]),4e-6,rel_tol=1e-6): raise ValueError('MIM default geometry mismatch')
                if numeric(gp.get('m','1'))!=1: raise ValueError('MIM multiplier differs')
                notes.append('MIM default 4um x 4um; measured capacitance must be compared with CDF 34.6223f')
        return netmap
    mapping=scope_check(scopes['TOP'],design['cells'][cell]['instances'])
    return dict(status='PASS',top_net_map=mapping,notes=notes,
                limitation='Checks source topology and qualified mapping; does not certify model accuracy or simulation.')
