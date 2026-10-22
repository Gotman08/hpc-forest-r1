"""Preserve a factual local experiment report and the exact confirmed deliveries."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text(encoding='utf8'))
state = read(HERE / 'state.json')
result = read(HERE / 'evidence/results.json')
audit = read(HERE / 'audit.json')
timing = read(HERE / 'timing-audit.json')
independent = read(HERE / 'independence-proof.json')
pairs = read(HERE / 'pairwise-audit.json')
gpu = read(HERE / 'gpu-audit.json')
access = read(HERE / 'access-audit.json')
skills = read(HERE / 'skills-audit.json')
export = read(HERE / 'export-verification.json')
worker_done = read(HERE / 'worker-finished.json')
assert result['pipeline_complete'] and gpu['all_passed'] and not worker_done['pending_diagnostics']
assert independent['mixed_ordinals_observed'] and independent['event_checks']['all_admitted_nodes_settled']
assert independent['event_checks']['one_pending_per_tree_verified']
assert not [c for c in pairs['checks'] if c['status'] != 'pass']
assert skills['all_requested_bindings_valid'] and skills['all_completed_reports_valid']
assert skills['all_invoked_effective_contents_valid'] and skills['all_completed_trace_receipts_match']
assert not [c for c in audit['checks'] if c['status'] != 'pass' and c['name'] != 'real_model_calls_to_both_mcp_servers_observed']
native_sha = hashlib.sha256((HERE / 'evidence/submission.zip').read_bytes()).hexdigest()
assert native_sha == (HERE / 'evidence/submission.zip.sha256').read_text().split()[0]
original = Path(read(Path(state['artifact']) / 'plan.json')['source_path'])
assert hashlib.sha256(original.read_bytes()).hexdigest() == state['source_sha256']

database = audit['database']
research = [r for r in database['trials'] if re.fullmatch(r'T[1-9][0-9]*', r['role'])]
trees = []
for child in result['forest_plan']['children']:
    rows = [r for r in research if r['role'] == child['role']]
    valid = [r for r in rows if r['result'].get('correct') is True and r['result'].get('times')]
    trees.append({'role': child['role'], 'subject': child['subject'], 'objective': child['objective'],
                  'trials': len(rows), 'valid_measured': len(valid),
                  'max_depth': max(r['mission']['depth'] for r in rows),
                  'max_valid_depth': max(r['mission']['depth'] for r in valid),
                  'best_search_ms': min(r['result']['mean_seconds'] for r in valid) * 1000})
final = result['final_g_confirmation']
best = result['best_confirmed']
ref = best['reference_seconds']
latest = [e['payload'] for e in timing['events'] if e['kind'] == 'adaptive_admission' and not e['payload']['inflight_roles']]
closure_reserve = latest[-1]['reserve_seconds']
next_costs = {d['pending_roles'][0]: d['next_work_seconds'] for d in latest[-3:]}
summary = {
    'job_id': state['job_id'], 'scope': state['scope'], 'pipeline_complete': True,
    'model': state['model'], 'reasoning_effort': state['effort'], 'token_limit': None,
    'search_policy': 'ab-mcts-a', 'trees': trees, 'research_trials': len(research),
    'valid_measured_research': sum(t['valid_measured'] for t in trees),
    'incorrect_research': sum(r['result'].get('correct') is False for r in research),
    'infrastructure_errors': sum(r['result'].get('status') == 'infrastructure_error' for r in research),
    'native_calls': audit['native_call_count'], 'tokens': pairs['tokens'],
    'mother_native_thread': result['mother_conversation']['thread_id'],
    'pairwise_steps': len(result['postprocess']['steps']), 'assembly_native_calls': len(pairs['pair_requests']),
    'same_mother': result['verification']['same_mother'], 'no_research_restart_after_assembly': True,
    'final_g_confirmed': final['status'] == 'confirmed', 'final_g_commit': final['outcome']['commit'],
    'final_g_ms': final['outcome']['mean_seconds'] * 1000,
    'reference_ms': ref * 1000, 'final_g_speedup': ref / final['outcome']['mean_seconds'],
    'best_confirmed_ms': best['mean_seconds'] * 1000, 'best_commit': best['commit'],
    'duration_seconds': timing['actual_seconds'], 'target_seconds': 1800,
    'unused_seconds': timing['unused_seconds'], 'reserve_at_closure_seconds': closure_reserve,
    'actual_finalization_seconds': timing['actual_seconds'] - timing['research_closure_seconds'],
    'timing_goal_fully_used': False,
    'observations': {'romeo_tools_configured_all_calls': access['availability_all_native_invocations'],
                     'actual_model_mcp_calls': access['actual_mcp_use_by_server'],
                     'compaction_event_observed': pairs['compaction']['actual_event_observed'],
                     'compaction_policy': pairs['compaction']['policy']},
    'native_submission_sha256': native_sha, 'final_g_zip_sha256': export['zip_sha256'],
    'original_unchanged': True,
}
(HERE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

def duration(seconds):
    total = round(seconds)
    return f'{total // 60} min {total % 60:02} s'

lines = [
    '# CUDA N-body — Luna Max — arbres indépendants — job ' + state['job_id'], '',
    '**Le pipeline a terminé, G final est confirmé et les exports sont valides. '
    'La durée cible de 30 minutes reste sous-utilisée : exécution réelle ' + duration(timing['actual_seconds']) + '.**', '',
    'La campagne neuve utilise le N-body original, un GPU GH200 ARM ROMEO, quatre CPU, TreeQuest 0.3.2 '
    'et uniquement AB-MCTS-A. Aucun ancien candidat optimisé n’a été fourni aux modèles. '
    'Le plafond de tokens est absent de la recherche, des réparations et de la fusion. '
    'Les sources embarquées correspondent aux 97 fichiers couverts par les 686 tests locaux réussis.', '',
    '| Arbre | Essais admis | Valides mesurés | Profondeur admise / valide | Meilleur en recherche (ms) |',
    '|---|---:|---:|---:|---:|',
]
for t in trees:
    lines.append(f"| {t['role']} | {t['trials']} | {t['valid_measured']} | {t['max_depth']} / {t['max_valid_depth']} | {t['best_search_ms']:.6f} |")
lines += ['', f"Total : {len(research)} essais de recherche, {summary['valid_measured_research']} programmes valides mesurés, "
          f"{summary['incorrect_research']} programme incorrect, {summary['infrastructure_errors']} erreur d’infrastructure. "
          f"{summary['native_calls']} appels natifs Luna Max ont été vérifiés, réparations et Mother comprises.", '',
          '**Parallélisme et progression indépendante.** Les trois processus natifs ont été observés simultanément. '
          f"{independent['mixed_samples']} échantillons montrent des arbres à des numéros d’essai différents en génération simultanée. "
          'Le premier associe T1 au premier essai et T2 au deuxième essai. Les événements du contrôleur confirment '
          'un seul essai non terminé par arbre et la terminaison de tous les essais admis. Les mesures GPU restent exclusives.', '',
          '**Mother et fusion.** Une seule conversation native, `' + summary['mother_native_thread'] + '`, '
          'relie la planification initiale et toutes les continuations de fusion. Deux étapes de fusion deux par deux '
          'ont demandé trois appels natifs, dont une réparation de G final. Aucun nouvel essai de recherche n’a été '
          'créé après la clôture. La compaction Codex CLI reste automatique ; aucun événement effectif de compaction '
          'n’a été observé sur ce lancement.', '',
          '| Programme | Temps confirmé, métrique combinée (ms) |', '|---|---:|',
          f"| Référence originale | {summary['reference_ms']:.6f} |",
          f"| Première fusion, retenue par le contrôleur | {summary['best_confirmed_ms']:.6f} |",
          f"| G final | {summary['final_g_ms']:.6f} |", '',
          f"G final est environ **{summary['final_g_speedup']:.2f}×** plus rapide que la référence. "
          'Chaque programme confirmé possède cinq échantillons frais. La métrique est la moyenne des cinq '
          'moyennes géométriques des temps d’événements CUDA pour N = 4096, 8192 et 16384. '
          'Compilation, transferts et démarrage des processus sont exclus. Le protocole protégé conserve '
          '11 cas de correction par phase, un oracle CPU FP64 et des données différentes en confirmation. '
          'Les journaux des trois programmes confirmés ont été rapatriés et recalculés indépendamment.', '',
          '**Exports.** `exports/G-final-confirme.zip` contient les sources du commit confirmé de G final, '
          '`' + summary['final_g_commit'] + '`, ses paramètres de lancement et son reçu de confirmation. '
          '`exports/meilleur-confirme.zip` conserve l’export natif du contrôleur pour le premier G, '
          '`' + summary['best_commit'] + '`. Les empreintes des fichiers ont été comparées au commit exact '
          'et à la proposition native finale ; les objets Git transférés ont passé `git fsck`. '
          'Il s’agit du kernel device CUDA et de son contrat de lancement pour le harnais NVRTC, '
          'avec le fichier original utilisateur préservé.', '',
          '**Durée : réserve encore trop prudente.** La recherche s’est clôturée après '
          + duration(timing['research_closure_seconds']) + ', avec ' + duration(timing['remaining_at_closure']) + ' restantes. '
          'Le contrôleur réservait ' + duration(closure_reserve) + ' pour la finalisation ; '
          'le prochain essai T2 était estimé à ' + duration(next_costs['T2']) + ' et a été refusé. '
          'La fusion réelle a pris ' + duration(timing['postprocess_seconds']) + ', la confirmation '
          + duration(timing['confirmation_seconds']) + ', et l’archive moins d’une seconde. '
          'La durée finale est ' + duration(timing['actual_seconds']) + ', soit '
          + duration(timing['unused_seconds']) + ' inutilisées. Le test valide le parallélisme, la conversation '
          'Mother et la confirmation/export de G final ; il ne valide pas une utilisation complète des 30 minutes. '
          'Aucune correction du moteur ni relance n’a été faite après observation de ce résultat.', '',
          '**Skills, documentation et ROMEO.** Les liaisons et contenus des six skills ont été vérifiés pour '
          'chaque appel, avec leurs traces déclaratives. Les deux serveurs MCP ont été configurés et observés '
          'pour Mother, les trois enfants et la Mother reprise. Treize consultations de documentation ont été '
          'observées, neuf par Mother en préparation et quatre par T3. Aucun appel métier au MCP ROMEO '
          'n’a été observé : accès disponible et utilisation effective sont distingués dans les audits. '
          'Le contrôle additionnel « appels aux deux serveurs observés » est donc négatif ; les 46 autres '
          'assertions de l’audit principal passent. Les 12 assertions de fusion et tous les contrôles GPU passent.', '',
          'Les preuves détaillées sont conservées dans `evidence/`, les audits JSON et `protocol/`. '
          'Le bundle Git conserve les programmes et leurs parents de recherche. Aucun commit ni push n’a été exécuté.', '']
(HERE / 'RAPPORT.md').write_text('\n'.join(lines), encoding='utf8')

destination = Path(state['repository']) / 'experiments/cuda-nbody-independent-20261021-774157'
destination.mkdir(exist_ok=False)
for name in ('RAPPORT.md', 'summary.json', 'audit.json', 'independence-proof.json', 'parallel-proof.json',
             'pairwise-audit.json', 'access-audit.json', 'skills-audit.json', 'gpu-audit.json',
             'timing-audit.json', 'export-verification.json', 'G-final-source-receipt.json',
             'tested-core-provenance.json', 'preparation.json', 'submission.json', 'collection.json'):
    shutil.copyfile(HERE / name, destination / name)
shutil.copytree(HERE / 'resultat', destination / 'exports')
saved = destination / 'evidence'
saved.mkdir()
for name in ('results.json', 'progress.json', 'allocation.json', 'device.json', 'gpu-preflight.json',
             'DONE.json', 'registry.sqlite3', 'experiments.json', 'runtime-manifest.json', 'submission.zip.sha256'):
    shutil.copyfile(HERE / 'evidence' / name, saved / name)
shutil.copytree(HERE / 'evidence/confirmation-logs', saved / 'confirmation-logs')
shutil.copyfile(Path(state['artifact']) / 'payload.tar.gz', destination / 'payload.tar.gz')
protocol = destination / 'protocol'
protocol.mkdir()
for name in ('prepare.py', 'pilot.py', 'cuda_evaluator.py', 'protocol.py', 'start_worker.py', 'audit.py',
             'independence_proof.py', 'analyse_timing.py', 'export_confirmed.py', 'final_report.py'):
    shutil.copyfile(HERE / name, protocol / name)
subprocess.run(['git', '--git-dir=' + str(HERE / 'evidence/source-repo/.git'), 'bundle', 'create',
                str(saved / 'research-history.bundle'), '--all'], check=True, capture_output=True)
publication = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(destination.rglob('*')) if p.is_file()}
(destination / 'publication-manifest.json').write_text(json.dumps(publication, indent=2) + '\n', encoding='utf8')
print(json.dumps({'report': str(destination / 'RAPPORT.md'), 'files': len(publication),
                  'summary': {k: summary[k] for k in ('research_trials', 'valid_measured_research', 'native_calls',
                               'final_g_ms', 'final_g_speedup', 'duration_seconds', 'unused_seconds')}}))
