"""Export exact confirmed commits locally, without changing the controller's choice."""
import hashlib
import io
import json
import re
import shutil
import sqlite3
import subprocess
import time
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
state = json.loads((HERE / 'state.json').read_text(encoding='utf8'))
evidence = HERE / 'evidence'
result = json.loads((evidence / 'results.json').read_text(encoding='utf8'))
final = result['final_g_confirmation']
outcome = final['outcome']
assert result['pipeline_complete'] and final['status'] == 'confirmed' and outcome['correct'] is True
assert final['experiment_id'] == result['postprocess']['mission_id']
assert outcome['commit'] == result['postprocess']['outcome']['commit']
assert len(outcome['times']) == 5 and re.fullmatch('[a-f0-9]{40}', outcome['commit'])

with sqlite3.connect((evidence / 'registry.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True) as con:
    stored = con.execute('SELECT payload FROM evaluations WHERE experiment_id=? AND phase=?',
                         (final['experiment_id'], 'confirmation')).fetchone()
    assert stored and json.loads(stored[0]) == outcome

winner_zip = evidence / 'submission.zip'
with zipfile.ZipFile(winner_zip) as archive:
    assert archive.testzip() is None
    winner_manifest = json.loads(archive.read('HPC_FOREST_MANIFEST.json'))
    assert winner_manifest['commit'] == result['best_confirmed']['commit']
    assert winner_manifest['final_g_confirmation'] == final
    assert winner_manifest['delivery']['kind'] == 'cuda-kernel'
    for entry in winner_manifest['delivery']['files'].values():
        assert hashlib.sha256(archive.read(entry['path'])).hexdigest() == entry['sha256']
    if winner_manifest['commit'] == outcome['commit']:
        source_archive = winner_zip.read_bytes()
    else:
        git_dir = evidence / 'source-repo/.git'
        if not git_dir.is_dir():
            raise SystemExit('NEED_CONFIRMED_G_GIT_OBJECTS: download this campaign repo to evidence/source-repo')
        source_archive = subprocess.run(['git', '--git-dir=' + str(git_dir), 'archive', '--format=zip',
                                         outcome['commit']], check=True, capture_output=True).stdout

destination = HERE / 'resultat'
destination.mkdir(exist_ok=True)
shutil.copyfile(winner_zip, destination / 'meilleur-confirme.zip')
source_files = {}
with zipfile.ZipFile(io.BytesIO(source_archive)) as archive:
    assert archive.testzip() is None
    for name in ('src/nbody_kernel.cu', 'src/launch.json'):
        source_files[name] = archive.read(name)
settings = json.loads(source_files['src/launch.json'])
assert set(settings) == {'block', 'items_per_block', 'shared_memory_bytes'}

calls = []
worker = Path(state['artifact']) / 'worker'
for directory in worker.iterdir():
    request_path, response_path = directory / 'downloaded-request.json', directory / 'response.json'
    if not request_path.is_file() or not response_path.is_file():
        continue
    request = json.loads(request_path.read_text(encoding='utf8'))
    conversation = request.get('conversation') or {}
    if conversation.get('phase') == 'assembly':
        calls.append((conversation['turn'], directory, json.loads(response_path.read_text(encoding='utf8'))))
_, last_directory, response = max(calls)
proposal_matches = []
for item in response['data']['files']:
    proposed = item['content'].encode('utf8')
    assert item['path'] in source_files and source_files[item['path']] == proposed
    proposal_matches.append({'path': item['path'], 'sha256': hashlib.sha256(proposed).hexdigest(), 'match': True})

manifest = {
    'format': 'hpc-forest-confirmed-final-g-v1', 'created_at': time.time(),
    'job_id': state['job_id'], 'session_id': state['session_id'],
    'model': state['model'], 'effort': state['effort'], 'search_policy': 'ab-mcts-a',
    'experiment_id': final['experiment_id'], 'commit': outcome['commit'],
    'controller_winner_commit': result['best_confirmed']['commit'],
    'is_controller_winner': result['best_confirmed']['commit'] == outcome['commit'],
    'confirmation': final, 'mother_conversation': result['mother_conversation'],
    'source_files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
                     for name, data in source_files.items()},
    'launch': settings, 'entry': 'nbody_step_naive',
    'delivery': 'CUDA device kernel and launch contract for the matching trusted NVRTC host harness',
    'source_original_sha256': state['source_sha256'],
}
export = destination / 'G-final-confirme.zip'
with zipfile.ZipFile(export, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for name, data in source_files.items():
        archive.writestr(name, data)
        output_path = destination / 'G-final' / Path(*PurePosixPath(name).parts)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
    archive.writestr('HPC_FOREST_G_FINAL_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
with zipfile.ZipFile(export) as archive:
    assert archive.testzip() is None
    for name, data in source_files.items():
        assert archive.read(name) == data
for path in (export, destination / 'meilleur-confirme.zip'):
    path.with_suffix(path.suffix + '.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n', encoding='ascii')

receipt = {'job_id': state['job_id'], 'experiment_id': final['experiment_id'],
           'confirmed_commit': outcome['commit'], 'native_nonce': last_directory.name,
           'files': proposal_matches, 'all_proposed_sources_match_confirmed_git_commit': True,
           'proof_basis': 'Exact independently confirmed Git commit; compared with final native proposal bytes',
           'export_zip': str(export), 'zip_sha256': hashlib.sha256(export.read_bytes()).hexdigest(),
           'all_exported_sources_match_confirmed_commit': True, 'manifest': manifest}
(HERE / 'G-final-source-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
(HERE / 'export-verification.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps({'job_id': state['job_id'], 'g_final_commit': outcome['commit'], 'is_controller_winner': manifest['is_controller_winner'],
                  'g_final_zip': str(export), 'zip_sha256': receipt['zip_sha256'], 'exported_sources': manifest['source_files']}))
