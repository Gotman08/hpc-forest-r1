"""Build the French report only from completed paired measurements and audited runs."""
import collections
import datetime
import html
import json
from pathlib import Path

R = Path(__file__).resolve().parent
O = R.parents[1]/'outputs/comparaison-reprises'


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def number(x, decimals=2):
    return 'n.d.' if x is None else f'{x:.{decimals}f}'.replace('.', ',')


def ratio(x,decimals=2):
    return number(x,decimals)+'×' if x is not None else 'n.d.'


def table(headers, rows):
    def cell(x):
        return str(x).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| '+' | '.join(headers)+' |',
                      '| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(cell(v) for v in row)+' |' for row in rows])


data = read(O/'RESULTATS.json')
validation = read(R/'validation-notes.json')
source_reviews = read(R/'source-review/observations.json')
assert {r['case_id'] for r in source_reviews} == {r['case_id'] for r in data['rows']}
audit = read(O/'AUDIT-FOREST.json')
hardware = read(O/'AUDIT-MATERIEL.json')
progress = read(O/'PROGRESSION-RECHERCHE.json')
stability = read(O/'STABILITE-BLACKSCHOLES.json')
transport = read(O/'AUDIT-TRANSPORT.json')
previous = read(O.parent/'comparaison-references/AUDIT-FOREST.json')
old = {r['case_id']: r for r in previous['campaigns'] if r.get('trees_selected')}
campaigns = audit['campaigns']
assert len(campaigns) == 14 and len(data['rows']) == 35
completed = sum(r['pipeline_complete'] for r in campaigns)
confirmed_g = sum(r['final_g_status'] == 'confirmed' for r in campaigns)
status = collections.Counter()
for r in campaigns:
    status.update(r['trial_statuses'])
old_trials = sum(sum(old[r['case_id']]['trial_counts'].values()) for r in campaigns)
new_trials = sum(sum(r['trial_counts'].values()) for r in campaigns)
counts = data['summary']['verdict_counts']
gain = counts.get('Nouveau plus rapide dans chaque bloc', 0)
loss = counts.get('Ancien plus rapide dans chaque bloc', 0)
mixed = counts.get('Écart dans la variabilité observée', 0)
unchanged = counts.get('Code ou binaire identique : variation de mesure', 0)
old_one = sum(t['attempts'] == 1 for r in campaigns for t in old[r['case_id']]['tree_details'])
new_one = sum(t['attempts'] == 1 for r in campaigns for t in r['tree_details'])

lines = [
    '# Reprises Forest : comparaison sur ROMEO', '',
    f"Rapport produit le {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}.", '',
    f"Les 14 programmes peu explorés ont été relancés avec une mémoire neuve et une cible de deux heures, contre trente minutes auparavant. {completed}/14 pipelines ont terminé et {confirmed_g}/14 intégrations G ont été confirmées. Le comparatif porte sur 35 lignes du tableau documentaire : **{gain} favorisent le nouveau code dans chaque bloc de mesure, {loss} favorisent l’ancien, {mixed} présentent des écarts qui changent de sens selon le bloc, et {unchanged} correspondent à un code ou binaire identique**.", '',
    'Ces 35 lignes ne sont pas 35 expériences indépendantes : certaines partagent le même programme et le même gagnant. Les étendues observées ne sont pas des intervalles de confiance. Une première tentative de 14 campagnes a été interrompue après environ 44 minutes pour corriger la capacité du contexte. Base64 a ensuite nécessité une relance supplémentaire après correction du classement des réponses tronquées. La comparaison finale retient une campagne par programme, toutes avec un contexte de 64 000 caractères ; les variations entre recherches restent possibles.', '',
    '## Les speedups côte à côte', '',
    'Chaque speedup ROMEO est le temps du naïf divisé par celui de la variante. « Ancien historique » vient de la première étude ; « ancien remesuré » et « nouveau » proviennent de la nouvelle allocation commune. Le ratio nouveau/ancien est le temps de l’ancien divisé par celui du nouveau : au-dessus de 1, le nouveau code est plus rapide. Les références publiées conservent leur matériel et leur protocole propres.', '',
    table(['Programme / entrée', 'Publié', 'Réf. ROMEO actuelle', 'Forest ancien historique', 'Forest ancien remesuré', 'Forest nouveau', 'Nouveau / ancien', 'Étendue par blocs'],
          [[r['label'], ratio(r['published_speedup']), ratio(r['reference_speedup']), ratio(r['previous_forest_speedup']), ratio(r['old_selected_speedup']), ratio(r['new_selected_speedup']), ratio(r['new_vs_old'],4), ' – '.join(ratio(x,4) for x in r['new_vs_old_range'])] for r in data['rows']]), '',
    'Le gagnant affiché est celui confirmé par le moteur avant cette comparaison. Les résultats de G sont conservés séparément dans le classeur, le CSV et les preuves ; aucun gagnant n’est choisi après lecture des mesures finales.', '',
    'Si les sources ou les binaires des deux gagnants ont la même empreinte SHA-256, leurs écarts de mesure ne sont pas comptés comme une amélioration ou une régression algorithmique. Les empreintes et ce constat figurent dans le CSV et le JSON.', '',
    '## Contrôle complémentaire de Black–Scholes', '',
    'La forte variabilité observée à 40 cœurs a motivé une répétition supplémentaire sur 21 blocs, dans une autre allocation ROMEO, avec les mêmes sources et pilotes protégés. Le tableau principal conserve ses sept blocs initiaux. Cette vérification décidée après observation ne constitue pas une répétition préenregistrée de toute l’étude.', '',
    table(['Cœurs', 'Nouveau / ancien : 7 blocs initiaux', 'Nouveau / ancien : 21 blocs supplémentaires', 'Étendue supplémentaire', 'Blocs supplémentaires favorables au nouveau'],
          [[r['threads'], ratio(r['primary']['new_vs_old'], 4), ratio(r['stability']['new_vs_old'], 4), ' – '.join(ratio(x, 4) for x in r['stability']['paired_ratio_range']), f"{r['stability']['new_faster_blocks']} / 21"] for r in stability['rows']]), '',
    'À 40 cœurs, les médianes et les rapports varient fortement entre allocations et entre blocs : le résultat ne permet pas une conclusion robuste sur un gain ou une régression reproductible. Les contrôles de correction passent. Les affinités ont changé (20–59, puis 0–39) ; les données ne permettent pas d’attribuer la variabilité à ce seul changement, à la charge du nœud ou à un autre effet. Aucun candidat n’est modifié à la suite de ce contrôle.', '',
    '## Changements dans les programmes retenus', '',
    'Cette lecture des sources décrit les différences entre les deux gagnants. Elle ne démontre pas quelle transformation a causé le gain : les variantes combinent parfois plusieurs changements, et les hypothèses de chaque essai sont conservées dans l’historique.', '',
    table(['Programme', 'Différences observées', 'Contrat et contrôles'],
          [[r['case_id'], r['changes'], r['contract_review']] for r in sorted(source_reviews, key=lambda r:r['case_id'])]), '',
    'Les diffs et leurs empreintes sont conservés dans `source-review/` dans les preuves. Aucun candidat n’a été corrigé manuellement après lecture des mesures finales.', '',
    '## Ce qui a été corrigé', '',
    '- Le validateur reconnaît les appels MCP de découverte autorisés (`list_mcp_resources` et `list_mcp_resource_templates`). Les arguments et les serveurs restent contrôlés ; cela ne donne aucun nouvel accès à un shell ou à des fichiers arbitraires.',
    '- La source fournie à la planification peut atteindre 128 000 caractères au lieu de 32 000. Une régression vérifie la transmission exacte d’une source dépassant l’ancienne limite.',
    '- La fenêtre de mémoire/contexte des essais passe de 12 000 à 64 000 caractères pour les 14 programmes. Le réglage précédent découpait les longues sources et perdait des pages entre appels éphémères, notamment pour Deferred. Un contrôle vérifie la transmission complète et exacte des 14 sources ; les appels natifs de Deferred confirment la présence du fichier complet.',
    '- Les wrappers Linux des nouvelles campagnes utilisent LF. Les trois anciens cas GPU dont l’empaquetage manquait de Makefile/run.sh disposent de wrappers vérifiés dans le précontrôle séparé.',
    '- Les sept anciennes erreurs causées uniquement par la découverte MCP ont été rejouées avec le parseur corrigé. Leur statut historique reste inchangé.', '',
    '- Base64 : un échec natif `max_output_tokens` est désormais un échec de génération, avec rejet du code incomplet. Il n’arrête plus tous les arbres comme une panne d’infrastructure. Les vraies pannes et appels interdits restent bloquants. Le journal réel a été rejoué hors ligne, et une nouvelle campagne vide utilise le correctif ; l’ancienne tentative conserve ses statuts historiques.', '',
    f"Validation locale du moteur : **{validation['tests']['pytest']}**, Ruff et la vérification du patch passent. Le premier profil avait déjà passé 829 tests ; neuf régressions supplémentaires vérifient le traitement de la limite de sortie. Sur ROMEO, les 68 étapes de précontrôle (construction, livraison, construction protégée et validation pour 17 programmes) ont réussi après correction de deux défauts du script de précontrôle : variable du rendu et chemin de bibliothèque CUDA. Les sources algorithmiques initiales et les contrôles protégés sont inchangés.", '',
    'Deux empreintes de moteur sont présentes dans les campagnes finales : les 13 campagnes non touchées par cet incident conservent leur version figée ; la nouvelle campagne Base64 ajoute uniquement le correctif de classement des réponses tronquées. Les versions et empreintes exactes figurent dans l’audit.', '',
    '## Exploration avant / après', '',
    f"Sur les 14 programmes retenus, les essais enregistrés passent de {old_trials} à {new_trials}, intégrations G comprises. Le nombre d’arbres n’ayant qu’un essai passe de {old_one} à {new_one}. Ces totaux ne comptent pas les simples lectures de mémoire comme des essais de code.", '',
    table(['Programme', 'Job nouveau', 'Arbres ancien → nouveau', 'Essais ancien → nouveau', 'Essais nouveaux par arbre', 'G', 'Profondeur max', 'Statuts de tous les essais', 'Durée SLURM (min)'],
          [[r['case_id'], r['job_id'], f"{old[r['case_id']]['trees_selected']} → {r['trees_selected']}", f"{sum(old[r['case_id']]['trial_counts'].values())} → {sum(r['trial_counts'].values())}", '; '.join(f"{k}: {v}" for k, v in r['trial_counts'].items() if k != 'G'), r['trial_counts'].get('G', 0), max((t['max_mission_depth'] for t in r['tree_details']), default=0), '; '.join(f'{s}: {n}' for s, n in r['trial_statuses'].items()), number(r['slurm_elapsed_seconds']/60 if r['slurm_elapsed_seconds'] is not None else None, 1)] for r in campaigns]), '',
    'Les rôles T1, T2… sont propres à chaque nouvelle campagne ; un T1 ancien n’a pas nécessairement le même sujet qu’un T1 nouveau. Mother choisit le nombre d’arbres. Les sujets, objectifs, parentés, profondeurs et statuts sont conservés dans les preuves et dans l’audit.', '',
    'Les compteurs de jetons et les durées par phase sont également conservés dans `AUDIT-FOREST.json`. Les phases pouvant se chevaucher, la somme de leurs durées ne représente pas le temps mural. Les compteurs de jetons du moteur ne constituent pas une facture du service de modèle.', '',
    'La cible de deux heures inclut la réserve adaptative pour l’intégration et la confirmation. Elle ne signifie pas deux heures pleines consacrées à proposer des candidats. L’efficacité CPU moyenne de SLURM inclut aussi les attentes du modèle et, dans les comparaisons, les variantes séquentielles ; elle ne mesure pas directement le parallélisme du noyau gagnant. Les allocations de 40 cœurs restent nécessaires pour comparer les configurations à 1, 4 et 40 cœurs.', '',
    '## Quand la recherche a progressé', '',
    'Ce tableau observe chaque nouvelle campagne à trente minutes puis à la fin de sa recherche. Ce ne sont pas deux recherches indépendantes à budgets différents. Les speedups ci-dessous utilisent l’objectif interne du moteur, parfois agrégé sur plusieurs configurations ; ils ne remplacent pas les speedups documentaires remesurés plus haut. Le meilleur score observé peut aussi bénéficier du bruit de mesure. G est exclu de cette courbe et confirmé séparément.', '',
    table(['Programme', 'Essais terminés à 30 min', 'Essais de recherche totaux', 'Meilleur speedup recherche à 30 min', 'Meilleur speedup recherche final', 'Ratio final / 30 min', 'Dernier essai terminé (min)'],
          [[r['case_id'], r['completed_trials_at_30_min'], r['search_trials'], ratio(r['best_search_speedup_at_30_min']), ratio(r['best_search_speedup_final']), ratio(r['late_best_search_ratio'], 3), number(r['last_search_settled_minute'], 1)] for r in progress['campaigns']]), '',
    'Le détail de chaque nouveau record, avec son arbre, sa profondeur et sa minute d’observation, est conservé dans `PROGRESSION-RECHERCHE.json`. Une intégration G peut encore améliorer le résultat au-delà du meilleur essai de recherche.', '',
    '## Mémoire, intervention et lieu des calculs', '',
    'Chaque programme possède une nouvelle session, un nouveau dépôt de campagne, une nouvelle base SQLite et une nouvelle conversation Mother. Les 14 reçus de démarrage attestent zéro essai et zéro document avant l’exploration. L’audit vérifie l’absence de réutilisation des sessions et conversations précédentes, ainsi que l’absence de partage de contexte entre programmes. Les métadonnées initiales et la source naïve sont présentes : une base neuve ne signifie pas une base sans métadonnées.', '',
    'La mémoire est ensuite conservée entre les essais d’un même programme : c’est le fonctionnement de Forest. Les appels de recherche sont éphémères ; Mother garde sa conversation pour planifier et intégrer. Les mémoires automatiques de Codex et le chargement des documents du projet sont désactivés. Les anciens candidats optimisés ne sont pas fournis au modèle.', '',
    'Pour les comparaisons de performance, chaque variante démarre dans un nouveau processus et reconstruit ses entrées. Les contrôles vérifient les sorties, et les gardes et empreintes d’entrée lorsqu’elles sont prévues par le pilote. Les caches du système et du JIT restent gérés normalement : aucune purge globale ni réinitialisation physique du GPU n’est effectuée. Les échauffements précèdent les mesures. Une mémoire Forest neuve ne signifie donc pas une machine matériellement remise à froid.', '',
    'L’intervention de l’opérateur concerne les correctifs du moteur, la capacité du contexte, les wrappers, le lancement, la surveillance des transferts et les analyses. Aucun conseil d’optimisation ni modification manuelle des candidats n’a été ajouté pendant ces recherches.', '',
    'Le contrôleur, TreeQuest AB-MCTS, les compilations, les validations et les chronométrages s’exécutent sur ROMEO sous SLURM. Le relais Codex est local et l’inférence du modèle `gpt-6-luna`, effort `max`, est hébergée. Les mesures CPU utilisent EPYC 9654 ; les mesures GPU utilisent GH200. Dire que « tout est sur ROMEO » serait donc inexact pour l’inférence du modèle.', '',
    '## Comparabilité et limites', '',
    table(['Allocation actuelle', 'Programmes', 'Job précédent → actuel', 'CPU observé', 'GPU observé', 'Même modèle CPU', 'Même sortie de version du compilateur'],
          [[r['group'], ', '.join(r['cases']), f"{r['previous']['job']} → {r['current']['job']}", r['current']['cpu']['Model name'], r['current'].get('gpu', {}).get('Product Name', '—'), 'oui' if r['comparisons']['cpu_model_same'] else 'non', 'oui' if r['comparisons']['compiler_version_output_same'] else 'non'] for r in hardware['allocations']]), '',
    'Les instantanés matériels, affinités CPU, versions, UUID GPU et limites de puissance observées sont conservés dans `AUDIT-MATERIEL.json`. Ils sont relevés au démarrage des jobs : ils ne constituent pas un suivi continu des fréquences ou de la température pendant les mesures. Le nom commercial du GPU et sa mémoire visible sont conservés séparément. La version CUDA affichée par le pilote décrit sa compatibilité ; le compilateur réellement chargé est nvcc V12.6.85, issu du paquet CUDA 12.6.3.', '',
    '- Ancien et nouveau candidats, naïf et référence sont exécutés dans la même allocation de comparaison, avec compilateurs et entrées identiques. Les sommes de contrôle des suites figées sont vérifiées avant exécution.',
    '- Les cinq programmes CPU disponibles sont comparés dans une première allocation ; Base64 utilise une seconde allocation après sa relance plus tardive. Pour chaque programme, tous les codes à comparer restent réunis sur le même matériel. Aucun ratio ne divise un temps d’un programme par celui d’un autre.',
    '- Sept blocs CPU, neuf blocs GPU et trois blocs de rendu, avec ordre pseudo-aléatoire des variantes. Chaque variante démarre dans un processus distinct. Les échauffements existants sont conservés. Aucun redémarrage du nœud, vidage global des caches, verrouillage des fréquences ou nœud physique exclusif n’est revendiqué.',
    '- Agrégation par médiane, sauf les lignes UTF-8 BEST (minimum) et MEAN (moyenne), reprises de la définition documentaire. Les valeurs absolues, blocs, tailles, graines et codes de sortie sont conservés.',
    '- Les speedups publiés et ROMEO ne diffèrent pas seulement par le matériel : les versions, compilateurs, entrées et protocoles peuvent aussi changer. Aucune normalisation par les FLOPS théoriques n’est appliquée.',
    '- Ces reprises changent à la fois l’infrastructure, la capacité du contexte et le temps de recherche. Elles ne permettent pas d’attribuer isolément un gain au temps supplémentaire. Des répétitions de recherche indépendantes et des essais à budget égal seraient nécessaires pour séparer ces effets.',
    '- Les diagnostics de la référence Volume hors de son domaine (dimensions non multiples de quatre) et du naïf UTF-8 historique sur texte malformé sont conservés. Ils ne sont pas transformés en speedups.', '',
    '## Diagnostics conservés', '',
    f"Statuts des essais nouveaux : `{json.dumps(dict(status), ensure_ascii=False, sort_keys=True)}`.", '',
    f"Les journaux des relais comptabilisent {transport['failed_operations']} opérations de transport en échec sur {transport['operations']} opérations observées, tentatives remplacées comprises. Ce compteur est distinct des statuts d’essais : une opération de transfert ratée peut être suivie d’une opération réussie. L’audit fournit chaque incident et les succès ultérieurs observés sur le même outil et le même chemin, sans prétendre que chaque appel a été rejoué à l’identique. Les transferts MCP manuels de préparation et de collecte ne font pas partie de ce journal.", '',
]
for r in campaigns:
    if not r['pipeline_complete'] or r['pipeline_error'] or r['final_g_status'] != 'confirmed':
        lines += [f"- {r['case_id']} : pipeline={r['pipeline_complete']}, G={r['final_g_status']}, erreur={r['pipeline_error'] or 'aucune signalée'}."]
    call_failures=collections.Counter(message for call in r['calls'] for message in call.get('native_failure_messages',[]))
    for message,n in call_failures.items():
        lines += [f"- {r['case_id']} : {n} appel(s) natif(s) avec le diagnostic `{message}`. Les réponses et statuts du moteur sont conservés sans reclassification manuelle."]
for f in data['summary']['failures']:
    lines += [f"- Contrôle final {f['case_id']} / {f['variant']}, n={f['n']}, bloc={f['block']} : correct={f['correct']}, sortie={f['exit_code']}, détail={f['error'] or 'voir le résultat brut' }."]
lines += ['', 'Le contrôle UTF-8 supplémentaire utilise les mêmes 79 729 chaînes que précédemment, avec entrées alignées sur 64 octets conformément au contrat et gardes mémoire autour des tampons.', '',
          table(['Variante UTF-8', 'Cas contrôlés', 'Échecs'],
                [[r['variant'],r['cases'],r['failed']] for r in data['utf8_audit']['records']]), '']
lines += ['', '## Fichiers', '',
          '- `COMPARAISON.xlsx` : speedups, temps de calcul, détails Forest et mesures brutes.',
          '- `COMPARAISON.csv` et `RESULTATS.json` : résultats exploitables.',
          '- `AUDIT-FOREST.json` et `DETAILS-FOREST.csv` : contextes, mémoire, arbres et exécution.',
          '- `AUDIT-MATERIEL.json` : matériel, compilateurs, affinités et instantanés GPU comparés entre études.',
          '- `PROGRESSION-RECHERCHE.json` : évolution de chaque recherche, essais à trente minutes et nouveaux records.',
          '- `STABILITE-BLACKSCHOLES.json` : répétition complémentaire de 21 blocs et données brutes, séparées du tableau principal.',
          '- `AUDIT-TRANSPORT.json` : opérations des relais et incidents de transfert, distincts des échecs des programmes.',
          '- `ESSAIS-FOREST.json` et `ESSAIS-FOREST.csv` : chaque essai ancien et nouveau, parenté, profondeur, hypothèse et diagnostic.',
          '- `DEMARRAGE-MEMOIRES.json` : les 14 reçus avant exploration.',
          '- `TENTATIVE-INTERROMPUE.json` : la première tentative à contexte de 12 000 caractères, conservée avec ses 507 essais enregistrés, dont 39 encore en attente à l’arrêt.',
          '- `TENTATIVE-BASE64-LIMITE.json` et `VALIDATION-LIMITE-SORTIE.json` : arrêt précoce de Base64, diagnostic et vérification du correctif.',
          '- `VALIDATION-CONTEXTE.json` : transmission exacte des sources au nouveau réglage de 64 000 caractères.',
          '- `CORRECTIFS.patch` et `VALIDATION-INFRASTRUCTURE.json` : changements et validation.',
          '- `PREUVES-ET-CODES.zip` : sources, scripts, journaux, résultats et manifestes de reproductibilité.', '']
(O/'RAPPORT.md').write_text('\n'.join(lines), encoding='utf8')

header = ['Programme / entrée', 'Publié', 'Référence ROMEO', 'Ancien historique', 'Ancien remesuré', 'Nouveau', 'Nouveau / ancien', 'Constat']
body = []
for r in data['rows']:
    values = [r['label'], ratio(r['published_speedup']), ratio(r['reference_speedup']), ratio(r['previous_forest_speedup']), ratio(r['old_selected_speedup']), ratio(r['new_selected_speedup']), ratio(r['new_vs_old'],4), r['verdict']]
    body.append('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in values)+'</tr>')
page = '''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Forest — reprises sur ROMEO</title><style>
body{font:16px/1.5 system-ui,sans-serif;color:#23314a;background:#f5f7fa;margin:0;padding:36px}main{max-width:1700px;margin:auto}h1{font-size:32px;line-height:1.15;margin-bottom:12px}p{max-width:1100px}.cards{display:flex;gap:16px;flex-wrap:wrap;margin:24px 0}.card{background:white;border:1px solid #dce2ea;border-radius:8px;padding:16px 24px;min-width:170px}.card b{font-size:30px;display:block}label{display:block;margin:24px 0 12px}input{font:inherit;border:1px solid #adb8c9;border-radius:5px;padding:8px;width:360px;max-width:85%}.scroll{overflow:auto;border:1px solid #dce2ea;background:white}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:14px}th{background:#243c62;color:white;text-align:left;white-space:nowrap}td,th{padding:12px;border-bottom:1px solid #e3e8ef}td:nth-child(n+2):nth-child(-n+7){text-align:right;white-space:nowrap}tr:nth-child(even){background:#f5f7fa}a{color:#204d86}.note{color:#58687d}footer{margin-top:28px}#count{font-size:14px;color:#58687d}
</style><main><h1>Forest : les reprises sur ROMEO</h1>
<p>14 programmes, mémoire neuve par programme, cible de 2 h contre 30 min auparavant. Les anciens et nouveaux codes sont remesurés dans la même allocation, avec les mêmes entrées.</p>
<div class="cards">'''+''.join(f'<div class="card"><b>{n}</b>{label}</div>' for n, label in [(gain, 'nouveau plus rapide'), (loss, 'ancien plus rapide'), (mixed, 'écart variable'), (unchanged, 'code ou binaire identique')])+'''</div>
<p class="note">Comptages sur 35 lignes documentaires, dont certaines partagent le même programme. « Plus rapide » signifie dans chaque bloc observé ; ce n’est pas un test de significativité. Les différences avec les publications ne mesurent pas isolément l’effet du matériel.</p>
<label>Filtrer par programme ou constat<br><input id="search" type="search" placeholder="Ex. Base64, référence, variabilité"></label><p id="count">35 lignes affichées</p>
<div class="scroll"><table id="results"><thead><tr>'''+''.join('<th>'+html.escape(x)+'</th>' for x in header)+'</tr></thead><tbody>'+''.join(body)+'''</tbody></table></div>
<p class="note">Speedup = temps du naïf / temps de la variante. Nouveau / ancien = temps ancien / temps nouveau. Les données détaillées et étendues par bloc sont disponibles dans le rapport et le classeur.</p>
<footer><a href="RAPPORT.md">Rapport détaillé</a> · <a href="COMPARAISON.xlsx">Classeur Excel</a> · <a href="COMPARAISON.csv">CSV</a> · <a href="AUDIT-FOREST.json">Audit Forest</a> · <a href="PREUVES-ET-CODES.zip">Preuves et codes</a></footer>
<script>document.querySelector('#search').addEventListener('input',e=>{let count=0;for(const row of document.querySelectorAll('tbody tr')){row.hidden=!row.textContent.toLocaleLowerCase('fr').includes(e.target.value.toLocaleLowerCase('fr'));count+=!row.hidden}document.querySelector('#count').textContent=count+' lignes affichées'});</script></main></html>'''
(O/'TABLEAU-DE-BORD.html').write_text(page, encoding='utf8')
print(json.dumps({'pipelines_complete': completed, 'G_confirmed': confirmed_g,
                  'old_trials': old_trials, 'new_trials': new_trials,
                  'old_single_trial_trees': old_one, 'new_single_trial_trees': new_one,
                  'new_faster': gain, 'old_faster': loss, 'mixed': mixed,'unchanged':unchanged}, ensure_ascii=False))
