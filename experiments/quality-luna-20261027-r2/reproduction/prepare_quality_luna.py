"""Prepare a fresh, bounded Luna Max pilot without touching the Forest engine."""
from __future__ import annotations

import importlib.util
import json
import shutil
import tarfile
import uuid
from pathlib import Path

from hpc_forest.core import atomic_json, file_digest

REPO = Path('C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1')
TASK = Path('C:/Users/nicol/Documents/Codex/2026-10-23/ce-que-je-voudrais-que-tu')
OLD = REPO / 'experiments/controlled-advisor-20261026'
STUDY = REPO / 'experiments/quality-luna-20261027'
WORK = TASK / 'work/quality-luna-20261027'
BASE = '/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260'
PYTHON = BASE + '/worker-venv/bin/python'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def manifest(root):
    return {p.relative_to(root).as_posix(): file_digest(p) for p in sorted(root.rglob('*')) if p.is_file()}


def archive(root, destination):
    with tarfile.open(destination, 'w:gz') as stream:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                stream.add(path, arcname=path.relative_to(root).as_posix(), recursive=False)


def change(path, before, after):
    source = path.read_text(encoding='utf8')
    if before not in source:
        raise ValueError('Expected script fragment missing: ' + str(path))
    path.write_text(source.replace(before, after), encoding='utf8')


def main():
    STUDY.mkdir(exist_ok=False)
    WORK.mkdir(exist_ok=False)
    for name in ('inputs', 'plans', 'reproduction'):
        shutil.copytree(OLD / name, STUDY / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copyfile(OLD / 'heldout-protocol.json', STUDY / 'heldout-protocol.json')
    runtime = read(TASK / 'work/controlled-advisor-20261026/tabpfn-runtime.json')
    conditions = {name: {'enabled': enabled, 'context_scope': 'tree',
                         'validation_policy': 'runtime_calibrated_v2'}
                  for name, enabled in [('off', False), ('corrected', True)]}
    protocol = read(OLD / 'protocol.json')
    for case in protocol['cases']:
        case['seeds'] = [307]
    protocol.update(schema='forest-quality-luna-pilot-v1', conditions=conditions,
        orders=[list(conditions)], common_initial_plan='Frozen Luna-authored plans from the controlled study; no earlier candidates or adviser examples imported',
        data_factor='94 pre-generation features including per-configuration measured parent evidence; only current tree and current campaign',
        validation_factor='runtime_calibrated_v2: child-minus-parent log1p measured speedup; chronological unseen-parent validation and empirical error margin; preflight before model load',
        material_limits='Four independent five-CPU allocations; same final codes remeasured sequentially together on one allocation. Shared nodes are not exclusive.',
        source_study='controlled-advisor-20261026',
        engine_scope='Current corrected engine in both conditions; this pilot isolates enabling its corrected adviser, not individual architecture changes',
        analysis={'replicates_per_problem_condition': 1, 'searches': 4,
            'contrasts': ['corrected/off'], 'aggregation': 'per-problem paired speedup ratios, all assigned arms retained',
            'failures': 'Report infrastructure failures and nondeliveries; no silent replacement',
            'scope': 'One pair per case is a functional pilot, not a reliable estimate of superiority'},
        engine_files=manifest(REPO / 'src/hpc_forest'),
        local_validation='docs/VALIDATION-QUALITE-20261027.md')
    protocol['engine_files'] = {k: v for k, v in protocol['engine_files'].items() if '__pycache__' not in k and not k.endswith('.pyc')}
    atomic_json(STUDY / 'protocol.json', protocol)

    scripts = STUDY / 'reproduction'
    change(scripts / 'run_block.py', 'Five-condition controlled study', 'Two-condition quality pilot')
    change(scripts / 'finish_study.py', 'afterany of all six search blocks', 'afterany of all four independent search blocks')
    change(scripts / 'analyze_controlled.py',
        "CONTRASTS = [('current', 'off'), ('data', 'current'), ('validation', 'current'),\n             ('both', 'validation'), ('both', 'data'), ('both', 'off')]",
        "CONTRASTS = [('corrected', 'off')]")
    change(scripts / 'analyze_controlled.py', 'Three searches per condition/problem; no universal superiority claim.',
           'One search per condition/problem: functional pilot only, no superiority inference.')
    change(scripts / 'analyze_controlled.py', 'both/off is an additional descriptive contrast.',
           'Both conditions use the same corrected engine; only the adviser enable flag differs.')
    audit = scripts / 'audit_advice.py'
    change(audit, 'if sample["target"] != sample["measured_score"] - sample["parent_score"]:',
        'runtime = sample.get("target_kind") == "child_minus_parent_log1p_speedup"\n'
        '        measured_key, parent_key = ("measured_value", "parent_value") if runtime else ("measured_score", "parent_score")\n'
        '        if sample["target"] != sample[measured_key] - sample[parent_key]:')
    change(audit, '"decision_guard": d.get("decision_guard"),',
        '"decision_guard": d.get("decision_guard"), "preflight_reason": d.get("preflight_reason"),\n'
        '               "prediction_target": d.get("prediction_target"),')
    change(audit, 'validation.get("mae_child_score", validation.get("mae_score_gain"))',
           'validation.get("mae_child_value", validation.get("mae_child_score", validation.get("mae_score_gain")))')
    change(audit, 'predicted = d["expected_child_scores"][index]',
        'runtime = d.get("validation_policy") == "runtime_calibrated_v2"\n'
        '                predicted = d["expected_child_values" if runtime else "expected_child_scores"][index]')
    change(audit, 'actual = sample["measured_score"]', 'actual = sample["measured_value" if runtime else "measured_score"]')
    for before, after in [('predicted_child_score', 'predicted_child_value'),
                          ('observed_child_score', 'observed_child_value'),
                          ('validation_mae_score_gain', 'validation_mae_child_value')]:
        change(audit, before, after)

    # The historical preparer is used only to package protected inputs and current
    # source. Its unrelated old initialization path is never called.
    spec = importlib.util.spec_from_file_location('quality_prepare', scripts / 'prepare.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CONDITIONS = conditions
    paired = module.prepare(STUDY, WORK / 'paired-staging', runtime, BASE, 'search')
    rows = []
    for pair in paired:
        original = Path(pair['archive']).parent / 'payload'
        for arm in pair['arms']:
            identity = f"quality-luna-20261027-{pair['case']}-{arm['condition']}-" + uuid.uuid4().hex[:8]
            payload = WORK / identity / 'payload'
            shutil.copytree(original, payload)
            remote = BASE + '/' + identity
            plan = {k: v for k, v in pair.items() if k not in {'archive', 'sha256', 'remote_archive'}}
            plan.update(scope='forest-quality-luna-20261027', pair_id=identity, arms=[arm], remote_root=remote)
            atomic_json(payload / 'pair.json', plan)
            cfg = read(payload / 'settings.json')
            cfg['codex']['mailbox_dir'] = remote + '/unused'
            cfg['advisor'].update(conditions['off'])
            atomic_json(payload / 'settings.json', cfg)
            files = manifest(payload)
            files.pop('files.json')
            atomic_json(payload / 'files.json', files)
            packed = payload.parent / 'payload.tar.gz'
            archive(payload, packed)
            row = {**plan, 'archive': str(packed), 'sha256': file_digest(packed), 'remote_archive': remote + '.tar.gz'}
            atomic_json(payload.parent / 'preparation.json', row)
            rows.append(row)
    atomic_json(WORK / 'preparations.json', rows)
    atomic_json(STUDY / 'assigned-arms.json', rows)

    common = WORK / 'common'
    common.mkdir()
    for path in scripts.glob('*.py'):
        shutil.copyfile(path, common / path.name)
    for name in ('protocol.json', 'heldout-protocol.json'):
        shutil.copyfile(STUDY / name, common / name)
    shutil.copytree(REPO / 'src/hpc_forest', common / 'engine/src/hpc_forest',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    atomic_json(common / 'blocks.json', rows)
    atomic_json(common / 'runtime.json', runtime)
    atomic_json(WORK / 'common-location.json', {'local': str(common), 'remote': BASE + '/quality-common-20261027-' + uuid.uuid4().hex[:8]})
    print(json.dumps({'study': str(STUDY), 'searches': len(rows), 'conditions': conditions}))


if __name__ == '__main__':
    main()
