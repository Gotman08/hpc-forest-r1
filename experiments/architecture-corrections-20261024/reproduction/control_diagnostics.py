"""Summarize rejected native control references without copying conversations."""
import json
from pathlib import Path

R = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def main():
    records = []
    for case, alias in read(R / 'main-selections.json').items():
        directory = R / 'campaigns' / alias
        active_file = next((directory / 'results').glob(
            'results-*/reference-' + case + '/report/active-architecture.json'))
        active = read(active_file)
        native = [(path, read(path))
                  for path in (directory / 'worker').glob('*/request.json')]
        for job in active['jobs']:
            if job['kind'] != 'mother' or job['status'] != 'unavailable':
                continue
            payload = json.loads(job['calls'][0]['request']['messages'][1]['content'])
            visible = set(job['visible_ids'])
            entry = {'case_id': case, 'control_job_id': job['id'],
                     'error': job.get('error'), 'expected_snapshot_id': job['snapshot_id'],
                     'expected_plan_revision': payload['plan_revision'], 'attempts': []}
            for request_path, request in native:
                if not request.get('mission_id', '').startswith(job['id'] + '-call-'):
                    continue
                response_path = request_path.with_name('response.json')
                if not response_path.exists():
                    continue
                data = read(response_path).get('data') or {}
                unknown = []
                for action in data.get('decisions', []):
                    for item in action.get('hypothesis_review', []):
                        for reference in sorted(set(item.get('evidence_ids', [])) - visible):
                            unknown.append({'report_id': item.get('report_id'),
                                'index': item.get('index'), 'evidence_id': reference,
                                'present_in_payload_sections': [key for key, value in payload.items()
                                    if reference in json.dumps(value)]})
                entry['attempts'].append({'slot_id': request_path.parent.name,
                    'response_snapshot_id': data.get('snapshot_id'),
                    'response_plan_revision': data.get('plan_revision'),
                    'hypothesis_references_outside_visible_ids': unknown})
            records.append(entry)
    (R / 'control-diagnostics.json').write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps({'unavailable_mother_jobs': len(records),
                      'native_attempts': sum(len(r['attempts']) for r in records)}))


if __name__ == '__main__':
    main()
