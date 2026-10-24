"""Per-program interpretation of measured outputs; never feeds running searches."""
import collections
import json
from pathlib import Path

R=Path(__file__).resolve().parent
O=R.parents[1]/'outputs/architecture-active'


def number(value):
    return f'{value:.5g}' if isinstance(value,(int,float)) else '—'


NOTES={
    'volume':(
        'Les deux versions préparent les facteurs de passage vers les coordonnées de voxels avant le rendu et utilisent un ordonnancement dynamique OpenMP. L’ancien distingue un chemin intérieur sans clamp et un chemin de bord, et distribue les pixels par blocs de 64. Le nouveau utilise trois clamps puis dérive les indices voisins, passe à des blocs de 256 et évite le calcul d’éclairage et de transmittance lorsque la densité locale est nulle. Le gain éventuel ne vient donc pas du seul ajout de parallélisme, déjà présent avant. Le protocole conserve le volume et les transformations de caméra déclarés ; l’audit séparé vérifie aussi les dimensions d’image prises en charge par la référence ISPC.',
        'paired-volume','.cpp'),
    'stencil_y':(
        'Les deux programmes utilisent une tuile partagée de 32×40 valeurs et un bloc de threads 32×16, avec deux sorties par thread. L’ancien traite deux lignes espacées de 16, accepte des dimensions passées en paramètres et calcule les coefficients à partir de la hauteur. Le nouveau traite deux lignes adjacentes, spécialise les dimensions à 64³ et initialise une fois les coefficients en mémoire constante ; les halos utilisent la même convention périodique de période 63. Cette spécialisation correspond au cas fixe testé, mais elle ne valide pas le nouveau programme pour d’autres dimensions. Le chargement des halos, l’adressage et l’écriture de la combinaison arithmétique changent aussi ; la mesure ne sépare pas leurs contributions.',
        'paired-stencil-y','.cu'),
    'aobench':(
        'L’ancien utilise un générateur PCG32 par thread et teste les intersections rayon par rayon, avec arrêt dès qu’un obstacle est trouvé. Le nouveau initialise un état aléatoire par pixel à partir d’une graine de rendu, prépare des tableaux de directions puis teste les sphères et le plan par boucles séparées ; il distribue les pixels par paquets dynamiques de 64. Le générateur et les tirages internes diffèrent donc, même lorsque le pilote reçoit la même graine. Le contrat autorise une équivalence statistique du rendu, contrôlée par une erreur quadratique moyenne et un biais moyen bornés : ce cas ne prouve pas une identité pixel par pixel. Plusieurs changements sont mesurés ensemble, dont la préparation des rayons, le générateur et l’ordonnancement.',
        'paired-aobench','.cpp'),
    'sgemm':(
        'L’ancien charge des tuiles A et B de 64×64 en mémoire partagée, synchronise les threads et calcule seize accumulateurs par thread. Le nouveau calcule huit sorties par thread, réparties sur deux lignes et quatre bandes de colonnes, en lisant directement A et B à chaque pas de réduction, sans tuile partagée. Il dépend donc davantage des caches et de la réutilisation locale aux threads. Le gain éventuel ne peut pas être déduit du seul nombre d’accumulateurs ; les mesures portent sur les matrices carrées du contrat, en FP32 et sans appel à une bibliothèque de multiplication optimisée.',
        'paired-sgemm','.cu'),
    'transpose':(
        'Les deux versions passent par une tuile partagée de 32×33 mots. L’ancien charge des scalaires avec des blocs de threads 32×8 et permute l’ordre des tuiles. Le nouveau charge et écrit quatre mots à la fois avec uint4, utilise des blocs 8×32 et revient à un ordre de tuiles direct. La comparaison agrège donc la vectorisation des accès et la distribution du travail. Le nouveau exploite le contrat de dimensions positives multiples de 32 ; il n’est pas validé ici pour des dimensions arbitraires hors de ce contrat.',
        'paired-transpose','.cu'),
    'stencil3d':(
        'Les deux versions conservent une équipe OpenMP pendant les pas de temps. L’ancien distribue les couples (z, y) par omp for collapse(2), avec des noyaux AVX/SSE écrits en intrinsics. Le nouveau affecte à chaque thread une tranche contiguë de z et utilise des pointeurs restrict ainsi qu’une boucle omp simd, dont le compilateur choisit les instructions. Il ne faut donc pas attribuer un éventuel gain au seul maintien d’une équipe persistante, déjà présent avant : la répartition du domaine et le code vectoriel ont aussi changé.',
        'paired-stencil3d','.cpp'),
    'base64':(
        'Les deux programmes décodent des blocs AVX2 de 32 caractères. L’ancien compacte les valeurs avec des instructions de multiplication-addition puis un mélange des octets. Le nouveau utilise des masques, décalages et opérations OU, et déroule jusqu’à quatre blocs avant de traiter la fin scalaire avec padding. Ce sont plusieurs compromis simultanés ; le déroulage ne garantit pas que le calcul par bloc soit moins coûteux. Le contrat porte sur des entrées Base64 standard valides : réussir ces contrôles ne prouve pas une détection complète des chaînes invalides.',
        'paired-base64','.cpp'),
    'sumabs':(
        'L’ancien remet la sortie à zéro puis accumule atomiquement les sommes de blocs, avec des lectures float4, huit accumulateurs par thread et 512 threads par bloc. Le nouveau écrit des sommes partielles avec des lectures float2 et 128 threads par bloc, puis lance une réduction finale distincte ; il borne le nombre de sommes partielles à 1 024 et spécialise ce cas. Cela remplace les additions atomiques sur la sortie par un second noyau et un tampon de travail. La comparaison mesure cet ensemble de choix ; elle ne permet pas d’isoler le coût des atomiques, de la vectorisation et des lancements.',
        'paired-sumabs','.cu'),
    'noise':(
        'L’ancien partage les premiers niveaux de la table de permutation entre les huit coins, mais recalcule les coordonnées de cellule et les poids à chaque pixel et octave. Le nouveau prépare séparément ces états pour les axes x, y et z, puis les réutilise dans la boucle des pixels. Les vecteurs de préparation sont alloués et remplis à chaque appel, donc leur coût fait partie du chronométrage ; il ne s’agit pas d’un cache conservé entre deux tests. L’écriture de l’interpolation diffère également, ce qui reste soumis à la tolérance du contrôle protégé. Sans ablation, le gain éventuel ne peut pas être attribué à une seule de ces modifications.',
        'paired-noise','.cpp'),
    'softmax':(
        'L’ancien utilise systématiquement une réduction en ligne par morceaux, puis relit les valeurs pour produire la sortie. Le nouveau calcule directement les lignes de largeur modérée et conserve un noyau par morceaux pour les lignes très larges ; il ajoute aussi des chemins de repli et la gestion du calcul en double précision. La remesure de la forme chronométrée ne départage pas nettement les deux versions : la plage des rapports entre blocs traverse 1. Davantage de chemins pris en charge ne constitue pas à lui seul un gain de vitesse sur cette entrée.',
        'paired-extra-softmax','.py'),
    'popcount':(
        'Les deux versions conservent le même déroulage de quatre éléments, la même dépendance au résultat précédent et un builtin de comptage de bits. La nouvelle nettoie les includes et enveloppe le builtin dans une fonction inline. Les fichiers sources diffèrent, mais les binaires comparés sont identiques, séparément avec GCC et Clang. Les rapports très proches de 1 sont donc des variations de mesure, pas un progrès algorithmique.',
        'paired-popcount-gcc','.cpp'),
    'binomial':(
        'L’ancien calcule une somme pondérée des valeurs terminales avec une récurrence des poids, linéaire dans le nombre de niveaux. Le nouveau conserve une récurrence triangulaire de remontée, quadratique dans ce nombre, mais vectorise huit options indépendantes et prépare les puissances et poids. Cette différence est algorithmique, pas seulement une taille de bloc. La vectorisation ne garantit donc pas une diminution du travail total. Le plan initial de Mother impose explicitement de conserver la formulation ou l’ordre de remontée dans plusieurs pistes ; aucune nouvelle branche de reformulation n’a été créée. La couverture des idées est donc une limite observable de cette recherche, même si les combinaisons intermédiaires fonctionnent.',
        'paired-binomial','.cpp'),
    'raytracer':(
        'Le nouveau distingue les rayons dont toutes les directions inverses sont finies, utilise pour eux un test de boîte spécialisé avec sorties anticipées, ajoute des indications de branchement et précharge le triangle suivant. Il conserve un chemin générique pour les directions inverses non finies. L’ancien et le nouveau distribuent le rendu par paquets de deux lignes avec OpenMP. Les différences mesurées agrègent donc surtout plusieurs modifications du parcours BVH et des intersections ; aucun profil matériel ne les départage ici.',
        'paired-raytracer','.cpp'),
    'blackscholes':(
        'Le nouveau chemin multithread emploie SSE2 pour calculer quatre options ensemble, avec des approximations polynomiales de log/exp et un retour scalaire hors de leur domaine. Le chemin à un thread reste scalaire. Cela concorde avec le gain marqué à quatre threads et le faible écart à un thread. À quarante threads, les blocs se recouvrent : le rapport central seul ne permet pas de conclure. La correction est celle des tolérances du contrat, pas une identité bit à bit pour toute entrée réelle possible.',
        'paired-blackscholes','.cpp'),
    'gemm_cpu':(
        'L’ancien utilise un micro-noyau AVX-512 8×32 directement sur les matrices. Le nouveau emploie un noyau 8×16 et, à partir de n=256, copie A et B en panneaux avec des blocs de 128 sur les dimensions k et n. Il ajoute donc une organisation des accès mémoire, mais aussi des copies et des synchronisations OpenMP. Les mesures par taille et par nombre de threads sont nécessaires pour juger le compromis ; le seul ajout de packing ne garantit pas un gain.',
        'paired-gemm-cpu','.cpp'),
    'mandelbrot':(
        'L’ancien traite des blocs de 128 pixels avec des boucles marquées omp simd. Le nouveau déroule explicitement huit orbites avec un indicateur actif pour chacune. Les deux répartissent les lignes avec OpenMP en ordonnancement dynamique. Ce changement échange une structure propice à la vectorisation contre un déroulage scalaire explicite ; la source seule ne permet pas de déduire les instructions effectivement émises ni leur coût.',
        'paired-mandelbrot','.cpp'),
    'deferred':(
        'Le nouveau programme prépare les propriétés des lumières dans un cache local à la tuile, parallélise les lignes du premier niveau de bornes Z et passe à un ordonnancement dynamique des tuiles de rendu. L’ancien utilisait un ordonnancement statique pour ces tuiles. Le gain à un thread indique que le seul parallélisme ne suffit pas à expliquer toute la différence ; aucune ablation ne sépare ici les effets du cache de lumières et de l’ordonnancement.',
        'paired-deferred','.cpp'),
    'argmin':(
        'Le nouveau code calcule d’abord le minimum avec AVX-512, puis recherche son premier indice dans un second parcours vectorisé. L’ancien procède par blocs et retrouve l’indice dans le bloc gagnant. La longueur du second parcours du nouveau dépend de la position du minimum : c’est une explication plausible du contraste entre les entrées aléatoires et décroissantes. Les mesures établissent le contraste ; elles n’isolent pas le coût de chaque instruction.',
        'paired-cpu-argmin','.cpp'),
    'reduction':(
        'Pour la taille chronométrée de 2^22 entiers, le nouveau programme remet la sortie à zéro puis lance 512 blocs au plus, avec accumulation par thread, réduction de warp et addition atomique par bloc. L’ancien réalise plusieurs étages de réduction par tuiles de 128 éléments. Le nombre de lancements et la répartition du travail changent donc réellement. Le gain mesuré est cohérent avec ce changement ; aucun profil matériel ne permet ici d’attribuer une fraction précise du gain à chaque mécanisme. Le vainqueur vient d’un arbre de recherche, pas de Gm1.',
        'paired-extra-reduction-s4convd','.cu'),
    's4convd':(
        'Le programme ancien conserve quatre accumulateurs pour les calculs forward et gradient d’entrée, et découpe le gradient du noyau en tuiles avec une réduction finale. Le nouveau conserve des boucles plus simples pour les deux premiers calculs et regroupe quatre coefficients par bloc pour le troisième. Les deux programmes passent les contrôles, mais le nouveau est moins rapide dans cette comparaison. Le parallélisme et les chaînes de dépendances constituent des pistes d’explication, pas une attribution démontrée sans profilage.',
        'paired-extra-reduction-s4convd','.cu'),
    'utf8':(
        'Les deux versions utilisent SSE2. L’ancien déroule deux blocs de 16 octets et vérifie les restrictions de second octet par opérations vectorielles. Le nouveau traite un bloc à la fois et inspecte certaines restrictions par une boucle sur les positions concernées. Les deux passent 79 729 chaînes de contrôle. La boucle supplémentaire est une hypothèse pour la régression sur le mélange UTF-8 chronométré ; elle n’est pas un défaut de correction.',
        'paired-utf8','.cpp'),
}


def main():
    data=json.loads((O/'RESULTATS.json').read_text(encoding='utf8'))
    engines={(e['period'],e['case_id']):e for e in data['engines']}
    lines=['# Diagnostic des recherches et des programmes livrés','',
        'Ce document distingue les faits mesurés, les décisions de la forêt et les hypothèses tirées des sources. Il est rédigé après les recherches concernées et n’est pas transmis aux modèles des campagnes en cours.','',
        'Le rapport actif / ancien est le temps ancien divisé par le temps nouveau, remesurés dans la même allocation. Une valeur supérieure à 1 favorise le nouveau. Une campagne réussie par programme ne suffit pas à attribuer un gain à l’architecture : le choix initial de Mother et les générations sont également variables.','',
        'Les analystes influencent certains essais par leurs avis, mais leurs opinions ne sont jamais des récompenses. Les liens avis → essai et décision → combinaison prouvent une utilisation du mécanisme ; ils ne prouvent pas que cet avis était nécessaire au gain. Une ablation avec plusieurs recherches indépendantes serait nécessaire pour établir cet effet.','']
    completed = [e for e in data['engines'] if e['period']=='new' and e['pipeline_complete']]
    historical = [e for e in data['engines'] if e['period']=='old']
    old_tokens = sum(e['native_usage_normalized']['known_tokens_normalized'] for e in historical)
    new_tokens = sum(e['native_usage_normalized']['known_tokens_normalized'] for e in completed)
    control_tokens = sum((e.get('active_summary') or {}).get('known_tokens',0) for e in completed)
    unknown_usage = sum(e['native_usage_normalized']['unknown_invocation_usage'] for e in historical + completed)
    complete_keys = {e['case_id'] for e in completed}
    research = [t for t in data['trees'] if t['period']=='new' and t['case_id'] in complete_keys and t.get('kind')!='intermediate_integration']
    observed = sum(bool(t.get('analyst_calls')) for t in research)
    combinations = [t for t in data['trials'] if t['period']=='new' and t['case_id'] in complete_keys and t['kind']=='intermediate_integration']
    beating_incumbent = [t for t in combinations if t.get('correct') and (t.get('speedup_over_incumbent_before_measurement') or 0)>1]
    all_suspended = [e['case_id'] for e in completed if e['all_research_trees_suspended_at_end'] and not e['explicit_research_closure']]
    lines += ['## Bilan transversal','',
        f"L’ancienne série archive {sum(e['total_trials'] for e in historical)} essais, dont {sum(e['correct_trials'] for e in historical)} corrects ; la nouvelle en archive {sum(e['total_trials'] for e in completed)}, dont {sum(e['correct_trials'] for e in completed)} corrects. Le taux de correction décrit les essais admis et ne mesure pas à lui seul la qualité de l’exploration : un système peut produire moins d’erreurs en explorant moins de pistes.", '',
        f"Les tentatives retenues comptent {old_tokens:,} tokens vérifiables pour l’ancienne série et {new_tokens:,} pour l’active, dont {control_tokens:,} pour l’analyse et le pilotage. {unknown_usage} invocations de ces deux séries retenues ont une consommation inconnue. Ces compteurs incluent le contexte traité et ne sont pas un prix facturé ; les appels et tokens en cache restent détaillés dans les reçus. Les coûts des échecs et des pilotes s’ajoutent séparément. Une allocation plus courte ne signifie donc pas nécessairement moins de travail modèle.", '',
        f"Sur les {len(completed)} campagnes terminées, {observed} / {len(research)} arbres de recherche ont effectivement reçu au moins un appel d’analyste. Les comptes ci-dessous concernent les tentatives retenues ; les échecs et leurs coûts restent séparément visibles.",'',
        f"Les {len(combinations)} essais de combinaison intermédiaire comprennent {sum(bool(t.get('correct')) for t in combinations)} programmes corrects et {len(beating_incumbent)} essais plus rapides que le meilleur candidat connu avant leur mesure exploratoire. Une combinaison qui améliore seulement ses propres sources peut encore rester derrière un autre arbre. Ces mesures exploratoires ne remplacent pas la confirmation finale.",'',
        'Campagnes terminées avec tous les arbres suspendus et sans fermeture explicite : '+(', '.join(all_suspended) or 'aucune')+'. Le contrôleur termine alors les travaux admis puis passe à la livraison. Il faut distinguer ce comportement du simple épuisement du budget nominal.','',
        '| Programme | Temps utilisé / budget nominal | Essais corrects / total | Appels analyse et pilotage | Tokens de contrôle connus | Tokens totaux connus |',
        '|---|---:|---:|---:|---:|---:|']
    for e in sorted(completed, key=lambda x:x['case_id']):
        a=e.get('active_summary') or {}
        lines.append('| '+' | '.join([e['case_id'],f"{100*e['elapsed_seconds']/e['target_seconds']:.1f} %",
            f"{e['correct_trials']} / {e['total_trials']}",str(a.get('control_calls',0)),str(a.get('known_tokens',0)),
            str(e['native_usage_normalized']['known_tokens_normalized'])])+' |')
    lines += ['', 'La fraction de temps peut dépasser 100 % lorsque la politique termine les travaux déjà admis et la confirmation. Les tokens connus n’incluent pas les consommations inconnues signalées dans les fiches ; les temps de phases se chevauchent et ne sont pas additionnables.','',
        'Les limites observées concernent donc aussi le pilotage : couvrir les arbres avant de les fermer, préserver des pistes de reformulation, et juger une combinaison contre le meilleur candidat disponible. Le fonctionnement des analystes et de Mother est établi ; leur bénéfice net varie selon le programme. Pour attribuer un gain à une composante, une étude suivante devrait répéter les recherches avec plusieurs initialisations, modes historique/observation/actif et budgets identiques, en comptant aussi le coût des analyses. Cette ablation n’a pas été exécutée dans cette campagne.','']
    native_failures = [r for r in json.loads((R/'infrastructure-retries.json').read_text(encoding='utf8'))
                       if not r.get('environment_changed')]
    lines += [f"La fiabilité des sorties de Mother est une autre limite mesurée : {len(native_failures)} tentatives ont été relancées après une sortie native incomplète sans reçu de fin de tour. Ces appels ne sont pas rejoués dans la même conversation. Les réponses plus courtes et la gestion explicite de leur limite sont des pistes à tester séparément ; changer ce comportement au milieu de la présente série aurait rompu le gel du moteur. Les tentatives ratées restent incluses dans le bilan de ressources.", '']
    for key in sorted({r['case_id'] for r in data['rows'] if r.get('case_id')}):
        lines += ['## '+key,'']
        old,new=engines.get(('old',key)),engines.get(('new',key))
        if not new or not new['pipeline_complete']:
            lines += ['La nouvelle campagne n’a pas encore produit de livraison confirmée dans ce dossier. Aucun résultat intermédiaire n’est présenté comme un résultat final.','']
            continue
        rows=[r for r in data['rows'] if r.get('case_id')==key]
        measured=[r for r in rows if r.get('new_vs_old') is not None]
        if measured:
            lines += ['| Observation | Entrée n | Threads CPU | Ancien (ms) | Actif (ms) | Actif / ancien | Plage des blocs | Verdict |',
                      '|---|---:|---:|---:|---:|---:|---:|---|']
            for row in measured:
                values=[row['id'],str(row['n']),str(row['threads']) if row['threads'] is not None else 'GPU',number(row['old_selected']['seconds']*1000),number(row['new_selected']['seconds']*1000),
                        number(row['new_vs_old']),number(row['new_vs_old_min'])+'–'+number(row['new_vs_old_max']),row['verdict']]
                lines.append('| '+' | '.join(values)+' |')
            lines += ['']
            scaling = {}
            for row in measured:
                if row.get('threads') is not None:
                    identity = tuple(row.get(k) for k in ['comparison_job','n','pattern','aggregation'])
                    scaling.setdefault(identity, {}).setdefault(row['threads'], row)
            scaling_rows = []
            for group in scaling.values():
                if 1 not in group or len(group) < 2:
                    continue
                serial = group[1]
                for threads, row in sorted(group.items()):
                    if threads == 1:
                        continue
                    scaling_rows.append('| '+' | '.join([str(row['n']),str(threads),
                        number(serial['old_selected']['seconds']/row['old_selected']['seconds']),
                        number(serial['new_selected']['seconds']/row['new_selected']['seconds'])])+' |')
            if scaling_rows:
                lines += ['Passage de 1 à plusieurs threads, sur les mêmes entrées et dans la même allocation :', '',
                    '| Entrée n | Threads | Ancien : temps 1 thread / temps parallèle | Actif : temps 1 thread / temps parallèle |',
                    '|---|---:|---:|---:|', *scaling_rows, '',
                    'Ces rapports décrivent la mise à l’échelle de chaque programme. Ils ne sont pas les speedups contre le naïf. Une augmentation du nombre de threads ne garantit pas un gain proportionnel ; ordonnancement, synchronisation, mémoire et partage du nœud peuvent intervenir. Cette campagne ne comporte pas le profilage nécessaire pour attribuer une mauvaise mise à l’échelle à une cause précise.', '']
            if len({row['n'] for row in measured if row.get('threads') is not None}) > 1:
                lines += ['Les lignes CPU de ce programme emploient plusieurs tailles d’entrée, reprises du tableau historique. Leurs temps bruts ne constituent pas une mesure de mise à l’échelle à problème constant. Le tableau de mise à l’échelle ci-dessus ne rapproche que les lignes de même taille, même motif, même agrégat et même allocation.', '']
        else:
            lines += ['La recherche est confirmée ; la remesure appariée est encore en attente.','']
        active=new.get('active_summary') or {}
        research_trees=[t for t in data['trees'] if t['period']=='new' and t['case_id']==key and t.get('kind')!='intermediate_integration']
        unobserved=[t['role'] for t in research_trees if not t.get('analyst_calls')]
        lines += [f"Couverture des analystes pendant la recherche : {len(research_trees)-len(unobserved)} / {len(research_trees)} arbres de recherche ont eu au moins un appel. Arbres sans appel : "+(', '.join(unobserved) or 'aucun')+'. Une fermeture ou le budget peut arrêter la recherche avant le premier bilan d’un arbre ; la présence du rôle ne vaut pas preuve de couverture complète.','']
        case_trees=[t for t in data['trees'] if t['period']=='new' and t['case_id']==key]
        lines += ['| Arbre | Essais corrects / total | Appels analyste | Meilleur objectif de recherche (ms) | Génération cumulée (s) | Compilation (s) | Contrôle (s) | Mesure (s) |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|']
        for t in case_trees:
            best=t.get('best_search_seconds')
            lines.append('| '+' | '.join([t['role'],f"{t['correct_trials']} / {t['trials']}",str(t['analyst_calls']),
                number(best*1000 if best is not None else None),number(t.get('generation_wall_sum')),
                number(t.get('compilation_wall_sum')),number(t.get('correctness_wall_sum')),number(t.get('measurement_wall_sum'))])+' |')
        lines += ['', 'Ces temps d’objectif sont les mesures exploratoires du contrat, pas les remesures appariées ci-dessus. Les durées de travail sont cumulées par arbre et ne s’additionnent pas à la durée murale de la campagne.','']
        for t in case_trees:
            subject=str(t.get('subject') or '').replace('\n',' ').replace('|',' / ')
            lines.append(f"- **{t['role']}** : {subject}")
        lines += ['']
        lines += [f"Mother a lancé {new['initial_trees']} arbres initiaux, puis créé {new['created_trees']} arbres ou combinaisons. {new['correct_trials']} essais sur {new['total_trials']} sont corrects. {active.get('control_calls',0)} appels d’analyse/pilotage ont produit {active.get('applied_actions',0)} actions appliquées ; {new['trials_with_analyst_or_mother_advice']} essais portent la provenance d’un avis et {new['trials_with_explicit_imports']} celle d’un import explicite.",'']
        if old:
            lines += [f"La durée réelle passe de {number(old['elapsed_seconds'])} à {number(new['elapsed_seconds'])} secondes, avec un budget nominal conservé de {new['target_seconds']} secondes. L’ancienne recherche comptait {old['correct_trials']} essais corrects sur {old['total_trials']}. Ces durées incluent des étapes qui se chevauchent ; la vitesse du code livré est une autre mesure.",'']
        if key == 'volume':
            lines += ['Un exemple concret de réutilisation d’une idée issue d’un programme plus lent apparaît ici. Le candidat T2 `6ee6084606d44971`, correct et mesuré à 5,54319 s, proposait de réduire les clamps dans Density. Mother l’a combiné avec Gm1 `91429a7d2ad74de9`, mesuré à 0,23523 s. Le programme G `8fdbf80fa1554618` a obtenu 0,22568 s en recherche, puis 0,22597 s lors de sa confirmation indépendante. Le diff entre les commits `ced00c4` et `ab87e45` ne change que le chargement des voisins dans Density et supprime son ancien helper D. Les identifiants et mesures sont dans ESSAIS.csv. Cette filiation atteste la réutilisation de l’idée ; elle n’isole pas l’effet causal d’un avis d’analyste ni celui de toute l’architecture.', '']
        usage=new['native_usage_normalized']
        failed_calls=[c for c in data['calls'] if c['case_id']==key and c['status']=='failed']
        if failed_calls:
            reasons=collections.Counter(c.get('error') or 'Motif non renseigné' for c in failed_calls)
            lines += [f"{len(failed_calls)} réponses d’analyse/pilotage ont échoué à la validation ou au transport dans cette tentative. Motifs enregistrés : "+'; '.join(f'{reason} ({count})' for reason,count in reasons.items())+'.','']
        lines += [f"Coût connu de cette tentative : {usage['native_invocations']} invocations natives, {usage['known_tokens_normalized']:,} tokens vérifiables, {usage['unknown_invocation_usage']} invocations à consommation inconnue. L’analyse et le pilotage représentent {active.get('known_tokens',0):,} tokens connus. Les tentatives échouées ne sont pas incluses dans ce chiffre et restent dans `TENTATIVES-PREALABLES.csv`.",'']
        if new['all_research_trees_suspended_at_end'] and not new['explicit_research_closure']:
            lines += ['Mother a suspendu tous les arbres de recherche. Après la fin des travaux déjà admis, le moteur a poursuivi l’assemblage et la confirmation. Ce fait explique une fin anticipée possible ; le statut brut `budget_exhausted` ne doit pas être interprété seul comme un épuisement du temps.','']
        elif new['explicit_research_closure']:
            lines += ['Mother a demandé explicitement la fermeture des nouvelles admissions. Les travaux déjà admis ont été terminés avant l’assemblage et la confirmation.','']
        actions=collections.Counter(d['kind'] for d in data['decisions'] if d['case_id']==key and d['status']=='applied')
        lines += ['Actions appliquées : '+(', '.join(f'{k} : {v}' for k,v in sorted(actions.items())) or 'aucune')+'.','']
        gm=[t for t in data['trials'] if t['period']=='new' and t['case_id']==key and t['kind']=='intermediate_integration']
        if gm:
            lines += ['| Combinaison | Correcte | Temps exploratoire (ms) | Gain sur sa meilleure source | Gain sur le meilleur disponible |',
                      '|---|---|---:|---:|---:|']
            for t in gm:
                lines.append('| '+' | '.join([t['role'],'Oui' if t['correct'] else 'Non',number(t['seconds']*1000 if t.get('seconds') else None),
                    number(t.get('speedup_over_best_declared_source')),number(t.get('speedup_over_incumbent_before_measurement'))])+' |')
            lines += ['', 'Ces valeurs sont les évaluations de recherche, sans se substituer aux temps de confirmation ou aux mesures appariées. Un gain supérieur à 1 améliore la référence indiquée.','']
        if key in NOTES:
            note,stem,suffix=NOTES[key]
            lines += ['Lecture des sources : '+note,'',
                f"Sources auditées : [ancienne](mesures/{stem}/{key}/old_selected/candidate{suffix}) et [nouvelle](mesures/{stem}/{key}/new_selected/candidate{suffix}).",'']
        lines += ['Les sujets de chaque arbre, diagnostics, coûts et filiations sont dans [ARBRES.csv](ARBRES.csv), [ESSAIS.csv](ESSAIS.csv), [DECISIONS.csv](DECISIONS.csv) et [CHRONOLOGIE.csv](CHRONOLOGIE.csv).','']
    (O/'ANALYSE.md').write_text('\n'.join(lines),encoding='utf8')
    print('Per-program analysis generated from',data['summary']['new_finished'],'completed campaigns')


if __name__=='__main__':
    main()
