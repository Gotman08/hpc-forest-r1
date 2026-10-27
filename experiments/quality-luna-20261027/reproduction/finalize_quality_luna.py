"""Verify frozen bundles and write the exact reviewable SLURM pipeline."""
import importlib.util
import json
import shlex
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from hpc_forest.config import load_config, validate
from hpc_forest.core import atomic_json, file_digest
from prepare_quality_luna import (
    BASE,
    PYTHON,
    STUDY,
    TASK,
    WORK,
    archive,
    manifest,
    read,
)


def audit_checks(scripts):
    spec = importlib.util.spec_from_file_location('pilot_audit', scripts / 'audit_advice.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='quality-audit-') as tmp:
        root = Path(tmp)
        campaign = root / 'campaign'
        campaign.mkdir()
        sample = {'id': 'child', 'feature_stage': 'before_generation', 'captured_at': 1,
            'observed_at': 3, 'target_kind': 'child_minus_parent_log1p_speedup',
            'target': 1.0, 'measured_value': 2.0, 'parent_value': 1.0,
            'measured_score': 0.9, 'parent_score': 0.8, 'source_sha256': 'a'}
        decision = {'id': 'decision', 'chosen_id': 'child', 'candidate_ids': ['child'],
            'called': True, 'reordered': False, 'seconds': 1, 'status': 'advised',
            'validation_policy': 'runtime_calibrated_v2', 'expected_child_values': [2.5]}
        with sqlite3.connect(campaign / 'registry.sqlite3') as db:
            db.executescript('CREATE TABLE metadata(key TEXT,value TEXT); CREATE TABLE trials(id TEXT,mission TEXT,result TEXT); CREATE TABLE events(id INTEGER PRIMARY KEY,kind TEXT,payload TEXT,created REAL);')
            db.execute('INSERT INTO metadata VALUES (?,?)', ('advisor_sample:child', json.dumps(sample)))
            db.execute('INSERT INTO trials VALUES (?,?,?)', ('child', '{}', '{"status":"valid"}'))
            for kind, payload, created in [('research_node_submitted', {'experiment_id': 'child'}, 2), ('advisor_decision', decision, 1)]:
                db.execute('INSERT INTO events(kind,payload,created) VALUES (?,?,?)', (kind, json.dumps(payload), created))
        db.close()
        directory = campaign / 'advisor/decision'
        directory.mkdir(parents=True)
        atomic_json(directory / 'request.json', {'candidates': [{'captured_at': 1}], 'context': []})
        atomic_json(directory / 'response.json', {'status': 'validated', 'validation': {'mae_child_value': 0.25}})
        rows, summary = module.audit(root)
        assert rows[0]['observed_child_value'] == 2.0
        assert rows[0]['validation_mae_child_value'] == 0.25
        assert summary['selected_child_mae'] == 0.5
        with sqlite3.connect(campaign / 'registry.sqlite3') as db:
            sample['target'] = 0.1
            db.execute('UPDATE metadata SET value=?', (json.dumps(sample),))
        db.close()
        try:
            module.audit(root)
        except ValueError as exc:
            assert 'measured transition' in str(exc)
        else:
            raise AssertionError('Wrong target units were accepted')
    return {'runtime_value_audit': 'passed', 'wrong_target_rejected': True}


def main():
    rows = read(WORK / 'preparations.json')
    common = WORK / 'common'
    location = read(WORK / 'common-location.json')
    common_remote = location['remote']
    scripts = STUDY / 'reproduction'
    for name in ('prepare_quality_luna.py', 'finalize_quality_luna.py', 'qualify_quality_luna.py'):
        shutil.copyfile(TASK / 'work' / name, scripts / name)
    shutil.copyfile(TASK / 'work/qualify_quality_luna.py', common / 'qualify_quality_luna.py')
    checks = audit_checks(scripts)
    sys.path.insert(0, str(common))
    import qualify_quality_luna
    from hpc_forest.advisor_validation import validation_split
    request = qualify_quality_luna.request(common)
    _, _, info = validation_split(request['context'], 'qualification', policy=request['validation_policy'])
    assert not info.get('reason'), info
    configs = {}
    sessions = set()
    engine_manifest = read(STUDY / 'protocol.json')['engine_files']
    for row in rows:
        payload = Path(row['archive']).parent / 'payload'
        assert file_digest(Path(row['archive'])) == row['sha256']
        assert manifest(payload / 'engine/src/hpc_forest') == engine_manifest
        for name, sha in read(payload / 'files.json').items():
            assert file_digest(payload / name) == sha
        cfg = load_config(payload / 'settings.json')
        cfg['advisor'].update(row['arms'][0]['advisor'])
        validate(cfg)
        assert cfg['codex']['model'] == 'gpt-6-luna' and cfg['codex']['reasoning_effort'] == 'max'
        assert not cfg['codex']['generator_pool']
        assert len(row['arms']) == 1
        arm = row['arms'][0]
        assert arm['session_id'] not in sessions
        sessions.add(arm['session_id'])
        configs.setdefault(row['case'], {})[arm['condition']] = cfg
    for case, variants in configs.items():
        a, b = variants['off'], variants['corrected']
        a['codex'].pop('mailbox_dir')
        b['codex'].pop('mailbox_dir')
        assert a['advisor'].pop('enabled') is False
        assert b['advisor'].pop('enabled') is True
        assert a == b, case
    checks.update(assigned_arms=len(rows), independent_sessions=len(sessions),
        same_engine_verified=True, only_adviser_enable_flag_differs=True,
        real_model_qualification_preflight=info)
    atomic_json(STUDY / 'preflight-local.json', checks)
    packed = WORK / 'common.tar.gz'
    files = manifest(common)
    files.pop('files.json', None)
    atomic_json(common / 'files.json', files)
    archive(common, packed)
    common_sha = file_digest(packed)
    upload = {'archive': str(packed), 'remote_archive': common_remote + '.tar.gz', 'sha256': common_sha}
    atomic_json(WORK / 'uploads.json', [upload, *rows])
    quote = shlex.quote

    def environment(root, extract=None):
        lines = ['set -eu', 'umask 077', 'run_root=' + quote(root)]
        if extract:
            lines.extend(['test ! -e "$run_root"',
                "printf '%s\\n' " + quote(extract['sha256'] + '  ' + extract['remote_archive']) + ' | sha256sum -c -',
                'mkdir "$run_root"', 'tar -xzf ' + quote(extract['remote_archive']) + ' -C "$run_root"'])
        lines.extend(['cd "$run_root"',
            'export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1',
            "export HF_HUB_OFFLINE=1 TABPFN_NO_BROWSER=1 CUDA_VISIBLE_DEVICES=''",
            'export TMPDIR="$run_root/process-tmp" TMP="$run_root/process-tmp" TEMP="$run_root/process-tmp"',
            'export XDG_CACHE_HOME="$run_root/cache"', 'mkdir -p "$TMPDIR" "$XDG_CACHE_HOME"',
            'export PYTHONPATH="$run_root/engine/src:$run_root"'])
        return '\n'.join(lines) + '\n'

    auth = 'env CODEX_HOME=/home/nimarano/.codex-forest-romeo '
    qualify = environment(common_remote, upload)
    qualify += quote(PYTHON) + ' -c ' + quote("from study_storage import storage_check; from pathlib import Path; print(storage_check(Path.cwd(), min_files=90000)); print(storage_check(Path('/home/nimarano'), fileset='home', min_files=100000, min_bytes=3*1024**3))") + '\n'
    qualify += auth + quote(BASE + '/runtime/bin/codex') + ' login status\n'
    qualify += auth + quote(BASE + '/tabpfn-venv-20261025/bin/python') + ' -u qualify_quality_luna.py\n'
    qualify += "printf '%s\\n' qualified > " + quote(common_remote + '/qualification-passed.txt') + '\n'
    stages = [{'name': 'qualify', 'command': qualify, 'cpus_per_task': 1, 'mem_gb': 8, 'time_limit': '00:20:00'}]
    for row in rows:
        name = row['case'] + '-' + row['arms'][0]['condition']
        command = 'set -eu\ntest -f ' + quote(common_remote + '/qualification-passed.txt') + '\n' + environment(row['remote_root'], row)
        command += 'export FOREST_STORAGE_GUARD=1\n'
        command += 'export FOREST_STUDY_STATE=' + quote('/home/nimarano/quality-luna-20261027/state/' + row['pair_id']) + '\n'
        command += 'export FOREST_PRESERVED_HOME=' + quote('/home/nimarano/quality-luna-20261027/settled') + '\n'
        command += 'export FOREST_ARM_ARCHIVES=' + quote(BASE + '/quality-luna-20261027-archives/' + row['pair_id']) + '\n'
        command += 'export FOREST_STUDY_ARCHIVE=' + quote(row['remote_root'] + '.metadata.tar.gz') + '\n'
        command += 'mkdir -p "$FOREST_STUDY_STATE" "$FOREST_PRESERVED_HOME" "$FOREST_ARM_ARCHIVES"\n'
        command += auth + quote(PYTHON) + ' -u run_block.py --pair "$run_root"\n'
        stages.append({'name': name, 'command': command, 'cpus_per_task': 5, 'mem_gb': 8,
            'time_limit': '02:20:00', 'depends_on': ['qualify'], 'condition': 'afterany'})
    command = environment(common_remote)
    command += 'export FOREST_PERSISTENT_BLOCKS=1\n'
    command += auth + quote(PYTHON) + ' -u finish_study.py --bundle "$run_root" --output ' + quote(common_remote + '-results') + '\n'
    stages.append({'name': 'compare', 'command': command, 'cpus_per_task': 5, 'mem_gb': 8,
        'time_limit': '01:00:00', 'depends_on': [s['name'] for s in stages[1:]], 'condition': 'afterany'})
    arguments = {'name': 'quality-luna-20261027', 'arch': 'x64cpu',
        'spack_packages': ['/fmrcj5jrubquulzxeqmhucxqunhodrxp'], 'stages': stages}
    atomic_json(STUDY / 'pipeline-arguments.json', arguments)
    print(json.dumps({'checks': checks, 'uploads': len(rows) + 1, 'pipeline': str(STUDY / 'pipeline-arguments.json')}))


if __name__ == '__main__':
    main()
