"""Pre-register six families and input splits without changing Forest or candidates."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
REPO = STUDY.parents[1]
TASK = Path('C:/Users/nicol/Documents/Codex/2026-10-23/ce-que-je-voudrais-que-tu')
WORK = TASK / 'work/diversified-advisor-20261026'
OLD = REPO / 'experiments/control-recovery-20261026'
HIST = TASK / 'work/reference-rerun/campaigns'
SUITE = '/scratch_p/nimarano/forest-reference-cpu-suite-20261023'
SPECS = [
    ('base64', 137, 1, [16384, 262144], [32768, 524288], [4, 8, 64, 1024]),
    ('argmin', 149, 1, [4093, 65536], [8191, 131072], [1, 2, 17, 8192]),
    ('popcount', 163, 1, [257, 2048], [509, 4096], [1, 17, 1000]),
    ('gemm_cpu', 179, 4, [384, 768], [513, 1025], [1, 17, 32, 128]),
    ('stencil3d', 191, 4, [96, 160], [121, 192], [16, 24, 32]),
    ('blackscholes', 211, 4, [32768, 262144], [65537, 524288], [1, 16, 128, 1024]),
]
DESCRIPTIONS = {
    'base64': 'Decode valid standard padded Base64 bytes from input1 (n bytes). Write the decoded byte count as uint64 at byte offset 0 and the exact decoded bytes starting at offset 16; bytes 8..15 are reserved.',
    'argmin': 'For n signed int32 input1 elements, write the index of the first minimum as int32. Ties must return the smallest index. Inputs include random, descending, equal and extreme integer values.',
    'popcount': 'Preserve the supplied recurrence: start a uint32 accumulator at zero, iterate parameter passes over n uint32 input1 values, and add the population count of input1[i] XOR the current accumulator at each step, with uint32 wraparound. Write the final uint32 accumulator. parameter=100.',
    'gemm_cpu': 'Compute row-major FP32 C=A@B for n by n matrices input1=A and input2=B, completely overwriting output C on every invocation. Inputs contain signed values. Match the independent FP64 oracle within .002+5e-5*abs(reference). No external BLAS calls.',
    'stencil3d': 'Compute the supplied six time steps of the 3D finite-difference stencil. input1 contains n^3 FP32 initial even-grid values; input2 contains n^3 vsq values. Output contains both n^3 buffers (even then odd), initialized as in the baseline. Coefficients [.5,-.25,.125,-.0625], interior [4,n-4) on all axes. Preserve boundaries. Tolerance 5e-5+5e-5*abs(reference).',
    'blackscholes': 'Compute the supplied FP32 Black-Scholes implementation including its CND approximation. input1 contains five consecutive arrays of length n: S,X,T,r,v; output contains n floats. Tolerance .001+5e-5*abs(reference). Timed inputs vary per element; also preserve behavior for constant inputs.',
}
NAIVE = {
    'argmin': 'ab32d82af4b8f30380f36379054d8256875599a46aa666b645e25e1dfc119a8f',
    'popcount': '22c92360e7e0dbc9381a1df3a3c5c8acc1236d4025789f523cef3bb421f5ce17',
}


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if (STUDY / 'protocol.json').exists():
        raise RuntimeError('The input registration is immutable; do not overwrite it')
    engine = read(TASK / 'work/control-recovery-20261026/validation-archive-v5.json')['source_hashes']
    if any(digest(REPO / name) != sha for name, sha in engine.items()):
        raise RuntimeError('Forest differs from the validated frozen engine')
    template = OLD / 'inputs/utf8'
    common_statement = read(template / 'settings.json')['forest']['statement'].split('Edit only src/candidate.cpp.', 1)[1]
    protocol_text = (template / 'validation/protocol.py').read_text(encoding='utf8')
    protocol_text = protocol_text.replace("seed=271 if phase=='confirmation' else 23", "seed=C['data_seeds']['confirmation' if phase=='confirmation' else 'search']")
    protocol_text = protocol_text.replace("specs=[(n,t,seed+101,0) for n,t in perf]", "specs=[(n,t,seed+101,C.get('performance_pattern',0)) for n,t in perf]")
    cases, heldout = [], {}
    for index, (name, seed, threads, sizes, reserved, checks) in enumerate(SPECS):
        target = STUDY / 'inputs' / name
        original = HIST / name / 'payload' if name not in NAIVE else template
        shutil.copytree(original, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        case = read(original / 'validation/case.json')
        if name in NAIVE:
            case = {'id': name, 'kind': name, 'suite': SUITE, 'trusted_files': {
                key: value for key, value in case['trusted_files'].items() if not key.startswith('cases/')}}
            case['trusted_files'][f'cases/{name}/naive.so'] = NAIVE[name]
            shutil.copyfile(WORK / (name + '-naive.cpp'), target / 'source/src/candidate.cpp')
        regimes = [1] if threads == 1 else [1, threads]
        case.update(n=sizes[-1], threads=threads, checks=checks, parameter=100 if name == 'popcount' else 0,
            performance=[[n, t] for n in sizes for t in regimes], performance_pattern=1,
            data_seeds={'search': 1103, 'confirmation': 3209})
        # Larger historical thread counts are not part of this new CPU protocol.
        case.pop('max_threads', None)
        statement = ('Optimize the supplied baseline on AMD EPYC 9654 with GCC 14.2.\n' + DESCRIPTIONS[name]
            + f'\nTimed sizes: {sizes}; timed thread budgets: {regimes}. Use the supplied public contract for all valid input sizes.\n'
            + 'Edit only src/candidate.cpp.' + common_statement)
        cfg = read(template / 'settings.json')
        cfg['problem'] = 'diversified-' + name
        cfg['forest']['statement'] = statement
        write(target / 'settings.json', cfg)
        (target / 'statement.txt').write_text(statement, encoding='utf8')
        (target / 'validation/protocol.py').write_text(protocol_text, encoding='utf8')
        (target / 'source/run.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\nexec "${FOREST_PYTHON:-python3}" "${FOREST_REFERENCE_SUITE:?}/cpu_driver.py" '
            + f'{name} ./build/solution {sizes[0]} 1204 {threads} bench 1\n', encoding='utf8')
        write(target / 'validation/case.json', case)
        heldout[name] = {**case, 'n': reserved[-1], 'performance': [[n, t] for n in reserved for t in regimes],
            'checks': sorted(set(checks + reserved)), 'data_seeds': {'search': 7867, 'confirmation': 7867}}
        files = {p.relative_to(target).as_posix(): digest(p) for p in sorted(target.rglob('*')) if p.is_file()}
        order = ['advisor_off', 'advisor_on'] if index % 2 == 0 else ['advisor_on', 'advisor_off']
        cases.append({'case': name, 'seed': seed, 'orders': order, 'source_origin': str(original),
            'files': files, 'program_threads': threads, 'allocation_cpus': threads+1,
            'performance': case['performance'], 'performance_pattern': 1})
    registration = read(OLD / 'protocol.json')
    for key in ('jobs', 'changed_control', 'previous_study', 'prior_cohort', 'protocol_change', 'comparisons'):
        registration.pop(key, None)
    registration.update(schema='forest-diversified-advisor-v1', status='registered_before_submission',
        registered_at=datetime.now(UTC).isoformat(), results=[], cases=cases, seeds='one predeclared seed per case',
        orders='alternating across cases; see each case', engine_source_hashes=engine,
        engine_validation='control-recovery-20261026: 1095 passed, 2 skipped',
        scope='six additional CPU families; one paired comparison each; twelve autonomous arms',
        primary_metric='confirmed_speedup_on_registered_search_distribution_within_cap',
        secondary_holdout='same immutable delivered commit, reserved shapes and seeds, no reselection or feedback',
        common_remeasurement='All six pairs completed before sequential common and reserved-input remeasurement.',
        pilot_gate='Naive protocol preflight only; no optimized-result selection or manual candidate help.',
        not_a_superiority_test='One replicate per family cannot estimate per-family search variance or universal superiority.',
        historical_overlap='These families exist in the project reference suite; novel for this TabPFN comparison, not proven unseen by Forest or foundation models.')
    write(STUDY / 'heldout-protocol.json', heldout)
    registration['heldout_protocol_sha256'] = digest(STUDY / 'heldout-protocol.json')
    write(STUDY / 'protocol.json', registration)
    print(json.dumps({'cases': [c['case'] for c in cases], 'protocol_sha256': digest(STUDY / 'protocol.json'),
                      'engine_files_verified': len(engine), 'arms': 12}))


if __name__ == '__main__':
    main()
