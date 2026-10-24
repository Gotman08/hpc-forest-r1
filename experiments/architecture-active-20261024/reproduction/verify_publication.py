"""Verify the complete public archive against hashes and its selected evidence."""
import datetime
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from archive import R, REPO, ROOT, policy


def main():
    destination = policy.DEST
    manifest = json.loads((destination / 'MANIFESTE-PUBLICATION.json').read_text(encoding='utf8'))
    entries = manifest['files']
    assert len(entries) == manifest['published_files']
    names = {e['path'] for e in entries}
    assert len(names) == len(entries)
    assert sys.argv[1:] in [[], ['--staged']], sys.argv[1:]
    staged = {}
    object_format = None
    if '--staged' in sys.argv:
        prefix = destination.relative_to(REPO).as_posix() + '/'
        raw = subprocess.check_output(['git','-C',str(REPO),'ls-files','--stage','-z','--',prefix])
        object_format = subprocess.check_output(['git','-C',str(REPO),'rev-parse','--show-object-format']).decode().strip()
        for record in raw.decode('utf8').split('\0'):
            if not record:
                continue
            info, name = record.split('\t',1)
            mode, oid, stage = info.split()
            assert stage == '0' and mode == '100644', (name, info)
            staged[name.removeprefix(prefix)] = oid
        assert set(staged) == names | {'MANIFESTE-PUBLICATION.json'}

    def verify_git(name, data):
        if staged:
            digest = hashlib.new(object_format, f'blob {len(data)}\0'.encode() + data).hexdigest()
            assert digest == staged[name], (name, 'Git staged bytes differ')

    verify_git('MANIFESTE-PUBLICATION.json', (destination/'MANIFESTE-PUBLICATION.json').read_bytes())
    secrets = []
    for version in R.parent.glob('active-architecture-*'):
        connection = version / 'broker/connection.json'
        if connection.is_file():
            token = json.loads(connection.read_text(encoding='utf8')).get('token')
            if isinstance(token, str) and len(token) > 15:
                secrets.append(token.encode())
    largest = 0
    checked_bytes = 0
    embedded_xml_files = 0
    for entry in entries:
        name = entry['path']
        assert not policy.path_reason(name), name
        path = Path('\\\\?\\' + str((destination / name).resolve()))
        data = path.read_bytes()
        assert len(data) == entry['bytes'], name
        assert policy.digest(data) == entry['sha256'], name
        verify_git(name, data)
        assert not policy.content_reason(data), name
        assert not any(token in data for token in secrets), name
        assert len(data) <= 50 * 1024**2, (name, len(data))
        largest = max(largest, len(data))
        checked_bytes += len(data)
        if name.endswith('.xlsx'):
            with zipfile.ZipFile(io.BytesIO(data)) as workbook:
                for member in workbook.namelist():
                    if member.endswith(('.xml', '.rels')):
                        xml = workbook.read(member)
                        assert not policy.content_reason(xml), (name, member)
                        assert not any(token in xml for token in secrets), (name, member)
                        embedded_xml_files += 1
    assert checked_bytes == manifest['published_bytes']
    outputs = ROOT / 'outputs/architecture-active'
    for path in outputs.iterdir():
        if path.is_file():
            assert path.name in names, path.name
            assert (destination / path.name).read_bytes() == path.read_bytes(), path.name
    results = json.loads((destination / 'RESULTATS.json').read_text(encoding='utf8'))
    assert results['summary']['new_finished'] == 21
    assert results['summary']['measured_rows'] == 57
    for engine in results['engines']:
        if engine['period'] == 'new':
            assert 'campagnes/' + engine['case_id'] + '/plan.json' in names
            assert 'campagnes/' + engine['case_id'] + '/source-history.json' in names
    assert 'validation/remesure-pilote/verification.json' in names
    long_destination = Path('\\\\?\\' + str(destination.resolve()))
    actual = {p.relative_to(long_destination).as_posix() for p in long_destination.rglob('*') if p.is_file()}
    assert actual == names | {'MANIFESTE-PUBLICATION.json'}, sorted(actual - names)
    result = {
        'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'all_checks_passed': True,
        'files_verified': len(entries),
        'bytes_verified': checked_bytes,
        'largest_file_bytes': largest,
        'known_private_tokens_checked': len(secrets),
        'embedded_workbook_xml_files_checked': embedded_xml_files,
        'credential_matches': 0,
        'unlisted_files': 0,
        'completed_programs': 21,
        'measured_rows': 57,
        'git_staged_bytes_verified': bool(staged),
    }
    (R / 'publication-verification.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
