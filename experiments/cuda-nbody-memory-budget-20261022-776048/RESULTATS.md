# CUDA N-body — budget adaptatif corrigé — Luna Max — job 776048

La campagne a exécuté **31 essais de recherche et 2 intégrations**, avec **4 arbres choisis par Mother**. Le meilleur programme confirmé mesure **0.099877 ms**, soit **18.58×** plus rapide que la référence originale mesurée pendant cette campagne.

Le temps confirmé est inférieur de 15.93 % à celui de l'ancienne campagne 774157. La durée du pipeline est **27 min 08 s**. Il reste 2 min 52 s avant la cible de 30 minutes.

| Campagne | Arbres | Essais de recherche | Intégrations | Durée du pipeline | Meilleur confirmé (ms) |
|---|---:|---:|---:|---:|---:|
| 774157 — Historique, fusion par paires | 3 | 18 | 2 | 25 min 07 s | 0.118800 |
| 775521 — Mémoire avant correction du budget | 3 | 3 | 2 | 14 min 53 s | 0.698771 |
| 775815 — Première correction, deux combinaisons maximum | 3 | 24 | 2 | 25 min 30 s | 0.523785 |
| 776048 — Budget corrigé et assemblage adaptatif | 4 | 31 | 2 | 27 min 08 s | 0.099877 |

La durée du pipeline commence à l'initialisation de la campagne et se termine après confirmation et export. Le temps de file d'attente et la préparation de l'allocation sont exclus. Les durées Slurm figurent séparément dans `job-efficiency.json`.

## Correction du budget

La réserve de finalisation utilisait auparavant les maxima de lectures, réparations et appels comme s'ils allaient tous être consommés. La campagne mémoire 775521 avait ainsi réservé plus de 52 minutes pour une cible totale de 30 minutes et arrêté la recherche après seulement trois essais.

Le contrôleur estime maintenant les appels et les générations probables, puis actualise ces coûts avec les durées observées. Il distingue le nombre de combinaisons prévues du plafond autorisé. Le pilote prévoit initialement deux intégrations ; son plafond de 16 permet de continuer si les résultats et le temps disponible le justifient. Avant chaque lecture facultative ou intégration supplémentaire, il préserve le temps estimé pour produire le code, le vérifier, confirmer et exporter. Un travail déjà admis se termine ; les 30 minutes restent donc une cible d'admission, pas une interruption brutale.

Sur le lancement final, la recherche s'est clôturée après **20 min 39 s**, puis la finalisation a pris **6 min 28 s**. La réserve à la clôture était de **9 min 15 s**. La décision d'arrêt d'assemblage enregistrée est : `{"action": "finish", "can_read": false, "can_start_round": false, "controller_budget_stop": true, "finish_seconds": 177.33256925809354, "read_required_seconds": 276.89905633199186, "reason": "Remaining time reserved for independent confirmation", "remaining_seconds": 227.1388554573059, "round_required_seconds": 351.5739216374156}`.

N reste variable. Les tests couvrent notamment 2, 3, 5, 7, 20, 56, 500 et 600 arbres dans le calcul du budget ; ce sont des tests du moteur, pas des campagnes GPU de 600 arbres. Mother a choisi 4 arbres pour cette campagne, contre trois pour les précédentes. TreeQuest AB-MCTS-A et le protocole de vérification sont conservés.

## Programmes réellement produits et évalués

| Arbre | Sujet | Essais | Valides mesurés | Profondeur maximale | Meilleur en recherche (ms) |
|---|---|---:|---:|---:|---:|
| T1 | Shared-memory source tiling | 9 | 8 | 2 | 0.889804 |
| T2 | Per-thread multi-target coarsening | 8 | 7 | 3 | 2.582085 |
| T3 | Source-parallel force reduction | 8 | 8 | 2 | 0.132813 |
| T4 | Force arithmetic simplification | 6 | 5 | 3 | 1.014575 |

Les agents ont produit des sources CUDA et des paramètres de lancement. Le contrôleur les a compilés et évalués sur un GPU GH200. La fusion produit également un nouveau programme soumis aux mêmes contrôles. 64 appels natifs Luna Max ont été vérifiés, dont 11 tours de la conversation Mother. Les lectures mémoire ciblées, les faits d'expériences et les instantanés de code sont conservés dans les preuves.

## Vérification et comparaison

Les **741 tests locaux** passent, ainsi que `python -m ruff check src tests`. Les sources du moteur embarquées ont été comparées au payload figé et aux sources testées.

Le fichier utilisateur original est inchangé : SHA-256 `566e9a4085ff08795269fdb76df607198f835c597ad2dfab4155ea4f0bc33291`. Les 12 fichiers du protocole protégé, du harnais et de la référence sont identiques à ceux de la campagne historique. Aucune solution optimisée ancienne n'a été fournie aux modèles. Le compilateur CUDA/NVRTC et le protocole de mesure sont conservés.

La confirmation utilise 11 cas de correction avec oracle CPU FP64 et cinq échantillons frais. Chaque échantillon est la moyenne géométrique des temps d'événements CUDA pour N = 4096, 8192 et 16384 ; le score présenté est la moyenne de ces cinq échantillons. Compilation, démarrage et transferts sont exclus. Les moyennes ont été recalculées à partir des journaux rapatriés. Les objets Git ont été contrôlés avec `git fsck` ; le code exporté correspond au commit confirmé et à une proposition native du modèle.

Cette comparaison porte sur une exécution par version. Mother a choisi indépendamment N et ses sujets : elle ne permet pas d'attribuer la différence de vitesse au seul budget ou à la seule mémoire. L'ancienne campagne et ses exports sont conservés.

## Livrables

- [Export du meilleur programme confirmé](submission.zip) : noyau CUDA device, paramètres de lancement et reçu du contrôleur pour le harnais NVRTC.
- [Source CUDA optimisée](optimized/src/nbody_kernel.cu) et [paramètres de lancement](optimized/src/launch.json).
- [Comparaison détaillée](comparison.json), [audit indépendant](audit.json), [résultats du contrôleur](results.json) et [tests locaux](verification.json).
- [Archive des preuves](evidence.zip) : journaux, dépôts et instantanés, échanges natifs, payload et vérification.

Commit confirmé : `fb0d9a4822413f62bf242c0a021d910821a9ac2a`. Empreinte de la source exportée : `ea8387cd4ace43f406430779101f22a41ecaa8e602fb234609f3cc25513ec2d2`. Aucun commit ni push du projet n'a été exécuté par cette intervention ; les commits de candidats appartiennent aux dépôts de campagne gérés par le contrôleur.

Une dernière correction de l'admission a été appliquée après ce lancement : une combinaison proche de la fin ne réserve plus les lectures que le contrôleur interdirait déjà. Elle est vérifiée dans la campagne 776290. Le présent résultat et ses 741 tests décrivent la version effectivement embarquée dans 776048.
