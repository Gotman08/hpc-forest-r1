"""Freeze equal-budget arms; this preparer never submits a job or optimizes code."""
import argparse
import copy
import json
import shutil
import tarfile
import uuid
from pathlib import Path

from hpc_forest.advisor import DEFAULT as ADVISOR_DEFAULT
from hpc_forest.config import load_config, validate
from hpc_forest.core import atomic_json, file_digest
from hpc_forest.model_skills import policy


def prepare(study, output, runtime, remote_base, protocol_path=None):
    protocol = json.loads((protocol_path or study / 'protocol.json').read_text(encoding='utf8'))
    repository = study.parents[1]
    prepared = []
    for case in protocol['cases']:
        for repeat, seed in enumerate([case['seed']]):
            pair_id = f"{case['case']}-r{repeat + 1}-" + uuid.uuid4().hex[:12]
            folder = output / pair_id
            folder.mkdir(parents=True)
            payload = folder / 'payload'
            payload.mkdir()
            inputs = study / 'inputs' / case.get('input_directory', case['case'])
            if any(file_digest(inputs / name) != sha for name, sha in case['files'].items()):
                raise RuntimeError('Historical input changed before freezing')
            shutil.copytree(inputs, payload / 'inputs')
            shutil.copytree(repository / 'src', payload / 'engine/src',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            shutil.copyfile(Path(__file__).with_name('run_pair.py'), payload / 'run_pair.py')
            remote = remote_base.rstrip('/') + '/diversified-advisor-' + pair_id
            config = load_config(inputs / 'settings.json')
            config['codex'].update(model='gpt-6-luna', reasoning_effort='max', generator_pool=[],
                                   executable=remote_base.rstrip('/') + '/runtime/bin/codex')
            config['codex']['mailbox_dir'] = remote + '/unused-before-arm-preparation'
            config['search'] = copy.deepcopy(protocol['search'])
            config['forest']['active'] = {'mode': 'full', 'code_analysis': True, 'closure_guards': True}
            config['skills'] = policy()
            config['harness']['research']['enabled'] = False  # Same no-web default as the native application.
            config['budget']['wall_seconds'] = protocol['search_target_seconds_per_arm']
            config['seed'] = seed
            config['advisor'] = {**ADVISOR_DEFAULT, 'enabled': False}
            config['advisor_runtime'] = runtime
            config['evolution'] = {'enabled': False}
            validate(config)
            atomic_json(payload / 'settings.json', config)
            arms = [{'id': uuid.uuid4().hex, 'session_id': uuid.uuid4().hex,
                     'condition': condition, 'enabled': condition == 'advisor_on'}
                    for condition in case['orders']]
            plan = {'scope': 'forest-diversified-advisor-20261026', 'pair_id': pair_id,
                    'case': case['case'], 'repeat': repeat + 1, 'seed': seed, 'arms': arms,
                    'cpus': case['allocation_cpus'], 'codex': config['codex']['executable'],
                    'target_seconds': protocol['search_target_seconds_per_arm'],
                    'cap_seconds': protocol['end_to_end_cap_seconds_per_arm'], 'remote_root': remote,
                    'protected_inputs': case['files'], 'operator_algorithm_hints': False,
                    'native_pc_relay': False, 'model': 'gpt-6-luna', 'effort': 'max'}
            atomic_json(payload / 'pair.json', plan)
            files = {p.relative_to(payload).as_posix(): file_digest(p) for p in sorted(payload.rglob('*'))
                     if p.is_file()}
            atomic_json(payload / 'files.json', files)
            archive = folder / 'payload.tar.gz'
            with tarfile.open(archive, 'w:gz') as stream:
                for path in sorted(payload.rglob('*')):
                    if path.is_file():
                        stream.add(path, arcname=path.relative_to(payload).as_posix(), recursive=False)
            record = {**plan, 'archive': str(archive), 'sha256': file_digest(archive),
                      'remote_archive': remote + '.tar.gz'}
            atomic_json(folder / 'preparation.json', record)
            prepared.append(record)
    atomic_json(output / 'preparations.json', prepared)
    return prepared


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--remote-base', required=True)
    parser.add_argument('--protocol', type=Path)
    args = parser.parse_args()
    rows = prepare(args.study.resolve(), args.output.resolve(),
                   json.loads(args.runtime.read_text()), args.remote_base, args.protocol)
    print(json.dumps([{'pair': row['pair_id'], 'remote': row['remote_root'], 'sha256': row['sha256']}
                      for row in rows]))
