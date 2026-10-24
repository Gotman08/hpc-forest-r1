"""Export observed SLURM reservations separately from application elapsed times."""
import csv
import json
from pathlib import Path

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/architecture-active'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    data = read(O / 'RESULTATS.json')
    selections = read(R / 'main-selections.json')
    rows = {}

    def add(path, scope, condition, case=None, expected_job=None, value=None):
        if not path.exists():
            return
        value = read(path) if value is None else value
        if not value.get('found'):
            return
        job = str(value['job_id'])
        if expected_job is not None:
            assert job == str(expected_job), (path, job, expected_job)
        row = {'job_id': job, 'scope': scope, 'condition': condition,
               'case_id': case, 'state': value.get('state'),
               'elapsed_seconds': value.get('elapsed_seconds'),
               'allocated_cpus': value.get('alloc_cpus'),
               'allocated_gpus': value.get('alloc_gpus'),
               'cpu_seconds_used': value.get('cpu_seconds_used'),
               'cpu_seconds_reserved': value.get('cpu_seconds_reserved'),
               'gpu_seconds_reserved': value['elapsed_seconds'] * value['alloc_gpus']
                    if value.get('elapsed_seconds') is not None and value.get('alloc_gpus') is not None else None,
               'cpu_efficiency_percent': value.get('cpu_efficiency_pct'),
               'max_rss_mb': value.get('max_rss_mb'), 'requested_memory_mb': value.get('req_mem_mb'),
               'memory_efficiency_percent': value.get('mem_efficiency_pct'),
               'evidence': str(path),
               'warning': 'Reserved GPU-seconds do not measure GPU utilization. CPU utilization alone does not measure GPU efficiency. Parallel allocations do not sum to wall time.'}
        if job in rows:
            assert rows[job] == row, (job, scope)
        rows[job] = row

    historical = {}
    def efficiency_records(value):
        if isinstance(value, dict):
            if value.get('found') and 'job_id' in value and 'elapsed_seconds' in value:
                yield value
            else:
                for child in value.values():
                    yield from efficiency_records(child)
        elif isinstance(value, list):
            for child in value:
                yield from efficiency_records(child)
    for root in [R.parent / 'reference-study', R.parent / 'reference-rerun']:
        for path in sorted(root.glob('job-efficiency*.json')):
            for value in efficiency_records(read(path)):
                job = str(value['job_id'])
                previous = historical.get(job)
                if previous is None or (value.get('elapsed_seconds') or 0) >= (previous[1].get('elapsed_seconds') or 0):
                    historical[job] = (path, value)
    missing_historical = []
    for engine in data['engines']:
        if engine['period'] == 'old':
            record = historical.get(str(engine['job_id']))
            if record:
                path, value = record
                add(path, 'historical_search', engine['case_id'], engine['case_id'], engine['job_id'], value)
            else:
                missing_historical.append({'case_id': engine['case_id'], 'job_id': engine['job_id']})
    for folder in sorted((R / 'campaigns').iterdir()):
        if (folder / 'plan.json').exists():
            plan = read(folder / 'plan.json')
            scope = 'active_search_selected' if selections[plan['case_id']] == folder.name else 'active_search_failed'
            add(folder / 'efficiency.json', scope, folder.name, plan['case_id'])
    for version in ['active-architecture-20261024', 'active-architecture-20261024-v2',
                    'active-architecture-20261024-v3', 'active-architecture-20261024-v4',
                    'active-architecture-20261024-v5']:
        for folder in sorted((R.parent / version / 'campaigns').glob('*')):
            add(folder / 'efficiency.json', 'pilot_or_interrupted', version + '/' + folder.name)
    for path in sorted(R.glob('paired-*-efficiency.json')):
        add(path, 'paired_measurements', path.name.removesuffix('-efficiency.json'))
    for path in sorted((R.parent / 'comparison-validation-20261024').glob('paired-*-efficiency.json')):
        add(path, 'paired_measurement_validation', path.name.removesuffix('-efficiency.json'))
    add(R / 'cuda-runtime-check-efficiency.json', 'runtime_validation', 'cuda-library-path')

    records = sorted(rows.values(), key=lambda row: (row['scope'], row['job_id']))
    with (O / 'RESSOURCES-SLURM.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]) if records else ['job_id'])
        writer.writeheader()
        writer.writerows(records)
    summary = {}
    for scope in sorted({r['scope'] for r in records}):
        group = [r for r in records if r['scope'] == scope]
        summary[scope] = {'jobs': len(group)}
        for field in ['elapsed_seconds', 'cpu_seconds_used', 'cpu_seconds_reserved', 'gpu_seconds_reserved']:
            summary[scope][field + '_known_sum'] = sum(r[field] for r in group if r[field] is not None)
            summary[scope][field + '_unknown_jobs'] = sum(r[field] is None for r in group)
    result = {'scopes': summary, 'records': records, 'missing_historical_evidence': missing_historical,
              'warning': 'Resources are observations from job_efficiency. Separate scopes; do not interpret allocated resources as actual GPU work or add concurrent elapsed times as wall time.'}
    (O / 'RESSOURCES-SLURM.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'scopes': summary, 'missing_historical_evidence': missing_historical}))


if __name__ == '__main__':
    main()
