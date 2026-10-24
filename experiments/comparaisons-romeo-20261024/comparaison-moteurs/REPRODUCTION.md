# Reproduire et vérifier cette comparaison

## Lire les résultats

Ouvrir `TABLEAU-DE-BORD.html` dans un navigateur : les données sont embarquées, sans bibliothèque externe ni accès réseau requis. Le rapport `RAPPORT.md` explique les résultats et la méthode `METHODE.md` précise les limites. Les CSV sont encodés en UTF-8 avec BOM et utilisent une virgule comme séparateur.

Le dossier voisin `comparaison-historique` contient la chronologie des 19 commits, les suites de tests des 12 révisions, les sept paquets déployés d'origine et le premier rejeu de 124 programmes. Le présent dossier contient les 21 campagnes neuves, leur transport, leurs sources et le second rejeu.

## Ce qui est figé

- `capsules/S1`, `S2` et `S3` : les 21 archives exactes envoyées au calculateur, avec leur relais local lorsqu'il est disponible. Les sources du moteur, les pilotes et les vérificateurs n'ont pas été modifiés. Les identifiants et chemins de session sont propres à chaque lancement.
- `protocol/`, `relance-controlee/protocol/`, `serie-atomique/protocol/` : plans SLURM, soumissions, reçus SHA-256, configurations, identités des moteurs et entrées de validation.
- `evidence/` dans chaque série : registre SQLite, résultats du contrôleur et journaux structurés ; les archives brutes `results.tar.gz` sont également conservées dans le dossier local.
- `native/` dans chaque série : requêtes, réponses publiques, invocations, métriques et diagnostics locaux. Les fichiers de connexion privés des adaptateurs ne sont pas distribués.
- `gpu-comparaison/` : archive d'entrée du rejeu, sources exactes dédupliquées, protocole, ordre des blocs et résultats par programme.

L'archive `historique-moteurs-et-cuda.zip` contient les deux rapports, les sources, les registres, les journaux et les capsules. Elle exclut les 21 archives brutes de résultats déjà représentées par ces pièces, afin d'éviter de dupliquer les tableaux binaires volumineux. `historique-moteurs-et-cuda-index.json` en donne la liste et les empreintes. Les archives exclues restent dans les dossiers locaux `evidence/` ; les tableaux binaires non rapatriés de S3 restent sur ROMEO.

## Recalculer les analyses sans GPU ni modèle

Extraire le ZIP en conservant son dossier `outputs/`. Depuis son dossier parent, utiliser Python 3.10 ou plus récent :

```text
python outputs/comparaison-moteurs/scripts/verify_engine_inputs.py
python outputs/comparaison-moteurs/scripts/verify_engine_replay.py
python outputs/comparaison-moteurs/scripts/engine_diagnostics.py
python outputs/comparaison-moteurs/scripts/build_engine_behavior.py
python outputs/comparaison-moteurs/scripts/build_engine_comparison.py
python outputs/comparaison-moteurs/scripts/build_engine_dashboard.py
python outputs/comparaison-moteurs/scripts/build_study_overview.py
```

Ces analyses utilisent la bibliothèque standard Python. Elles vérifient les empreintes, les cas de correction et les calculs géométriques et arithmétiques depuis les journaux. `FOREST_COMPARISON_ROOT` permet d'indiquer un autre dossier racine contenant `outputs/`. Le script de rapport conserve les conclusions éditoriales complémentaires du dossier lorsque celles-ci sont séparées des tableaux générés.

Pour revérifier un fichier local, comparer son SHA-256 à `MANIFEST-SHA256.json`. Le manifeste ne s'inclut pas lui-même. Le fichier `.zip.sha256` correspond à l'archive livrée. Si une analyse est régénérée, ses octets ou sa date de génération peuvent changer : le manifeste correspond aux fichiers de la livraison initiale.

## Rejouer les programmes sur GPU

`gpu-comparaison/payload.tar.gz` contient `gpu_replay.py`, le banc CUDA, le protocole de validation, `variants.json`, les sources et un manifeste d'entrée. Le script original de soumission se trouve dans `gpu-comparaison/mcp-plan.json` ; l'archive de départ est vérifiée avant extraction.

Le calcul utilise un GH200 ARM, CUDA/NVRTC 12.6.3 et CMake 3.30.5. Le protocole nécessite NumPy et construit le banc C++/CUDA sur le nœud de calcul. Adapter uniquement les chemins, l'identifiant de session, l'environnement logiciel et les paramètres d'allocation à la machine cible. Utiliser un nouveau dossier distant : les scripts refusent de réutiliser le dossier d'une exécution précédente. Ne pas remplacer des résultats existants.

Dans le dossier extrait, définir `FOREST_CUDA_HARNESS` vers le binaire compilé et `FOREST_CUDA_CACHE` vers un nouveau dossier de cache, puis exécuter `gpu_replay.py`. Il vérifie les sources, construit les programmes, vérifie les 22 cas, puis exécute cinq blocs mélangés avec une référence avant et après chaque bloc. Les résultats sont réunis dans `replay-results.tar.gz` avec un reçu SHA-256.

Les temps d'une autre machine ne doivent pas être comparés directement aux valeurs GH200 sans nouvelle référence. La conformité numérique des 22 cas ne constitue pas une preuve universelle pour toutes les entrées possibles.

## Relancer les moteurs

Les capsules constituent la source exacte des moteurs testés. `engine_study.py`, les deux versions du relais et les adaptateurs sont fournis comme traces exécutables de l'orchestration. Leur configuration d'origine référence les chemins Windows et ROMEO de cette étude ; ils ne forment pas un lanceur universel prêt à exécuter sur une autre installation.

Une relance exige une nouvelle session, une mémoire vide, un dossier de résultats distinct, l'environnement Python du moteur, une connexion ROMEO autorisée et un accès au modèle. Les identifiants d'autorisation fournis décrivent les campagnes terminées et ne doivent pas être réutilisés pour un nouveau lancement. Les clés privées de connexion locales doivent être créées de nouveau.

Conserver le même programme initial, le budget d'admission de 1 800 secondes, `finish-started`, la graine 23, `gpt-6-luna` avec effort `max`, les consignes historiques et le protocole. Le modèle est un service : sa version interne et son échantillonnage ne sont pas figés par la graine du moteur. Une relance ne garantit donc pas les mêmes propositions ni le même meilleur programme.

## Diagnostics à interpréter correctement

- Un programme valide peut appartenir à une campagne dont l'export a échoué.
- Une génération refusée pour des références de mémoire invalides n'est pas une preuve d'erreur CUDA : son code n'a pas nécessairement été évalué.
- La somme des durées natives parallèles n'est pas la durée murale de la campagne.
- Les compteurs de jetons d'une conversation persistante sont cumulés par le service. Les colonnes normalisées utilisent leurs différences ; les valeurs brutes restent disponibles. Un appel interrompu sans compteur connu est marqué comme tel, sans inventer sa consommation.
- Les observations de S1 et S2 ne sont pas des répétitions propres de S3 : le transport et les interruptions diffèrent.
