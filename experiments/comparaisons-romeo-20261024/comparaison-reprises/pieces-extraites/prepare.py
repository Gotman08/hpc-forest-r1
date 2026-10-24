"""Freeze independent reruns without importing any previous candidate or memory."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tarfile
import time
import uuid

R = Path(__file__).resolve().parent
OLD = R.parent / 'reference-study'
REPO = Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')
CASES = ['base64', 'deferred', 'aobench', 'raytracer', 'reduction', 's4convd',
         'softmax', 'stencil3d', 'sumabs', 'volume', 'gemm_cpu', 'mandelbrot',
         'blackscholes', 'utf8']
SCOPE = 'reference-rerun-luna-max-v1'
REQUEST = ('Corrige les erreurs d’infrastructure puis relance les cas peu explorés '
           'avec plus de temps et une mémoire neuve par programme. '
           'Compare les nouveaux speedups aux précédents sur ROMEO.')


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf8')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    inventory = []
    engine = {f.relative_to(REPO).as_posix(): sha(f) for f in (REPO/'src').rglob('*')
              if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'}
    write(R/'engine-files.json', engine)
    (R/'engine.patch').write_bytes(subprocess.check_output(['git', 'diff', '--', 'src', 'tests'], cwd=REPO))
    shutil.copyfile(REPO/'tests/test_mcp_discovery.py', R/'test_mcp_discovery.py')
    for key in CASES:
        prior = OLD/'campaigns'/('deferred_r2' if key == 'deferred' else key)
        a = R/'campaigns'/key
        if a.exists():
            raise RuntimeError('Never overwrite a prepared campaign: '+str(a))
        p = a/'payload'
        shutil.copytree(prior/'payload', p, ignore=shutil.ignore_patterns('project', '__pycache__', '*.pyc'))
        shutil.copytree(REPO/'src', p/'project/src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        session = uuid.uuid4().hex
        remote = '/scratch_p/nimarano/forest-reference-rerun-'+key+'-'+session
        cfg = read(p/'settings.json')
        cfg['budget']['wall_seconds'] = 7200
        cfg['codex'].update(session_id=session, mailbox_dir=remote+'/pending/mailbox')
        plan = read(p/'plan.json')
        plan.update(scope=SCOPE, session_id=session, remote_root=remote, wall_seconds=7200,
                    created_at=time.time(), old_candidates_imported=False,
                    previous_job=read(prior/'job.json')['job_id'], previous_case=prior.name,
                    fresh_memory=True, engine_manifest_sha256=sha(R/'engine-files.json'))
        for name, data in [('plan.json', plan), ('settings.json', cfg)]:
            write(p/name, data)
            write(a/name, data)
        shutil.copyfile(p/'statement.txt', a/'statement.txt')
        pilot = (p/'pilot.py').read_text(encoding='utf8')
        pilot = pilot.replace('reference-comparison-luna-max-v1', SCOPE)
        # Assert the campaign is empty before the baseline and first Mother call.
        pilot = pilot.replace('controller.db.event("cuda_nbody_fresh_campaign", result)', '''
            fresh = {
                'session_id': plan['session_id'], 'epoch': controller.db.get('current_epoch'),
                'trial_count': len(controller.db.rows('SELECT id FROM trials')),
                'document_count': len(controller.db.rows('SELECT * FROM documents')),
                'previous_candidates_imported': False,
                'initial_source_sha256': plan['source_sha256'],
            }
            if fresh['trial_count'] or fresh['document_count']:
                raise InfrastructureError('Fresh campaign unexpectedly contains prior research')
            atomic_json(output / 'fresh-memory.json', fresh)
            controller.db.event('reference_rerun_fresh_campaign', fresh)'''.strip())
        (p/'pilot.py').write_text(pilot, encoding='utf8', newline='\n')
        for name in ['Makefile', 'run.sh']:
            assert (p/'source'/name).is_file(), (key, name)
        source_files = {f.relative_to(p/'source').as_posix(): sha(f)
                        for f in (p/'source').rglob('*') if f.is_file()}
        prior_files = {f.relative_to(prior/'payload/source').as_posix(): sha(f)
                       for f in (prior/'payload/source').rglob('*') if f.is_file()}
        assert source_files == prior_files, key
        protected = {f.relative_to(p/'validation').as_posix(): sha(f)
                     for f in (p/'validation').rglob('*') if f.is_file()}
        assert all(sha(prior/'payload/validation'/name) == value for name, value in protected.items())
        write(p/'runtime-manifest.json', {f.relative_to(p).as_posix(): sha(f) for f in p.rglob('*')
                                       if f.is_file() and f.name != 'runtime-manifest.json'})
        with tarfile.open(a/'payload.tar.gz', 'w:gz') as archive:
            for f in sorted(p.iterdir()):
                archive.add(f, arcname=f.name)
        prep = {'condition': key, 'remote_root': remote, 'remote_payload': remote+'.tar.gz',
                'remote_results': remote+'.results.tar.gz', 'artifact': str(a),
                'session_id': session, 'model_mcp': False, 'payload_sha256': sha(a/'payload.tar.gz')}
        write(a/'preparation.json', prep)
        command = (prior/'command.sh').read_text().replace(read(prior/'plan.json')['remote_root'], remote)
        command = command.replace(read(prior/'preparation.json')['payload_sha256'], prep['payload_sha256'])
        (a/'command.sh').write_text(command, encoding='utf8', newline='\n')
        inventory.append({'case_id': key, 'previous_job': plan['previous_job'],
                          'previous_seconds': 1800, 'new_seconds': 7200,
                          'session_id': session, 'remote_root': remote, 'gpus': plan['gpus'],
                          'cpus': plan['cpus'], 'source_files': source_files,
                          'protected_files': protected, 'baseline_identical': True,
                          'payload_sha256': prep['payload_sha256']})
    write(R/'campaigns.json', inventory)
    for name in ['relay.py', 'engine_broker_client.py']:
        shutil.copyfile(OLD/name, R/name)
    broker = (OLD/'broker.py').read_text()
    broker = broker.replace('work/reference-study/broker', 'work/reference-rerun/broker')
    broker = broker.replace('forest-reference-run-', 'forest-reference-rerun-')
    broker = broker.replace('outputs/comparaison-references', 'outputs/comparaison-reprises')
    (R/'broker.py').write_text(broker, encoding='utf8')
    support = (OLD/'launch_support.py').read_text()
    # Do not retain the obsolete refresh routine which modifies old preparation.
    start = support.index('def refresh():')
    end = support.index('def broker():', start)
    support = support[:start]+support[end:]
    support = support.replace("if sys.argv[1]=='refresh':refresh()\n    elif", 'if')
    old_request = 'Tester notre systeme avec tous les types de code du classeur fourni et comparer ses resultats en tenant compte des differences materielles.'
    support = support.replace(old_request, REQUEST)
    (R/'launch_support.py').write_text(support, encoding='utf8')
    write(R/'protocol.json', {'scope': SCOPE, 'request': REQUEST, 'cases': CASES,
          'selection_rule': 'At least one research tree had exactly one trial in the preceding completed campaign.',
          'wall_seconds_per_program': 7200, 'model': 'gpt-6-luna', 'effort': 'max', 'seed': 23,
          'fresh_sessions': True, 'old_candidates_supplied_to_model': False,
          'protected_protocol_identical': True, 'baseline_sources_identical': True,
          'final_comparison': 'Paired old/new selected programs, naive and published optimized reference in the same ROMEO allocation.'})
    print(json.dumps([{'case': x['case_id'], 'cpus': x['cpus'], 'gpus': x['gpus']} for x in inventory]))


if __name__ == '__main__':
    main()
