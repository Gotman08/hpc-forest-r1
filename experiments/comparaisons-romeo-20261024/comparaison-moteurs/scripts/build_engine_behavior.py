"""Explain controller behavior independently of final GPU rankings."""
from collections import Counter
import json
from engine_study import ROOT,CONDITIONS,read,write
from build_engine_comparison import LABELS,duration,number,ms

BASE=ROOT/'outputs/comparaison-moteurs'

def main():
    primary=[]
    for key in CONDITIONS:
        d=BASE/'serie-atomique/data'/key
        s=read(d/'summary.json');events=read(d/'events.json');native=read(d/'native-summary.json');calls=read(d/'native-calls.json');trials=read(d/'lineage.json')
        admissions=[e['payload'] for e in events if e['kind']=='adaptive_admission']
        primary.append({'key':key,'summary':s,'events':events,'native':native,'calls':calls,'trials':trials,'first_admission':admissions[0]})
    all_trials=[t for r in primary for t in r['trials']]
    local_attempts=read(BASE/'data/diagnostics-tentatives-locales.json')
    local_missions=read(BASE/'data/diagnostics-missions-locales.json')
    counts=Counter(t['status'] for t in all_trials if t['role']!='G')
    selection_counts={r['key']:Counter(x.get('status') for x in r['summary']['postprocess'].get('selections',[])) for r in primary}
    out=['# Comportements des moteurs et diagnostics expliqués','',
        'Ce document décrit les décisions effectivement observées dans les nouvelles campagnes. Le [rapport comparatif](RAPPORT.md) donne les temps du rejeu commun ; le [rapport historique](../comparaison-historique/RAPPORT.md) contient les commits, les tests avant/après et les anciens programmes.',
        '', '## Ce qui a été exécuté', '',
        'Les trois séries représentent **21 campagnes, 225 essais enregistrés et 389 appels natifs**. S1 et S2 conservent les problèmes de transport. S3 est la série principale : **134 essais de recherche** (121 valides, 9 incorrects, 3 générations refusées, 1 doublon) et **15 assemblages valides**. Les sept recherches de S3 s’arrêtent sur une décision de budget, sans essai classé comme erreur d’infrastructure. Les sept G finaux sont confirmés ; six exports sur sept aboutissent.',
        '', 'Les configurations historiques sont conservées. Le modèle choisit le nombre d’arbres et leurs sujets à chaque nouveau départ ; ce nombre n’est donc pas forcé à une valeur commune. Les campagnes comparent des systèmes complets, pas une fonction isolée du moteur.',
        '', '## Admission : la correction de réserve change réellement le travail engagé','',
        '| État | Arbres | Réserve initiale estimée | Temps restant alors | Recherche terminée à | Essais recherche / valides | Finalisation observée |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in primary:
        s=r['summary'];a=r['first_admission'];c=s['research_counts']
        out.append(f"| {r['key']} | {s['forest_width']} | {duration(a['reserve_seconds'])} | {duration(a['remaining_seconds'])} | {duration(s['search_elapsed_seconds'])} | {sum(c.values())} / {c.get('valid',0)} | {duration(s['total_elapsed_seconds'])} |")
    out+=['',
        '**775521 reproduit une réserve trop conservatrice.** Dès le premier calcul, elle réserve environ 52 minutes alors qu’il en reste 28. L’exception de première vague permet trois essais, puis aucune nouvelle recherche n’est admise. La campagne finit pourtant en moins de 13 minutes. La réserve est une estimation, pas du temps réellement consommé. Les traces `adaptive_admission` et `budget_stop` rendent ce mécanisme directement observable.',
        '', 'Dans 775815 et les états suivants, la réserve initiale est proche de 10–12 minutes. Ces campagnes engagent davantage d’essais. Cela établit une différence de décision et de volume exploré dans ces exécutions ; le nombre d’essais seul ne garantit pas un meilleur programme.',
        '', '[Décisions complètes de 775521](serie-atomique/data/775521/events.json) · [Décisions de 775815](serie-atomique/data/775815/events.json)',
        '', '## Les pistes proposées expliquent ce qui a été exploré','']
    for r in primary:
        out.append(f"- **{r['key']} — {LABELS[r['key']]}** : "+'; '.join(c['subject'] for c in r['summary']['forest_plan']['children'])+'.')
    out+=['',
        'Les trois premiers plans proposent explicitement de répartir le calcul des sources entre les lanes d’un warp, puis de réduire les contributions vers une cible. Les quatre suivants se concentrent sur d’autres combinaisons : tuilage, réutilisation par shuffle, plusieurs cibles par thread et arithmétique. La réutilisation de données par shuffle et la réduction parallèle des forces sont des choix différents.',
        '', 'Les sources sélectionnées confirment cette distinction : les trois premiers programmes ont respectivement 16, 8 et 8 cibles par bloc pour 512, 256 et 256 threads ; les quatre suivants conservent autant de cibles par bloc que de threads. Ce constat décrit les programmes obtenus, sans attribuer à lui seul les écarts de performance à une version du moteur.',
        '', '## Ce que la critique du plan a changé dans 780448','',
        'La planification initiale prend **61,42 s** et la critique **65,14 s** de temps natif. La critique conserve trois arbres et resserre leurs objectifs : T1 doit garder une cible par thread avec mémoire partagée ; T2 traite plusieurs cibles par thread sans mémoire partagée ; T3 isole contrôle de boucle et arithmétique. Elle insiste aussi sur l’exclusion de l’auto-interaction pour éviter les valeurs non finies dans le cas de masse extrême.',
        '', 'Cette critique rend les pistes plus distinctes et maintient les contraintes numériques. Elle n’ajoute pas la réduction parallèle des contributions aux forces. S3 ne comporte pas une campagne identique avec cette seule critique désactivée : on ne peut donc pas en déduire son effet causal sur le meilleur temps final.',
        '', '[Réponse de critique et plan révisé](serie-atomique/data/780448/summary.json) · [Tests fonctionnels avant/après de la réserve de critique](../comparaison-historique/RAPPORT.md)',
        '', '## Assemblage : modification, réglage ou copie','',
        '| État | G | Noyau seul | Lancement seul | Noyau et lancement | Copie exacte |',
        '|---|---:|---:|---:|---:|---:|']
    for r in primary:
        g=[t for t in r['trials'] if t['role']=='G'];c=Counter(t['change_kind'] for t in g)
        out.append(f"| {r['key']} | {len(g)} | {c['noyau seul']} | {c['lancement seul']} | {c['noyau et lancement']} | {c['copie exacte']} |")
    out+=['',
        'Dans 772923, le premier G conserve la réduction par warp et ajoute le chargement des sources en mémoire partagée. Le G suivant garde cette structure et remplace la racine suivie d’une division par `rsqrtf` et des produits. Cette seconde transition modifie uniquement le calcul du coefficient d’interaction : le [patch exact](serie-atomique/diffs/772923/63513b28c5484e1e.patch) et les mesures de son parent permettent une comparaison directe.',
        '', 'Dans 774157 et 776290, le dernier G est une copie octet pour octet de son parent pour les deux fichiers autorisés. Il ne reçoit pas une nouvelle mesure indépendante dans le rejeu dédupliqué. Une copie peut servir à confirmer ou livrer un choix ; elle n’est pas une nouvelle optimisation.',
        '', '[Toutes les différences et leurs mesures](tables/comparaison-essais.csv)',
        '', '## Les échecs ne désignent pas tous le même problème','',
        '- **Export de 772923 :** le G est valide et confirmé. L’export échoue ensuite avec `Submission requires a Makefile and run.sh in the imported repository`. Il s’agit d’une exigence de l’ancien exporteur, pas d’un échec CUDA. Les sources et les résultats restent récupérés.',
        '- **Neuf essais incorrects dans S3 :** huit échouent aux comparaisons numériques et un à la compilation NVRTC (`Particle` non défini). Le contrôleur classe ces deux types dans `incorrect`, d’où l’intérêt de lire le diagnostic détaillé.',
        '- **Trois générations refusées dans 775815 :** le message est `Lesson references unseen or unrelated evidence`. Le refus concerne les références des leçons de mémoire. Ces codes n’ont pas nécessairement été évalués et ne sont pas comptés comme programmes numériquement incorrects.',
        '- **Un doublon dans 774157 :** une proposition correspond à un programme déjà rencontré ; ce statut est conservé séparément.',
        '- **S2 / 776290 :** un appel natif tente un outil de collaboration `wait`, sans destinataire. Le contrôle d’accès du moteur rejette la réponse. Le journal contient deux événements (début et fin) pour cette même invocation ; aucun sous-agent n’est observé dans cette trace. Cet incident n’est pas assimilé à une panne SCP.',
        '', 'Six des huit échecs numériques finaux ont une seule composante hors de la tolérance combinée à N=16384, avec des masses préservées. Les deux autres révèlent une erreur de couverture des sorties dans 776048 : `items_per_block=512` annonce 512 cibles, alors que le noyau écrit seulement une cible par thread. À N=257, un seul bloc est lancé. Avec 256 threads, une particule reste sans écriture (7 composantes en désaccord) ; avec 128 threads, 129 particules restent sans écriture (903 composantes). La taille de la tuile de sources a été confondue avec le nombre de cibles écrites.',
        '', '[Cas avec 256 threads](serie-atomique/evidence/776048/logs/e1/87f49c37da994ca1/search/attempt-001/correctness.log) · [Cas avec 128 threads](serie-atomique/evidence/776048/logs/e1/645de581d96d4755/search/attempt-001/correctness.log) · [Erreur de compilation](serie-atomique/evidence/776290/logs/e1/dbbc5eebcbc94010/search/attempt-001/correctness.log)',
        '', 'Le détail contient aussi les tentatives internes `-h01`, `-h02`, etc. : 38 lignes de cas en échec apparaissent dans S3, y compris les réparations et les reprises de vérification. Ce ne sont pas 38 essais distincts. Certains essais finalement valides, notamment dans 772923 et 780448, ont d’abord produit une version rejetée puis réparée. Le premier contrôle de développement réussi clôt cette phase locale ; la vérification officielle et la confirmation restent séparées.',
        '', '[Évaluations](tables/diagnostics-evaluations.csv) · [Cas numériques](tables/diagnostics-cas.csv) · [Appels de S2 / 776290](relance-controlee/data/776290/native-calls.json)',
        '', '## Réparations à l’intérieur d’un essai', '',
        'Les 225 journaux de mission contiennent 313 étapes locales. Dans S3, 212 étapes se répartissent en 136 contrôles de développement réussis, 40 échoués, 24 propositions refusées, 11 lectures mémoire et une lecture documentaire. Une étape de lecture n’est pas une nouvelle proposition de code. Les 24 refus portent tous sur les références des leçons ; seuls trois essais se terminent par un refus de génération.',
        '', '| État | Contrôles locaux réussis | Contrôles locaux échoués | Propositions refusées | Missions réussies après un contrôle échoué |',
        '|---|---:|---:|---:|---:|']
    for key in CONDITIONS:
        attempts=[a for a in local_attempts if a['series']=='atomic' and a['condition']==key]
        missions=[m for m in local_missions if m['series']=='atomic' and m['condition']==key]
        c=Counter(a['state'] for a in attempts)
        out.append(f"| {key} | {c['development_passed']} | {c['development_failed']} | {c['generation_failed']} | {sum(m['passed_after_development_failure'] for m in missions)} |")
    out+=['',
        'Sept missions de S3 atteignent un contrôle réussi après au moins un contrôle échoué. Par exemple, dans 780448 / `2495c63d565b4f3e`, la première proposition annule algébriquement la masse cible et échoue à N=16384. La suivante abandonne cette transformation, conserve le chemin de masse initial et remplace le calcul racine/division par `rsqrtf` ; elle passe. Il s’agit d’un changement d’hypothèse après diagnostic, pas de la validation de la première transformation.',
        '', '[Journal de cet essai](serie-atomique/evidence/780448/logs/2495c63d565b4f3e/node-harness.json) · [Toutes les étapes locales, hypothèses et états](tables/diagnostics-tentatives-locales.csv) · [Résumé par mission](tables/diagnostics-missions-locales.csv)',
        '', 'Les journaux déclarent `holdout_access=false` et `outer_tree_reward_assigned=false` pour cette phase locale : réussir ici ne constitue pas encore une confirmation. Les essais formels et leurs jeux de vérification restent identifiés séparément. Les compteurs de propositions refusées ou de contrôles échoués ne doivent donc pas être ajoutés aux neuf essais finalement incorrects.',
        '', '## Sélections mémoire : décisions acceptées et refusées','',
        '| État | Décisions enregistrées | Refusées |', '|---|---:|---:|']
    for key,c in selection_counts.items():out.append(f"| {key} | {sum(c.values())} | {c.get('rejected',0)} |")
    out+=['',
        'Les refus de sélection sont conservés avec leur message. Par exemple, 775521 tente deux fois de figer des entrées pendant une lecture de sélection, ce que le protocole interdit, avant de fournir une décision acceptée. Ces tentatives consomment des appels et du temps, même si l’assemblage finit ensuite par réussir.',
        '', '[Décisions, sources choisies et justifications](tables/diagnostics-selections.csv)',
        '', '## Transport : ce que les mesures établissent','',
        'La série S2 a sept opérations d’écriture en échec. Ses files d’attente atteignent environ **241 s** et une opération elle-même environ **179 s**. Une campagne peut donc perdre son signal de présence pendant que des réponses existent déjà localement. Le petit test préalable réussi ne prédisait pas cette situation sous charge.',
        '', 'Dans S3, les **1 568 écritures atomiques** réussissent : durée médiane **0,068 s**, 95e percentile **0,348 s**, maximum **1,219 s** ; attente maximale **0,073 s**. Les téléchargements et cinq gros envois SCP réussissent aussi. Les 64 lectures de répertoire en échec précèdent la première apparition réussie des boîtes aux lettres et correspondent à la mise en route. Aucun échec de transfert après mise en route n’est observé dans ce journal.',
        '', 'Cette série utilise à la fois plusieurs connexions persistantes et des écritures atomiques pour les petits messages. Les observations ne séparent pas l’effet de chacun de ces changements. Elles montrent que le transport a été nettement moins contraignant dans S3, sans prouver une robustesse générale sur d’autres charges.',
        '', '[Statistiques de transport](tables/transport-summary.csv) · [Toutes les erreurs et leur contexte](tables/transport-errors.csv)',
        '', '## Un défaut de comptage des jetons reproduit dans les sept moteurs','',
        'La version locale de Codex renvoie les compteurs cumulés du fil dans `turn.completed.usage`. Les moteurs additionnent ces compteurs à chaque reprise de la Mother. Un exemple minimal, exécuté contre leurs sept sources figées, donne 110 jetons au premier appel, puis 165 au total après reprise : les moteurs additionnent 275, alors que le total du fil reste 165.',
        '', 'Les tableaux de cette étude utilisent les différences de compteurs d’un même fil, en gardant les valeurs brutes pour l’audit. Les jetons en cache sont déjà inclus dans l’entrée. Le budget configuré ici observe les jetons sans plafond : cette correction d’analyse ne change pas les décisions des campagnes exécutées. L’effet sous un plafond de jetons n’a pas été testé.',
        '', '[Preuve sur une session réelle](protocol/codex-token-counter-semantics.json) · [Contre-exemple exécuté sur les sept moteurs](protocol/token-counter-regression.json)',
        '', '## Ce qui reste établi par les tests fonctionnels historiques','',
        'Les tests avant/après du premier rapport montrent que les résumés mémoire exposent mieux les résultats mesurés, que le code peut être conservé lorsque des leçons facultatives sont absentes, et que la réserve de critique tient compte du travail d’une forêt provisoire de grande taille. Ces corrections ont un effet fonctionnel vérifié. Elles ne démontrent pas une amélioration systématique du programme CUDA trouvé.',
        '', 'Les campagnes neuves ajoutent un autre niveau de preuve : décisions observées, essais, erreurs, assemblages et confirmations. Le rejeu commun ajoute enfin la comparaison des programmes eux-mêmes. Les trois niveaux sont complémentaires.', '']
    (BASE/'COMPORTEMENTS.md').write_text('\n'.join(out),encoding='utf8')
    write(BASE/'data/behavior-summary.json',{'primary_research_statuses':dict(counts),'primary_research_trials':sum(counts.values()),
        'primary_integration_trials':sum(t['role']=='G' for t in all_trials),'selection_statuses':{k:dict(v) for k,v in selection_counts.items()}})
    print(json.dumps({'report':str(BASE/'COMPORTEMENTS.md'),'research_trials':sum(counts.values()),'integration_trials':15}))

if __name__=='__main__':main()
