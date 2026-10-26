# Lire les CSV

- **comparison-summary.csv** réunit les six familles : speedups des deux distributions, durées, essais, arrêts, erreurs, analyses indisponibles et appels TabPFN. C'est le fichier de comparaison principal.
- **registered/common-comparison.csv** et **reserved/common-comparison.csv** utilisent la remesure finale 784761. Les fichiers `common-thread-times.csv` et `common-raw-samples.csv` voisins détaillent tailles, threads et cinq rondes.
- **generalization-comparison.csv** et **reserved-source-audit.json** vérifient les mêmes commits livrés, sans sélection sur le résultat réservé.
- **timing-dispersion.csv** décrit la dispersion des cinq mesures par code et régime. Il ne mesure pas l'incertitude des recherches LLM.
- **arms.csv** et **paired-comparison.csv** conservent les résultats de recherche et la première remesure dans chaque paire. Le champ historique `speedup_common` dans arms.csv signifie « commun à la paire » ; il ne doit pas être confondu avec le résultat final du job 784761.
- **control-recovery.csv**, **control-events.csv**, **analyst-quality.csv**, **closure-quality.csv** et **idle-recovery-effects.csv** détaillent le fonctionnement, les reprises, les échecs et les décisions.
- **learning-curves.csv** contient les préfixes à 10/30/60/90 minutes de la même recherche ; ce ne sont pas des répétitions indépendantes, ni nécessairement les codes finalement livrés.

Les cellules sans livraison restent vides. Ne pas convertir Popcount avec conseiller en zéro speedup, ni le retirer du taux de livraison. Le CSV de synthèse conserve le motif de son échec initial.

Les CSV destinés à Excel sont UTF-8 avec BOM ; utiliser `utf-8-sig` pour les lire en Python.
