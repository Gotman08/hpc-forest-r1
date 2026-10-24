# Validation du premier lot d'analystes — 24 octobre 2026

Cette validation porte sur l'identité du modèle, le fonctionnement des analystes
et leur isolement vis-à-vis de la recherche. Les compilations et confirmations
de contrôle utilisent une petite campagne C locale sous Windows/Python 3.13.
Les générations de recherche de cette campagne sont simulées ; les appels de
ses analystes à Codex sont réels et hébergés. Ce contrôle ne mesure pas un nouveau
speedup CUDA sur ROMEO.

## Contrôles automatisés

Les contrôles requis sont `python -m pytest` et `python -m ruff check src tests`.
Le [reçu des tests](evidence/observer-tests-20261024.json) conserve les comptes,
les empreintes des rapports JUnit et celle du manifeste des sources.

| Passage | Résultat |
| --- | --- |
| Suite complète sur sources de production figées | 844 cas : 842 réussites, 2 échecs |
| Recontrôle complet de `test_controls.py` et `test_mother_conversation.py` | 52 réussites, aucun échec |
| Couverture finale, avec le dernier résultat de chaque cas | 844 cas distincts réussis, aucun saut |
| Ruff (`src`, `tests` et `tools/native_smoke.py`) | réussi |

Le premier échec du passage figé concernait un arrêt de processus Windows en
4,83 s au lieu des moins de 4 s exigées. Le processus était bien interrompu.
Le même test repasse isolément en 0,45 s, avec le même seuil et sans modification
du code d'arrêt des processus. Cet incident de durée n'a donc pas été reproduit
pendant le recontrôle.

Le deuxième venait du double natif de test : sa barrière de dix secondes imposait
une synchronisation à chaque génération. Une branche attendant la mesure de son
précédent essai arrivait 17,63 s après l'autre. Le double vérifie maintenant
uniquement le démarrage simultané des arbres. Le test de reprise invalide ensuite
cette barrière et exige que les générations suivantes progressent indépendamment.
Les assertions sur la conversation Mother, le nombre d'appels, les checkpoints
et la fusion restent contrôlées. L'ordonnanceur de production n'est pas modifié.

Les 63 modules de production sont restés identiques entre le passage figé et le
recontrôle. Les 52 cas relancés incluent les deux échecs, ainsi que les autres
tests des deux modules concernés ; ils ne représentent pas 52 nouveaux cas.

Le test de non-interférence réalise une recherche avec compilation C, TreeQuest,
réparations, fusion et confirmation, puis compare les tables `metadata`, `trees`,
`slots`, `trials`, `evaluations`, `events` et `memory_facts` avant et après analyse.
Il vérifie aussi l'identité du gagnant et l'absence de nouveaux appels de recherche.
Les analystes restent hors du chemin du contrôleur et de son ordonnanceur.

Les tests couvrent les références à un autre arbre, les preuves altérées, les
lectures paginées, les chemins refusés, les réponses d'une autre requête, les
appels d'outils interdits, le dernier appel réservé au bilan, les interruptions,
la reprise sans répétition et les verrous de lecture Windows transitoires.

La construction avec `uv build --wheel` réussit. Les **63 modules Python** de la
wheel ont été comparés octet par octet avec les sources locales.

## Appels natifs

Le [reçu synthétique](evidence/observer-native-20261024.json) conserve les
empreintes des requêtes et réponses, les identifiants des contextes natifs, les
paramètres de modèle, la couverture et les bilans produits.

| Mesure | Résultat |
| --- | --- |
| Modèle demandé à chaque appel | `gpt-6-luna` |
| Effort à chaque appel | `max` |
| Arbres de recherche / analystes | 2 / 2 |
| Appels natifs | 6 : deux lectures puis un bilan par arbre |
| Contextes natifs éphémères distincts | 6 |
| Bilans structurés valides | 2 |
| Appels d'outils observés | 0 |
| Tokens exacts de ce contrôle réussi | 68 191 |
| Appels de consommation inconnue | 0 |
| Durée cumulée des appels | 93,81 s |
| Reprise du même dossier | aucun nouvel appel ; empreintes des réponses identiques |

T1 a reçu les résumés de quatre preuves (référence, essai et deux tentatives de
développement) ; T2 en a reçu trois. Chacun a effectué deux lectures détaillées.
La consultation du catalogue ne constitue pas une lecture intégrale de tous
les fichiers : les lectures et leurs offsets sont enregistrés dans le reçu.

Les bilans restent des interprétations du modèle, avec observations citées,
hypothèses non testées, tests proposés et conditions d'arrêt. Leur validation
structurelle ne prouve pas qu'une hypothèse augmentera les performances.

## Corrections issues des essais

Un premier contrôle natif a montré qu'un rappel dans le prompt ne suffisait pas
à réserver le dernier appel au bilan. Le schéma natif de ce dernier appel
n'autorise désormais que `action = report`. Un autre contrôle a rencontré un
verrou bref de lecture sur `state.json` sous Windows : la sauvegarde de
l'observation réessaie désormais de façon bornée, sans répéter l'appel du modèle.
Ces protections ont leurs tests de régression. Le reçu ci-dessus correspond au
contrôle réussi après ces corrections, et son coût n'inclut pas les essais
précédents conservés localement dans `artifacts/observer-validation/`.

Pendant le premier passage complet des tests, des ajustements des sources ont
déclenché deux arrêts pour changement d'empreinte du moteur. Cette protection
n'a pas été désactivée : la vérification finale utilise des sources figées.
Les anciens tests du choix implicite du modèle ont aussi été adaptés au nouveau
contrat explicite Luna Max.

## Image

L'image fournie a été copiée sans modification dans
`docs/images/forest-architecture-proposee.png` et liée depuis le README.
SHA-256 identique au fichier original :
`60dcc71c0a1c58825d8e0d2bebf9fa7031679139e016c511daf4da8205a63504`.

Le [mode d'emploi](ANALYSTES-OBSERVATION.md) distingue l'observation actuelle
des retours vers Mother et combinaisons intermédiaires proposés pour la suite.
