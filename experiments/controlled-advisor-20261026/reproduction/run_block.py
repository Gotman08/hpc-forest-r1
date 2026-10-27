"""Five-condition controlled study using the single existing Forest controller."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import signal
import subprocess
import sys
import time
import traceback
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from hpc_forest.config import load_config
from hpc_forest.controller import Controller, create_workspace
from hpc_forest.core import atomic_json, digest, file_digest
from hpc_forest.gitops import git
from hpc_forest.registry import Registry
from hpc_forest.reporting import report
from hpc_forest.support.sources import committed_source_snapshot


def storage_module():
    spec = importlib.util.spec_from_file_location('controlled_study_storage', Path(__file__).with_name('study_storage.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save_state(pair, name, value):
    storage_module().record_state(pair, name, value)


def preserve_arm(pair, arm):
    destination = os.environ.get('FOREST_PRESERVED_HOME')
    if not destination:
        return
    source = pair / ('forest-app-' + arm['id'])
    if not source.exists():
        return
    archive_root = Path(os.environ['FOREST_ARM_ARCHIVES'])
    receipt = storage_module().preserve(source,
        Path(destination) / pair.name / source.name, archive_root / (arm['id'] + '.tar.gz'),
        allowed_root=pair)
    save_state(pair, arm['id'] + '-preservation.json', receipt)
    atomic_json(pair / (arm['id'] + '-preservation.json'), receipt)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def checkpoint_archive(pair):
    """Archive block metadata; preserved arms also have verified standalone archives."""
    target = os.environ.get('FOREST_STUDY_ARCHIVE')
    if not target:
        return
    target = Path(target)
    if not target.is_absolute() or pair == target.parent or pair in target.parents:
        raise RuntimeError('Evidence archive must be outside the working directory')
    temporary = target.with_name(target.name + '.partial')
    subprocess.run(['tar', '-czf', str(temporary), '-C', str(pair), '.'], check=True, timeout=300)
    os.replace(temporary, target)


def evaluator_class(inputs):
    spec = importlib.util.spec_from_file_location('protected_benchmark', inputs / 'benchmark_evaluator.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BenchmarkEvaluator


def control(root):
    import hpc_forest.controller as controller_module
    import hpc_forest.node_harness as harness_module
    launch = read(root / 'launch.json')
    evaluator = evaluator_class(Path(launch['inputs']))
    # All five conditions use the same protected metric and evaluator adapter.
    controller_module.create_evaluator = evaluator
    harness_module.create_evaluator = evaluator
    done = {'pipeline_complete': False, 'session_id': launch['session_id']}
    frozen = None
    if not launch.get('planning_only'):
        from frozen_planning import install
        frozen = read(Path(launch['frozen_plan']))
        if file_digest(Path(launch['frozen_plan'])) != launch['frozen_plan_file_sha256']:
            raise RuntimeError('Frozen initial plan file changed')
        install(frozen)
    try:
        with Controller(root / 'campaign') as forest:
            if launch.get('planning_only'):
                from hpc_forest.mother import prepare_forest
                forest._start()
                epoch = forest.epoch()
                selected = prepare_forest(forest, epoch, forest._baseline(epoch))
                initial = forest.db.get(f"mother_plan:preparation:{epoch['id']}")
                review = forest.db.get(f"mother_plan_review:{epoch['id']}", {})
                authored = review.get('result', initial)
                plan_record = {'schema': 'forest-frozen-mother-plan-v1', 'plan': authored['plan'],
                    'plan_sha256': digest(authored['plan']), 'planning_receipt': authored['conversation'],
                    'planning_session_id': launch['session_id'], 'case': launch['case'],
                    'model': 'gpt-6-luna', 'effort': 'max', 'operator_algorithm_hints': False,
                    'source_plan_sha256': selected['plan_sha256'], 'planning_only': True,
                    'research_trials': len(forest.db.rows('SELECT id FROM trials'))}
                if plan_record['research_trials']:
                    raise RuntimeError('Shared planning imported research')
                atomic_json(root.parent / 'frozen-plan.json', plan_record)
                done.update(pipeline_complete=True, planning_only=True, plan_record=plan_record)
                return 0
            forest.run(on_progress=lambda value: atomic_json(root / 'progress.json', value))
            selected = forest.db.get('forest_plan:1', {})
            if selected.get('plan_sha256') != frozen['plan_sha256']:
                raise RuntimeError('Initial plan mismatch')
            if selected['conversation']['thread_id'] == frozen['planning_receipt']['thread_id']:
                raise RuntimeError('Planning conversation must not be shared')
            done.update(initial_plan_sha256=selected['plan_sha256'],
                        initial_mother_thread_id=selected['conversation']['thread_id'])
            best = forest.confirm()
            state = forest.status()
            report(root / 'campaign')
            if (state.get('postprocess', {}).get('status') != 'complete'
                    or state.get('final_g_confirmation', {}).get('status') not in {'confirmed', 'rejected'}):
                raise RuntimeError('Incomplete final assembly or confirmation')
            for name, content in committed_source_snapshot(root / 'campaign/repo', best['commit']).items():
                target = root / 'confirmed-code' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding='utf8')
            done.update(pipeline_complete=True, best_confirmed=best, final_state=state,
                        search_started=forest.db.get('started'), finished_at=time.time())
            forest.db.set('pipeline_finished:1', done['finished_at'])
        return 0
    except Exception as exc:
        done.update(error_type=type(exc).__name__, error=str(exc))
        traceback.print_exc()
        return 1
    finally:
        save_state(root.parent, launch['id'] + '-done.json', done)
        atomic_json(root / 'done.json', done)
        atomic_json(root / 'campaign/mailbox/DONE.json', done)


def run_arm(pair, plan, arm, cpus):
    from hpc_forest.codex_mailbox import initialize_channel
    root = pair / ('forest-app-' + arm['id'])
    root.mkdir()
    started = time.time()
    inputs = pair / 'inputs'
    config = load_config(pair / 'settings.json')
    config['advisor'].update(arm['advisor'])
    charged = 0.0 if arm.get('planning_only') else read(pair / 'frozen-plan.json')['charged_planning_seconds']
    cap = plan['cap_seconds'] - charged
    config['budget']['wall_seconds'] = plan['target_seconds'] - charged
    if not arm.get('planning_only'):
        config['forest']['plan_review_calls'] = 0  # The shared plan was already reviewed once.
    if cap <= 0 or config['budget']['wall_seconds'] <= 0:
        raise RuntimeError('Common planning exhausted the registered budget')
    config['codex'].update(session_id=arm['session_id'], mailbox_dir=str(root / 'campaign/mailbox'))
    config['target_id'] = 'romeo-tabpfn-' + plan['pair_id']
    create_workspace(root / 'campaign', config, inputs / 'source', inputs / 'validation')
    with closing(Registry(root / 'campaign/registry.sqlite3')) as db:
        if db.rows('SELECT id FROM trials'):
            raise RuntimeError('An experiment must start without previous trials')
        # Remove the initialization documentation seed; no earlier result is imported.
        with db.connection:
            db.connection.execute('DELETE FROM documents')
        atomic_json(root / 'fresh-memory.json', {'trials': 0, 'documents': 0,
                    'advisor_samples': 0, 'session_id': arm['session_id'], 'imported_candidates': False})
    launch = {**arm, 'session_id': arm['session_id'], 'model': 'gpt-6-luna', 'effort': 'max',
              'generator_pool': [], 'inputs': str(inputs), 'codex': plan['codex'],
              'scope': plan['scope'], 'pair_id': plan['pair_id'], 'case': plan['case'],
              'frozen_plan': str(pair / 'frozen-plan.json'),
              'frozen_plan_file_sha256': plan.get('frozen_plan_file_sha256')}
    atomic_json(root / 'launch.json', launch)
    initialize_channel(root / 'campaign/mailbox', arm['session_id'], os.environ['SLURM_JOB_ID'],
                       model=launch['model'], effort=launch['effort'])
    atomic_json(root / 'authorization.json', {'schema': 'forest-app-authorization-v1',
        'mission_id': arm['id'], 'session_id': arm['session_id'], 'next_model': launch['model'],
        'reasoning_effort': launch['effort'], 'generator_pool': [],
        'expires_at': started + cap, 'manifest_sha256': file_digest(root / 'launch.json'),
        'completion': {'policy': 'finish-started', 'token_policy': 'observe-only'}})
    processes, streams = [], []
    result = {'condition': arm['condition'], 'id': arm['id'], 'started_at': started,
              'target_seconds': plan['target_seconds'], 'cap_seconds': plan['cap_seconds'],
              'model': launch['model'], 'effort': launch['effort'], 'pc_relay': False}
    try:
        for role, affinity, command in (
            ('worker', str(cpus[-1]), ['-m', 'hpc_forest.webapp.remote_runner', str(root), '--role', 'worker']),
            ('controller', ','.join(map(str, cpus[:-1])), [str(Path(__file__)), '--control', str(root)]),
        ):
            stream = (root / (role + '.log')).open('wb')
            streams.append(stream)
            processes.append(subprocess.Popen(['taskset', '-c', affinity, sys.executable, '-u', *command],
                stdout=stream, stderr=subprocess.STDOUT, start_new_session=True))
        next_progress = 0.0
        while processes[1].poll() is None:
            if time.monotonic() >= next_progress:
                progress = read(root / 'progress.json') if (root / 'progress.json').exists() else {}
                snapshot = {'block': plan['pair_id'], 'condition': arm['condition'],
                    'elapsed_seconds': time.time() - started, 'status': progress.get('status', 'preparation'),
                    'costs': progress.get('costs'), 'advisor': progress.get('advisor')}
                save_state(pair, 'progress.json', snapshot)
                print(json.dumps(snapshot), flush=True)
                storage = storage_module().guard(pair)
                if storage:
                    save_state(pair, 'storage.json', storage)
                next_progress = time.monotonic() + 60
            if processes[0].poll() is not None:
                raise RuntimeError('Native Luna worker stopped')
            if time.time() - started >= cap:
                raise TimeoutError('Common end-to-end budget reached')
            time.sleep(1)
        processes[0].wait(timeout=min(60, max(1, cap - (time.time() - started))))
        result.update(exit_codes=[p.returncode for p in processes], **read(root / 'done.json'))
    except Exception as exc:
        result.update(pipeline_complete=False, error_type=type(exc).__name__, error=str(exc))
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        for stream in streams:
            stream.close()
        result['elapsed_seconds'] = time.time() - started
        result['charged_planning_seconds'] = charged
        result['charged_elapsed_seconds'] = result['elapsed_seconds'] + charged
        result['finished_within_cap'] = result['charged_elapsed_seconds'] <= plan['cap_seconds']
        save_state(pair, arm['id'] + '-result.json', result)
        atomic_json(root / 'arm-result.json', result)
    return result


def remeasure(pair, plan, results):
    config = load_config(pair / 'settings.json')
    config['target_id'] = 'romeo-tabpfn-' + plan['pair_id']
    config['advisor']['enabled'] = False
    root = create_workspace(pair / 'remeasure', config, pair / 'inputs/source', pair / 'inputs/validation')
    candidates = [{'id': 'naive', 'worktree': str(root / 'repo'), 'commit': git(root / 'repo', 'rev-parse', 'HEAD'), 'baseline': True}]
    for result in results:
        if not result.get('pipeline_complete') or not result.get('finished_within_cap'):
            continue
        arm_root = pair / ('forest-app-' + result['id'])
        commit = result['best_confirmed']['commit']
        worktree = arm_root / 'remeasure-source'
        git(arm_root / 'campaign/repo', 'worktree', 'add', '--detach', str(worktree), commit)
        candidates.append({'id': result['condition'], 'worktree': str(worktree), 'commit': commit})
    with closing(Registry(root / 'registry.sqlite3')) as db:
        evaluator = evaluator_class(pair / 'inputs')(root, db.get('config'), db.get('manifest'), db.get('protocol_id'), None)
        measured = {key: asdict(value) for key, value in evaluator.confirm(candidates, 1).items()}
    naive = measured['naive']
    for outcome in measured.values():
        outcome['speedup'] = (naive['mean_seconds'] / outcome['mean_seconds']
            if naive['status'] == outcome['status'] == 'valid' and outcome['correct'] else None)
    atomic_json(pair / 'paired-measurements.json', {'outcomes': measured, 'candidates': candidates,
                'same_allocation': True, 'separate_from_search_rewards': True})


def main(pair):
    plan = read(pair / 'pair.json')
    cpus = sorted(os.sched_getaffinity(0))
    if (not os.environ.get('SLURM_JOB_ID', '').isdigit() or len(cpus) != plan['cpus']
            or platform.machine() != 'x86_64'):
        raise RuntimeError('Expected CPU allocation and affinity are required')
    for name, sha in read(pair / 'files.json').items():
        if file_digest(pair / name) != sha:
            raise RuntimeError('Frozen pair input changed: ' + name)
    runtime = read(pair / 'settings.json')['advisor_runtime']
    if file_digest(Path(runtime['model_path'])) != runtime['model_sha256']:
        raise RuntimeError('Pinned TabPFN checkpoint is unavailable')
    auth = subprocess.run([plan['codex'], 'login', 'status'], capture_output=True, text=True, timeout=30)
    if auth.returncode or 'Logged in using ChatGPT' not in auth.stdout + auth.stderr:
        raise RuntimeError('Native ROMEO OAuth is unavailable')
    atomic_json(pair / 'allocation.json', {'job_id': os.environ['SLURM_JOB_ID'], 'host': platform.node(),
                'affinity': cpus, 'machine': platform.machine(), 'model': 'gpt-6-luna', 'effort': 'max',
                'pc_relay': False, 'files_manifest_sha256': file_digest(pair / 'files.json')})
    results = []
    for arm in plan['arms']:
        storage = storage_module().guard(pair, start=True)
        if storage:
            save_state(pair, 'storage.json', storage)
        try:
            result = run_arm(pair, plan, arm, cpus)
        except Exception as exc:
            result = {'id': arm['id'], 'condition': arm['condition'], 'pipeline_complete': False,
                'finished_within_cap': False, 'error_type': type(exc).__name__, 'error': str(exc)}
            save_state(pair, arm['id'] + '-result.json', result)
            traceback.print_exc()
        results.append(result)
        save_state(pair, 'pair-results.json', results)
        atomic_json(pair / 'pair-results.json', results)
        preserve_arm(pair, arm)
        checkpoint_archive(pair)
    if plan.get('planning_only'):
        if results[0].get('pipeline_complete'):
            frozen = read(pair / 'frozen-plan.json')
            frozen['charged_planning_seconds'] = results[0]['elapsed_seconds']
            frozen['allocation'] = read(pair / 'allocation.json')
            atomic_json(pair / 'frozen-plan.json', frozen)
    else:
        threads = [r.get('initial_mother_thread_id') for r in results if r.get('pipeline_complete')]
        if len(threads) != len(set(threads)):
            raise RuntimeError('Arms shared a Mother conversation')
        remeasure(pair, plan, results)
    checkpoint_archive(pair)
    return 0 if all(r.get('pipeline_complete') for r in results) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pair', type=Path)
    parser.add_argument('--control', type=Path)
    args = parser.parse_args()
    raise SystemExit(control(args.control.resolve()) if args.control else main(args.pair.resolve()))
