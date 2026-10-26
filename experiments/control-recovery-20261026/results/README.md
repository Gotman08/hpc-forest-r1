# Lire les mesures

- **common-comparison.csv** : comparaison finale des nouvelles livraisons, toutes remesurées dans le job 784760.
- **historical-comparison.csv** : anciennes et nouvelles livraisons remesurées dans ce même job. Une ancienne livraison absente reste vide.
- **common-thread-times.csv**, **common-raw-samples.csv**, **common-input-audit.json** : temps par régime, échantillons et contrôles d'identité des entrées.
- **arms.csv**, **paired-comparison.csv** : données de recherche et première remesure au sein de chaque job de paire. Le champ historique `speedup_common` d'arms.csv signifie « commun à la paire », et ne doit pas remplacer la remesure finale entre jobs.
- **control-recovery.csv**, **control-events.csv**, **historical-stops.csv** : reprises, reçus et décisions d'arrêt.
- **analyst-quality.csv**, **closure-quality.csv**, **idle-recovery-effects.csv** : qualité des analyses, revues de clôture et admissions après réouverture.
- **learning-curves.csv** : trajectoires aux budgets intermédiaires ; elles ne remplacent pas la confirmation du code livré.

Les CSV utilisent UTF-8 avec BOM lorsqu'ils sont destinés à Excel. Les lecteurs Python doivent employer `utf-8-sig`. Une absence de mesure n'est pas un speedup nul.
