"""Integrity guards for new frontend experiments, not electrical qualification.

Manifests detect changed recorded artifacts; they are not signed attestations.
Analysis reports live separately so that a new analysis cannot rewrite evidence.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


MANIFEST_NAME = 'evidence_manifest.json'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_nominal_or_fixed_calibration(vdd, temp, calibration_from):
    if (vdd != 1.8 or temp != 27) and not calibration_from:
        raise ValueError('Non-nominal voltage/temperature linearity requires '
                         '--calibration-from at 1.8 V, 27 C; per-condition refitting is forbidden.')


def snapshot_calibration(source_summary, folder):
    """Keep the actual coefficients and matching circuit used by this run."""
    source_summary, folder = Path(source_summary), Path(folder)
    source_core = source_summary.parent/'frontend_pdk_snapshot.spice'
    destinations = {
        'calibration_source_summary.json': source_summary,
        'calibration_source_frontend.spice': source_core,
    }
    for name in (*destinations, 'calibration_source_metadata.json'):
        if (folder/name).exists():
            raise FileExistsError('Refusing to replace frozen calibration: '+str(folder/name))
    contents = {name: source.read_bytes() for name, source in destinations.items()}
    provenance = {}
    for name, source in destinations.items():
        (folder/name).write_bytes(contents[name])
        provenance[name] = {'original_path': str(source.resolve()),
                            'sha256': hashlib.sha256(contents[name]).hexdigest()}
    (folder/'calibration_source_metadata.json').write_text(json.dumps(provenance, indent=2)+'\n')
    return folder/'calibration_source_summary.json', folder/'calibration_source_frontend.spice'


def write_manifest(folder, required, producer_paths=()):
    """Freeze hashes after a successful new run, never over an existing manifest."""
    folder = Path(folder)
    destination = folder/MANIFEST_NAME
    if destination.exists():
        raise FileExistsError('Refusing to replace immutable experiment manifest')
    for name in required:
        if not (folder/name).is_file():
            raise ValueError('Missing required experiment evidence: '+name)
    files = {path.name: {'sha256': sha256(path), 'size_bytes': path.stat().st_size}
             for path in sorted(folder.iterdir()) if path.is_file() and path.name != MANIFEST_NAME}
    manifest = {'version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
                'scope': 'Recorded artifact integrity only, not an electrical test PASS',
                'files': files,
                'producer_code': {str(Path(path).resolve()): sha256(path) for path in producer_paths}}
    with destination.open('x') as stream:
        stream.write(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return destination


def verify_manifest(folder):
    """Return False for explicitly unverified legacy runs; reject changed evidence."""
    folder = Path(folder)
    path = folder/MANIFEST_NAME
    if not path.exists():
        return False
    manifest = json.loads(path.read_text())
    if manifest.get('version') != 1 or not isinstance(manifest.get('files'), dict) or not manifest['files']:
        raise ValueError('Unsupported or empty evidence manifest')
    for name, expected in manifest['files'].items():
        if Path(name).name != name or name in ('.', '..', MANIFEST_NAME):
            raise ValueError('Manifest artifact must be a direct child file: '+name)
        artifact = folder/name
        if (not artifact.is_file() or artifact.stat().st_size != expected['size_bytes']
                or sha256(artifact) != expected['sha256']):
            raise ValueError('Frozen experiment evidence changed or is missing: '+name)
    return True


def write_analysis(folder, result):
    directory = Path(folder)/'analyses'
    directory.mkdir(exist_ok=True)
    path = directory/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'_summary.json')
    with path.open('x') as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return path
