"""Real TabPFN plumbing replay, isolated from every new search campaign."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from hpc_forest.core import atomic_json, digest


def qualify(bundle, output):
    output.mkdir(parents=True, exist_ok=False)
    records = []
    for path in sorted((bundle / 'qualification-inputs').glob('*.json')):
        original = json.loads(path.read_text(encoding='utf8'))
        for scope in ('campaign', 'tree'):
            for policy in ('gain_rank_v2', 'decision_calibrated_v1'):
                request = {**original, 'context_scope': scope, 'validation_policy': policy}
                if scope == 'tree':
                    request['context'] = [e for e in original['context']
                                          if e['role'] == original['candidates'][0]['role']]
                directory = output / (path.stem + '-' + scope + '-' + policy)
                atomic_json(directory / 'request.json', request)
                with (directory / 'worker.log').open('wb') as log:
                    result = subprocess.run([sys.executable, '-m', 'hpc_forest.advisor_worker',
                        str(directory / 'request.json'), str(directory / 'response.json')],
                        stdout=log, stderr=subprocess.STDOUT, timeout=120)
                response = json.loads((directory / 'response.json').read_text(encoding='utf8'))
                valid = (result.returncode == 0 and response.get('request_sha256') == digest(request)
                         and response.get('status') in {'validated', 'validation_rejected'})
                records.append({'case': path.stem, 'context_scope': scope, 'validation_policy': policy,
                    'context_size': len(request['context']), 'status': response.get('status'),
                    'reason': response.get('validation', {}).get('reason'), 'contract_passed': valid})
    atomic_json(output / 'qualification.json', {'records': records,
        'historical_replay_only': True, 'imported_into_new_searches': False,
        'predictive_benefit_established': False})
    print(json.dumps(records), flush=True)
    return 0 if len(records) == 8 and all(r['contract_passed'] for r in records) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(qualify(args.bundle.resolve(), args.output.resolve()))
