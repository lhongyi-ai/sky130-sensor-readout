#!/usr/bin/env python3
"""PREPARED_NOT_RUN. Explicit future Linux execution only, after native creation.

Uses the operator's already configured school environment. Runs serially, creates
one new result directory, never starts Virtuoso, never edits the PDK or cells.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,shutil,subprocess,sys,uuid

HERE=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--workdir',type=Path,required=True,help='Existing Cadence startup directory containing cds.lib')
    ap.add_argument('--pdk',type=Path,default=Path('/opt/cadence/CDK/sky130_release_0.0.3'))
    ap.add_argument('--out',type=Path,required=True,help='New result directory; existing paths are refused')
    a=ap.parse_args()
    pdk=a.pdk.resolve();wd=a.workdir.resolve();out=a.out.resolve()
    assert sys.platform.startswith('linux'),'This prepared runner is for the configured school Linux environment only'
    assert (wd/'cds.lib').is_file() and not out.exists()
    assert shutil.which('pvs') and shutil.which('strmout'),'Use existing configured Cadence environment'
    # This preparation intentionally has not qualified the Copper branch.
    assert not os.environ.get('Copper'),'Copper is set: review the flow branch before using 0.2um contacts'
    metadata=json.loads((HERE/'school_via_exclusion_resolved_metadata.json').read_text())
    for f in metadata['files']:
        q=pdk/'Sky130_DRC'/f['name']
        assert hashlib.sha256(q.read_bytes()).hexdigest()==f['sha256'],('School DRC input changed',str(q))
    out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env['PEGASUS_DRC']=str(pdk/'Sky130_DRC')
    summary={'status':'RUNNING','formal_ADC_PEX_allowed':False,'cases':{},'runtime_flow':{'Copper_environment_present':False,'Copper_command_definition':False,'areaid_mt_added':False},
             'scope':'Native stream-out; school ordinary DRC plus project MIM DRC and topology LVS. No PEX/simulation.'}
    def save():(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    def run(cmd,path,label):
        (path/(label+'.argv.json')).write_text(json.dumps(cmd,indent=2)+'\n')
        with (path/(label+'.console')).open('w') as f:
            return subprocess.run(cmd,cwd=path,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
    cases=json.loads((HERE/'control_geometry.json').read_text())['cases']
    save()
    for key,case in cases.items():
        dest=out/key;dest.mkdir();(dest/'cds.lib').symlink_to(wd/'cds.lib');top=case['cell']
        record={'cell':top,'expected_LVS':'MATCH' if key=='good' else 'MISMATCH','DRC_acceptance':'NOT_EVALUATED'};summary['cases'][key]=record;save()
        record['stream_exit']=run(['strmout','-library','project1','-topCell',top,'-view','layout','-strmFile',str(dest/'layout.gds'),'-layerMap',str(HERE/'access.map'),
            '-logFile',str(dest/'stream.log'),'-summaryFile',str(dest/'stream.sum'),'-convertPin','geometry'],dest,'stream')
        if record['stream_exit']!=0 or not (dest/'layout.gds').exists():save();raise RuntimeError('Stream failed '+key)
        record['gds_sha256']=hashlib.sha256((dest/'layout.gds').read_bytes()).hexdigest()
        for flavor in ['school_drc','mim_drc','lvs']:
            check=dest/flavor;check.mkdir()
            for f in (HERE/'rules').glob('*.pvl'):shutil.copyfile(f,check/f.name)
            if flavor=='lvs':
                shutil.copyfile(HERE/(key+'.cdl'),check/'source.cdl')
                (check/'control.pvl').write_text('results_db -erc "'+str(check/'erc.ascii')+'" -ascii\nreport_summary -erc "'+str(check/'erc.txt')+'" -replace\n')
                args=['pvs','-lvs','-license_timeout','30','-gds',str(dest/'layout.gds'),'-top_cell',top,'-source_cdl',str(check/'source.cdl'),'-source_top_cell',top,
                      '-layout_top_cell',top,'-spice',str(check/'extracted.spice'),'-control',str(check/'control.pvl'),'-log',str(check/'pvs.log'),'-disable_enc_parser_log',str(check/'mim_lvs.pvl')]
            else:
                deck=pdk/'Sky130_DRC/sky130_rev_0.0_1.0.drc.pvl' if flavor=='school_drc' else check/'mim_drc.pvl'
                args=['pvs','-drc','-license_timeout','30','-gds',str(dest/'layout.gds'),'-top_cell',top,'-ascrdb',str(check/'errors.ascii'),'-log',str(check/'pvs.log'),'-disable_enc_parser_log',str(deck)]
            record[flavor+'_exit']=run(args,check,'pvs');save()
            if flavor=='lvs':
                report=check/(top+'.lvsrpt.cls');txt=report.read_text(errors='replace') if report.exists() else ''
                m=re.search(r'Run Result\s*:\s*(\S+)',txt);record['actual_LVS']=m.group(1) if m else 'NOT_RUN'
                record['LVS_matches_expected']=record['actual_LVS']==record['expected_LVS']
            else:
                reports={str(f.relative_to(check)):f.read_text(errors='replace') for f in check.glob('*.sum')}
                record[flavor+'_summary_totals']={n:re.findall(r'(?m)^Total (?:Original Geometry|DRC RuleChecks|DRC Results)[^\n]*',t) for n,t in reports.items()}
                # Never treat exit zero as no violations; actual check coverage and counts require report review.
                record[flavor+'_acceptance']='REVIEW_REQUIRED'
            save()
    summary['status']='EXECUTED_REVIEW_REQUIRED';save();print(out)

if __name__=='__main__':main()
