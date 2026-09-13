"""Re-evaluate retained evidence; never rewrite source attempts or old FAILs."""
import hashlib
import json
from pathlib import Path

from audit import check
from passive_models import analyze_passive

PREVIOUS_MANIFEST = 'c982275d2f5046439e77e4e5236d614d083e865fbb86414059a38d06f652aa66'
IDENTS = ('res_dc', 'mim_ac', 'rc_step')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_passives(root, cfg, deck, netlist_body, log_audit, check_model=True):
    root = Path(root)
    manifest = sha(root/'package_manifest.json')
    jobs = {j['id']: j for j in json.loads((root/'jobs.json').read_text())}
    records = {}
    model_hashes = set()
    for ident in IDENTS:
        attempts = sorted((root/'runs'/ident).glob('*/status.json'))
        if not attempts: raise ValueError('Missing passive attempt: '+ident)
        path = attempts[-1]
        out = path.parent
        state = json.loads(path.read_text())
        if state['status'] != 'PASS':
            raise ValueError('Latest '+ident+' did not complete; retain and resolve '+out.name)
        if state['job'] != jobs[ident]: raise ValueError('Frozen passive job differs: '+ident)
        if state.get('package_sha256') not in (PREVIOUS_MANIFEST, manifest):
            raise ValueError('Unreviewed evidence package: '+ident)
        if any(state['site'].get(k) != cfg.get(k) for k in ['ocean', 'spectre', 'workdir', 'model']):
            raise ValueError('Site configuration differs from passive evidence: '+ident)
        model_hashes.add(state['model_entry_sha256'])
        raw = (out/'native_netlist.scs').read_text()
        if sha(out/'native_netlist.scs') != state['native_netlist_sha256']:
            raise ValueError('Native body hash differs: '+ident)
        selection = json.loads((out/'native_selection.json').read_text())
        if selection['selected_body_sha256'] != state['native_netlist_sha256'] or sha(out/'native_input.scs') != selection['returned_input_sha256']:
            raise ValueError('Native envelope evidence differs: '+ident)
        check(raw, json.loads((root/'design.json').read_text()), jobs[ident]['cell'], jobs[ident]['params'])
        if sha(out/'input.scs') != state['input_sha256'] or (out/'input.scs').read_text() != deck(jobs[ident], netlist_body(raw), state['site']):
            raise ValueError('Executed analysis differs from frozen deck: '+ident)
        logged = json.loads((out/'log_audit.json').read_text())
        if log_audit((out/'spectre.out').read_text(), logged['exit_code'])['status'] != 'PASS':
            raise ValueError('Spectre completion not verified: '+ident)
        if (out/'export_complete.txt').read_text().strip() != 'COMPLETE':
            raise ValueError('Export incomplete: '+ident)
        metrics = analyze_passive(out, jobs[ident])
        names = ['status.json', 'metrics.json', 'native_netlist.scs', 'native_input.scs', 'native_selection.json',
                 'input.scs', 'spectre.out', 'log_audit.json', 'export_complete.txt', 'spectre_version.txt']
        names += ['VIN.csv', 'VOUT.csv'] if ident == 'rc_step' else ['TEST.csv', 'VTEST_p.csv']
        records[ident] = dict(attempt=out.name, source_status=state['status'],
                              source_performance_status=state['performance_status'],
                              metrics=metrics, fingerprints={n: sha(out/n) for n in names})
    if len(model_hashes) != 1: raise ValueError('Passive jobs use different model entry hashes')
    model_hash = next(iter(model_hashes))
    if check_model and sha(Path(cfg['model'])) != model_hash:
        raise ValueError('Installed model entry changed since passive simulations')
    return dict(status='PASS' if all(r['metrics']['status'] == 'PASS' for r in records.values()) else 'FAIL',
                kind='REANALYSIS_OF_RETAINED_SPECTRE_RESULTS', acceptance_revision='M0_MODEL_REVIEW_V1',
                package_sha256=manifest, model_entry_sha256=model_hash, site=cfg,
                current_site_model_checked=check_model, records=records,
                scope='Default passive migration tests at TT / 27 C only',
                limitations=['No new simulation was run by this reanalysis.',
                             'PDK model dependency files are not independently hash-certified.',
                             'MOS, OTA, PVT, noise, layout and ADC qualification are separate.'])


def same_evidence(saved, current):
    return (saved.get('status') == current.get('status') == 'PASS' and
            saved.get('current_site_model_checked') and current.get('current_site_model_checked') and
            all(saved.get(k) == current.get(k) for k in
                ['acceptance_revision', 'package_sha256', 'model_entry_sha256', 'site', 'records']))
