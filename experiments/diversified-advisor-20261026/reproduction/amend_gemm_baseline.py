"""Repair unsupported naive GEMM sizes before any optimization in this case."""
import copy
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

study = Path(__file__).resolve().parents[1]
original = study / 'inputs/gemm_cpu'
target = study / 'inputs/gemm_cpu_v2'
shutil.copytree(original, target)
source = target / 'source/src/candidate.cpp'
text = source.read_text(encoding='utf8')
needle = 'else if(n==32)mm<32>((const float*)input1,(const float*)input2,(float*)output);}'
if text.count(needle) != 1:
    raise RuntimeError('Unexpected historical GEMM wrapper')
replacement = '''else if(n==32)mm<32>((const float*)input1,(const float*)input2,(float*)output);
else {
    // Same naive r,c,k accumulation for sizes outside the historical instantiations.
    const float* A = (const float*)input1;
    const float* B = (const float*)input2;
    float* C = (float*)output;
    for (int r=0; r<n; ++r)
        for (int c=0; c<n; ++c)
            for (int k=0; k<n; ++k)
                C[r*n+c] += A[r*n+k] * B[k*n+c];
}}
'''
source.write_text(text.replace(needle, replacement), encoding='utf8')
original_protocol = study / 'protocol.json'
protocol = json.loads(original_protocol.read_text(encoding='utf8'))
case = copy.deepcopy(next(c for c in protocol['cases'] if c['case'] == 'gemm_cpu'))
case['input_directory'] = 'gemm_cpu_v2'
case['files'] = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(target.rglob('*')) if p.is_file()}
protocol['cases'] = [case]
protocol['amendment'] = {
    'registered_at': datetime.now(UTC).isoformat(),
    'parent_protocol_sha256': hashlib.sha256(original_protocol.read_bytes()).hexdigest(),
    'failed_preflight_job': '784719',
    'optimization_arms_started': 0,
    'reason': 'Historical naive wrapper computes only n=32,128,1024; all other sizes return zeros.',
    'change': 'Same naive r,c,k accumulation added for other n; old instantiations preserved.',
    'unchanged': ['Forest engine', 'LLM', 'budgets', 'order', 'data', 'checks', 'oracle', 'tolerances', 'heldout registration'],
    'not_comparable_to_published_baseline_timing': True,
}
protocol['status'] = 'amended_before_gemm_optimization'
(study / 'protocol-amendment-gemm.json').write_text(json.dumps(protocol, indent=2) + '\n', encoding='utf8')
print(json.dumps(protocol['amendment']))
