"""Independent, read-only audit of the frozen live campaign and its final receipts."""
import hashlib
import json
import re
import sqlite3
import statistics
import time
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

from local_status import status

HERE = Path(__file__).resolve().parent
STATE = json.loads((HERE / 'state.json').read_text())
ART = Path(STATE['artifact'])
EVIDENCE = HERE / 'evidence'

def read(path):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    live = status()
    result = read(EVIDENCE / 'results.json')
    final = bool(result)
    checks = []

    def check(name, value, detail=None, pending=False):
        record = {'name': name, 'status': 'pending' if pending else 'pass' if value else 'fail'}
        if detail is not None:
            record['detail'] = detail
        checks.append(record)

    plan = read(ART / 'plan.json')
    settings = read(ART / 'settings.json')
    plan.update(budget=settings['budget'], binary_tree=settings['binary_tree'],
        historical_candidates_imported=plan['old_candidates_imported'])
    check('only_ab_mcts_a', plan.get('binary_tree') == {'enabled': False}
          and (result or read(EVIDENCE / 'progress.json')).get('search_policy') == 'ab-mcts-a',
          pending=not final and not read(EVIDENCE / 'progress.json'))
    check('duration_1800_seconds', plan.get('wall_seconds') == 1800)
    check('unlimited_tokens', plan.get('token_budget') is None and plan['budget'].get('tokens') is None
          and plan['budget'].get('mission_tokens') is None and plan['completion'].get('postprocess_tokens') is None
          and plan['completion'].get('token_policy') == 'observe-only')
    check('adaptive_reserve_and_finish_started', plan['completion'].get('reserve_policy') == 'adaptive'
          and plan['completion'].get('policy') == 'finish-started')
    check('persistent_mother_requested', plan.get('forest') == {'policy': 'mother', 'conversation': 'persistent', 'integration': 'pairwise'})
    check('no_historical_program_import', plan.get('historical_candidates_imported') is False)
    local_checks = read(HERE.parent / 'independent-fixes-20261021-b50004dd/verification.json')
    check('core_686_tests_and_ruff_passed',
          local_checks.get('pytest') == {'tests': 686, 'failures': 0, 'errors': 0, 'skipped': 0}
          and local_checks.get('ruff') == 'passed')
    check('tested_runtime_unchanged_at_local_validation', local_checks.get('tested_sources_unchanged') is True)
    provenance = read(HERE/'tested-core-provenance.json')
    check('shipped_engine_matches_686_tested_sources',provenance.get('all_match') is True
          and provenance.get('tested_files') == 97)

    native = []
    for call in live['calls']:
        directory = ART / 'worker' / call['nonce']
        request = read(directory / 'downloaded-request.json')
        invocation = read(directory / 'invocation.json')
        response = read(directory / 'response.json')
        delivered = read(directory / 'delivered.json')
        request_sha = sha(directory / 'downloaded-request.json')
        events = []
        path = directory / 'codex.jsonl'
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
        turns = [e['usage'] for e in events if e.get('type') == 'turn.completed']
        observed = sum(u['input_tokens'] + u['output_tokens'] for u in turns)
        usage = response.get('usage') or {}
        completed = bool(response and delivered)
        identity_ok = all(request.get(k) == v for k, v in {
            'session_id': STATE['session_id'], 'model': STATE['model'], 'reasoning_effort': STATE['effort']}.items())
        invocation_ok = bool(invocation) and invocation.get('request_sha256') == request_sha
        if invocation:
            identity_ok &= invocation.get('model') == STATE['model'] and invocation.get('reasoning_effort') == STATE['effort']
        checks_ok = identity_ok and invocation_ok
        no_limits = (request.get('token_ceiling') is None and request.get('token_policy') == 'observe-only'
                     and request.get('expires_at') is None and request.get('deadline_policy') == 'finish-started')
        exact_ok = (usage.get('token_accounting') == 'exact' and bool(turns)
                    and usage.get('tokens') == observed and usage.get('llm_calls') == len(turns))
        integrity_ok = (usage.get('codex_jsonl_sha256') == sha(path) if path.exists() else False)
        if completed:
            checks_ok &= response.get('request_sha256') == request_sha and delivered.get('request_sha256') == request_sha
            checks_ok &= delivered.get('response_sha256') == sha(directory / 'response.json')
            identity_ok &= all(response.get(k) == v for k, v in {
                'session_id': STATE['session_id'], 'model': STATE['model'], 'reasoning_effort': STATE['effort']}.items())
        native.append({**call, 'request_sha256': request_sha, 'native_observed_tokens': observed,
            'native_completed_turns': len(turns), 'model_identity_verified': bool(identity_ok),
            'request_and_response_integrity': bool(checks_ok), 'usage_exact_verified': bool(exact_ok),
            'native_log_integrity_verified': bool(integrity_ok), 'delivered': completed,
            'unlimited_request': no_limits, 'argv': invocation.get('argv', [])})
    completed = [c for c in native if c['delivered']]
    check('all_requests_luna_max', bool(native) and all(c['model_identity_verified'] for c in native))
    access = read(HERE / 'access-audit.json')
    access_calls = access.get('native_calls', [])
    check('both_mcp_servers_configured_for_all_native_invocations', bool(access_calls)
          and all(c['romeo_access_configured'] and c['documentation_access_configured'] for c in access_calls))
    delivered_nonces = {c['nonce'] for c in completed}
    completed_access = [c for c in access_calls if c['nonce'] in delivered_nonces]
    check('required_mcp_startup_succeeded_for_completed_invocations', bool(completed_access)
          and all(c['native_exit_code'] == 0 for c in completed_access), pending=not final and not completed_access)
    check('both_mcp_bindings_preserved', bool(read(ART/'worker/model-mcp.json'))
          and bool(read(ART/'worker/documentation-mcp.json')))
    check('no_forbidden_mcp_tool_call', not access.get('forbidden_calls'))
    check('native_mcp_router_enabled_without_runtime_error', bool(access_calls)
          and all(c.get('model_tool_router_enabled') for c in access_calls)
          and not access.get('model_tool_runtime_errors'))
    successful_servers = access.get('successful_mcp_use_by_server') or {}
    check('real_model_calls_to_both_mcp_servers_observed', successful_servers.get('romeo', 0) > 0
          and successful_servers.get('hpc_docs', 0) > 0, successful_servers,
          pending=not final and not all(successful_servers.get(server, 0) > 0 for server in ('romeo', 'hpc_docs')))
    assembly_access = [c for c in access_calls if c.get('phase') == 'assembly']
    check('resumed_mother_retains_both_mcp_servers', bool(assembly_access)
          and all(c['resume_retains_both_servers'] and c['romeo_access_configured']
                  and c['documentation_access_configured'] for c in assembly_access),
          pending=not final and not assembly_access)
    check('requests_without_token_or_time_ceiling', bool(native) and all(c['unlimited_request'] for c in native))
    check('native_usage_exact_and_hashes_match', bool(completed) and all(c['usage_exact_verified']
          and c['native_log_integrity_verified'] and c['request_and_response_integrity'] for c in completed),
          pending=not final and not completed)
    check('all_native_requests_delivered', len(completed) == len(native), pending=not final)
    check('no_native_response_error', all(c['response_error'] is None for c in completed))
    diagnostics = [read(ART / 'worker' / call['nonce'] / 'diagnostics-delivered.json') for call in native]
    published = sum({'codex.jsonl', 'invocation.json', 'skills-usage.json'} <= set(record.get('files', [])) for record in diagnostics)
    check('all_native_diagnostics_published_to_romeo', published == len(native),
          {'published': published, 'expected': len(native)}, pending=not bool(live['worker_finished']))

    proof = read(HERE / 'parallel-proof.json')
    check('all_n_native_processes_observed_simultaneously', proof.get('all_n_simultaneous_verified') is True,
          {'chosen_trees': proof.get('chosen_trees'), 'simultaneous_samples': proof.get('simultaneous_samples')},
          pending=not final and not proof.get('all_n_simultaneous_verified'))
    independent = read(HERE / 'independence-proof.json')
    check('different_trial_ordinals_overlap_in_native_processes',
          independent.get('mixed_ordinals_observed') is True, independent.get('first_mixed_sample'),
          pending=not final and not independent.get('mixed_ordinals_observed'))
    mothers = [c for c in native if c.get('conversation')]
    mothers.sort(key=lambda c: c['conversation']['turn'])
    planning = [c for c in mothers if c['conversation']['phase'] == 'planning']
    assembly = [c for c in mothers if c['conversation']['phase'] == 'assembly']
    check('mother_planning_only_once', len(planning) == 1)
    conversation_ok = bool(assembly and planning)
    previous = None
    for index, call in enumerate(mothers):
        request = call['conversation']
        receipt = call.get('conversation_receipt') or {}
        conversation_ok &= request.get('turn') == index
        if index == 0:
            conversation_ok &= request.get('thread_id') is None and request.get('previous_request_sha256') is None
        else:
            conversation_ok &= (request.get('id') == previous.get('id')
                and request.get('thread_id') == previous.get('thread_id')
                and request.get('previous_request_sha256') == previous.get('request_sha256'))
            argv = call['argv']
            resume_index = argv.index('resume') if 'resume' in argv else -1
            conversation_ok &= resume_index >= 0 and argv[resume_index + 1] == previous.get('thread_id')
        conversation_ok &= (receipt.get('id') == request.get('id') and receipt.get('turn') == index
            and receipt.get('request_sha256') == call['request_sha256']
            and call['native_thread_ids'] == [receipt.get('thread_id')]
            and '--ephemeral' not in call['argv'] and '--last' not in call['argv'])
        previous = receipt
    check('mother_resumes_original_native_conversation', conversation_ok, pending=not final and not all(c['delivered'] for c in assembly) or not assembly and not final)
    assembly_schemas_ok = bool(assembly)
    for call in assembly:
        request = read(ART / 'worker' / call['nonce'] / 'downloaded-request.json')
        properties = request['schema'].get('properties', {})
        assembly_schemas_ok &= ('files' in properties and 'children' not in properties
                               and 'features.multi_agent=false' in call['argv'])
    check('mother_assembly_uses_code_schema_and_subagents_disabled', assembly_schemas_ok, pending=not bool(assembly) and not final)
    research = [c for c in native if re.fullmatch(r'T[1-9][0-9]*', c['role'])]
    no_restart = bool(assembly) and max((c['claimed_at'] for c in research), default=0) < min(c['claimed_at'] for c in assembly)
    check('no_research_native_invocation_after_mother_assembly', no_restart, pending=not final)

    database = None
    zip_manifest = None
    if final and (EVIDENCE / 'registry.sqlite3').exists():
        with sqlite3.connect((EVIDENCE / 'registry.sqlite3').as_uri() + '?mode=ro&immutable=1', uri=True) as con:
            con.row_factory = sqlite3.Row
            check('terminal_sqlite_integrity', con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
            meta = {r['key']: json.loads(r['value']) for r in con.execute('SELECT * FROM metadata')}
            rows = [dict(r) for r in con.execute('SELECT * FROM trials ORDER BY created,id')]
            evaluations = [dict(r) for r in con.execute('SELECT * FROM evaluations ORDER BY created,id')]
            for row in rows:
                row['mission'] = json.loads(row['mission'])
                row['result'] = json.loads(row['result']) if row['result'] else None
                row.pop('before_state', None)
            for row in evaluations:
                row['payload'] = json.loads(row['payload'])
            trees = [dict(r) for r in con.execute('SELECT id,epoch,role,sha256,version,stopped FROM trees')]
            slots = [dict(r) for r in con.execute('SELECT * FROM slots ORDER BY created,id')]
            scheduler = meta.get('research_scheduler:1') or {}
            check('independent_scheduler_used', scheduler.get('policy') == 'independent-v1'
                  and scheduler.get('one_pending_trial_per_tree') is True)
            closed = meta.get('search_closed:1')
            started = meta.get('mother_assembly_started:1')
            research_rows = [r for r in rows if re.fullmatch(r'T[1-9][0-9]*', r['role'])]
            check('registry_search_closed_before_assembly', isinstance(closed, (float, int))
                  and isinstance(started, (float, int)) and closed <= started)
            check('no_research_trial_after_permanent_closure', bool(closed and started and research_rows)
                  and all(r['created'] < closed <= started for r in research_rows))
            research_roles = {child['role'] for child in live['forest']['children']}
            check('same_n_research_trees_persist_across_waves', bool(research_rows)
                  and {r['role'] for r in research_rows} == research_roles
                  and all(len({r['tree_id'] for r in research_rows if r['role'] == role}) == 1 for role in research_roles)
                  and all(r['epoch'] == 1 for r in research_rows)
                  and all(len([t for t in trees if t['role'] == role]) == 1 for role in research_roles))
            check('real_treequest_0_3_2', bool(trees) and all('0.3.2' in t['version'] for t in trees), trees)
            database = {'metadata': meta, 'trials': rows, 'evaluations': evaluations, 'trees': trees, 'slots': slots}
        costs = result.get('costs', {})
        check('controller_matches_reported_native_counters', costs.get('exact_tokens_used') == sum(c['native_observed_tokens'] for c in completed)
              and costs.get('tokens_used') == costs.get('exact_tokens_used') and costs.get('unknown_usage_calls') == 0
              and costs.get('bounded_usage_calls') == 0 and costs.get('tokens_reserved') == 0)
        post = result.get('postprocess') or {}
        confirmation = result.get('final_g_confirmation') or {}
        outcome = confirmation.get('outcome') or {}
        final_evals = [r for r in evaluations if r['experiment_id'] == confirmation.get('experiment_id') and r['phase'] == 'confirmation']
        check('final_g_and_mother_assembly_complete', post.get('status') == 'complete'
              and (post.get('mother') or {}).get('status') == 'complete')
        check('final_g_independently_confirmed', confirmation.get('status') == 'confirmed' and outcome.get('correct') is True
              and confirmation.get('experiment_id') == post.get('mission_id')
              and outcome.get('commit') == (post.get('outcome') or {}).get('commit')
              and len(final_evals) == 1 and final_evals[0]['payload'] == outcome)
        expected_repetitions = meta['config']['protocol']['confirmation_repetitions']
        times = outcome.get('times') or []
        check('final_g_has_five_fresh_confirmation_samples', expected_repetitions == 5 and len(times) == expected_repetitions
              and all(isinstance(t, (float, int)) and t > 0 for t in times)
              and abs(statistics.mean(times) - outcome.get('mean_seconds', -1)) < 1e-12,
              {'samples_seconds': times, 'mean_seconds': outcome.get('mean_seconds'), 'expected_repetitions': expected_repetitions})
        check('pipeline_complete_and_no_error', result.get('pipeline_complete') is True and not result.get('error'))
    else:
        for label in ('registry_search_closed_before_assembly', 'no_research_trial_after_permanent_closure',
                      'same_n_research_trees_persist_across_waves', 'real_treequest_0_3_2', 'controller_matches_reported_native_counters',
                      'final_g_and_mother_assembly_complete', 'final_g_independently_confirmed',
                      'final_g_has_five_fresh_confirmation_samples', 'pipeline_complete_and_no_error'):
            check(label, False, pending=True)

    manifest = read(ART / 'runtime-manifest.json')
    changed = [name for name, expected in manifest.items()
               if not (ART / 'payload' / name).exists() or sha(ART / 'payload' / name) != expected]
    check('all_frozen_runtime_sources_unchanged', len(manifest) >= 80 and not changed, changed)
    if (EVIDENCE / 'runtime-manifest.json').exists():
        check('remote_runtime_manifest_matches', sha(EVIDENCE / 'runtime-manifest.json') == STATE['runtime_manifest_sha256'])
    if (EVIDENCE / 'gpu-preflight.json').exists():
        gpu = read(EVIDENCE/'gpu-preflight.json')
        phases = gpu.get('phases') or {}
        check('gpu_original_matches_cpu_oracle_on_two_independent_phases', gpu.get('passed') is True
              and set(phases) == {'search','confirmation'}
              and all(p.get('cases') == 11 for p in phases.values())
              and phases['search']['seed'] != phases['confirmation']['seed'])
    check('protected_cuda_protocol_unchanged',
          sha(ART / 'payload/validation/protocol.py') == sha(HERE.parent / 'cuda-nbody-campaign-20261021/protocol.py'))
    exported = EVIDENCE/'submission.zip'
    if exported.exists():
        with zipfile.ZipFile(exported) as archive:
            check('zip_integrity', archive.testzip() is None)
            zip_manifest = json.loads(archive.read('HPC_FOREST_MANIFEST.json'))
            check('zip_embeds_exact_final_g_confirmation', zip_manifest.get('final_g_confirmation') == result.get('final_g_confirmation')
                  and zip_manifest.get('mother_conversation') == result.get('mother_conversation'))
            check('zip_embeds_confirmed_selected_program', zip_manifest.get('commit') == (result.get('best_confirmed') or {}).get('commit'))
    if final:
        source_receipt = read(HERE / 'G-final-source-receipt.json')
        check('native_g_proposal_matches_exact_confirmed_commit',
              source_receipt.get('all_proposed_sources_match_confirmed_git_commit') is True
              and source_receipt.get('experiment_id') == (result.get('postprocess') or {}).get('mission_id')
              and source_receipt.get('confirmed_commit') == ((result.get('final_g_confirmation') or {}).get('outcome') or {}).get('commit'),
              pending=not bool(source_receipt))
    totals = Counter(c['status'] for c in checks)
    output = {'job_id': STATE['job_id'], 'observed_at': time.time(), 'terminal_results_available': final,
        'checks': checks, 'counts': dict(totals), 'native_call_count': len(native), 'native_delivered': len(completed),
        'native_reported_tokens_sum': sum(c['native_observed_tokens'] for c in completed),
        'token_counter_caveat': 'Raw Mother resume counters are cumulative; do not sum them as unique consumed tokens.',
        'native_diagnostics_published': published,
        'calls_by_role': dict(Counter(c['role'] for c in native)), 'native_calls': native,
        'mother_conversation': mothers, 'parallel_proof': proof, 'database': database, 'zip_manifest': zip_manifest}
    (HERE / 'audit.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: output[k] for k in ('job_id', 'terminal_results_available', 'counts', 'native_call_count',
                                          'native_delivered', 'native_reported_tokens_sum', 'calls_by_role')}))
    print(json.dumps({'failed': [c for c in checks if c['status'] == 'fail']}))
    return output

if __name__ == '__main__':
    audit()
