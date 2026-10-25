"""Check measurement provenance, frozen engine and exported report artifacts."""
import ast
import csv
import hashlib
import json
import re
import tarfile
from pathlib import Path

import prepare

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/forest-corrections-20261024'
D = prepare.REPO / 'experiments/architecture-corrections-20261024'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    expected = read(R / 'engine-files.json')
    assert prepare.inventory(prepare.REPO / 'src') == expected
    selection = read(R / 'main-selections.json')
    for alias in selection.values():
        directory = R / 'campaigns' / alias
        assert prepare.inventory(directory / 'payload/project/src') == expected
        assert read(directory / 'worker-finished.json')['pending_diagnostics'] == []
        assert read(directory / 'relay-exit.json')['exit_code'] == 0
    for source in R.glob('*.py'):
        ast.parse(source.read_text(encoding='utf8'))
    data = read(O / 'RESULTATS.json')
    assert len(data['engines']) == 9 and len(data['rows']) == 15
    corrected = [e for e in data['engines'] if e['period'] == 'corrected']
    assert len(corrected) == 3 and all(e['pipeline_complete'] for e in corrected)
    assert sum(e['completed_analyses'] for e in corrected) == 43
    assert sum(e['verified_source_citations'] for e in corrected) == 159
    assert all(r['input_comparability_verified'] for r in data['rows'])
    for audit in data['binary_audits'].values():
        assert all(r['original_binary_unchanged'] and r['identical_to_original_binary']
                   and r['diagnostic_returncode'] == r['objdump_returncode'] == 0
                   for r in audit['records'])
    records = {r['variant']: r for r in data['audits']['utf8_extended']['records']}
    assert records['new_selected']['cases'] == 101205
    assert records['new_selected']['failed'] == records['new_g']['failed'] == 0
    assert records['diagnostic_43cb_e0']['failed'] == 314
    for name, count in [('comparaison.csv', 15), ('engines.csv', 9)]:
        with (O / name).open(encoding='utf-8-sig', newline='') as stream:
            assert len(list(csv.DictReader(stream))) == count
    for link in re.findall(r'\]\(([^)]+)\)', (O / 'RAPPORT.md').read_text(encoding='utf8')):
        if not re.match(r'https?://', link):
            assert (O / link).exists(), link
    for link in re.findall(r'href="([^"]+)"', (O / 'TABLEAU-DE-BORD.html').read_text(encoding='utf8')):
        assert (O / link).exists(), link
    # Read the task-owned bearer only in memory; never emit it or copy its file.
    credentials = read(R / 'broker/connection.json')
    tokens = [value.encode() for key, value in credentials.items()
              if any(word in key.lower() for word in ['token', 'secret', 'bearer'])
              and isinstance(value, str) and len(value) > 20]
    assert tokens, 'Expected transport secret for the leak check'
    scanned = 0
    for directory in [O, D] if D.exists() else [O]:
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            assert not any(token in raw for token in tokens), 'Transport secret in report artifact'
            if path.name.endswith('.tar.gz'):
                with tarfile.open(path) as archive:
                    for member in archive.getmembers():
                        if member.isfile():
                            content = archive.extractfile(member).read()
                            assert not any(token in content for token in tokens), 'Transport secret in source archive'
            scanned += 1
    manifest_count = None
    if D.exists():
        manifest = read(D / 'MANIFESTE.json')
        for name, record in manifest.items():
            raw = (D / name).read_bytes()
            assert len(raw) == record['bytes']
            assert hashlib.sha256(raw).hexdigest() == record['sha256']
        manifest_count = len(manifest)
    receipt = {'engine_files_unchanged': len(expected), 'complete_campaigns': 3,
        'documentary_comparisons': 15, 'measurement_records': len(data['measurements']),
        'source_citations': 159, 'extended_utf8_cases_per_variant': 101205,
        'artifact_files_scanned_without_transport_secret': scanned,
        'bundle_manifest_verified_files': manifest_count, 'passed': True}
    destination = R / 'bundle-validation.json' if D.exists() else O / 'ARTIFACT-VALIDATION.json'
    destination.write_text(json.dumps(receipt, indent=2), encoding='utf8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
