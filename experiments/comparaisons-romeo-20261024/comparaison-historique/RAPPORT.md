# Comparaison historique — HPC Forest / CUDA N-body

Étude du 23/10/2026 à 12:17, heure de Paris. Dépôt observé au commit `934627c1399b48e4aa0f25630e9c4223680a3511`.

## Résultat et périmètre

L’étude reconstruit **19 commits**, **7 campagnes**, **138 essais de recherche ou d’assemblage** et **124 programmes distincts octet pour octet**, retrouvés dans **152 évaluations valides**. Les programmes lents sont inclus. Les essais incorrects et les incidents restent dans l’historique. Aucune source d’une évaluation valide ne manque.

**Trois types de preuves sont séparés :** les campagnes historiques avec leurs décisions, les nouvelles exécutions GPU de leurs programmes, et les vérifications fonctionnelles des versions du moteur. Les tests du moteur ne sont pas de nouvelles recherches de 30 minutes avec Mother. Les relances GPU n’appellent aucun modèle.

Les **124/124 programmes** ont une mesure complète sur le job ROMEO **780574**. Le plus rapide du rejeu est `76ae01a77792ba54` : **0,099979 ms**, soit **18,55×** la référence remesurée. Son origine : campagne(s) 776048.

Chaque programme est vérifié sur les 11 cas de recherche et les 11 cas de confirmation. Les temps proviennent de cinq répétitions fraîches ; chaque répétition agrège trois tailles. Une référence supplémentaire est mesurée au début et à la fin de chaque bloc.

## Comparaison des gagnants historiques

Le choix du gagnant de chaque campagne est conservé. Il n’est pas remplacé a posteriori par un candidat favorisé par les nouvelles mesures. Les valeurs ci-dessous sont des moyennes en millisecondes ; plus petit est meilleur.

| Campagne | N | Recherche : essais / valides | Durée historique | Confirmé historique (ms) | Rejeu commun (ms) | Accélération du rejeu |
|---|---:|---:|---:|---:|---:|---:|
| 772923 | 4 | 12 / 12 | 21 min 30 s | 0,112061 | 0,112097 | 16,55× |
| 774157 | 3 | 18 / 17 | 25 min 06 s | 0,118800 | 0,118485 | 15,66× |
| 775521 | 3 | 3 / 2 | 14 min 53 s | 0,698771 | 0,694817 | 2,67× |
| 775815 | 3 | 24 / 22 | 25 min 29 s | 0,523785 | 0,524202 | 3,54× |
| 776048 | 4 | 31 / 28 | 27 min 07 s | 0,099877 | 0,099979 | 18,55× |
| 776290 | 4 | 27 / 24 | 28 min 20 s | 0,853836 | 0,851464 | 2,18× |
| 780448 | 3 | 8 / 4 | 23 min 23 s | 1,009931 | 1,004113 | 1,85× |

## Stabilité et détail des nouvelles mesures

Les **630 échantillons** et **1890 temps par taille** ont été recalculés depuis les journaux. Les **2750 contrôles de cas** incluent la référence de contrôle supplémentaire ; les 124 programmes historiques représentent 2 728 contrôles. Aucun résultat incorrect ni mesure manquante dans ce rejeu.

La référence de contrôle varie de **1,853883 à 1,856035 ms**, soit une étendue de **0,116 %** de sa moyenne. Le coefficient de variation médian des programmes est de **0,339 %** ; le maximum est de **1,301 %**. Ces valeurs décrivent la dispersion du chronométrage, pas la probabilité de réussite d’une recherche.

Le premier programme est premier dans quatre blocs sur cinq. Son prédécesseur gagne le quatrième bloc. Les intervalles min–max des deux meilleurs se recouvrent : leur faible écart ne mérite pas la même confiance que les grandes accélérations.

| Rang moyen | Programme | Moyenne (ms) | Min–max (ms) | Écart-type (ms) | Accélération |
|---|---|---:|---:|---:|---:|
| 1 | `76ae01a77792ba54` | 0,099979 | 0,099298–0,100413 | 0,000482 | 18,55× |
| 2 | `730dbea752a62077` | 0,100599 | 0,099876–0,101100 | 0,000463 | 18,44× |
| 3 | `4704be25d1320417` | 0,112097 | 0,111070–0,113168 | 0,000911 | 16,55× |
| 4 | `50e73c61acbe8f6d` | 0,118485 | 0,117800–0,118898 | 0,000457 | 15,66× |
| 5 | `8aa85299cbd8681c` | 0,132798 | 0,132094–0,133319 | 0,000501 | 13,97× |
| 6 | `46949a163efb77f5` | 0,133071 | 0,132265–0,133885 | 0,000675 | 13,94× |
| 7 | `e0bab23a11d5ec24` | 0,135511 | 0,134681–0,136210 | 0,000601 | 13,69× |
| 8 | `fc683b2707d02c75` | 0,137614 | 0,136708–0,138776 | 0,000755 | 13,48× |
| 9 | `b5fecac6d15812be` | 0,141817 | 0,141372–0,142497 | 0,000453 | 13,08× |
| 10 | `3b26d2a24d3ac27c` | 0,143238 | 0,142779–0,143792 | 0,000446 | 12,95× |

### Taille du problème et précision

Le temps agrégé masque des accélérations différentes selon la taille. Voici les moyennes des latences brutes du gagnant et de la référence :

| Particules | Référence (ms) | Gagnant (ms) | Accélération |
|---|---:|---:|---:|
| 4096 | 0,929779 | 0,027951 | 33,26× |
| 8192 | 1,855724 | 0,095982 | 19,33× |
| 16384 | 3,699857 | 0,372533 | 9,93× |

L’écart absolu maximal du gagnant sur les deux jeux de correction est **0.000267028808594**, sans aucune sortie hors de la tolérance combinée absolue et relative. Les masses restent identiques. Réussir ces cas n’implique pas une identité bit à bit de toutes les positions et vitesses.

[Mesures de chaque taille et chaque bloc](tables/mesures-par-taille.csv) · [Erreurs numériques de chaque cas](tables/correction-par-cas.csv) · [Vérification des agrégats](protocol/replay-verification.json)

## Transformations dont l’effet peut être comparé directement

Les observations suivantes relient une différence exacte de fichiers à la base directe, toutes deux remesurées. « Plus rapide dans 5/5 blocs » reste une description des mesures ; ce n’est pas un test de significativité ni cinq recherches indépendantes.

| Campagne / transition | Modification visible dans le patch | Effet frais sur le temps | Blocs plus rapides |
|---|---|---:|---:|
| [776048 / `bd224cee51694d00`](diffs/776048/bd224cee51694d00.patch) | `sqrtf` + division remplacés par `rsqrtf` et produit de trois inverses ; lancement inchangé | 24,40 % de réduction | 5/5 |
| [776048 / `f1843fc5ccdb4b63`](diffs/776048/f1843fc5ccdb4b63.patch) | Suppression de la masse cible dans la force et de sa division à la mise à jour de vitesse | 0,62 % de réduction | 4/5 |
| [775521 / `fe8207f9ecac4c0b`](diffs/775521/fe8207f9ecac4c0b.patch) | Racine inverse avec une correction de Newton à la place de la racine + division | 30,77 % de réduction | 5/5 |
| [776290 / `1650707a621649ef`](diffs/776290/1650707a621649ef.patch) | Même kernel : bloc de 256 réduit à 32, avec adaptation des sorties par bloc | 4,05 % de réduction | 5/5 |
| [780448 / `154507185f9c4846`](diffs/780448/154507185f9c4846.patch) | Même kernel : bloc de 256 réduit à 128 | 3,21 % de réduction | 5/5 |
| [780448 / `4068c0071be145e3`](diffs/780448/4068c0071be145e3.patch) | Deux cibles adjacentes par thread et 512 sorties par bloc au lieu d’une cible par thread | -70,79 % de réduction | 0/5 |
| [774157 / `83808cc6f6df42b9`](diffs/774157/83808cc6f6df42b9.patch) | Copie strictement identique de la base ; une seule identité rejouée | 0,00 % de réduction | 0/5 |

Une réduction négative signifie un ralentissement. Le passage à deux cibles par thread dans 780448 allonge ainsi le temps de **70,79 %**. La perte est observée ; le rejeu ne contient pas de profilage matériel permettant de l’attribuer aux registres, à l’occupation ou aux accès mémoire.

Le meilleur kernel répartit déjà le calcul des sources entre threads avant le remplacement de la racine. Le gain de **24,40 %** correspond à cette base précise ; ce n’est pas le gain de `rsqrtf` dans tous les kernels.

À source CUDA strictement identique, **6 familles** couvrent **15 programmes** avec des paramètres différents. Les **12 comparaisons** de lancement sont conservées séparément. Un changement de `launch.json` peut avoir un effet mesurable sans être une fusion de kernels.

[Toutes les comparaisons de lancement](tables/comparaisons-lancements.csv) · [Toutes les transitions, bloc par bloc](tables/transitions-par-bloc.csv)


## Ce que les observations permettent de conclure

- **Les changements n’améliorent pas tous la vitesse obtenue.** Le meilleur résultat historique vient de 776048, avant la critique du plan et plusieurs améliorations de mémoire.
- **La représentation mémoire est corrigée.** Le même test avant/après reproduit l’absence du bilan factuel dans l’ancienne version, puis vérifie le meilleur programme, une alternative lente et le dernier échec dans la nouvelle.
- **Les leçons facultatives ne doivent pas faire perdre le code.** Le test avant/après reproduit `CandidateRejected: Missing memory envelope`, puis passe avec conservation du code au commit `06f2b38`.
- **La réserve de critique tient désormais compte de N.** Les tests avant/après montrent que les anciens calculs admettaient la critique avec 20 ou 600 arbres malgré le travail d’assemblage restant ; `106196b` corrige ces cas. Cela prouve un changement de décision budgétaire, pas un gain de vitesse du programme produit.
- **Le nombre d’essais et les sujets explorés comptent.** Après la correction de réserve, les campagnes observées passent de 3 essais à 24 puis 31 ; le meilleur lancement explore aussi une réduction parallèle des forces absente de plusieurs autres plans. Ces facteurs changent ensemble : leur contribution individuelle n’est pas isolée.
- **L’assemblage peut régresser ou recopier un programme.** Les différences de fichiers et les mesures sont conservées pour chaque intégration. Une déclaration de « fusion » n’est pas utilisée comme preuve de nouveauté.
- **L’incident du relais reste une limite réelle.** La campagne 780448 termine l’assemblage et la confirmation après une recherche interrompue. Elle ne démontre pas une meilleure régularité.

Le rejeu fixe le matériel, les entrées, le vérificateur et la mesure pour comparer les programmes. Il ne mesure pas la probabilité qu’un moteur retrouve une optimisation lors d’une nouvelle recherche. Pour attribuer causalement une amélioration de recherche à une fonction du moteur, il faudrait des campagnes neuves répétées, à modèle, programme et budget identiques, avec tous les échecs conservés.

## Chronologie des commits

| Date (Paris) | Commit | Nature | Modification enregistrée |
|---|---|---|---|
| 19/10 22:40 | `e6679c3` | Code / tests | feat(r1): add reconstructed engine and optional binary search |
| 21/10 19:43 | `cd2ea1a` | Code / tests | feat(forest): add adaptive parallel Mother campaigns |
| 22/10 18:57 | `a99cef6` | Code / tests | feat(memory): add persistent research memory and budgeted assembly |
| 22/10 19:00 | `fb8da63` | Preuves / documentation | docs(experiments): archive CUDA campaign results and reliability audit |
| 22/10 19:05 | `84ed198` | Code / tests | fix(memory): expose measured outcomes in paged tree summaries |
| 22/10 19:18 | `9628345` | Code / tests | fix(memory): preserve consultations and clarify assembly decisions |
| 22/10 19:26 | `d2f79e7` | Code / tests | feat(mother): review research plans within the campaign budget |
| 22/10 19:29 | `3b91ec6` | Code / tests | feat(memory): expose measured source changes and repeated programs |
| 23/10 04:30 | `06f2b38` | Code / tests | fix(memory): keep code when optional lessons are omitted |
| 23/10 04:31 | `6ee21f4` | Code / tests | feat(reliability): compare confirmed runs and prepare repeat studies |
| 23/10 04:38 | `b4c469d` | Preuves / documentation | docs(experiments): archive source change evidence for past assemblies |
| 23/10 04:47 | `2ea3236` | Code / tests | test(mother): cover CLI critique defaults and overrides |
| 23/10 04:49 | `106196b` | Code / tests | fix(mother): reserve provisional forest work before plan critique |
| 23/10 04:53 | `5bf1402` | Preuves / documentation | docs(reliability): record local validation and experiment limits |
| 23/10 04:59 | `2ee6125` | Code / tests | fix(cuda): enable budgeted plan review in fresh campaigns |
| 23/10 05:03 | `3589e02` | Preuves / documentation | docs(experiments): record fresh 30 minute Luna Max campaign |
| 23/10 05:18 | `9add740` | Preuves / documentation | test(experiments): recompute confirmed CUDA measurements from logs |
| 23/10 05:20 | `91408f2` | Preuves / documentation | docs(experiments): record relay interruption without resetting campaign |
| 23/10 05:40 | `934627c` | Preuves / documentation | test(experiments): archive Luna Max run and relay failure evidence |

Le dépôt contient **10 états distincts de `src/`** pour 12 commits touchant code, lanceurs ou tests. Les commits documentaires ne constituent pas de nouveaux moteurs.

## Versions réellement embarquées

Les empreintes de tous les payloads retrouvés correspondent à leurs manifestes, et leur identité de moteur correspond au registre de campagne. La correspondance Git ci-dessous compare les sources Python après normalisation CRLF/LF ; les empreintes exactes d’origine restent dans les données.

| Campagne | Sources retrouvées | Correspondance Git du moteur |
|---|---|---|
| 772923 | Oui, manifeste vérifié | `cd2ea1a` |
| 774157 | Oui, manifeste vérifié | État intermédiaire : 9 fichiers différents du commit le plus proche `cd2ea1a` |
| 775521 | Oui, manifeste vérifié | État intermédiaire : 3 fichiers différents du commit le plus proche `a99cef6` |
| 775815 | Oui, manifeste vérifié | État intermédiaire : 2 fichiers différents du commit le plus proche `a99cef6` |
| 776048 | Oui, manifeste vérifié | État intermédiaire : 1 fichiers différents du commit le plus proche `a99cef6` |
| 776290 | Oui, manifeste vérifié | `a99cef6`, `fb8da63` |
| 780448 | Oui, manifeste vérifié | `106196b`, `5bf1402`, `2ee6125`, `3589e02`, `9add740`, `91408f2`, `934627c` |

**Quatre campagnes utilisent des états intermédiaires sans commit identique.** Les rattacher directement à un commit voisin fausserait l’historique. Les payloads figés permettent de les identifier exactement.

## Vérifications fonctionnelles des versions

Chaque révision utilise ses propres tests non modifiés, un import depuis sa source Git, un dossier de travail et un répertoire temporaire distincts. Python 3.13 sous Windows est commun à cette matrice. Les nombres de tests changent avec les versions et ne sont pas des scores de performance.

| Commit | Tests collectés | Réussis | Échecs / erreurs | Ignorés | Ruff |
|---|---:|---:|---:|---:|---|
| `e6679c3` | 297 | 294 | 3 | 0 | OK |
| `cd2ea1a` | 659 | 659 | 0 | 0 | OK |
| `a99cef6` | 742 | 742 | 0 | 0 | OK |
| `84ed198` | 747 | 747 | 0 | 0 | OK |
| `9628345` | 759 | 759 | 0 | 0 | OK |
| `d2f79e7` | 776 | 775 | 1 | 0 | OK |
| `3b91ec6` | 779 | 778 | 1 | 0 | OK |
| `06f2b38` | 780 | 779 | 1 | 0 | OK |
| `6ee21f4` | 791 | 789 | 2 | 0 | OK |
| `2ea3236` | 793 | 793 | 0 | 0 | OK |
| `106196b` | 797 | 797 | 0 | 0 | OK |
| `2ee6125` | 799 | 799 | 0 | 0 | OK |

La première révision présente trois échecs de préparation du binaire de référence sous Windows : elle cherche `solution` alors que le compilateur produit `solution.exe`. Le diagnostic vient de `contracts.py`, et la version suivante passe ces tests.

Les trois dernières suites ont dépassé 30 minutes : seule leur supervision a été prolongée, avant expiration, en conservant les processus pytest et leurs tests inchangés. Les codes de sortie ont été observés directement par Windows. Ce temps total dépend des scénarios et de leur exécution simultanée ; il ne classe pas la vitesse des moteurs. [Trace de prolongation](protocol/test-supervision-extension.json).

De `d2f79e7` à `6ee21f4`, le test CLI attend encore un dictionnaire sans `plan_review_calls`, alors que la nouvelle valeur par défaut est 2. Cet échec signale une attente de test obsolète, corrigée dans `2ea3236` ; il ne suffit pas à conclure que la critique du plan ne fonctionne pas.

La suite de `6ee21f4` présente aussi une `PermissionError` Windows lors de la lecture d’une réponse locale publiée par un thread. Les dix répétitions séquentielles prévues de ce test passent toutes. Le module de messagerie est identique entre `6ee21f4` et `2ee6125`. L’échec initial est conservé : il n’est ni effacé par les répétitions, ni déclaré corrigé. Le lien éventuel avec la charge simultanée n’est pas établi. [Les dix répétitions et leurs journaux](regression-tests/mailbox-repeats/results.json).

Les premières tentatives du banc utilisaient un répertoire temporaire partagé et pouvaient se bloquer mutuellement ; elles sont exclues des résultats retenus. Le banc a ensuite isolé TEMP/TMP. Des chemins d’archives de diagnostics trop longs pour Windows ont été exclus de l’extraction des snapshots de test ; la référence CUDA utilisée par les tests est extraite inchangée de chaque commit. Les archives originales sont conservées. [Journaux des tentatives de préparation exclues](protocol/excluded-setup-attempts.zip).

### Régressions ciblées avant/après

| Cas | Parent, résultat | Correctif, résultat | Portée |
|---|---|---|---|
| Bilan mémoire | `fb8da63`, sortie 1 | `84ed198`, sortie 0 | Absence de résultats factuels avant, conservation de la variante lente après |
| Consultations et décisions | `84ed198`, sortie 4 | `9628345`, sortie 0 | Module absent avant : comparaison de capacité, pas reproduction d’une décision identique |
| Leçons omises | `3b91ec6`, sortie 1 | `06f2b38`, sortie 0 | Rejet du code avant ; code conservé après |
| Réserve selon N | `2ea3236`, sortie 1 | `106196b`, sortie 0 | Critique admise à tort pour N=20 et N=600 avant |

## Les 15 intégrations, une par une

Le gain est calculé par rapport à la base directe : positif = plus rapide ; négatif = plus lent. Une base non mesurée n’est pas remplacée par une valeur supposée. Une modification de source ne prouve pas une nouveauté sémantique.

| Campagne / essai | Changement vérifié | Temps historique (ms) | Gain historique / base | Gain du rejeu / base | Diff |
|---|---|---:|---:|---:|---|
| 772923 / `cef9331719264e06` | kernel et lancement | 0,136129 | 9,96 % | 9,73 % | [patch](diffs/772923/cef9331719264e06.patch) |
| 772923 / `dfa1304088594a93` | lancement seul | 0,893750 | -0,59 % | -0,07 % | [patch](diffs/772923/dfa1304088594a93.patch) |
| 772923 / `9d292814876943c9` | kernel seul | 0,111956 | — % | 18,54 % | [patch](diffs/772923/9d292814876943c9.patch) |
| 774157 / `5aa175847b2145d7` | kernel seul | 0,119188 | 12,60 % | 12,56 % | [patch](diffs/774157/5aa175847b2145d7.patch) |
| 774157 / `83808cc6f6df42b9` | copie exacte | 0,119370 | — % | 0,00 % | [patch](diffs/774157/83808cc6f6df42b9.patch) |
| 775521 / `79c03ae33d024935` | kernel et lancement | 1,646950 | -63,43 % | -63,37 % | [patch](diffs/775521/79c03ae33d024935.patch) |
| 775521 / `fe8207f9ecac4c0b` | kernel seul | 0,698728 | 30,66 % | 30,77 % | [patch](diffs/775521/fe8207f9ecac4c0b.patch) |
| 775815 / `b9c8264315b147ca` | kernel seul | 0,591664 | 38,55 % | 39,16 % | [patch](diffs/775815/b9c8264315b147ca.patch) |
| 775815 / `1a380d99a03b42a0` | kernel seul | 0,523677 | — % | 10,84 % | [patch](diffs/775815/1a380d99a03b42a0.patch) |
| 776048 / `bd224cee51694d00` | kernel seul | 0,100528 | 24,31 % | 24,40 % | [patch](diffs/776048/bd224cee51694d00.patch) |
| 776048 / `f1843fc5ccdb4b63` | kernel seul | 0,099649 | — % | 0,62 % | [patch](diffs/776048/f1843fc5ccdb4b63.patch) |
| 776290 / `1650707a621649ef` | lancement seul | 0,853705 | 4,04 % | 4,05 % | [patch](diffs/776290/1650707a621649ef.patch) |
| 776290 / `5db7ae8c14c24b28` | lancement seul | 0,853937 | — % | -0,16 % | [patch](diffs/776290/5db7ae8c14c24b28.patch) |
| 780448 / `4068c0071be145e3` | kernel et lancement | 1,781623 | -71,67 % | -70,79 % | [patch](diffs/780448/4068c0071be145e3.patch) |
| 780448 / `154507185f9c4846` | lancement seul | 1,010046 | 2,68 % | 3,21 % | [patch](diffs/780448/154507185f9c4846.patch) |

## Historique détaillé par campagne

### 772923 — Première campagne CUDA, recherche par vagues

Le programme final est confirmé, mais le contrôleur initial échoue à l’export, car il exige Makefile et run.sh. L’export a été récupéré séparément. Les mesures restent valides ; le pipeline initial ne s’est pas terminé normalement.

Moteur observé : `a85718af81c0b3562baa502f72806833b7e2d21d08b253f53049cde7318f8c3a`. Modèle : `gpt-6-luna`, effort `max`. Cible : 30 minutes. Temps avant fermeture de recherche : 15 min 01 s ; pipeline : 21 min 30 s.

| Horodatage Paris | Étape enregistrée | Diagnostic de décision |
|---|---|---|
| 21/10 18:30:58 | Espace préparé | — |
| 21/10 18:33:51 | Proposition initiale de Mother terminée | complete |
| 21/10 18:33:51 | Plan des arbres fixé | complete |
| 21/10 18:46:12 | Arrêt des nouvelles recherches | Remaining time reserved for final Mother, G and confirmation |
| 21/10 18:51:44 | Assemblage terminé | complete |

[Chronologie complète des 42 événements, avec données brutes](tables/evenements-772923.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.

| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Shared-memory tiled source reuse across output threads | 3 | 3 | 0,986914 |
| T2 | Warp-parallel source reduction for each output particle | 3 | 3 | 0,151183 |
| T3 | Reciprocal-square-root interaction arithmetic | 3 | 3 | 0,888510 |
| T4 | Register-blocked multiple outputs per thread | 3 | 3 | 2,689032 |

[Tous les essais et diagnostics](tables/essais-772923.csv) · [Événements horodatés](data/campaigns/772923/events.json) · [Décisions conservées](data/campaigns/772923/decisions.json)

| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |
|---|---|---|---|---:|---:|---|
| 2 min 40 s | `2566292e782540b6` / `origine` | T1, 1 | valid | 1,083291 | 1,086846 | kernel et lancement |
| 2 min 40 s | `0b61d20a4da644c3` / `origine` | T2, 1 | valid | 0,151183 | 0,152446 | kernel et lancement |
| 2 min 40 s | `f1e1b4dc8e504ce8` / `origine` | T3, 1 | valid | 1,008499 | 1,012038 | kernel seul |
| 2 min 40 s | `7dd235a5cd3f46a3` / `origine` | T4, 1 | valid | 2,689032 | 2,699662 | kernel et lancement |
| 5 min 56 s | `006bdfda35a841b4` / `origine` | T1, 1 | valid | 0,996286 | 0,992382 | kernel et lancement |
| 5 min 56 s | `4eee245c5aed46d6` / `0b61d20a4da644c3` | T2, 2 | valid | 0,152235 | 0,151828 | kernel seul |
| 5 min 56 s | `50afa0cd330a4a13` / `origine` | T3, 1 | valid | 1,509459 | 1,506223 | kernel seul |
| 5 min 56 s | `f7b2616b99824cf5` / `7dd235a5cd3f46a3` | T4, 2 | valid | 4,496918 | 4,476818 | kernel et lancement |
| 9 min 47 s | `e7e4f078010b4a8a` / `origine` | T1, 1 | valid | 0,986914 | 0,991627 | kernel et lancement |
| 9 min 47 s | `0223355582454a51` / `origine` | T2, 1 | valid | 0,163322 | 0,165520 | kernel et lancement |
| 9 min 47 s | `4ca3c7496b0b40eb` / `f1e1b4dc8e504ce8` | T3, 2 | valid | 0,888510 | 0,890060 | kernel seul |
| 9 min 47 s | `0cc8661a7fcf4aba` / `origine` | T4, 1 | valid | 3,531931 | 3,550625 | kernel et lancement |
| 15 min 01 s | `cef9331719264e06` / `origine` | G, 1 | valid | 0,136129 | 0,137614 | kernel et lancement |
| 17 min 15 s | `dfa1304088594a93` / `origine` | G, 1 | valid | 0,893750 | 0,890722 | lancement seul |
| 18 min 56 s | `9d292814876943c9` / `origine` | G, 1 | valid | 0,111956 | 0,112097 | kernel seul |

### 774157 — Arbres indépendants, assemblage par paires

Le programme confirmé est rapide. La dernière intégration recopie exactement sa base dans les deux fichiers autorisés. Cette copie a été évaluée, mais ne constitue pas une nouvelle transformation du programme.

Moteur observé : `13564fba5f011d277b8447900c07f3adbc5adf6e929cdb1d2fa4fb5953d79072`. Modèle : `gpt-6-luna`, effort `max`. Cible : 30 minutes. Temps avant fermeture de recherche : 21 min 37 s ; pipeline : 25 min 06 s.

| Horodatage Paris | Étape enregistrée | Diagnostic de décision |
|---|---|---|
| 21/10 21:37:04 | Espace préparé | — |
| 21/10 21:40:27 | Proposition initiale de Mother terminée | complete |
| 21/10 21:40:27 | Plan des arbres fixé | complete |
| 21/10 21:58:49 | Arrêt des nouvelles recherches | No independent research node fits before finalization |
| 21/10 22:01:34 | Assemblage terminé | complete |
| 21/10 22:02:18 | Export préparé | — |

[Chronologie complète des 112 événements, avec données brutes](tables/evenements-774157.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.

| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Pair-interaction arithmetic and reciprocal-square-root optimization | 2 | 1 | 1,106310 |
| T2 | Warp-cooperative source summation per output | 9 | 9 | 0,136367 |
| T3 | CTA shared-memory source tiling | 7 | 7 | 0,962585 |

[Tous les essais et diagnostics](tables/essais-774157.csv) · [Événements horodatés](data/campaigns/774157/events.json) · [Décisions conservées](data/campaigns/774157/decisions.json)

| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |
|---|---|---|---|---:|---:|---|
| 3 min 16 s | `943df5f6be5e4748` / `origine` | T1, 1 | valid | 1,106310 | 1,102400 | kernel et lancement |
| 3 min 16 s | `c6e77902a5e74242` / `origine` | T2, 1 | valid | 0,151338 | 0,151566 | kernel et lancement |
| 3 min 16 s | `a1a2a6f0f51445f0` / `origine` | T3, 1 | valid | 1,054493 | 1,058375 | kernel et lancement |
| 5 min 20 s | `8f8097de6798435a` / `c6e77902a5e74242` | T2, 2 | valid | 0,151703 | 0,152417 | lancement seul |
| 5 min 40 s | `127df14b9f84416d` / `origine` | T3, 1 | valid | 0,969535 | 0,965409 | kernel et lancement |
| 7 min 03 s | `c623d142c61e4271` / `origine` | T2, 1 | valid | 0,147889 | 0,146875 | kernel et lancement |
| 7 min 54 s | `e13dcfc677534f32` / `a1a2a6f0f51445f0` | T3, 2 | valid | 1,057769 | 1,053419 | kernel et lancement |
| 9 min 31 s | `7f6db32f9b464521` / `8f8097de6798435a` | T2, 3 | valid | 0,149296 | 0,149713 | kernel et lancement |
| 9 min 53 s | `f50e21f64fbd4530` / `origine` | T1, 1 | incorrect | — | — | kernel et lancement |
| 10 min 21 s | `83e8ca4bbc4145e7` / `origine` | T3, 1 | valid | 0,966347 | 0,964045 | kernel et lancement |
| 13 min 01 s | `0543ac052dc04716` / `origine` | T3, 1 | valid | 0,970423 | 0,966547 | kernel et lancement |
| 13 min 14 s | `914692762286487e` / `c6e77902a5e74242` | T2, 2 | valid | 0,158977 | 0,159844 | lancement seul |
| 14 min 42 s | `e40943d49da94d90` / `c6e77902a5e74242` | T2, 2 | valid | 0,136367 | 0,135511 | kernel et lancement |
| 15 min 31 s | `d129a2ab69114b6f` / `origine` | T3, 1 | valid | 1,004383 | 1,001085 | kernel et lancement |
| 16 min 22 s | `1a75516fa2764876` / `c623d142c61e4271` | T2, 2 | valid | 0,169468 | 0,172830 | lancement seul |
| 17 min 33 s | `46d61565c7ed487e` / `origine` | T3, 1 | valid | 0,962585 | 0,967984 | kernel et lancement |
| 18 min 20 s | `30ed81897acb4b26` / `origine` | T2, 1 | valid | 0,171393 | 0,171647 | kernel et lancement |
| 20 min 06 s | `3a770eb0bff44bf3` / `30ed81897acb4b26` | T2, 2 | valid | 0,177792 | 0,177965 | lancement seul |
| 21 min 37 s | `5aa175847b2145d7` / `origine` | G, 1 | valid | 0,119188 | 0,118485 | kernel seul |
| 22 min 58 s | `83808cc6f6df42b9` / `origine` | G, 1 | valid | 0,119370 | 0,118485 | copie exacte |

### 775521 — Mémoire persistante, réserve de budget trop conservatrice

La réserve de finalisation surévalue les coûts possibles. La recherche ne produit que trois essais avant assemblage. La première combinaison est plus lente que sa base ; la seconde l’améliore.

Moteur observé : `29cab89e782cdaa41b4104cd1a0a018872a4831560506aef60b5c576c688eb03`. Modèle : `gpt-6-luna`, effort `max`. Cible : 30 minutes. Temps avant fermeture de recherche : 6 min 43 s ; pipeline : 14 min 53 s.

| Horodatage Paris | Étape enregistrée | Diagnostic de décision |
|---|---|---|
| 22/10 12:40:33 | Espace préparé | — |
| 22/10 12:43:10 | Proposition initiale de Mother terminée | complete |
| 22/10 12:43:10 | Plan des arbres fixé | complete |
| 22/10 12:47:22 | Arrêt des nouvelles recherches | No independent research node fits before finalization |
| 22/10 12:54:44 | Assemblage terminé | complete |
| 22/10 12:55:31 | Export préparé | — |

[Chronologie complète des 40 événements, avec données brutes](tables/evenements-775521.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.

| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Explore staging source positions and mass in shared memory in source chunks so multiple target threads reuse each staged source. Keep the output mapping at one target per thread to distinguish this from register-blocked output work. Tune a valid block/items_per_block/shared_memory_bytes configuration and the shared tile layout; handle partial source and target tiles without letting inactive threads skip required barriers. Preserve i==j exclusion, the exact interface and all correctness requirements. Compare using the prescribed three-size geometric-mean kernel-time objective, and retain only candidates that pass the full correctness checks. | 1 | 1 | 1,007746 |
| T2 | Explore assigning a small batch of target particles to each thread, with separate accumulators, so a source particle's loaded position and mass can be reused across those targets. This is an output-axis/register-reuse investigation, not merely another one-target-per-thread shared-memory tile. Tune the batch size and allowed launch configuration while monitoring register pressure and available parallelism. Cover all target tails and preserve the full state, self exclusion, numerical requirements, and exact masses. Measure against the prescribed objective and validate every candidate with the complete oracle/check suite. | 1 | 1 | 2,604582 |
| T3 | Explore lowering the cost of pair evaluation while retaining the one-target-per-thread mapping as a clear comparison: for example, algebraically cancel target mass in the acceleration expression and evaluate inverse distance with rsqrtf to form an inverse-cube factor. Test arithmetic ordering and only consider FMA or loop unrolling when measurements justify them. These transformations change floating-point rounding: preserve softening and self exclusion, use no global fast-math option, and reject any candidate that fails tolerances, oracle checks, or the nonfinite-output constraint, including extreme-mass and coincident-position cases. Compare on the official geometric-mean metric. | 1 | 0 | — |

[Tous les essais et diagnostics](tables/essais-775521.csv) · [Événements horodatés](data/campaigns/775521/events.json) · [Décisions conservées](data/campaigns/775521/decisions.json)

| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |
|---|---|---|---|---:|---:|---|
| 2 min 31 s | `85c1ff0376cc4045` / `origine` | T1, 1 | valid | 1,007746 | 1,003699 | kernel et lancement |
| 2 min 31 s | `16bd9f82c0e34e9f` / `origine` | T2, 1 | valid | 2,604582 | 2,598537 | kernel et lancement |
| 2 min 31 s | `2a7cd6b7c3af45e9` / `origine` | T3, 1 | incorrect | — | — | kernel seul |
| 8 min 33 s | `79c03ae33d024935` / `origine` | G, 1 | valid | 1,646950 | 1,639699 | kernel et lancement |
| 11 min 37 s | `fe8207f9ecac4c0b` / `origine` | G, 1 | valid | 0,698728 | 0,694817 | kernel seul |

### 775815 — Première correction du calcul de réserve

Le calcul de réserve devient moins conservateur. La campagne passe à 24 essais de recherche, dont 22 valides. Le sujet de réduction parallèle des sources n’est pas présent dans le plan de cette campagne.

Moteur observé : `8804f49ee164a741951857d8307f214e705c9ad223e0d71d940481c8d7f262dc`. Modèle : `gpt-6-luna`, effort `max`. Cible : 30 minutes. Temps avant fermeture de recherche : 20 min 12 s ; pipeline : 25 min 29 s.

| Horodatage Paris | Étape enregistrée | Diagnostic de décision |
|---|---|---|
| 22/10 14:15:21 | Espace préparé | — |
| 22/10 14:16:57 | Proposition initiale de Mother terminée | complete |
| 22/10 14:16:57 | Plan des arbres fixé | complete |
| 22/10 14:35:39 | Arrêt des nouvelles recherches | No independent research node fits before finalization |
| 22/10 14:40:19 | Assemblage terminé | complete |
| 22/10 14:40:56 | Export préparé | — |

[Chronologie complète des 150 événements, avec données brutes](tables/evenements-775815.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.

| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Shared-memory tiling of source particles | 12 | 12 | 0,962888 |
| T2 | Pairwise force arithmetic and numerical accuracy | 5 | 3 | 1,015670 |
| T3 | Register-blocked output mapping and launch geometry | 7 | 7 | 2,570465 |

[Tous les essais et diagnostics](tables/essais-775815.csv) · [Événements horodatés](data/campaigns/775815/events.json) · [Décisions conservées](data/campaigns/775815/decisions.json)

| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |
|---|---|---|---|---:|---:|---|
| 1 min 30 s | `de30553b88e54531` / `origine` | T1, 1 | valid | 0,995664 | 1,000463 | kernel et lancement |
| 1 min 30 s | `5398a8f78ec94cc1` / `origine` | T2, 1 | incorrect | — | — | kernel seul |
| 1 min 30 s | `15e748c538d3437c` / `origine` | T3, 1 | valid | 2,586802 | 2,597268 | kernel et lancement |
| 2 min 51 s | `d92cf45cd6814646` / `origine` | T1, 1 | valid | 0,964987 | 0,970998 | kernel et lancement |
| 3 min 18 s | `16acacf704444b7c` / `origine` | T3, 1 | valid | 2,674025 | 2,678196 | kernel et lancement |
| 4 min 17 s | `8dc9c16f618345ed` / `origine` | T1, 1 | valid | 1,196577 | 1,203903 | kernel et lancement |
| 4 min 32 s | `4b1937b9658c4b1f` / `5398a8f78ec94cc1` | T2, 2 | valid | 1,850356 | 1,847359 | kernel seul |
| 4 min 58 s | `ddc14e877adb45d7` / `15e748c538d3437c` | T3, 2 | valid | 4,258111 | 4,276257 | kernel et lancement |
| 5 min 41 s | `0fa3c15e02bc4240` / `origine` | T1, 1 | valid | 0,964868 | 0,965729 | kernel et lancement |
| 6 min 48 s | `2b0d41e0d521450c` / `origine` | T3, 1 | valid | 2,597440 | 2,587537 | kernel et lancement |
| 7 min 11 s | `634bff6fffc04501` / `0fa3c15e02bc4240` | T1, 2 | valid | 0,962888 | 0,966365 | kernel et lancement |
| 7 min 59 s | `f5b5515eac7f42bc` / `origine` | T2, 1 | valid | 1,015670 | 1,011934 | kernel seul |
| 8 min 16 s | `357bbe6e115540df` / `d92cf45cd6814646` | T1, 2 | valid | 0,967008 | 0,961517 | kernel et lancement |
| 9 min 14 s | `6aabcd3c82f94ae7` / `4b1937b9658c4b1f` | T2, 3 | valid | 1,033302 | 1,026047 | kernel seul |
| 9 min 26 s | `6254e9c4756443e9` / `0fa3c15e02bc4240` | T1, 2 | valid | 0,969027 | 0,961068 | kernel et lancement |
| 9 min 51 s | `c7a378a9af3d4d0d` / `origine` | T3, 1 | valid | 2,592751 | 2,576535 | kernel et lancement |
| 11 min 26 s | `c4dd3a2f62154641` / `origine` | T1, 1 | valid | 0,970844 | 0,960983 | kernel et lancement |
| 12 min 28 s | `bfcb46dd975e49d9` / `origine` | T3, 1 | valid | 2,570465 | 2,554815 | kernel et lancement |
| 13 min 12 s | `b3e3951ce1ec4c59` / `5398a8f78ec94cc1` | T2, 2 | generation_failed | — | — | non disponible |
| 13 min 54 s | `18c0e5f33d554ea1` / `de30553b88e54531` | T1, 2 | valid | 0,968978 | 0,962896 | kernel et lancement |
| 14 min 46 s | `d9eff8edb675451d` / `origine` | T1, 1 | valid | 0,964409 | 0,959644 | kernel et lancement |
| 15 min 32 s | `92d277cd78574f87` / `origine` | T3, 1 | valid | 2,690773 | 2,682700 | kernel et lancement |
| 16 min 11 s | `b952bd34ae97444d` / `origine` | T1, 1 | valid | 0,967594 | 0,961603 | kernel et lancement |
| 17 min 43 s | `ab6e69917d074845` / `origine` | T1, 1 | valid | 0,967956 | 0,965986 | kernel et lancement |
| 21 min 07 s | `b9c8264315b147ca` / `origine` | G, 1 | valid | 0,591664 | 0,587941 | kernel seul |
| 24 min 00 s | `1a380d99a03b42a0` / `origine` | G, 1 | valid | 0,523677 | 0,524202 | kernel seul |

### 776048 — Assemblage adaptatif et budget corrigé

Cette campagne explore explicitement la réduction parallèle des forces sur les sources. La première combinaison améliore la meilleure variante de cet arbre. Elle fournit le meilleur programme confirmé de l’historique archivé.

Moteur observé : `309c2f2a0aa2a92d3e256f9de5464fc36c6cb79c559941ca236c807c5d2ca725`. Modèle : `gpt-6-luna`, effort `max`. Cible : 30 minutes. Temps avant fermeture de recherche : 20 min 39 s ; pipeline : 27 min 07 s.

| Horodatage Paris | Étape enregistrée | Diagnostic de décision |
|---|---|---|
| 22/10 14:46:52 | Espace préparé | — |
| 22/10 14:49:06 | Proposition initiale de Mother terminée | complete |
| 22/10 14:49:06 | Plan des arbres fixé | complete |
| 22/10 15:07:35 | Arrêt des nouvelles recherches | No independent research node fits before finalization |
| 22/10 15:13:09 | Arrêt budgétaire de l’assemblage | Remaining time reserved for independent confirmation |
| 22/10 15:13:09 | Assemblage terminé | complete |
| 22/10 15:14:04 | Export préparé | — |

[Chronologie complète des 190 événements, avec données brutes](tables/evenements-776048.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.

| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Shared-memory source tiling | 9 | 8 | 0,889804 |
| T2 | Per-thread multi-target coarsening | 8 | 7 | 2,582085 |
| T3 | Source-parallel force reduction | 8 | 8 | 0,132813 |
| T4 | Force arithmetic simplification | 6 | 5 | 1,014575 |

[Tous les essais et diagnostics](tables/essais-776048.csv) · [Événements horodatés](data/campaigns/776048/events.json) · [Décisions conservées](data/campaigns/776048/decisions.json)

| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |
|---|---|---|---|---:|---:|---|
| 2 min 10 s | `aae515bf57f94665` / `origine` | T1, 1 | valid | 0,969324 | 0,966793 | kernel et lancement |
| 2 min 10 s | `e099ff53da844775` / `origine` | T2, 1 | valid | 2,615282 | 2,608123 | kernel et lancement |
| 2 min 10 s | `072b1a80b8fa466d` / `origine` | T3, 1 | valid | 0,151833 | 0,152003 | kernel et lancement |
| 2 min 10 s | `7a33f8f04fdf415f` / `origine` | T4, 1 | valid | 1,014575 | 1,010285 | kernel seul |
| 3 min 56 s | `2edf23e904aa477b` / `origine` | T1, 1 | valid | 0,993255 | 0,998163 | kernel et lancement |
| 4 min 20 s | `335e165bec36493e` / `e099ff53da844775` | T2, 2 | valid | 4,167635 | 4,178025 | kernel et lancement |
| 4 min 46 s | `36b0e8c95e694a2e` / `origine` | T4, 1 | incorrect | — | — | kernel seul |
| 4 min 58 s | `54965513c23b4631` / `origine` | T3, 1 | valid | 0,144362 | 0,143238 | kernel et lancement |
| 5 min 21 s | `5e30f66d28c84e34` / `origine` | T1, 1 | valid | 0,958558 | 0,963314 | kernel et lancement |
| 5 min 44 s | `3aec87f1ed714bf4` / `origine` | T2, 1 | valid | 2,582085 | 2,590567 | kernel et lancement |
| 6 min 04 s | `8052fe0a6b7b4d62` / `072b1a80b8fa466d` | T3, 2 | valid | 0,132813 | 0,133071 | kernel et lancement |
| 6 min 34 s | `b067236e66fc41e3` / `origine` | T1, 1 | valid | 0,960974 | 0,963896 | kernel et lancement |
| 7 min 17 s | `986ed4e1c49d44e1` / `origine` | T3, 1 | valid | 0,143566 | 0,143974 | kernel et lancement |
| 7 min 48 s | `917b639f9f734e82` / `origine` | T4, 1 | valid | 1,848557 | 1,847284 | kernel seul |
| 8 min 01 s | `d4299d0b4ca44112` / `b067236e66fc41e3` | T1, 2 | valid | 0,966752 | 0,969610 | kernel et lancement |
| 8 min 53 s | `08eb76bfcf6f4c3b` / `335e165bec36493e` | T2, 3 | valid | 2,764882 | 2,768821 | kernel et lancement |
| 9 min 01 s | `6c7b9306ff1c45c4` / `origine` | T3, 1 | valid | 0,197327 | 0,197579 | kernel et lancement |
| 9 min 18 s | `4cac546b57bc4d08` / `2edf23e904aa477b` | T1, 2 | valid | 0,968444 | 0,971555 | kernel et lancement |
| 9 min 59 s | `929d39cd705e4487` / `e099ff53da844775` | T2, 2 | valid | 2,585403 | 2,593848 | lancement seul |
| 10 min 53 s | `7d651842ff4e48f5` / `origine` | T3, 1 | valid | 0,298464 | 0,298900 | kernel et lancement |
| 11 min 20 s | `cc1fd62237d84c67` / `b067236e66fc41e3` | T1, 2 | valid | 0,889804 | 0,883173 | kernel et lancement |
| 11 min 48 s | `206c8a2af7294599` / `917b639f9f734e82` | T4, 2 | valid | 1,180286 | 1,175606 | kernel seul |
| 12 min 09 s | `b306ffa7eebb4043` / `e099ff53da844775` | T2, 2 | valid | 3,424644 | 3,418125 | kernel et lancement |
| 12 min 48 s | `0c5c6d925f44466a` / `origine` | T3, 1 | valid | 0,141159 | 0,141817 | kernel et lancement |
| 13 min 18 s | `adcb4f6a36b74958` / `206c8a2af7294599` | T4, 3 | valid | 1,180030 | 1,176672 | kernel seul |
| 14 min 01 s | `7bedf3b808574349` / `origine` | T1, 1 | incorrect | — | — | kernel et lancement |
| 14 min 37 s | `82706559abee4549` / `3aec87f1ed714bf4` | T2, 2 | valid | 4,251409 | 4,233022 | kernel et lancement |
| 15 min 12 s | `f914248a67cb48e9` / `origine` | T4, 1 | valid | 1,089936 | 1,087204 | kernel seul |
| 15 min 36 s | `9bcc1b2d95ca4e8b` / `origine` | T3, 1 | valid | 0,132873 | 0,132798 | kernel et lancement |
| 17 min 00 s | `6aa6069b720f4954` / `origine` | T2, 1 | incorrect | — | — | kernel et lancement |
| 18 min 06 s | `2505e16e21d24a25` / `aae515bf57f94665` | T1, 2 | valid | 0,921254 | 0,916360 | kernel et lancement |
| 21 min 58 s | `bd224cee51694d00` / `origine` | G, 1 | valid | 0,100528 | 0,100599 | kernel seul |
| 25 min 30 s | `f1843fc5ccdb4b63` / `origine` | G, 1 | valid | 0,099649 | 0,099979 | kernel seul |

### 776290 — Correction de l’admission en fin de budget

La décision budgétaire de fin de campagne est corrigée, mais le programme final reste beaucoup plus lent que celui de 776048. Les deux intégrations ne changent que launch.json par rapport à leur base.

Moteur observé : `e97183fce446d8d7db79e22e0508c8f4910c3929d4dd2c063560494ea4ea45c4`. Modèle : `gpt-6-luna`, effort `max`. Cible : 30 minutes. Temps avant fermeture de recherche : 20 min 39 s ; pipeline : 28 min 20 s.

| Horodatage Paris | Étape enregistrée | Diagnostic de décision |
|---|---|---|
| 22/10 15:20:33 | Espace préparé | — |
| 22/10 15:22:46 | Proposition initiale de Mother terminée | complete |
| 22/10 15:22:46 | Plan des arbres fixé | complete |
| 22/10 15:41:15 | Arrêt des nouvelles recherches | No independent research node fits before finalization |
| 22/10 15:48:09 | Arrêt budgétaire de l’assemblage | Remaining time reserved for independent confirmation |
| 22/10 15:48:09 | Assemblage terminé | complete |
| 22/10 15:48:56 | Export préparé | — |

[Chronologie complète des 170 événements, avec données brutes](tables/evenements-776290.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.

| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Tuilage des sources en mémoire partagée | 7 | 7 | 1,005207 |
| T2 | Diffusion warp des sources par registres et shuffles | 8 | 8 | 0,889680 |
| T3 | Blocage de plusieurs cibles par thread | 6 | 6 | 2,590768 |
| T4 | Réduction arithmétique et calcul de l’inverse de la distance | 6 | 3 | 0,984958 |

[Tous les essais et diagnostics](tables/essais-776290.csv) · [Événements horodatés](data/campaigns/776290/events.json) · [Décisions conservées](data/campaigns/776290/decisions.json)

| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |
|---|---|---|---|---:|---:|---|
| 2 min 10 s | `35c7d193c8a34331` / `origine` | T1, 1 | valid | 1,005207 | 1,000741 | kernel seul |
| 2 min 10 s | `a47dcaea04a9475f` / `origine` | T2, 1 | valid | 0,976558 | 0,975284 | kernel seul |
| 2 min 10 s | `377b57d9fd5245fb` / `origine` | T3, 1 | valid | 2,590768 | 2,606817 | kernel et lancement |
| 2 min 10 s | `da61858a6bc84794` / `origine` | T4, 1 | incorrect | — | — | kernel seul |
| 3 min 46 s | `52d4281997e54319` / `origine` | T1, 1 | valid | 1,017050 | 1,012835 | kernel seul |
| 4 min 01 s | `a47bc86ffef142bf` / `origine` | T3, 1 | valid | 2,609252 | 2,608384 | kernel et lancement |
| 4 min 15 s | `d826ec029be64b8b` / `a47dcaea04a9475f` | T2, 2 | valid | 1,738208 | 1,734490 | kernel seul |
| 5 min 41 s | `ea1e8dbc578e4807` / `origine` | T1, 1 | valid | 1,614399 | 1,602872 | kernel et lancement |
| 6 min 15 s | `f4a29d1b77484ed3` / `da61858a6bc84794` | T4, 2 | valid | 1,814647 | 1,830412 | kernel seul |
| 6 min 35 s | `ec3c2b107121491a` / `origine` | T2, 1 | valid | 0,904282 | 0,902162 | kernel seul |
| 7 min 01 s | `6ae20d0a866240de` / `377b57d9fd5245fb` | T3, 2 | valid | 4,202550 | 4,207106 | kernel et lancement |
| 7 min 15 s | `34a8792fc6fe41b4` / `origine` | T1, 1 | valid | 1,696272 | 1,686051 | kernel et lancement |
| 8 min 35 s | `99c33593615e4830` / `d826ec029be64b8b` | T2, 3 | valid | 1,740541 | 1,731543 | kernel et lancement |
| 8 min 49 s | `9fc61170db0a481f` / `34a8792fc6fe41b4` | T1, 2 | valid | 1,698342 | 1,688256 | kernel seul |
| 9 min 04 s | `df91a829afbd4cb1` / `origine` | T4, 1 | generation_failed | — | — | non disponible |
| 10 min 16 s | `f264cb6f7b244f1e` / `origine` | T3, 1 | valid | 2,747957 | 2,716970 | kernel et lancement |
| 10 min 26 s | `505a0137c1e74ebf` / `a47dcaea04a9475f` | T2, 2 | valid | 0,936043 | 0,932210 | kernel seul |
| 11 min 52 s | `f704764fdf4646db` / `origine` | T3, 1 | valid | 3,420253 | 3,366253 | kernel et lancement |
| 11 min 53 s | `36621123dde34055` / `f4a29d1b77484ed3` | T4, 3 | valid | 1,021009 | 1,034981 | kernel seul |
| 12 min 12 s | `8d1b57c6a222477c` / `a47dcaea04a9475f` | T2, 2 | valid | 0,977258 | 0,977496 | kernel seul |
| 12 min 28 s | `f4d8f90ea00e469f` / `52d4281997e54319` | T1, 2 | valid | 1,124496 | 1,116114 | kernel et lancement |
| 13 min 12 s | `2d8a76b886264ac3` / `f4a29d1b77484ed3` | T4, 3 | valid | 0,984958 | 1,011701 | kernel seul |
| 13 min 43 s | `2b123bd88aec470e` / `ec3c2b107121491a` | T2, 2 | valid | 0,889680 | 0,887363 | kernel seul |
| 14 min 22 s | `4750d0315ca24212` / `f4a29d1b77484ed3` | T4, 3 | incorrect | — | — | kernel seul |
| 14 min 44 s | `5d697700e03a461a` / `origine` | T3, 1 | valid | 2,714235 | 2,727241 | kernel et lancement |
| 15 min 10 s | `5ebf2310933040f2` / `origine` | T2, 1 | valid | 0,942241 | 0,938473 | kernel seul |
| 15 min 49 s | `2109090d5aa349b0` / `34a8792fc6fe41b4` | T1, 2 | valid | 3,316742 | 3,307886 | kernel et lancement |
| 22 min 01 s | `1650707a621649ef` / `origine` | G, 1 | valid | 0,853705 | 0,851464 | lancement seul |
| 26 min 23 s | `5db7ae8c14c24b28` / `origine` | G, 1 | valid | 0,853937 | 0,852839 | lancement seul |

### 780448 — Mémoire enrichie, critique du plan et interruption du relais

Une critique du plan est bien exécutée. Une interruption du relais ferme prématurément la recherche : huit essais sont admis, dont trois sans mesure à cause de l’infrastructure. La première combinaison ralentit sa base ; la seconde ne modifie que le lancement. La fin du pipeline ne supprime pas l’incident de recherche.

Moteur observé : `489223b2b83e5a217a79d3a6643bdb586ca90f69b16c99f2da842ba574f26be2`. Modèle : `gpt-6-luna`, effort `max`. Cible : 30 minutes. Temps avant fermeture de recherche : 13 min 18 s ; pipeline : 23 min 23 s.

| Horodatage Paris | Étape enregistrée | Diagnostic de décision |
|---|---|---|
| 23/10 05:02:19 | Espace préparé | — |
| 23/10 05:04:59 | Proposition initiale de Mother terminée | complete |
| 23/10 05:04:59 | Décision d’admettre la critique | can_review=True, requis=971,49 s, restant=1659,31 s |
| 23/10 05:06:25 | Critique du plan terminée | accepted |
| 23/10 05:06:25 | Plan des arbres fixé | complete |
| 23/10 05:25:14 | Assemblage terminé | complete |
| 23/10 05:26:02 | Export préparé | — |

[Chronologie complète des 62 événements, avec données brutes](tables/evenements-780448.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.

| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Tuilage partagé comparé aux accès globaux directs | 3 | 2 | 1,037837 |
| T2 | Réduction du coût arithmétique par interaction | 2 | 0 | — |
| T3 | Microtuilage des cibles en registres et réglage du lancement | 3 | 2 | 2,751189 |

[Tous les essais et diagnostics](tables/essais-780448.csv) · [Événements horodatés](data/campaigns/780448/events.json) · [Décisions conservées](data/campaigns/780448/decisions.json)

| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |
|---|---|---|---|---:|---:|---|
| 3 min 46 s | `b4566ea4300e442d` / `origine` | T1, 1 | valid | 1,086267 | 1,081379 | kernel seul |
| 3 min 46 s | `863a66f2a7c94930` / `origine` | T2, 1 | incorrect | — | — | kernel seul |
| 3 min 46 s | `d995469144fa4584` / `origine` | T3, 1 | valid | 3,361482 | 3,336728 | kernel seul |
| 6 min 17 s | `bfe2017023684f87` / `origine` | T1, 1 | valid | 1,037837 | 1,037415 | kernel seul |
| 6 min 34 s | `49ece3a057ac4f0a` / `origine` | T3, 1 | valid | 2,751189 | 2,742975 | kernel seul |
| 9 min 19 s | `51cd68ced3b4434e` / `origine` | T1, 1 | infrastructure_error | — | — | non disponible |
| 9 min 32 s | `00b8f673dfd142ef` / `d995469144fa4584` | T3, 2 | infrastructure_error | — | — | non disponible |
| 10 min 18 s | `96ed268570b947ab` / `863a66f2a7c94930` | T2, 2 | infrastructure_error | — | — | non disponible |
| 18 min 07 s | `4068c0071be145e3` / `origine` | G, 1 | valid | 1,781623 | 1,771780 | kernel et lancement |
| 20 min 52 s | `154507185f9c4846` / `origine` | G, 1 | valid | 1,010046 | 1,004113 | lancement seul |

## Protocole du rejeu et limites

- Un GH200 ARM, quatre CPU, 16 Go, CUDA/NVRTC 12.6.3 et CMake fixés par empreinte Spack. GPU réservé via SLURM ; aucune mesure GPU concurrente dans l’étude.
- Le protocole archivé est repris sans changement : 11 cas, graines 20261021 et 20261022, masses conservées exactement, tolérances GPU `atol=5e-5`, `rtol=2e-4`. La référence est contrôlée par un oracle CPU FP64 ; pour les grands tableaux, celui-ci porte sur 32 lignes réparties, tandis que la comparaison GPU porte sur toutes les sorties.
- Tous les chronométrages frais utilisent le jeu de confirmation, commun aux 124 programmes. Tailles de performance : 4096, 8192, 16384. Dix échauffements, 100 lancements chronométrés par taille. Moyenne géométrique des trois temps, puis moyenne arithmétique des cinq répétitions.
- Ordre des programmes mélangé de manière reproductible dans chacun des cinq blocs, graine 20261023. La référence de contrôle encadre chaque bloc ; ces mesures sont des répétitions de benchmark, pas des campagnes de recherche indépendantes.
- Les programmes sont distincts selon leurs octets et leurs paramètres. Un changement de commentaire ou d’espacement peut créer une nouvelle identité sans changer l’algorithme. Les fichiers d’origine et les hashes restent disponibles.
- Les hypothèses et leçons du modèle restent des déclarations. Les statuts, temps, erreurs, modifications et sorties de tests proviennent des registres ou des nouvelles exécutions.
- Les études historiques concernent un seul problème. Elles ne suffisent pas à établir une régularité sur d’autres programmes.

## Fichiers pour vérifier ou poursuivre

- [Tableau de bord interactif](TABLEAU-DE-BORD.html) : campagnes, essais, code, diagnostics et commits.
- [Campagnes](tables/campagnes.csv), [124 programmes](tables/programmes-remesures.csv), [138 essais remesurés quand valides](tables/essais-avec-remesures.csv), [15 intégrations](tables/integrations.csv).
- `sources/` : deux fichiers exacts par programme ; `diffs/` : différences avec chaque base.
- `gpu/` : mesures fraîches, contrôles par cas, ordre des benchmarks, environnement et journaux.
- `engine-tests-isolated/` et `regression-tests/` : commandes, logs, résultats JUnit et diagnostics.
- `data/` et `protocol/` : historique, provenance, empreintes, décisions, reçus et plan SLURM.
- `scripts/` et `reproduction-gpu.tar.gz` : collecte, analyse, matrice et payload exact du rejeu.
- `engines/` : archives des 12 révisions testées et sources Python exactes des 7 moteurs réellement embarqués, y compris les états intermédiaires.

Le dépôt d’origine et ses campagnes n’ont pas été modifiés. Aucun push ni nouvelle optimisation manuelle.
