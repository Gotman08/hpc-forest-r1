# CUDA N-body — budget adaptatif corrigé — Luna Max — job 776290

La campagne a exécuté **27 essais de recherche et 2 intégrations**, avec **4 arbres choisis par Mother**. Le meilleur programme confirmé mesure **0.853836 ms**, soit **2.15×** plus rapide que la référence originale mesurée pendant cette campagne.

Ce dernier programme prend 7.19 fois plus de temps que le meilleur de l'ancienne campagne 774157 ; il ne le remplace pas. La durée du pipeline est **28 min 21 s**. Il reste 1 min 39 s avant la cible de 30 minutes.

Le meilleur programme parmi les campagnes comparées reste celui du job **776048**, à **0.099877 ms**. [Son export confirmé](../cuda-nbody-memory-budget-20261022-776048/submission.zip) reste disponible ; le dernier lancement ne le remplace pas automatiquement.

| Campagne | Arbres | Essais de recherche | Intégrations | Durée du pipeline | Meilleur confirmé (ms) |
|---|---:|---:|---:|---:|---:|
| 774157 — Historique, fusion par paires | 3 | 18 | 2 | 25 min 07 s | 0.118800 |
| 775521 — Mémoire avant correction du budget | 3 | 3 | 2 | 14 min 53 s | 0.698771 |
| 775815 — Première correction, deux combinaisons maximum | 3 | 24 | 2 | 25 min 30 s | 0.523785 |
| 776048 — Assemblage adaptatif avant la dernière admission | 4 | 31 | 2 | 27 min 08 s | 0.099877 |
| 776290 — Budget corrigé, décision finale sans lectures superflues | 4 | 27 | 2 | 28 min 21 s | 0.853836 |

La durée du pipeline commence à l'initialisation de la campagne et se termine après confirmation et export. Le temps de file d'attente et la préparation de l'allocation sont exclus. Les durées Slurm figurent séparément dans `job-efficiency.json`.

## Correction du budget

La réserve de finalisation utilisait auparavant les maxima de lectures, réparations et appels comme s'ils allaient tous être consommés. La campagne mémoire 775521 avait ainsi réservé plus de 52 minutes pour une cible totale de 30 minutes et arrêté la recherche après seulement trois essais.

Le contrôleur estime maintenant les appels et les générations probables, puis actualise ces coûts avec les durées observées. Il distingue le nombre de combinaisons prévues du plafond autorisé. Le pilote prévoit initialement deux intégrations ; son plafond de 16 permet de continuer si les résultats et le temps disponible le justifient. Avant chaque lecture facultative ou intégration supplémentaire, il préserve le temps estimé pour produire le code, le vérifier, confirmer et exporter. Un travail déjà admis se termine ; les 30 minutes restent donc une cible d'admission, pas une interruption brutale.

Une combinaison supplémentaire ne réserve qu'une décision obligatoire, son épisode de code et la confirmation. Le coût nominal de plusieurs lectures reste visible dans les traces, mais ne bloque plus un tour qui peut décider avec les preuves déjà consultées. Chaque lecture facultative conserve son admission propre. Ce dernier cas a été identifié dans 776048, puis couvert par un test de régression avant ce lancement.

Sur le lancement final, la recherche s'est clôturée après **20 min 39 s**, puis la finalisation a pris **7 min 41 s**. La réserve à la clôture était de **9 min 16 s**. À la dernière décision, il restait 2 min 26 s, contre 3 min 49 s estimées pour une nouvelle décision, la production du code et la finalisation. Le contrôleur a donc réservé la fin du budget à la confirmation. L'estimation prudente explique le temps finalement inutilisé ; la campagne n'a pas consommé exactement 30 minutes.

N reste variable. Les tests couvrent notamment 2, 3, 5, 7, 20, 56, 500 et 600 arbres dans le calcul du budget ; ce sont des tests du moteur, pas des campagnes GPU de 600 arbres. Mother a choisi 4 arbres pour cette campagne ; 774157 et 775521 en avaient trois, 776048 en avait aussi quatre. TreeQuest AB-MCTS-A et le protocole de vérification sont conservés. Ce lancement a produit deux intégrations : l'autorisation d'un tour tardif sans lecture supplémentaire est couverte par le test de régression, mais aucun troisième tour n'a effectivement été admis ici.

## Programmes réellement produits et évalués

| Arbre | Sujet | Essais | Valides mesurés | Profondeur maximale | Meilleur en recherche (ms) |
|---|---|---:|---:|---:|---:|
| T1 | Tuilage des sources en mémoire partagée | 7 | 7 | 2 | 1.005207 |
| T2 | Diffusion warp des sources par registres et shuffles | 8 | 8 | 3 | 0.889680 |
| T3 | Blocage de plusieurs cibles par thread | 6 | 6 | 2 | 2.590768 |
| T4 | Réduction arithmétique et calcul de l’inverse de la distance | 6 | 3 | 3 | 0.984958 |

Les agents ont produit des sources CUDA et des paramètres de lancement. Le contrôleur les a compilés et évalués sur un GPU GH200. La fusion produit également un nouveau programme soumis aux mêmes contrôles. 62 appels natifs Luna Max ont été vérifiés, dont 10 tours de la conversation Mother. Les lectures mémoire ciblées, les faits d'expériences et les instantanés de code sont conservés dans les preuves.

Les 27 essais comprennent 24 programmes valides mesurés. Un essai a échoué pendant la génération parce qu'une leçon citait une preuve non consultée ou étrangère à son contexte. Quatre demandes de sélection de Mother ont été rejetées, dont des demandes d'arrêt mal formées ; le chemin de repli du contrôleur a produit une deuxième intégration réelle. Celle-ci conserve le noyau de la première et modifie ses paramètres de lancement de 32 à 64. Son temps confirmé, **0.853871 ms**, n'améliore pas le meilleur programme à **0.853836 ms**. L'arrêt final enregistré est une décision de budget du contrôleur.

## Vérification et comparaison

Les **742 tests locaux** passent, ainsi que `python -m ruff check src tests`. Les sources du moteur embarquées ont été comparées au payload figé et aux sources testées.

Le fichier utilisateur original est inchangé : SHA-256 `566e9a4085ff08795269fdb76df607198f835c597ad2dfab4155ea4f0bc33291`. Les 12 fichiers du protocole protégé, du harnais et de la référence sont identiques à ceux de la campagne historique. Aucune solution optimisée ancienne n'a été fournie aux modèles. Le compilateur CUDA/NVRTC et le protocole de mesure sont conservés.

La confirmation utilise 11 cas de correction avec oracle CPU FP64 et cinq échantillons frais. Chaque échantillon est la moyenne géométrique des temps d'événements CUDA pour N = 4096, 8192 et 16384 ; le score présenté est la moyenne de ces cinq échantillons. Compilation, démarrage et transferts sont exclus. Les moyennes ont été recalculées à partir des journaux rapatriés. Les objets Git ont été contrôlés avec `git fsck` ; le code exporté correspond au commit confirmé et à une proposition native du modèle.

Cette comparaison porte sur une exécution par version. Mother a choisi indépendamment N et ses sujets : elle ne permet pas d'attribuer la différence de vitesse au seul budget ou à la seule mémoire. L'ancienne campagne et ses exports sont conservés.

## Livrables

- [Export du meilleur programme confirmé de ce lancement](submission.zip) : noyau CUDA device, paramètres de lancement et reçu du contrôleur pour le harnais NVRTC.
- [Source CUDA optimisée](optimized/src/nbody_kernel.cu) et [paramètres de lancement](optimized/src/launch.json).
- [Comparaison détaillée](comparison.json), [audit indépendant](audit.json), [résultats du contrôleur](results.json) et [tests locaux](verification.json).
- [Entrée réellement fournie aux modèles et limites du contexte](INPUT.md), avec les messages initiaux exacts.
- [Archive des preuves](evidence.zip) : journaux, dépôts et instantanés, échanges natifs, payload et vérification.

Commit confirmé : `6dc99abed60b4a25c79a582edf996c33bf83d242`. Empreinte de la source exportée : `4b787d26122c687f91b78396f46200b2ce4526cae6de1da456bf0f26f2d3d86f`. Aucun commit ni push du projet n'a été exécuté par cette intervention ; les commits de candidats appartiennent aux dépôts de campagne gérés par le contrôleur.
