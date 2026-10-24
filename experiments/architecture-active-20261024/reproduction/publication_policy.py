"""Archive selected study outputs, preserving source bytes and recording omissions."""
import collections
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile

TASK = Path(r'C:\Users\nicol\Documents\Codex\2026-10-23\ce-que-je-voudrais-que-tu')
OUTPUTS = TASK / 'outputs'
REPO = Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')
DEST = REPO / 'experiments/comparaisons-romeo-20261024'
FILES = {}
OMITTED = []
ARCHIVES = []
PATTERNS = {
    'api_key': rb'\bsk-[A-Za-z0-9_-]{20,}',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'bearer': rb'\bBearer\s+[A-Za-z0-9_.-]{20,}',
    'private_key': rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    'credential_value': rb'"(?:access_token|refresh_token|client_secret|api_key)"\s*:\s*"[^"\s]{16,}"',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def path_reason(name, allow_archive=False):
    p = PurePosixPath(name.replace('\\', '/'))
    parts = {part.lower() for part in p.parts}
    base = p.name.lower()
    if p.is_absolute() or '..' in p.parts or any(':' in part for part in p.parts):
        return 'unsafe_path'
    if parts & {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', '.ruff_cache'}:
        return 'environment_or_cache'
    if parts & {'native', 'worker', 'conversations', 'fetch-locks', 'authorizations'}:
        return 'native_session_or_cache'
    if base in {'authorization.json', 'authorization-pending.json', 'owner.json', 'worker-ready.json', 'auth.json', '.env'} or (base.startswith('.env.') and base != '.env.example') or base.endswith('.lock'):
        return 'execution_authorization_or_lock'
    if p.suffix.lower() in {'.sqlite3', '.sqlite', '.db', '.pkl', '.pickle', '.pyc'}:
        return 'raw_runtime_state'
    if p.suffix.lower() in {'.exe', '.dll', '.so', '.a', '.o', '.obj', '.bin', '.npy', '.npz'}:
        return 'compiled_or_intermediate_binary'
    if not allow_archive and (base.endswith(('.zip', '.tar.gz', '.tgz', '.gz'))):
        return 'original_archive_kept_locally'
    return None


def content_reason(data):
    for name, pattern in PATTERNS.items():
        if re.search(pattern, data):
            return 'credential_pattern:' + name
    if data.startswith((b'\x7fELF', b'MZ\x90\x00')):
        return 'compiled_binary'
    return None


def omitted(source, reason, data=None, size=None):
    record = {'source': source, 'reason': reason}
    if data is not None:
        record.update(bytes=len(data), sha256=digest(data))
    elif size is not None:
        record['bytes'] = size
    OMITTED.append(record)


def write(relative, data, source):
    relative = PurePosixPath(relative).as_posix()
    assert not path_reason(relative, allow_archive=True), relative
    resolved = (DEST / relative).resolve()
    assert resolved.is_relative_to(DEST.resolve()), relative
    target = Path('\\\\?\\' + str(resolved))
    if target.exists():
        assert target.read_bytes() == data, f'Existing file differs: {relative}'
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    record = {'path': relative, 'source': source, 'bytes': len(data), 'sha256': digest(data)}
    if relative in FILES:
        assert FILES[relative] == record, relative
    FILES[relative] = record


def inspect_zip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for member in z.infolist():
            if member.is_dir():
                continue
            why = path_reason(member.filename)
            if why:
                return why
            why = content_reason(z.read(member))
            if why:
                return why
    return None


def inspect_tar(data):
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tf:
        for member in tf:
            if member.isdir():
                continue
            if not member.isfile():
                return 'archive_nonregular_member'
            why = path_reason(member.name)
            if why:
                return why
            why = content_reason(tf.extractfile(member).read())
            if why:
                return why
    return None


def extract_suite(z, archive_source, target_prefix):
    member_name = 'references/protected-suites.tar.gz'
    data = z.read(member_name)
    source = archive_source + '!' + member_name
    ARCHIVES.append({'source': source, 'bytes': len(data), 'sha256': digest(data), 'extracted_to': target_prefix})
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tf:
        for member in tf:
            if member.isdir():
                continue
            item_source = source + '!' + member.name
            if not member.isfile():
                omitted(item_source, 'archive_nonregular_member', size=member.size)
                continue
            why = path_reason(member.name)
            raw = tf.extractfile(member).read()
            why = why or content_reason(raw)
            if why:
                omitted(item_source, why, raw)
            else:
                write(target_prefix + '/' + member.name, raw, item_source)


def extract_evidence(group, extract_protected=False):
    path = OUTPUTS / group / 'PREUVES-ET-CODES.zip'
    archive_source = 'outputs/' + path.relative_to(OUTPUTS).as_posix()
    ARCHIVES.append({'source': archive_source, 'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest(), 'extracted_to': group + '/pieces-extraites'})
    with zipfile.ZipFile(path) as z:
        for member in z.infolist():
            if member.is_dir():
                continue
            name = member.filename
            source = archive_source + '!' + name
            why = path_reason(name)
            if name.startswith('rapport/'):
                why = 'report_already_present_at_group_root'
            if why:
                omitted(source, why, size=member.file_size)
                continue
            data = z.read(member)
            why = content_reason(data)
            if why:
                omitted(source, why, data)
            else:
                write(group + '/pieces-extraites/' + name, data, source)
        if extract_protected:
            extract_suite(z, archive_source, group + '/pieces-extraites/references/protected-suites')


def main():
    paths = subprocess.check_output(['rg', '--files', '--hidden', '--no-ignore', str(OUTPUTS)]).decode().splitlines()
    for path in sorted(map(Path, paths)):
        relative = path.relative_to(OUTPUTS).as_posix()
        source = 'outputs/' + relative
        data = path.read_bytes()
        why = path_reason(relative)
        if relative.startswith('schema-forest-jev/') and path.name in {'index.html', 'collection.pdf'}:
            why = 'duplicate_diagram_container_png_svg_published'
        safe_container = relative.startswith('comparaison-historique/engines/') and path.suffix == '.zip'
        safe_container = safe_container or relative == 'comparaison-historique/reproduction-gpu.tar.gz'
        if safe_container:
            why = inspect_zip(data) if path.suffix == '.zip' else inspect_tar(data)
        if not why:
            why = content_reason(data)
        if why:
            omitted(source, why, data)
        else:
            if path.suffix == '.xlsx':
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for name in z.namelist():
                        if name.endswith(('.xml', '.rels')):
                            assert not content_reason(z.read(name)), (relative, name)
            write(relative, data, source)
    print(json.dumps({'phase':'direct_outputs','files':len(FILES),'omissions':len(OMITTED)}), flush=True)
    extract_evidence('comparaison-references', extract_protected=True)
    print(json.dumps({'phase':'reference_sources','files':len(FILES),'omissions':len(OMITTED)}), flush=True)
    extract_evidence('comparaison-reprises')
    manifest = {
        'schema_version': 1,
        'archived_on': '2026-10-24',
        'description': 'Sources, rapports et preuves existants copies sans recalcul. Les fichiers internes extraits conservent leurs octets; les conteneurs originaux restent locaux lorsqu ils comprennent des sessions ou des donnees intermediaires.',
        'files': sorted(FILES.values(), key=lambda item: item['path']),
        'original_archives': ARCHIVES,
        'omitted': OMITTED,
        'summary': {'published_files': len(FILES), 'published_bytes': sum(x['bytes'] for x in FILES.values()), 'omitted_items': len(OMITTED), 'omitted_by_reason': dict(collections.Counter(x['reason'] for x in OMITTED))},
    }
    (DEST / 'MANIFESTE-PUBLICATION.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest['summary']), flush=True)
    print(json.dumps({'credential_pattern_omissions': [x['source'] for x in OMITTED if x['reason'].startswith('credential_pattern')]}), flush=True)


if __name__ == '__main__':
    main()
