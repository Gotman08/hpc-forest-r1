"""Check frozen sources, resource parity and separation of reserved inputs."""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preparations', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    study = Path(__file__).resolve().parents[1]
    protocol, reserved = read(study / 'protocol.json'), read(study / 'heldout-protocol.json')
    pairs = read(args.preparations)
    if len(pairs) != 6 or len({p['case'] for p in pairs}) != 6:
        raise ValueError('Expected six distinct preregistered pairs')
    rows = []
    for pair in pairs:
        root = Path(pair['archive']).parent / 'payload'
        cfg = read(root / 'settings.json')
        case = read(root / 'inputs/validation/case.json')
        expected = next(c for c in protocol['cases'] if c['case'] == pair['case'])
        amendment = study / 'protocol-amendment-gemm.json'
        if pair['case'] == 'gemm_cpu' and amendment.exists():
            expected = read(amendment)['cases'][0]
        if (cfg['codex']['model'] != 'gpt-6-luna' or cfg['codex']['reasoning_effort'] != 'max'
                or cfg['codex']['generator_pool'] or cfg['evolution']['enabled']
                or cfg['budget']['wall_seconds'] != 5400 or pair['cap_seconds'] != 7200
                or pair['cpus'] != case['threads'] + 1 or pair['seed'] != expected['seed']
                or [a['condition'] for a in pair['arms']] != expected['orders']):
            raise ValueError('Configuration differs from registration')
        if pair['protected_inputs'] != expected['files']:
            raise ValueError('Pair does not match the registered input version')
        for name, sha in expected['files'].items():
            if hashlib.sha256((root / 'inputs' / name).read_bytes()).hexdigest() != sha:
                raise ValueError('Frozen problem input changed: ' + name)
        for name, sha in protocol['engine_source_hashes'].items():
            if hashlib.sha256((root / 'engine' / name).read_bytes()).hexdigest() != sha:
                raise ValueError('Engine changed: ' + name)
        if ({n for n, _ in case['performance']} & {n for n, _ in reserved[pair['case']]['performance']}
                or set(case['data_seeds'].values()) & set(reserved[pair['case']]['data_seeds'].values())
                or (root / 'heldout-protocol.json').exists()):
            raise ValueError('Reserved inputs overlap or were supplied to research payload')
        rows.append({'case': pair['case'], 'source_hashes_verified': len(protocol['engine_source_hashes']),
                     'reserved_shapes_and_seeds_disjoint': True, 'configured_model': 'gpt-6-luna',
                     'effort': 'max', 'cpus': pair['cpus'], 'sha256': pair['sha256']})
    if sum(p['arms'][0]['enabled'] for p in pairs) != 3:
        raise ValueError('Condition order must be balanced across cases')
    args.output.write_text(json.dumps({'passed': True, 'pairs': rows}, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'pairs_verified': len(rows), 'engine_files_per_pair': len(protocol['engine_source_hashes'])}))


if __name__ == '__main__':
    main()
