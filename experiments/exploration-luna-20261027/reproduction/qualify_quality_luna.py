"""Synthetic runtime-contract check only; no rows enter the real searches."""
import json
import os
import platform
import time
from pathlib import Path

from hpc_forest.advisor import FEATURES, MODEL_VERSION, PACKAGE_VERSION, VERSION
from hpc_forest.advisor_validation import validation_split
from hpc_forest.advisor_value import POLICY, TARGET
from hpc_forest.advisor_worker import predict
from hpc_forest.core import atomic_json


def request(bundle):
    context = []
    for i in range(36):
        parent = 0.6931471805599453
        gain = 0.04 * (i + 1)
        features = [0.0] * len(FEATURES)
        features[0] = i + 1
        features[1] = (i + 1) * 3
        context.append({'id': 'synthetic-' + str(i), 'role': 'qualification',
            'source_sha256': format(i // 2, '064x'), 'features': features,
            'captured_at': 2 * i, 'observed_at': 2 * i + 1,
            'target': gain, 'parent_value': parent, 'measured_value': parent + gain,
            'target_kind': TARGET})
    features = [0.0] * len(FEATURES)
    features[0:2] = [37, 111]
    return {'schema': VERSION, 'feature_names': FEATURES, 'model_version': MODEL_VERSION,
        'package_version': PACKAGE_VERSION, 'validation_policy': POLICY, 'seed': 307,
        'runtime': json.loads((bundle / 'runtime.json').read_text()), 'context': context,
        'candidates': [{'id': 'synthetic-proposal', 'role': 'qualification',
            'source_sha256': 'f' * 64, 'captured_at': 100, 'parent_value': 0.6931471805599453,
            'features': features}]}


def main():
    bundle = Path(__file__).resolve().parent
    if not os.environ.get('SLURM_JOB_ID') or platform.machine() != 'x86_64':
        raise RuntimeError('Qualification requires a ROMEO CPU compute allocation')
    data = request(bundle)
    _, _, preflight = validation_split(data['context'], 'qualification', policy=POLICY)
    if preflight.get('reason'):
        raise RuntimeError('Synthetic fixture never reaches model fitting')
    started = time.monotonic()
    output = bundle / 'qualification'
    output.mkdir(exist_ok=False)
    atomic_json(output / 'request.json', data)
    response = predict(data)
    atomic_json(output / 'response.json', response)
    validation = response.get('validation', {})
    if ('mae_child_value' not in validation or validation.get('value_scale') != 'log1p_speedup'
            or response['status'] not in {'validated', 'validation_rejected'}):
        raise RuntimeError('No completed real TabPFN fit and held-out predictions')
    receipt = {'status': 'qualified', 'seconds': time.monotonic() - started,
        'job_id': os.environ['SLURM_JOB_ID'], 'host': platform.node(), 'features': len(FEATURES),
        'schema': VERSION, 'policy': POLICY, 'real_model_fit_and_prediction': True,
        'synthetic_context': True, 'import_into_search': False,
        'response_status': response['status'], 'validation_reason': validation.get('reason')}
    atomic_json(output / 'receipt.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
