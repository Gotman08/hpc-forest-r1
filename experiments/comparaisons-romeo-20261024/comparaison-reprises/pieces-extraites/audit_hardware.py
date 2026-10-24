"""Compare recorded hardware snapshots, without treating idle clocks as run telemetry."""
import datetime
import hashlib
import json
import re
from pathlib import Path

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/comparaison-reprises'
OLD = R.parent / 'reference-study'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def field(text, name):
    match = re.search(r'^\s*' + re.escape(name) + r'\s*:\s*(.*?)\s*$', text, re.M)
    return match.group(1) if match else None


def section_field(text, section, name):
    match = re.search(r'^    ' + re.escape(section) + r'\s*\n(.*?)(?=^    \S|\Z)', text, re.M | re.S)
    return field(match.group(1), name) if match else None


def snapshot(path):
    d = read(path)
    cpu, gpu = d['cpu'], d.get('gpu', '')
    result = {
        'file': path.name, 'file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'job': d['job'], 'snapshot_unix_seconds': d['start'],
        'cpu': {key: field(cpu, key) for key in ['Architecture', 'Model name', 'CPU(s)',
                'Thread(s) per core', 'Core(s) per socket', 'Socket(s)', 'NUMA node(s)']},
        'allocated_affinity': d.get('affinity'),
        'compiler_version_output': d['compiler'],
        'driver_sha256': d.get('driver_sha256'),
        'timing_driver_sha256': d.get('timing_driver_sha256'),
        'additional_check_driver_sha256': d.get('additional_check_driver_sha256'),
        'scene_sha256': d.get('scene_sha256'),
    }
    if gpu:
        result['gpu'] = {key: field(gpu, key) for key in ['Product Name', 'Product Architecture',
            'GPU UUID', 'Driver Version', 'CUDA Version', 'Performance State', 'GPU Current Temp']}
        result['gpu']['framebuffer_total'] = section_field(gpu, 'FB Memory Usage', 'Total')
        result['gpu']['gpu_power_limit'] = section_field(gpu, 'GPU Power Readings', 'Current Power Limit')
        result['gpu']['module_power_limit'] = section_field(gpu, 'Module Power Readings', 'Current Power Limit')
        result['gpu']['snapshot_sm_clock'] = section_field(gpu, 'Clocks', 'SM')
    return result


mapping = [
    ('paired-cpu', 'cpu-final-environment.json'),
    ('paired-cpu-base64', 'cpu-final-environment.json'),
    ('paired-extra', 'extra-final-environment.json'),
    ('paired-cpu-blackscholes-stability', 'cpu-final-environment.json'),
    *[('paired-render-' + case, 'render-' + case + '-final-environment.json')
      for case in ['aobench', 'deferred', 'raytracer', 'volume']],
]
rows = []
for stem, old_file in mapping:
    previous = snapshot(OLD / old_file)
    current = snapshot(R / (stem + '-environment.json'))
    cases = read(R / (stem + '-transfer.json'))['keys']
    comparisons = {
        'cpu_model_same': previous['cpu']['Model name'] == current['cpu']['Model name'],
        'cpu_architecture_same': previous['cpu']['Architecture'] == current['cpu']['Architecture'],
        'smt_same': previous['cpu']['Thread(s) per core'] == current['cpu']['Thread(s) per core'],
        'compiler_version_output_same': previous['compiler_version_output'] == current['compiler_version_output'],
    }
    if 'gpu' in current:
        for key in ['Product Name', 'GPU UUID', 'Driver Version', 'framebuffer_total', 'module_power_limit']:
            comparisons['gpu_' + key + '_same'] = previous['gpu'].get(key) == current['gpu'].get(key)
    for key in ['driver_sha256', 'timing_driver_sha256', 'additional_check_driver_sha256', 'scene_sha256']:
        if previous.get(key) is not None and current.get(key) is not None:
            comparisons[key + '_same'] = previous[key] == current[key]
    rows.append({'group': stem, 'cases': cases, 'previous': previous, 'current': current,
                 'comparisons': comparisons})

result = {
    'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'allocations': rows,
    'scope': [
        'Old and new selected programs are both rerun within each current allocation.',
        'Node CPU counts describe installed hardware, not the CPU count allocated to a benchmark.',
        'GPU snapshots are observations at job start, not continuous measurement of clocks or throttling.',
        'No node reboot, global cache flush, fixed clock setting or exclusive physical node is claimed.',
        'Reported nvidia-smi CUDA Version describes driver compatibility; compiler_version_output records the actual toolkit.',
        'Published hardware remains documentary metadata in RESULTATS.json; no theoretical FLOPS normalization is applied.',
    ],
}
(O / 'AUDIT-MATERIEL.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf8')
print(json.dumps([{'group': r['group'], 'previous_job': r['previous']['job'],
                  'current_job': r['current']['job'], 'comparisons': r['comparisons']} for r in rows]))
