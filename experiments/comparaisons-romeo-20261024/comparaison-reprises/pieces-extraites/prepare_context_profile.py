"""Stage a fresh, uniform 64k context profile; preserve the interrupted 12k attempt."""
import copy
import json
import shutil
import sys
import tarfile
import time
import uuid
from pathlib import Path
from prepare import R, read, write, sha

sys.path.insert(0, str(R/'campaigns/base64/payload/project/src'))
from hpc_forest.core import canonical
from hpc_forest.memory_context import source_view
from hpc_forest.support.sources import source_snapshot

stage = R/('staging-campaigns-context64000-'+uuid.uuid4().hex)
stage.mkdir(exist_ok=False)
inventory = []
checks = []
scope = 'reference-rerun-luna-max-v2'
for item in read(R/'campaigns.json'):
    key = item['case_id']
    old = R/'campaigns'/key
    new = stage/key
    payload = new/'payload'
    shutil.copytree(old/'payload', payload, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    session = uuid.uuid4().hex
    remote = '/scratch_p/nimarano/forest-reference-rerun-'+key+'-'+session
    cfg = read(payload/'settings.json')
    cfg['memory']['context_characters'] = 64000
    cfg['codex'].update(session_id=session, mailbox_dir=remote+'/pending/mailbox')
    plan = read(old/'plan.json')
    prior_remote = plan['remote_root']
    plan.update(scope=scope, session_id=session, remote_root=remote, created_at=time.time(),
                memory=copy.deepcopy(cfg['memory']), context_profile='full-source-64000',
                interrupted_context_12000_job=read(old/'job.json')['job_id'])
    for name, data in [('settings.json', cfg), ('plan.json', plan)]:
        write(new/name, data)
        write(payload/name, data)
    pilot = (payload/'pilot.py').read_text(encoding='utf8')
    assert 'reference-rerun-luna-max-v1' in pilot
    (payload/'pilot.py').write_text(pilot.replace('reference-rerun-luna-max-v1', scope), encoding='utf8', newline='\n')
    shutil.copyfile(old/'statement.txt', new/'statement.txt')
    original = source_snapshot(payload/'source')
    old_view, _ = source_view(payload/'source', {'memory': {'enabled': True, 'max_result_characters': 12000}})
    new_view, context = source_view(payload/'source', {'memory': {'enabled': True, 'max_result_characters': 64000}})
    assert new_view == original and not context['memory'].get('source_read_required'), key
    expected_sources = {name: digest for name, digest in item['source_files'].items()
                        if name.startswith('src/') and '__pycache__' not in Path(name).parts and not name.endswith('.pyc')}
    assert set(original) == set(expected_sources), (key, set(original), set(expected_sources))
    assert all(sha(payload/'source'/name) == expected_sources[name] == sha(old/'payload/source'/name) for name in original)
    assert {p.relative_to(payload/'validation').as_posix(): sha(p) for p in (payload/'validation').rglob('*') if p.is_file()} == item['protected_files']
    checks.append({'case_id': key, 'serialized_source_characters': len(canonical(original)),
                   'source_files': len(original), 'complete_at_12000': old_view == original,
                   'complete_at_64000': True, 'source_unchanged': True, 'validation_unchanged': True})
    write(payload/'runtime-manifest.json', {p.relative_to(payload).as_posix(): sha(p) for p in payload.rglob('*')
                                          if p.is_file() and p.name != 'runtime-manifest.json'})
    with tarfile.open(new/'payload.tar.gz', 'w:gz') as archive:
        for p in sorted(payload.rglob('*')):
            if p.is_file():
                archive.add(p, arcname=p.relative_to(payload).as_posix())
    prep = read(old/'preparation.json')
    old_hash = prep['payload_sha256']
    prep.update(remote_root=remote, remote_payload=remote+'.tar.gz', remote_results=remote+'.results.tar.gz',
                artifact=str(R/'campaigns'/key), session_id=session, payload_sha256=sha(new/'payload.tar.gz'))
    write(new/'preparation.json', prep)
    (new/'command.sh').write_text((old/'command.sh').read_text().replace(prior_remote, remote).replace(old_hash, prep['payload_sha256']), encoding='utf8', newline='\n')
    record = copy.deepcopy(item)
    record.update(remote_root=remote, session_id=session, payload_sha256=prep['payload_sha256'],
                  context_characters=64000, interrupted_context_12000_job=plan['interrupted_context_12000_job'])
    record['excluded_cached_bytecode'] = [name for name in item['source_files'] if name.endswith('.pyc')]
    record['source_files'] = {p.relative_to(payload/'source').as_posix(): sha(p) for p in (payload/'source').rglob('*') if p.is_file()}
    inventory.append(record)
write(stage/'campaigns.json', inventory)
write(R/'staged-context-profile.json', {'path': str(stage), 'scope': scope, 'validated_campaigns': len(inventory)})
write(R/'source-context-validation.json', {'context_before': 12000, 'context_after': 64000,
      'engine_source_unchanged_from_first_rerun': True, 'model_informed_of_old_results': False,
      'reason': 'Paged source and bounded history on ephemeral calls did not retain the complete long current source.',
      'observed_paging': {'base64': 16083, 'deferred': 27282, 'volume_generated_source': 16837},
      'checks': checks})
print(json.dumps({'staged': len(inventory), 'complete_sources': sum(c['complete_at_64000'] for c in checks),
                  'baseline_sources_needing_larger_context': [c['case_id'] for c in checks if not c['complete_at_12000']]}))
