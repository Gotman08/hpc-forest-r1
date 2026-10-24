# Reproduire ou auditer cette étude

Le rapport principal est `RAPPORT.md`. Ouvrir `TABLEAU-DE-BORD.html` directement dans un navigateur : son affichage, ses filtres et ses graphiques n’ont aucune dépendance réseau. Garder les autres dossiers à côté pour suivre les liens vers les sources et les preuves.

## Périmètre exact

Le dépôt source est `hpc-forest-r1`, HEAD `934627c1399b48e4aa0f25630e9c4223680a3511`. Les 19 commits accessibles localement ont été recensés. Les 7 registres CUDA ont été lus en mode SQLite lecture seule. Les objets Git archivés ont été vérifiés avec `git fsck --full` ; aucun état Python sérialisé de recherche n’a été exécuté pour cette collecte.

Les 124 programmes sont les couples de fichiers `src/nbody_kernel.cu` et `src/launch.json` distincts octet pour octet qui possèdent au moins une évaluation historiquement valide avec un temps positif. Les 152 occurrences conservent campagne, commit, essai et phase. Les programmes lents et le programme original sont inclus. Les copies exactes sont regroupées, sans prétendre regrouper toutes les équivalences sémantiques.

Les programmes incorrects, les générations échouées et les incidents d’infrastructure figurent dans les 138 essais historiques. Ils ne sont pas transformés en nouveaux programmes valides. Les 15 intégrations restent des essais distincts.

## Rejeu GPU

`reproduction-gpu.tar.gz` est le payload exact envoyé sur ROMEO pour le job 780574. Son empreinte, la commande et les logiciels Spack sont conservés dans `protocol/gpu-replay-plan.json` et `protocol/job-receipt.json`. Il contient les 124 programmes, une copie supplémentaire de la référence comme contrôle, le protocole historique, le harnais et le script de rejeu. Le manifeste interne protège les fichiers avant le démarrage.

Pour une nouvelle exécution, extraire ce payload dans un nouveau dossier d’une allocation GH200 ARM. Les chemins du plan sont ceux de l’exécution de cette étude : utiliser de nouveaux chemins, sans écraser l’ancienne allocation. Charger les logiciels fixés dans le reçu, puis exécuter sur le nœud de calcul :

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export FOREST_CUDA_HARNESS="$PWD/harness-build/cuda_test_harness"
export FOREST_CUDA_CACHE="$PWD/cache"
cmake -S cuda_test_harness -B harness-build -DCMAKE_BUILD_TYPE=Release
cmake --build harness-build --parallel 4
python -u gpu_replay.py
```

Le Python doit fournir NumPy ; celui de l’étude est identifié dans le reçu. Le harnais exige CUDA/NVRTC 12.6.3. Aucun calcul ne doit être fait sur le nœud de connexion. Le script refuse un dossier `results` préexistant, vérifie le manifeste, effectue le préflight, contrôle les deux phases puis mesure cinq blocs avec ordre mélangé. Les contrôles n’ajustent aucun candidat ni aucune tolérance.

Le script archive les résultats JSON et les journaux, mais conserve les grands fichiers binaires intermédiaires sur le calculateur. `gpu/results/records/` contient les erreurs numériques par cas, les masses exactes, les temps par taille et tous les échantillons. `gpu/results/environment.json` contient l’environnement observé. Les traces de harnais indiquées dans ces enregistrements restent sur le dossier distant original.

## Matrice des moteurs

`engine-tests-isolated/<commit>/result.json` conserve la commande exacte, la version Python, les résultats JUnit et Ruff. Les snapshots de chaque commit viennent de `git archive`. Les tests sont ceux du commit, sans modification. Les diagnostics de campagne profondément imbriqués sont exclus des snapshots de test pour éviter la limite des chemins Windows ; le fichier `experiments/cuda-nbody-20261021/input/reference.cu` utilisé par un test est extrait depuis le même commit.

Chaque processus a son propre `PYTHONPATH`, `TEMP`, `TMP`, `TMPDIR` et répertoire pytest. Plusieurs suites peuvent fonctionner simultanément. Leur durée n’est donc pas un benchmark comparatif du moteur. Le nombre de tests diffère selon les versions.

Pour les trois dernières révisions, la limite de supervision initiale de 30 minutes a été prolongée avant expiration. Les mêmes processus pytest ont continué, sans relance ni modification des tests. Leur code de sortie a été observé directement avec les handles Windows ; les identifiants et la méthode sont dans `protocol/test-supervision-extension.json`. Le script `finish_engine_matrix.py` documente cette reprise de supervision et contient les identifiants historiques : il ne doit pas être réutilisé tel quel pour une nouvelle exécution. Pour reproduire la matrice, donner directement un délai suffisant à `engine_matrix.py`.

`regression-tests/` applique quelques tests strictement identiques au parent du correctif et au correctif. Le cas des consultations rencontre un module absent dans l’ancienne version ; cette observation est signalée séparément des défauts reproduits sur une interface existante.

## Scripts et chemins

Les scripts d’analyse livrés reprennent les chemins de ce poste et du dépôt conservé. Exécutés dans le dossier livré à son emplacement original, ils retrouvent le dossier de travail de cette étude. Pour déplacer toute l’étude, adapter les constantes `ROOT` et `REPO` dans les scripts concernés. `historical_audit.py` dispose directement des arguments `--repo`, `--work` et `--output`.

Ordre de reconstruction : `historical_audit.py`, `reconstruct_history.py`, matrice des moteurs, import de l’archive GPU, `verify_replay.py`, `analyze_replay.py`, puis `build_report.py`. Le comparateur mathématique ne réutilise pas les moyennes sans contrôle : il recalcule les moyennes géométriques à partir des latences par taille, puis les moyennes de répétitions, écarts-types et accélérations.

La régénération des dates utilise le fuseau Europe/Paris ; installer `tzdata` si nécessaire hors de la période originale du 19 au 24 octobre 2026. Tous les textes des programmes et des diagnostics sont traités comme des données.

## Portée des conclusions

Cette étude remesure les codes archivés et vérifie les mécanismes des moteurs. Elle ne relance pas de recherches neuves avec Mother et ne mesure pas leur probabilité de réussite. Les cinq répétitions GPU servent à mesurer la dispersion du chronométrage ; elles ne sont pas cinq campagnes de recherche indépendantes. Une étude de régularité demanderait plusieurs départs neufs par moteur, avec programme, modèle, budget et protocole contrôlés.

## Sources embarquées et intégrité de la livraison

`engines/commits/` conserve les 12 révisions testées (sources, tests, lanceurs et exemples). `engines/deployed/` conserve les sources Python exactes des 7 moteurs réellement utilisés, y compris les 4 états sans commit identique. Le périmètre de chaque archive est indiqué dans `engines/manifest.json`.

`MANIFEST-SHA256.json` protège les fichiers du dossier livré, sauf le manifeste lui-même. L’archive ZIP de livraison contient ce dossier complet. Les archives d’objets Git et les grands fichiers intermédiaires restent à leur emplacement d’origine ; les fichiers nécessaires à l’examen des résultats sont livrés.
