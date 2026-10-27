"""Freeze the preregistered factorial study; never select plans from outcomes."""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import tarfile
import uuid
from pathlib import Path

from hpc_forest.advisor import DEFAULT
from hpc_forest.config import load_config, validate
from hpc_forest.core import atomic_json, digest, file_digest
from hpc_forest.model_skills import policy

CONDITIONS = {
    'off': {'enabled': False, 'context_scope': 'campaign', 'validation_policy': 'gain_rank_v2'},
    'current': {'enabled': True, 'context_scope': 'campaign', 'validation_policy': 'gain_rank_v2'},
    'data': {'enabled': True, 'context_scope': 'tree', 'validation_policy': 'gain_rank_v2'},
    'validation': {'enabled': True, 'context_scope': 'campaign', 'validation_policy': 'decision_calibrated_v1'},
    'both': {'enabled': True, 'context_scope': 'tree', 'validation_policy': 'decision_calibrated_v1'},
}


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def manifest(root):
    return {p.relative_to(root).as_posix(): file_digest(p) for p in sorted(root.rglob('*')) if p.is_file()}


def initialize(study):
    previous = study.parent / 'diversified-advisor-20261026'
    cases = []
    reserved = {}
    for case, directory, sizes in [('gemm_cpu', 'gemm_cpu_v2', [449, 897]),
                                    ('blackscholes', 'blackscholes', [49153, 393217])]:
        inputs = study / 'inputs' / case
        inputs.mkdir(parents=True, exist_ok=False)
        source = previous / 'inputs' / directory
        for name in ('source', 'validation'):
            shutil.copytree(source / name, inputs / name)
        for name in ('settings.json', 'statement.txt', 'benchmark_evaluator.py'):
            shutil.copyfile(source / name, inputs / name)
        public = read(inputs / 'validation/case.json')
        public['data_seeds'] = {'search': 4409, 'confirmation': 5501}
        atomic_json(inputs / 'validation/case.json', public)
        hidden = copy.deepcopy(public)
        hidden.update(n=sizes[-1], checks=sorted(set(public['checks'] + sizes)),
                      performance=[[n, t] for n in sizes for t in (1, 4)],
                      data_seeds={'search': 8669, 'confirmation': 8669})
        reserved[case] = hidden
        cases.append({'case': case, 'files': manifest(inputs), 'seeds': [307, 401, 503]})
    # Different positions across blocks reduce order effects; the schedule is fixed
    # before any optimization. It does not perfectly balance all 5 positions at n=3.
    orders = [list(CONDITIONS), ['data', 'both', 'off', 'validation', 'current'],
              ['validation', 'current', 'both', 'data', 'off']]
    record = {'schema': 'forest-controlled-advisor-v1', 'status': 'registered_before_search',
        'model': 'gpt-6-luna', 'effort': 'max', 'generator_pool': [],
        'conditions': CONDITIONS, 'cases': cases, 'orders': orders,
        'search_target_seconds_per_arm': 5400, 'end_to_end_cap_seconds_per_arm': 7200,
        'common_planning_cap_seconds': 1200, 'allocation_cpus': 5,
        'common_initial_plan': 'one newly authored and reviewed Luna plan per problem, shared across all 15 searches',
        'shared_plan_cost': 'full planning elapsed time charged equally to every arm',
        'planning_acknowledgement': 'real first native turn, exact JSON equality checked before dispatch',
        'initial_plan_review': '2 common planning reviews; no arm-specific initial revision',
        'later_mother': 'unrestricted normal active steering, recorded as mediator',
        'fresh_database_and_llm_sessions': True, 'cross_campaign_training': False,
        'operator_algorithm_hints': False, 'pc_relay': False,
        'data_factor': 'filter context to selected role in current epoch before deduplication/128-row cap; same features and gain target',
        'validation_factor': 'chronological same-tree heldout, disjoint parent hashes, 3 independent parents, 3 child-value pairs, rank > .5, MAE below zero-gain baseline; decision margin max(.005,2*MAE); no clipped ties',
        'validation_not_claimed': 'empirical margin is not a confidence bound; holdout is observational, not counterfactual regret',
        'search_policy': {'algorithm': 'ab-mcts-a', 'distribution': 'gaussian'},
        'primary_metric': 'final confirmed speedup on common registered distribution, delivered within charged cap',
        'secondary_metrics': ['reserved-input correctness and speedup', 'measured best at common search checkpoints',
            'mother branch/suspend/integrate/close choices', 'adviser activation and rejected reasons',
            'accepted forecast error', 'total calls and time', 'failures and non-deliveries'],
        'analysis': {'replicates_per_problem_condition': 3, 'searches': 30,
            'contrasts': ['current/off', 'data/current', 'validation/current', 'both/validation', 'both/data'],
            'aggregation': 'paired log speedup ratios by problem and seed; show all runs, median and range',
            'failures': 'report all assigned arms; no silent replacement or exclusion from delivery rates',
            'scope': 'small controlled study conditional on two frozen Mother plans, not universal superiority'},
        'reserved_inputs_visible_to_models': False,
        'material_limits': 'same allocation within block; shared node possible; all final codes remeasured together after searches'}
    atomic_json(study / 'heldout-protocol.json', reserved)
    record['reserved_protocol_sha256'] = file_digest(study / 'heldout-protocol.json')
    atomic_json(study / 'protocol.json', record)
    return record


def prepare(study, output, runtime, remote_base, phase, case_filter=None):
    protocol = read(study / 'protocol.json')
    repository = study.parents[1]
    output.mkdir(parents=True, exist_ok=False)
    prepared = []
    for case_index, case in enumerate(protocol['cases']):
        if case_filter and case['case'] != case_filter:
            continue
        repeats = [(0, 607)] if phase == 'plan' else list(enumerate(case['seeds'], 1))
        for repeat, seed in repeats:
            block_id = f"{case['case']}-{phase}-r{repeat}-" + uuid.uuid4().hex[:10]
            folder = output / block_id
            payload = folder / 'payload'
            payload.mkdir(parents=True)
            inputs = study / 'inputs' / case['case']
            if manifest(inputs) != case['files']:
                raise RuntimeError('Registered inputs changed')
            shutil.copytree(inputs, payload / 'inputs')
            shutil.copytree(repository / 'src/hpc_forest', payload / 'engine/src/hpc_forest',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            for name in ('run_block.py', 'frozen_planning.py', 'study_storage.py'):
                shutil.copyfile(study / 'reproduction' / name, payload / name)
            remote = remote_base.rstrip('/') + '/controlled-advisor-' + block_id
            config = load_config(inputs / 'settings.json')
            config['codex'].update(model='gpt-6-luna', reasoning_effort='max', generator_pool=[],
                executable=remote_base.rstrip('/') + '/runtime/bin/codex', mailbox_dir=remote + '/unused')
            config['search'] = protocol['search_policy']
            config['forest']['active'] = {'mode': 'full', 'code_analysis': True, 'closure_guards': True}
            config['skills'] = policy()
            config['harness']['research']['enabled'] = False
            config['budget']['wall_seconds'] = protocol['search_target_seconds_per_arm']
            config['seed'] = seed
            config['advisor'] = {**DEFAULT, 'enabled': False}
            config['advisor_runtime'] = runtime
            config['evolution'] = {'enabled': False}
            validate(config)
            atomic_json(payload / 'settings.json', config)
            if phase == 'plan':
                arms = [{'id': uuid.uuid4().hex, 'session_id': uuid.uuid4().hex,
                         'condition': 'shared_planning', 'planning_only': True, 'advisor': CONDITIONS['off']}]
            else:
                frozen_path = study / 'plans' / (case['case'] + '.json')
                frozen = read(frozen_path)
                if (frozen['model'] != 'gpt-6-luna' or frozen['effort'] != 'max'
                        or frozen['research_trials'] != 0 or frozen['case'] != case['case']
                        or frozen['plan_sha256'] != digest(frozen['plan'])):
                    raise RuntimeError('Unverified common plan')
                shutil.copyfile(frozen_path, payload / 'frozen-plan.json')
                order = protocol['orders'][repeat - 1]
                if case_index:
                    order = list(reversed(order))
                arms = [{'id': uuid.uuid4().hex, 'session_id': uuid.uuid4().hex,
                         'condition': condition, 'advisor': CONDITIONS[condition]} for condition in order]
            plan = {'scope': 'forest-controlled-advisor-20261026', 'pair_id': block_id,
                'case': case['case'], 'repeat': repeat, 'seed': seed, 'arms': arms,
                'cpus': 5, 'codex': config['codex']['executable'],
                'target_seconds': protocol['search_target_seconds_per_arm'],
                'cap_seconds': protocol['common_planning_cap_seconds'] if phase == 'plan'
                    else protocol['end_to_end_cap_seconds_per_arm'], 'remote_root': remote,
                'planning_only': phase == 'plan', 'protected_inputs': case['files'],
                'protocol_sha256': file_digest(study / 'protocol.json'),
                'frozen_plan_file_sha256': file_digest(payload / 'frozen-plan.json') if phase != 'plan' else None,
                'operator_algorithm_hints': False, 'model': 'gpt-6-luna', 'effort': 'max'}
            atomic_json(payload / 'pair.json', plan)
            atomic_json(payload / 'files.json', manifest(payload))
            archive = folder / 'payload.tar.gz'
            with tarfile.open(archive, 'w:gz') as stream:
                for path in sorted(payload.rglob('*')):
                    if path.is_file():
                        stream.add(path, arcname=path.relative_to(payload).as_posix(), recursive=False)
            row = {**plan, 'archive': str(archive), 'sha256': file_digest(archive),
                   'remote_archive': remote + '.tar.gz'}
            atomic_json(folder / 'preparation.json', row)
            prepared.append(row)
    atomic_json(output / 'preparations.json', prepared)
    return prepared


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--initialize', action='store_true')
    parser.add_argument('--phase', choices=['plan', 'search'])
    parser.add_argument('--case', choices=['gemm_cpu', 'blackscholes'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--remote-base')
    args = parser.parse_args()
    if args.initialize:
        record = initialize(args.study.resolve())
        print(json.dumps({'searches': record['analysis']['searches'], 'conditions': list(CONDITIONS)}))
    else:
        rows = prepare(args.study.resolve(), args.output.resolve(), read(args.runtime), args.remote_base, args.phase, args.case)
        print(json.dumps([{'block': row['pair_id'], 'remote': row['remote_root'], 'sha256': row['sha256']} for row in rows]))
