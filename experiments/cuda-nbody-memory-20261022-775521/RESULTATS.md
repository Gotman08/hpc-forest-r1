# Résultat du harnais mémoire — CUDA N-body

La campagne ROMEO **775521** a terminé toute la chaîne avec **Luna Max** (`gpt-6-luna`, effort `max`) : choix de N, code des arbres, contrôles GPU, consultation des archives, deux combinaisons codées par Mother et confirmation indépendante.

Le programme retenu passe de **1,846 ms à 0,699 ms** : **2,64× plus rapide**, soit **62,2 % de temps en moins**. Il améliore aussi de **30,7 %** le temps confirmé du meilleur arbre seul.

## Ce qui s’est réellement passé

Mother a choisi **3 arbres**, sans nombre imposé dans le code. Cet essai court comporte un sommet de recherche par arbre, avec réparations internes, puis deux expériences d’intégration.

| Programme | Piste | Recherche (ms) | Confirmation (ms) |
| --- | --- | ---: | ---: |
| Référence | Kernel fourni | 1,857 | 1,846 |
| T1 | Mémoire partagée | 1,008 | 1,008 |
| T2 | Deux particules cibles par thread | 2,605 | — |
| T3 | Réduction du calcul arithmétique | Incorrect | — |
| Combinaison 1 | T1 + idée de T2 | 1,647 | — |
| Combinaison 2 | T1 + idée de T3 adaptée et réparée | **0,699** | **0,699** |

La première combinaison, correcte mais moins rapide que T1, n’a pas remplacé la meilleure référence. Mother est repartie de T1 pour la seconde. Le résultat gagnant conserve le calcul des forces pondéré par les masses et ajoute un calcul de distance inverse avec `rsqrtf`, affiné par une étape de Newton.

Les temps sont la moyenne de répétitions du temps géométrique des kernels pour **N=4096, 8192 et 16384**, sur **NVIDIA GH200 120GB**, avec NVRTC CUDA 12.6.3. La confirmation utilise cinq répétitions, d’autres données, un contrôle GPU de référence et un oracle CPU FP64. Les 11 cas de correction du gagnant passent. Compilation et transferts sont exclus de cette métrique.

## Mémoire et contrôle

- Politique réelle **TreeQuest AB-MCTS-A**, version 0.3.2.
- **18 appels natifs**, dont **13 tours de la même conversation Mother**.
- **4 lectures ciblées acceptées**, 8 instantanés de développement, 6 fiches d’expérience dont la référence, **5 leçons**.
- Deux demandes de lecture mal formées ont été rejetées. Une leçon citant une preuve non autorisée a également été rejetée ; Mother a corrigé sa proposition.
- Les contrôles sont restés distincts des déclarations des modèles. Chaque combinaison a reçu sa propre évaluation.
- La source originale et le validateur protégé sont inchangés.
- Usage enregistré : **8 536 702 tokens**, incluant les entrées mises en cache ; ce nombre cumule les appels et ne représente pas une taille de contexte.
- Allocation réussie : 15 min 22 s. Avec le premier essai de diagnostic : **25 min 14 s de GPU** au total.

Le premier essai, **775456**, a révélé un contrat incomplet pour le nouveau tour de sélection. La phase et le schéma ont été ajoutés, un test a reproduit le problème, puis une nouvelle campagne a été lancée. Les campagnes et journaux antérieurs sont conservés.

## Validation du logiciel

La dernière suite complète a exécuté **716 tests : 715 réussites et un échec de temporisation dans un test unitaire de transport**. Son délai de trois secondes démarrait avant les imports et l’initialisation du worker ; la requête expirait donc avant son traitement. Le démarrage du délai a été déplacé après cette préparation, en conservant sa durée et toutes les assertions. Aucun validateur de campagne n’a été modifié.

Après cette correction, **les 26 tests du module de transport passent**. Les autres 715 résultats proviennent de la suite complète : il ne s’agit pas d’une nouvelle exécution intégrale sans échec. Les huit tests ciblant le contrat de sélection et l’intégration passent également. **Ruff et `git diff --check` passent.** Les commandes, résultats et empreintes des journaux sont conservés dans `verification.json`.

## Livraison et preuves

- [Kernel optimisé](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/optimized/src/nbody_kernel.cu)
- [Configuration de lancement](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/optimized/src/launch.json)
- [Paquet vérifié](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/submission.zip)
- [Audit des sources, mesures et reçus](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/audit.json)
- [Rapport complet du contrôleur](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/rapport.md)
- [Résultats structurés](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/results.json)
- [Archive locale des preuves et versions de code](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/evidence.zip)
- [Validation logicielle](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/cuda-nbody-memory-20261022-775521/verification.json)
- [Architecture et configuration du harnais](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/docs/MEMOIRE.md)

Employer le kernel avec sa configuration validée : **256 threads**, **256 sorties par bloc**, **4096 octets de mémoire partagée dynamique**. Le paquet contient le manifeste du commit confirmé.

Les tests de pagination couvrent N=2,3,5,7,20,56,78,500,600. Cette campagne native en a utilisé 3 ; elle ne mesure pas l’exécution simultanée de 600 modèles, ni un gain général sur tous les programmes. La borne de mémoire concerne chaque vue injectée ; la conversation native conserve sa compaction automatique.
