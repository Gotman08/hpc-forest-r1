# Résultats réels — Forest, Luna Max et conseiller TabPFN

Le 27 octobre 2026, **les quatre recherches ont livré un programme correct**,
ensuite revérifié et remesuré sur ROMEO avec les entrées prévues et les entrées
réservées. Aucun blocage terminal du contrôleur ni fermeture finale anticipée
pour convergence n'a été observé. **Le bénéfice de TabPFN n'est pas démontré** :
il n'a modifié aucun choix de parent dans ce pilote.

La suite logicielle du moteur gelé compte **1 151 réussites, 0 échec et 3 tests
ignorés** pour des raisons d'environnement. Voir la
[validation complète](../../docs/VALIDATION-REPRISE-20261027.md).

## Résultats des programmes livrés

Les speedups ci-dessous comparent chaque programme à la référence naïve dans
la même remesure. Il s'agit du temps du calcul, pas de la durée de recherche.
La colonne « avec » désigne l'activation du conseiller, pas une intervention
effective de celui-ci.

| Problème | Conseiller | Speedup, entrées prévues | Speedup, entrées réservées | Essais corrects / essais de recherche | Arbres de recherche / profondeur maximale |
|---|---|---:|---:|---:|---:|
| GEMM CPU | Sans | **94,60×** | **71,85×** | 69 / 69 | 3 / 2 |
| GEMM CPU | Avec | **28,18×** | **23,76×** | 38 / 38 | 3 / 2 |
| Black–Scholes | Sans | **14,33×** | **15,76×** | 48 / 48 | 5 / 4 |
| Black–Scholes | Avec | **13,30×** | **14,66×** | 38 / 39 | 4 / 3 |

L'unique essai non correct de Black–Scholes avec conseiller est un échec de
compilation. Aucun échec d'infrastructure candidat n'est enregistré. Les quatre
programmes livrés passent les deux distributions de vérification.

Tous les bras démarrent avec trois arbres. Mother crée ensuite deux arbres
supplémentaires sans conseiller et un avec conseiller sur Black–Scholes. Les
combinaisons intermédiaires sont distinctes de ces arbres : deux dans chacun
des bras GEMM et dans Black–Scholes sans conseiller, trois dans Black–Scholes
avec conseiller. La profondeur indique la filiation mesurée, pas le nombre
d'appels au modèle.

| Problème | Conseiller | Durée de campagne | Durée imputée, plan commun compris | Job de recherche |
|---|---|---:|---:|---:|
| GEMM CPU | Sans | 4 899,23 s | 5 037,76 s | 786457 |
| GEMM CPU | Avec | 4 835,50 s | 4 974,04 s | 786458 |
| Black–Scholes | Sans | 4 855,36 s | 5 068,93 s | 786460 |
| Black–Scholes | Avec | 4 952,82 s | 5 166,39 s | 786459 |

Les plafonds sont égaux, les durées consommées ne le sont pas. La cible est
5 400 secondes de recherche et le plafond imputé de bout en bout 7 200 secondes.
Le temps du plan commun est intégralement imputé à chaque bras : 138,54 secondes
sur GEMM et 213,58 secondes sur Black–Scholes. La remesure comparative externe
est une étape séparée, sans sélection d'un nouveau candidat.

## Ce qui a effectivement été testé

Un seul Forest, avec le contrat `hpc-forest-active-v4-admission-liveness`, le
véritable TreeQuest AB-MCTS-A et la même graine 307. Tous les rôles LLM emploient
**`gpt-6-luna`, effort `max`**, sans mélange de modèles. Les appels OAuth sont
exécutés directement sur ROMEO, sans relais du PC.

L'audit des quatre archives retrouve **515 invocations natives** : 157 pour
GEMM sans conseiller, 93 avec, 136 pour Black–Scholes sans et 129 avec. Toutes
correspondent au modèle, à l'effort et à l'empreinte de la requête d'origine.
Cet audit vérifie les paramètres demandés et transmis au CLI ; il n'inspecte
pas l'implémentation interne du fournisseur et ne signifie pas que chaque appel
a réussi.

Les deux conditions partagent exactement le même moteur et le même plan
initial de Mother par problème. Seul le drapeau d'activation du conseiller
change. Les décisions ultérieures de Mother restent libres et tracées.
Les [reçus de lancement](fresh-launch-receipts.json) attestent des mémoires et
conversations neuves, sans candidat ni exemple du conseiller importé d'une
campagne précédente. Les programmes, les transformations et les décisions
d'arrêt ont été produits par Forest, sans correction manuelle ni suggestion
d'optimisation pendant ces recherches. Les corrections du moteur ont été
effectuées avant le lancement et ses empreintes sont gelées dans le
[protocole](protocol.json).

Les recherches partagent `romeo-c022`, avec des ensembles de CPU logiques
disjoints et cinq CPU alloués par bras. Quatre servent au calcul/contrôleur,
le cinquième au worker du modèle. Les allocations ne sont pas exclusives :
elles ne prouvent ni l'équivalence NUMA ni l'absence d'une charge extérieure.

La remesure commune **786461**, terminée avec succès, s'exécute séquentiellement
sur **`romeo-c023`**, dans une même allocation, sans appel LLM. Chaque
configuration possède cinq échantillons appariés à la référence par taille,
threads, graine, motif et empreinte d'entrée. Cela représente 32 lignes de
configuration et 160 couples d'échantillons pour les quatre candidats et les
deux distributions. Les compilations utilisent le même GCC 14.2.

| Distribution | GEMM CPU | Black–Scholes | Threads |
|---|---|---|---|
| Prévue | n = 384, 768 | n = 32 768, 262 144 | 1 et 4 |
| Réservée | n = 449, 897 | n = 49 153, 393 217 | 1 et 4 |

Les contrôles de correction incluent aussi les petits cas du contrat. Les
entrées réservées sont évaluées après la sélection, sans retour vers la
recherche. Les cinq répétitions temporelles ne sont pas cinq recherches
indépendantes.

## Arrêts et reprise du contrôle

Les quatre résultats terminaux indiquent `final_reserve_or_deadline`, avec
`budget_exhausted` et `forest_closed: false`. La recherche cède donc la place
à la confirmation selon son budget ; aucune clôture finale pour convergence
n'a été validée. Une action `close` acceptée peut demander un drainage et une
revue : elle ne prouve pas, à elle seule, que Forest est fermé.

Deux observations exercent les mécanismes corrigés :

- Sur GEMM sans conseiller, Mother demande `continue Gm1` alors que la limite
  de cette combinaison est atteinte. Forest refuse avec `checkpoint_limit`
  au lieu d'effacer la revue d'inactivité et de se bloquer comme en R2.
- Sur Black–Scholes avec conseiller, une revue d'inactivité ne fournit pas de
  clôture finale valide. Forest rouvre automatiquement T3
  (`idle_review_without_valid_closure`) et poursuit jusqu'à sa réserve finale.

Les protections ont également refusé neuf suspensions après progrès récent
dans GEMM avec conseiller, ainsi que plusieurs demandes fondées sur un état
devenu ancien. Ces refus protègent l'exploration ; ils ne démontrent pas que
les orientations restantes sont optimales.

Les événements complets sont dans [mother-events.csv](results/mother-events.csv)
et [analysis.json](results/analysis.json).

## Analystes et incidents conservés

| Problème | Conseiller | Bilans de code complets | Citations de source | Appels analyste, réussis / total | Appels Mother, réussis / total |
|---|---|---:|---:|---:|---:|
| GEMM CPU | Sans | 25 | 143 | 32 / 32 | 42 / 43 |
| GEMM CPU | Avec | 19 | 87 | 22 / 22 | 25 / 25 |
| Black–Scholes | Sans | 22 | 103 | 34 / 37 | 28 / 30 |
| Black–Scholes | Avec | 21 | 97 | 34 / 34 | 34 / 35 |

Un bilan peut demander plusieurs appels ou lectures. Les citations sont liées
aux sources réellement exposées ; un analyste a notamment demandé une portion
de fichier absente de l'extrait initial. Cette traçabilité ne garantit pas à
elle seule la qualité du raisonnement.

Les quatre appels Mother rejetés concernent deux preuves indisponibles, un
instantané non correspondant et un texte d'action invalide. Les tâches Mother
correspondantes se terminent ensuite correctement. Sur Black–Scholes sans
conseiller, deux lectures d'analyste hors du périmètre visible sont refusées,
puis cette tâche aboutit.

Un autre analyste du même bras dépasse la limite de sortie après **905,56
secondes**. Sa tâche est marquée indisponible ; Forest continue et livre quand
même. L'usage en tokens de cet appel reste inconnu, pas zéro. C'est une faiblesse
résiduelle de coût et de fiabilité, explicitement conservée dans le
[diagnostic](diagnostics/blackscholes-off-output-limit.json).

Les exports `*-control-calls.csv` détaillent chaque appel. Leurs durées peuvent
se chevaucher avec la recherche et ne doivent pas être additionnées à la durée
murale de la campagne.

## Pourquoi ces chiffres ne prouvent pas un effet négatif du classement TabPFN

| Mesure | GEMM avec conseiller | Black–Scholes avec conseiller |
|---|---:|---:|
| Exemples observés | 38 | 39 |
| Sources parentes distinctes, toutes branches confondues | 3 | 12 |
| Occasions avec plusieurs propositions | 20 | 35 |
| Refus avant chargement, contexte indépendant insuffisant | 7 | 7 |
| Appels réels au modèle TabPFN | **0** | **1** |
| Validations acceptées | **0** | **0** |
| Choix de parent modifiés | **0** | **0** |
| Temps cumulé du conseiller | 0,93 s | 8,12 s |

GEMM manque surtout de diversité de parents, pas seulement de nombre de lignes.
La validation par arbre exige des parents distincts entre les données de
contexte et celles de contrôle. Les 38 exemples ne suffisent donc pas à
constituer le contrôle indépendant requis. La prévalidation évite de charger
le modèle inutilement.

Black–Scholes fournit une fois un contexte exploitable : cinq lignes de
contexte issues de quatre parents et six lignes de contrôle issues de trois
autres parents. L'appel dure 5,79 secondes. Son erreur absolue moyenne sur
`log(1 + speedup)` vaut **0,493**, contre **0,378** pour la simple référence
parent. Il ordonne correctement 6 des 11 paires évaluables. Forest rejette
donc sa calibration (`calibration_not_better_than_parent_baseline`) et conserve
la proposition TreeQuest. La marge calculée est empirique, pas un intervalle
de confiance. Les issues des enfants non générés restent inconnues.

Le conseiller n'a ainsi choisi aucun mauvais parent dans ce pilote : il n'en
a changé aucun. Son temps mesuré ne suffit pas non plus à expliquer l'écart
de 69 contre 38 essais sur GEMM. Les réponses LLM, les durées, les choix de
Mother et les trajectoires ont divergé malgré le même plan initial. La graine
TreeQuest commune ne rend pas les appels LLM déterministes. Des effets de
chronologie ou de charge ne sont pas exclus.

## Lecture des programmes produits, après la recherche

Sur GEMM, le [programme sans conseiller](delivered-codes/gemm_cpu-r1-off.cpp)
emploie un micro-noyau de 8 × 16 valeurs, des accumulateurs locaux, un déroulage
de la réduction par quatre et une répartition statique entre threads. Le
[programme avec conseiller](delivered-codes/gemm_cpu-r1-corrected.cpp) travaille
par groupes de huit lignes et met à jour toute la largeur de C à chaque k.
Cette différence de structure est compatible avec l'écart observé, mais son
coût causal précis n'a pas été isolé par ablation ou profilage.

À n = 768 et quatre threads, les moyennes appariées sont **2,03 ms** sans
conseiller contre **7,10 ms** avec. L'écart existe aussi à un thread : **7,91 ms**
contre **28,40 ms**. Il ne se réduit donc pas à un défaut de parallélisme.

Sur Black–Scholes, les deux programmes utilisent un chemin AVX2 et OpenMP,
avec des approximations et contrôles numériques différents. À n = 262 144,
quatre threads, les moyennes sont **0,245 ms** sans conseiller contre
**0,264 ms** avec ; à un thread, **0,973 ms** contre **1,047 ms**. Le programme
du bras avec conseiller est plus lent dans les huit configurations prévues
et réservées, mais l'écart est bien moindre que sur GEMM. Aucune transformation
particulière n'est déclarée responsable sans expérience isolée.

Ces observations sont postérieures à la sélection ; les quatre fichiers livrés
sont des copies inchangées, vérifiées par [SHA-256](delivered-codes/manifest.json).

## Historique et portée de la conclusion

R1 a été interrompue après découverte d'un défaut de schéma de citation. R2,
après sa correction, a livré trois programmes sur quatre et révélé le blocage
de reprise sur GEMM avec conseiller. R3 livre quatre programmes sur quatre
avec la correction de ce blocage. Les tentatives interrompues et échouées
restent conservées et identifiées.

Les remesures R2 et R3 ont utilisé respectivement c022 et c023. Leurs chiffres
historiques ne constituent pas une ablation matérielle et logicielle contrôlée.
Les nouveaux speedups ne prouvent donc pas à eux seuls un gain de l'architecture.
Les tests de régression, le refus réel de `continue Gm1` et la reprise réelle
de T3 constituent les preuves directes du comportement corrigé.

**Ce pilote valide la livraison et les garde-fous ; il ne valide pas un gain
du conseiller.** Une seule recherche par condition et problème ne permet
pas d'attribuer toute la différence à TabPFN, aux données ou à Mother. La
prochaine évaluation de son utilité doit comporter des répétitions indépendantes
et constater d'abord des décisions effectivement acceptées, sans affaiblir la
validation pour forcer son activation.

## Données et reproduction

- [Comparaison compacte](results/comparison.csv), [résultats complets des bras](results/arms.csv),
  [temps par configuration](results/configuration-timings.csv) et
  [échantillons appariés et empreintes](results/configuration-timing-evidence.json).
- [Décisions du conseiller](results/adviser-decisions.csv),
  [motifs de prévalidation](results/adviser-preflight.csv),
  [provenance de cet export](results/adviser-preflight-provenance.json).
- [Résumé Mother](results/mother-control.csv), [trajectoires](results/trajectory.csv),
  [achèvement de la remesure](results/completion.json).
- Audits natifs : [GEMM sans](results/gemm_cpu-off-model-invocations.json),
  [GEMM avec](results/gemm_cpu-corrected-model-invocations.json),
  [Black–Scholes sans](results/blackscholes-off-model-invocations.json),
  [Black–Scholes avec](results/blackscholes-corrected-model-invocations.json).
- Durées des appels : [GEMM sans](results/gemm_cpu-off-control-calls.csv),
  [GEMM avec](results/gemm_cpu-corrected-control-calls.csv),
  [Black–Scholes sans](results/blackscholes-off-control-calls.csv),
  [Black–Scholes avec](results/blackscholes-corrected-control-calls.csv).
- [Archives originales](results/recovered-archives.json),
  [reçu de collecte](results/local-collection.json),
  [contrôle final des empreintes](results/final-verification.json),
  [préparation reproductible](reproduction/prepare_quality_retry_r3.py).

Dans les CSV, `corrected` signifie conseiller activé ; les deux conditions
utilisent le moteur corrigé. Le suffixe `r1` des noms de candidats signifie
répétition 1 de cette tentative R3. Le champ historique `speedup_common` dans
`arms.csv` décrit la confirmation interne ; la comparaison finale utilise
**`registered_speedup` et `reserved_speedup`**. L'export original des décisions
laissait le motif de prévalidation vide : le CSV complémentaire le récupère
depuis `payload.validation.reason`, sans modifier l'événement brut. Les temps
par configuration sont des moyennes arithmétiques d'échantillons ; l'indicateur
global reste celui du protocole gelé.
