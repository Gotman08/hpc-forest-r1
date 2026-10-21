# Essai CUDA N-corps — job ROMEO 772923

Modèle **gpt-6-luna**, effort **max**. Cible : un GPU NVIDIA GH200 sur ROMEO ARM.
Durée configurée : **30 minutes**. Durée jusqu’à la confirmation puis la tentative d’export : **21 min 31 s**.
Aucun quota de tokens, aucun plafond de profondeur ni de cycles. Les modèles admis terminent leur travail.

## Intervention de l’opérateur

Le code initial est celui du fichier fourni. Le seul changement de départ est mécanique : extraction du kernel, suppression de main et des includes hôtes dans cette extraction, ajout de extern "C" pour le point d’entrée. Aucune transformation algorithmique, aucun ancien candidat optimisé et aucune réparation manuelle des propositions. Mother et les enfants ont choisi et écrit leurs transformations seuls.
Empreinte du fichier original : `566e9a4085ff08795269fdb76df607198f835c597ad2dfab4155ea4f0bc33291`. Le fichier original a été conservé.

## Résultats confirmés

La mesure est le temps GPU du kernel par événements CUDA. Elle exclut compilation, allocation, transferts mémoire et démarrage des processus. L’objectif est la moyenne des répétitions de la moyenne géométrique des temps pour 4 096, 8 192 et 16 384 particules.

| Programme | Temps confirmé de l’objectif (ms) | Rapport référence / programme |
|---|---:|---:|
| Référence originale | 1,8488 | 1 |
| Meilleur confirmé `9d292814876943c9` | 0,1121 | 16,50× |
| G final `9d292814876943c9` | 0,1121 | 16,50× |

Réduction du temps GPU de l’objectif : **93,94 %**. Ce pourcentage ne représente pas le temps total de l’application.

Chaque programme confirmé a cinq mesures fraîches sur les entrées de confirmation ; le contrôleur alterne leur ordre de mesure.

| Finaliste | Cinq mesures de l’objectif (ms) |
|---|---|
| `baseline-e1` | 1,8490, 1,8539, 1,8534, 1,8443, 1,8432 |
| `9d292814876943c9` | 0,1123, 0,1120, 0,1108, 0,1131, 0,1121 |
| `cef9331719264e06` | 0,1369, 0,1373, 0,1372, 0,1359, 0,1367 |

| Programme | N=4 096 (ms) | N=8 192 (ms) | N=16 384 (ms) |
|---|---:|---:|---:|
| Référence | 0,9260 | 1,8476 | 3,6933 |
| Meilleur confirmé | 0,0334 | 0,1070 | 0,3942 |
| G final | 0,0334 | 0,1070 | 0,3942 |

Chaque cellule par taille est la moyenne des cinq mesures de confirmation correspondantes.

## Arbres choisis et déroulement

Mother a choisi **4 arbres** sans recevoir la durée ou le temps restant. **12 essais de recherche**, dont **12 programmes corrects mesurés**. Cycles observés : **3**.

| Arbre | Sujet choisi par Mother | Programmes valides | Profondeur valide maximale | Meilleur temps de recherche (ms) |
|---|---|---:|---:|---:|
| T1 | Shared-memory tiled source reuse across output threads | 3 | 1 | 0,9869 |
| T2 | Warp-parallel source reduction for each output particle | 3 | 2 | 0,1512 |
| T3 | Reciprocal-square-root interaction arithmetic | 3 | 2 | 0,8885 |
| T4 | Register-blocked multiple outputs per thread | 3 | 2 | 2,6890 |

Les temps de recherche et les temps confirmés emploient des jeux de données distincts. Ils ne sont pas interchangeables.

Le parallélisme réel des processus natifs est documenté dans `parallel-proof.json`. La fusion contient **3 étapes mesurées**, avec la conversation native Mother `01a15f4d-c734-76b3-b3d1-79fbb9a2de26`. Aucun arbre n’a été relancé après sa fermeture.

| Étape de fusion | Sources mesurées | Temps de recherche G (ms) | Programme retenu pour la suite |
|---|---|---:|---|
| `cef9331719264e06` | `e7e4f078010b4a8a`, `0b61d20a4da644c3` | 0,1361 | `cef9331719264e06` |
| `dfa1304088594a93` | `4ca3c7496b0b40eb`, `7dd235a5cd3f46a3` | 0,8938 | `4ca3c7496b0b40eb` |
| `9d292814876943c9` | `cef9331719264e06`, `4ca3c7496b0b40eb` | 0,1120 | `9d292814876943c9` |

La recherche a été fermée après 901,8 s. Le contrôleur avait encore 898,2 s, estimait 289,1 s pour la passe suivante et réservait 656,2 s à la fin du travail. Temps non utilisé sur la cible de 30 minutes : 509,0 s. Ces chiffres sont les observations de ce test ; la réserve n’a pas été modifiée pendant la campagne.

Tentatives internes du harnais : 16. Propositions refusées en développement avant correction par les modèles : 1. Aucun correctif opérateur.

Tokens natifs réconciliés : 1223227. Les compteurs des reprises Mother sont cumulatifs ; leur somme brute n’est pas une consommation unique.

## Skills, documentation et MCP

Les instructions des skills de phase et des trois skills communs sont vérifiées pour chaque invocation. Leurs déclarations d’utilisation sont conservées séparément des appels réellement observés aux outils.

| Acteur | Appels documentaires réussis | Appels ROMEO réussis |
|---|---:|---:|
| T1 | 4 | 0 |
| T2 | 0 | 0 |
| T3 | 0 | 0 |
| T4 | 0 | 0 |
| mother-final-assembly | 0 | 0 |
| mother-preparation | 12 | 0 |

La disponibilité des deux MCP ne prouve pas leur utilisation. Les transferts du contrôleur via ROMEO ne sont pas comptés comme des consultations des modèles.

Sur ce lancement, les modèles ont effectué 16 appels documentaires réussis et aucun appel ROMEO. L’accès ROMEO était chargé et vérifié pour chaque invocation ; son utilisation effective n’est donc pas confirmée.

Compaction automatique Codex CLI : configuration native conservée ; événement effectivement observé : **non**. Aucun seuil de compaction forcé.

## Validation et preuves

Le harnais compare tous les états produits à la référence CUDA originale, avec tolérances absolue 5e-5 et relative 2e-4, et conservation exacte des masses. La référence a été contrôlée par un oracle CPU FP64 sur les 11 cas de chaque phase, toutes les particules des petits cas et 32 indices répartis des grands cas. Recherche et confirmation utilisent des entrées distinctes.

Tests du moteur corrigé : 659 réussis, Ruff réussi avant ce lancement. Adaptateur CUDA : 17 tests réussis. Préflight GPU : 22 cas réussis. Charge utile gelée : 81 fichiers, SHA-256 `2819a3b48b41ba6620779f78bad77b3aa39c6d4804089e7a54a2e8352cc33876`.

Audit général : `{'pass': 44, 'fail': 2}`. Audit des mesures CUDA : `True`. Audit de fusion : `{'pass': 12}`.

Fichiers principaux : `audit.json`, `gpu-audit.json`, `pairwise-audit.json`, `parallel-proof.json`, `skills-audit.json`, `access-audit.json`, `evidence/results.json`, `evidence/registry.sqlite3`, `evidence/confirmed-sources.zip`.

Le code retenu et son réglage de lancement exact sont copiés dans `resultat/src/`. Le zip contient le programme sélectionné par les confirmations du contrôleur.

## Incident d’export

Le contrôleur a confirmé les programmes puis échoué pendant l’export standard, car l’import CUDA n’avait pas Makefile et run.sh. Le statut brut du job est donc FAILED et pipeline_complete=false. Il ne s’agit pas d’un échec de calcul ou de confirmation. L’archive Git déjà produite avant ce contrôle a été récupérée à l’identique sous le nom confirmed-sources.zip, avec son manifeste et ses empreintes. Aucun programme, test, mesure ni résultat brut n’a été modifié. Aucun modèle ni calcul HPC n’a été relancé. Cet export est une archive des sources CUDA confirmées, sans lanceur autonome ajouté après mesure. Détails : export-recovery.json et job-diagnosis.json.

Six dossiers de diagnostics avaient aussi rencontré un délai de transfert au moment de leur publication. La récupération des fichiers conservés a réussi pour 6 dossiers, avec vérification d’empreintes et sans appel modèle ni allocation supplémentaire. Le premier collecteur des journaux de confirmation a rencontré une erreur de fermeture du client MCP ; sa reprise a récupéré les 21 journaux des trois programmes confirmés. Les 15 mesures brutes ont été rapprochées des résultats de la base. Ces incidents de transfert n’affectent pas les mesures GPU. Détails : diagnostic-recovery.json et confirmation-log-transfers.json.
