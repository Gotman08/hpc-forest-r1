"""Read preserved evidence; distinguish real measurements from control/model calls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import tarfile
from collections import Counter
from pathlib import Path


def audit(archive_path, database_path):
    with sqlite3.connect(database_path.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        records = [(json.loads(m), json.loads(r or '{}'), created)
                   for m, r, created in db.execute('SELECT mission,result,created FROM trials ORDER BY created,id')]
        metadata = {k: json.loads(v) for k, v in db.execute('SELECT key,value FROM metadata')}
    trials = [(m, r, t) for m, r, t in records
              if m.get('budget_phase') == 'search' and m.get('kind') == 'research' and m['role'] != 'G']
    trial_ids = {m['id'] for m, _, _ in trials}
    exposures = {}
    parsed_requests = 0
    with tarfile.open(archive_path, 'r|gz') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if not member.isfile() or not name.startswith('campaign/logs/') or not name.endswith('/codex-request.json'):
                continue
            request = json.load(archive.extractfile(member))
            for message in request.get('messages', []):
                content = message.get('content', '')
                marker = '\n\nCURRENT SOURCE AS DATA:'
                if message.get('role') != 'user' or marker not in content:
                    continue
                payload = json.loads(content.split(marker, 1)[0])
                identity = payload.get('experiment')
                if identity not in trial_ids and isinstance(identity, str):
                    original, separator, turn = identity.rpartition('-h')
                    if separator and turn.isdigit() and original in trial_ids:
                        identity = original
                if identity not in trial_ids:
                    continue
                parsed_requests += 1
                context = payload.get('context_as_data', {})
                exploration = context.get('exploration_context', {})
                pages = exploration.get('source_excerpts', [])
                chars = sum(len(page['text']) for page in pages)
                if chars > 6000:
                    raise ValueError('Source excerpt bound exceeded')
                item = exposures.setdefault(identity, {'requests': 0, 'with_context': False,
                    'with_sources': False, 'max_characters': 0, 'sources': set(), 'slower_sources': set()})
                item['requests'] += 1
                item['with_context'] |= bool(exploration)
                item['with_sources'] |= bool(pages)
                item['max_characters'] = max(item['max_characters'], chars)
                item['sources'].update(page['evidence_id'] for page in pages)
                entries = context.get('diverse_measured_sources', {}).get('entries', [])
                if entries:
                    fastest = min(entry['mean_seconds'] for entry in entries)
                    item['slower_sources'].update(entry['id'] for entry in entries
                        if entry['mean_seconds'] > fastest and entry['id'] in item['sources'])
    rows = []
    for m, r, created in trials:
        exposed = exposures.get(m['id'], {})
        rows.append({'id': m['id'], 'role': m['role'], 'created': created,
            'parent_id': m.get('parent_id'), 'base_source_id': m.get('base_source_id'),
            'base_commit': m.get('base_commit'), 'depth': m.get('depth'),
            'expansion': m.get('selection', {}).get('expansion'),
            'status': r.get('status'), 'correct': r.get('correct'),
            'has_real_samples': bool(r.get('times')), 'mean_seconds': r.get('mean_seconds'),
            'source_tree_hash': r.get('tree_hash'), 'hypothesis': m.get('hypothesis'),
            'proposal_requests': exposed.get('requests', 0),
            'exploration_context_exposed': exposed.get('with_context', False),
            'source_excerpts_exposed': exposed.get('with_sources', False),
            'excerpt_characters_max': exposed.get('max_characters', 0),
            'inspiration_ids': json.dumps(sorted(exposed.get('sources', []))),
            'slower_inspiration_ids': json.dumps(sorted(exposed.get('slower_sources', [])))})
    valid = [r for r in rows if r['correct'] is True and r['has_real_samples']]
    jobs = [v for k, v in metadata.items() if k.startswith('active_control:')]
    duration = lambda kind: sum(c.get('elapsed_seconds') or 0 for j in jobs
                               if j['kind'] == kind for c in j.get('calls', []))
    summary = {'research_trials': len(rows), 'correct_measured_trials': len(valid),
        'correct_distinct_source_trees': len({r['source_tree_hash'] for r in valid if r['source_tree_hash']}),
        'status_counts': dict(Counter(r['status'] for r in rows)),
        'parent_identities': len({r['parent_id'] or r['base_commit'] for r in rows}),
        'selected_parent_ids': len({r['parent_id'] for r in rows if r['parent_id']}),
        'root_proposals': sum(not r['parent_id'] for r in rows),
        'refinement_proposals': sum(bool(r['parent_id']) for r in rows),
        'max_depth': max((r['depth'] or 0 for r in rows), default=0),
        'research_roles': len({r['role'] for r in rows}),
        'parsed_proposal_requests': parsed_requests,
        'trials_with_parsed_proposal': len(exposures),
        'trials_with_exploration_context': sum(r['exploration_context_exposed'] for r in rows),
        'trials_with_archived_source_excerpts': sum(r['source_excerpts_exposed'] for r in rows),
        'trials_with_slower_inspirations': sum(r['slower_inspiration_ids'] != '[]' for r in rows),
        'archive_enabled': metadata.get('config', {}).get('evolution', {}).get('enabled', False),
        'archive_entries': sum(k.startswith('evolution_entry:') for k in metadata),
        'analyst_calls': sum(len(j['calls']) for j in jobs if j['kind'] == 'analyst'),
        'mother_calls': sum(len(j['calls']) for j in jobs if j['kind'] == 'mother'),
        'analyst_call_seconds_sum': duration('analyst'), 'mother_call_seconds_sum': duration('mother'),
        'stop_reason': metadata.get('research_scheduler:1', {}).get('stop_reason'),
        'interpretation': 'Exact source trees and parent identities are not algorithmic strategy counts. '
            'Exposing an inspiration does not prove that the model used it. Call durations overlap research; '
            'their sums are not campaign wall time. Intermediate integrations and final assembly are excluded '
            'from research trial counts.'}
    for key in ('archive_enabled', 'research_trials'):
        if summary[key] is None:
            raise ValueError('Missing required evidence: ' + key)
    return rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('database', type=Path)
    parser.add_argument('output_prefix', type=Path)
    args = parser.parse_args()
    rows, summary = audit(args.archive, args.database)
    with args.archive.open('rb') as stream:
        archive_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    with args.database.open('rb') as stream:
        database_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with args.output_prefix.with_suffix('.csv').open('w', encoding='utf8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    result = {'archive': str(args.archive), 'archive_sha256': archive_sha,
              'database': str(args.database), 'database_sha256': database_sha, 'summary': summary}
    args.output_prefix.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
