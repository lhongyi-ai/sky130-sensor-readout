import copy
import csv
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from audit import check,numeric,MAP
from analyze import ac_metrics,step_metrics,op
from run import deck,log_audit,netlist_body,DEFAULT

class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design=json.loads((ROOT/'design.json').read_text())
        cls.jobs=json.loads((ROOT/'jobs.json').read_text())

    def test_expression_safety(self):
        self.assertAlmostEqual(numeric('(1)*(1)'),1)
        self.assertAlmostEqual(numeric('1.8-VSG',dict(VSG=.3)),1.5)
        self.assertAlmostEqual(numeric('500n'),.5e-6)
        for expr in ['__import__("os").system("true")','1/0','MISSING','1e999']:
            with self.assertRaises(Exception): numeric(expr)

    def resistor_fixture(self):
        return 'R0 (TEST VSS VSS) res_high_po_0p35 r=979.33 w=350n l=350n\nVTEST (TEST VSS) vsource dc=VTEST mag=1\nVSSSUP (VSS 0) vsource dc=0\n'

    def test_pass_and_short_and_body_fault(self):
        original=self.resistor_fixture()
        self.assertEqual(check(original,self.design,'p1b_tb_res',{'VTEST':0})['status'],'PASS')
        for bad in [original.replace('TEST VSS VSS','TEST VSS TEST'),original.replace('VSS 0','TEST 0'),original.replace('350n','350u'),original+'R2 (TEST VSS) resistor r=1k\n']:
            with self.assertRaises(ValueError): check(bad,self.design,'p1b_tb_res',{'VTEST':0})

    def test_immutable_reference_sizes(self):
        ota={x['name']:x for x in self.design['cells']['p1b_ota_legacy_r4']['instances']}
        self.assertEqual(len(ota),15)
        self.assertEqual(ota['M3A']['props']['w'],'25u')
        self.assertEqual(ota['M3B']['terminals'],ota['M3A']['terminals'])
        self.assertEqual(ota['M4B']['terminals'],ota['M4A']['terminals'])
        self.assertEqual(ota['M1']['terminals']['G'],'VINN')
        self.assertEqual(ota['M2']['terminals']['G'],'VINP')
        self.assertEqual(ota['RZ1']['props']['r'],'2k')
        self.assertEqual(ota['CC1']['props']['c'],'3p')

    def test_13_pvt_conditions(self):
        formal=[j for j in self.jobs if j['id'].startswith('P')]
        self.assertEqual(len(formal),52)
        self.assertEqual(len({j['point'] for j in formal}),13)
        self.assertEqual(len({j['id'] for j in self.jobs}),len(self.jobs))
        for j in formal:
            self.assertEqual(j['params']['VCM'],.9)
            self.assertEqual(j['params']['CL'],5e-12)
        self.assertEqual(next(j for j in formal if j['id']=='P13_op')['params']['VDD'],1.98)

    def test_repair_preserves_interrupted_ota_namespace(self):
        self.assertNotIn('p1b_ota_legacy',self.design['cells'])
        self.assertNotIn('p1b_ota_legacy_r1',self.design['cells'])
        self.assertNotIn('p1b_ota_legacy_r2',self.design['cells'])
        self.assertNotIn('p1b_ota_legacy_r3',self.design['cells'])
        self.assertIn('p1b_ota_legacy_r4',self.design['cells'])
        for cell in self.design['cells'].values():
            for obj in cell['instances']:
                if obj['lib']=='project1': self.assertEqual(obj['cell'],'p1b_ota_legacy_r4')

    def test_numeric_predicate_regression_and_early_runtime_check(self):
        text=(ROOT/'create.il').read_text()
        self.assertNotIn('flonump(',text)
        self.assertNotIn('fixp(',text)
        creation=text.split('procedure(p1bCreateAll()',1)[1]
        self.assertLess(creation.index('p1bTypeSelfCheck()'),creation.index('p1bSymbol('))

    def test_explicit_size_mapping_preserves_source_and_strict_audit(self):
        source=(ROOT/'reference/ota_subckt.spice').read_text()
        self.assertIn('W=7.22005',source)
        mapping=json.loads((ROOT/'size_mapping.json').read_text())['devices']
        self.assertEqual(len(mapping),12)
        self.assertTrue(all(abs(x['relative_change'])<.0005 for x in mapping))
        self.assertEqual(next(x for x in mapping if x['device']=='M8')['cadence_w_um'],'7.22')
        fixture=self.fixture_ota();job=next(j for j in self.jobs if j['id']=='P01_ac')
        with self.assertRaises(ValueError):
            check(fixture.replace('w=7.22u','w=7.22005u',1),self.design,job['cell'],job['params'])

    def test_m7_split_preserves_total_width_and_connections(self):
        ota={x['name']:x for x in self.design['cells']['p1b_ota_legacy_r4']['instances']}
        self.assertNotIn('M7',ota)
        for name in ['M7A','M7B']:
            self.assertEqual(ota[name]['terminals'],dict(D='VOUT',G='VBP',S='VDD',B='VDD'))
            self.assertEqual(ota[name]['props'],dict(w='36.1u',fw='36.1u',l='0.8u',fingers='1',m='1'))
        self.assertAlmostEqual(sum(numeric(ota[n]['props']['w']) for n in ['M7A','M7B']),72.2e-6)
        self.assertTrue(all(numeric(x['props']['fw'])<=50e-6 for x in ota.values() if x['cell'] in ['pfet_01v8','nfet_01v8']))
        job=next(j for j in self.jobs if j['id']=='P01_ac')
        fixture=self.fixture_ota()
        missing='\n'.join(line for line in fixture.splitlines() if not line.startswith('M7B '))
        with self.assertRaises(ValueError): check(missing,self.design,job['cell'],job['params'])

    def test_parallel_op_sum_and_missing_device_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/'op.csv').write_text('name,value\nVDD,1.8\nVSS,0\nivdd,-0.00015\n')
            rows=[]
            for obj in self.design['cells']['p1b_ota_legacy_r4']['instances']:
                if obj['cell'] not in ['pfet_01v8','nfet_01v8']: continue
                sign=-1 if obj['cell']=='pfet_01v8' else 1
                rows.append(obj['name']+','+str(sign*10e-6)+',0.001,0.00001,'+str(sign*.9)+','+str(sign*.2))
            header='device,ids,gm,gds,vds,vdsat\n'
            (folder/'op_devices.csv').write_text(header+'\n'.join(rows)+'\n')
            result=op(folder,{})
            self.assertAlmostEqual(result['parallel_group_operating_points']['M7']['ids'],-20e-6)
            self.assertAlmostEqual(result['parallel_group_operating_points']['M7']['gm'],.002)
            self.assertTrue(result['all_devices_saturated'])
            (folder/'op_devices.csv').write_text(header+'\n'.join(r for r in rows if not r.startswith('M7B,'))+'\n')
            with self.assertRaises(ValueError): op(folder,{})

    def test_netlist_preservation(self):
        raw='simulator lang=spectre\nglobal 0\n'+self.resistor_fixture()
        body=netlist_body(raw)
        self.assertEqual(body,self.resistor_fixture())
        with self.assertRaises(ValueError): netlist_body(raw+'include "unknown.scs"\n')
        for j in self.jobs:
            s=deck(j,body,DEFAULT)
            self.assertIn('section='+j['corner'],s)
            self.assertIn('temp='+str(j['temp']),s)
            self.assertIn(body,s)

    def test_log_does_not_pass_missing_or_failed_runs(self):
        good='Spectre completes with 0 errors, 1 warning, and 4 notices.'
        self.assertEqual(log_audit(good,0)['status'],'PASS')
        for text,code in [('',0),(good,1),('Spectre completes with 1 errors',0)]:
            self.assertEqual(log_audit(text,code)['status'],'FAIL')

    def test_all_crossings_retained(self):
        r=ac_metrics([(1,10+0j),(10,.1+0j),(100,10+0j),(1000,.1+0j)])
        self.assertEqual([x['direction'] for x in r['crossings']],['down','up','down'])
        self.assertIsNone(ac_metrics([(1,10+0j),(10,2+0j)])['pm_deg'])

    def test_step_missing_transition_rejected(self):
        with self.assertRaises(ValueError): step_metrics([(0,.8+0j),(5e-6,.8+0j)],[(0,.8+0j),(5e-6,.8+0j)])

    def test_synthetic_single_pole_measurement(self):
        rows=[(10**(i/100),1000/(1+1j*10**(i/100)/1e4)) for i in range(1001)]
        m=ac_metrics(rows)
        self.assertAlmostEqual(m['gain_dB'],60,places=5)
        self.assertAlmostEqual(m['ugb_MHz'],10,places=3)
        self.assertTrue(89<m['pm_deg']<91)

    def test_frozen_real_ngspice_measurement_regression(self):
        # Historical waveform replay validates measurement code only, never Cadence qualification.
        with (ROOT/'reference/pvt_summary.csv').open() as f: refs=list(csv.DictReader(f))
        for ref in refs:
            rows=[]
            for line in (ROOT/'reference/pvt_raw'/(ref['point_id']+'_transient.tsv')).read_text().splitlines():
                toks=line.split()
                try: rows.append(tuple(float(x) for x in toks[:3]))
                except ValueError: pass
            m=step_metrics([(t,complex(i)) for t,i,o in rows],[(t,complex(o)) for t,i,o in rows])
            for key in ['sr_pos_V_per_us','sr_neg_V_per_us','worst_settling_us']:
                if ref[key]=='': self.assertIsNone(m[key],ref['point_id']+key)
                else: self.assertAlmostEqual(m[key],float(ref[key]),places=6,msg=ref['point_id']+key)

    def test_frozen_real_loop_regression(self):
        with (ROOT/'reference/pvt_summary.csv').open() as f: refs=list(csv.DictReader(f))
        for ref in refs:
            rows=[]
            for line in (ROOT/'reference/pvt_raw'/(ref['point_id']+'_loop.tsv')).read_text().splitlines():
                toks=line.split()
                try: rows.append((float(toks[0]),complex(float(toks[1]),float(toks[2]))))
                except ValueError: pass
            m=ac_metrics(rows)
            for key in ['ugb_MHz','pm_deg']:
                self.assertAlmostEqual(m[key],float(ref[key]),places=6,msg=ref['point_id']+key)

    def fixture_ota(self):
        def render(obj):
            model,mp=MAP.get(obj['cell'],(obj['cell'],{}))
            props={mp.get(k,k):v for k,v in obj['props'].items() if k not in ['fw','fingers']}
            if obj['cell'] in ['nfet_01v8','pfet_01v8']:
                w=numeric(obj['props']['w'])
                props.update(dict(as_=str(w*.265e-6),ad=str(w*.265e-6),ps=str(2*w+.53e-6),pd=str(2*w+.53e-6)))
                props['as']=props.pop('as_')
            return obj['name']+' ('+' '.join(obj['terminals'].values())+') '+model+' '+' '.join(k+'='+v for k,v in props.items())+'\n'
        c=self.design['cells']['p1b_ota_legacy_r4']
        return 'subckt p1b_ota_legacy_r4 '+' '.join(c['ports'])+'\n'+''.join(render(x) for x in c['instances'])+'ends p1b_ota_legacy_r4\n'+''.join(render(x) for x in self.design['cells']['p1b_tb_ac']['instances'])

    def test_ota_native_audit_fault_injection(self):
        fixture=self.fixture_ota();job=next(j for j in self.jobs if j['id']=='P01_ac')
        self.assertEqual(check(fixture,self.design,job['cell'],job['params'])['status'],'PASS')
        for bad in [fixture.replace('w=25u','w=50u',1),fixture.replace('m=1','m=(1)*(2)',1),
                    fixture.replace('NMIR VINN TAIL VSS','NMIR VINP TAIL VSS',1),
                    fixture.replace('c=3p','c=3u'),fixture.replace('VBP VBP VDD VDD','VBP VBP VDD VSS',1),
                    fixture.replace('M3B (','M3C (',1)]:
            with self.assertRaises(ValueError): check(bad,self.design,job['cell'],job['params'])

if __name__=='__main__': unittest.main()
