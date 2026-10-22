"""Correlate concurrent native processes and measured per-tree trial identities."""
import json
import re
import sqlite3
import time
from pathlib import Path

from local_status import HERE, read, status

live = status()
result = read(HERE / 'evidence/results.json') or read(HERE / 'evidence/progress.json')
rows = result.get('trials', [])
trials = {row['id']: json.loads(row['mission']) if isinstance(row['mission'], str) else row['mission'] for row in rows}
requests = {c['nonce']: c for c in live['calls'] if re.fullmatch(r'T[1-9][0-9]*', c['role'])}
proofs = []
process_file = HERE / 'native-processes.jsonl'
for line in process_file.read_text(encoding='utf-8-sig').splitlines() if process_file.exists() else []:
    sample = json.loads(line)
    linked = []
    for process in sample.get('processes', []):
        matching = [c for nonce, c in requests.items() if nonce in process.get('command', '')]
        if len(matching) != 1:
            continue
        call = matching[0]
        mission_id = re.sub(r'-h[0-9]+$', '', call['mission_id'])
        mission = trials.get(mission_id)
        if mission:
            linked.append({'role': call['role'], 'ordinal': mission['ordinal'], 'mission_id': mission_id,
                           'nonce': call['nonce'], 'pid': process['pid']})
    if len({c['role'] for c in linked}) >= 2 and len({c['ordinal'] for c in linked}) >= 2:
        proofs.append({'observed_utc': sample['observed_utc'], 'processes': linked})

event_checks = None
database = HERE / 'evidence/registry.sqlite3'
if database.exists() and read(HERE / 'evidence/results.json'):
    with sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True) as con:
        events = [{'kind': kind, 'payload': json.loads(payload), 'created': created}
                  for kind, payload, created in con.execute('SELECT kind,payload,created FROM events WHERE kind IN (?,?) ORDER BY id',
                      ('research_node_submitted', 'research_node_settled'))]
        inflight, violations, continued = {}, [], []
        settled_counts = {}
        for event in events:
            payload, role = event['payload'], event['payload']['role']
            if event['kind'] == 'research_node_submitted':
                if role in inflight:
                    violations.append({'role': role, 'event': event})
                if settled_counts.get(role, 0) and inflight:
                    continued.append({'role': role, 'ordinal': payload['ordinal'], 'at': event['created'],
                                      'other_unsettled_roles': sorted(inflight)})
                inflight[role] = payload['experiment_id']
            else:
                if inflight.pop(role, None) != payload['experiment_id']:
                    violations.append({'role': role, 'event': event})
                settled_counts[role] = settled_counts.get(role, 0) + 1
        event_checks = {'one_pending_per_tree_verified': not violations, 'violations': violations,
                        'all_admitted_nodes_settled': not inflight,
                        'continued_while_other_trees_unsettled': continued,
                        'settled_counts': settled_counts}

receipt = {'job_id': live['job_id'], 'at': time.time(), 'mixed_ordinals_observed': bool(proofs),
           'mixed_samples': len(proofs), 'first_mixed_sample': proofs[0] if proofs else None,
           'last_mixed_sample': proofs[-1] if proofs else None, 'event_checks': event_checks,
           'meaning': 'Different trees have native model generations for different trial ordinals active simultaneously.'}
(HERE / 'independence-proof.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf8')
print(json.dumps({k: v for k, v in receipt.items() if k != 'last_mixed_sample'}))
