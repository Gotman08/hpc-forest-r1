# Validation diversifiée du conseiller — lot préenregistré

Demandé pendant les essais de régression UTF-8/Mandelbrot : **six problèmes
supplémentaires, avec et sans TabPFN, mêmes budgets**. Ce lot contient douze
exécutions neuves, une paire par problème. Le moteur reste exactement celui
validé par les 1 095 tests du lot `control-recovery-20261026` : aucun ajustement
de Forest à partir des résultats de ce lot n'est autorisé pendant sa mesure.

## Choix fixé avant les recherches

| Problème | Famille couverte | Graine de recherche | Ordre |
| --- | --- | --- | --- |
| Base64 | Décodage d'octets | 137 | sans, avec |
| Argmin | Réduction et égalités | 149 | avec, sans |
| Popcount récurrent | Calcul entier avec dépendance | 163 | sans, avec |
| GEMM CPU | Calcul matriciel dense | 179 | avec, sans |
| Stencil 3D | Voisinage spatial et accès mémoire | 191 | sans, avec |
| Black–Scholes | Calcul flottant et fonctions mathématiques | 211 | avec, sans |

Ces familles existent dans la suite de référence du projet ; elles sont nouvelles
pour ce comparatif TabPFN, pas nécessairement inédites dans tout l'historique de
Forest ou dans les données d'entraînement des modèles. Leur choix ne dépend pas
des speedups de la recherche en cours. Les programmes commencent au code naïf,
avec conversations, mémoire et exemples du conseiller vides.

Les formes, graines et régimes de mesure seront figés dans `protocol.json` avant
soumission. Plusieurs tailles seront utilisées pendant la recherche. Des tailles
et graines supplémentaires seront réservées à une remesure finale des livraisons,
sans retour vers les agents ni nouvelle sélection de code sur ces résultats.
Les oracles et les tolérances de correction sont ceux de la suite protégée.

## Comparaison

Un seul Forest, GPT-6 Luna effort max partout, aucune combinaison de modèles.
Les deux conditions d'une paire utilisent le même nœud, les mêmes ressources,
entrées et plafonds : 5 400 s de recherche, 7 200 s du lancement à la fin.
L'attente des modèles et le coût du conseiller comptent dans ces plafonds.
Les deux conditions s'exécutent successivement. Les ordres sont équilibrés
entre les six problèmes ; une seule paire par problème ne mesure pas la variance
des recherches sur ce problème.

Le prétest GEMM initial (`784719`) a rejeté le naïf : son adaptateur historique
ne calcule que pour n=32,128,1024. Aucun bras d'optimisation n'avait démarré.
L'[amendement enregistré](protocol-amendment-gemm.json) ajoute le même calcul
élémentaire r,c,k pour les autres n, sans changer les entrées, l'oracle, les
tolérances ni Forest. Les fichiers initiaux restent dans `inputs/gemm_cpu`,
ceux utilisés pour la nouvelle soumission dans `inputs/gemm_cpu_v2`. Cette
référence élargie ne doit pas être confondue avec un speedup publié auparavant.

Les échecs, codes incorrects, clôtures précoces et absence d'appel au conseiller
restent rapportés. Aucun remplacement après examen des résultats. Les conclusions
sur les cas connus (régression), les familles supplémentaires (ce lot) et les
entrées finales réservées seront séparées. On ne prétendra pas démontrer une
supériorité universelle avec douze exécutions.
