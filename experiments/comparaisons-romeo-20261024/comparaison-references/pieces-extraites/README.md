# Preuves et codes — comparaison ROMEO / Forest

Voir rapport/RAPPORT.md pour les résultats et limites. Toutes les dates sont celles de la campagne du 23 octobre 2026.

L’audit complémentaire rapport/DETAILS-FOREST.md détaille les sessions neuves, la mémoire persistante interne, les interventions de préparation, le nombre d’arbres et l’architecture hybride ROMEO / relais local / inférence hébergée. AUDIT-FOREST.json fournit les constats et empreintes ; les invocations complètes restent dans les dossiers de travail locaux et ne sont pas exportées avec la configuration de connexion du relais.

- references/protected-suites.tar.gz : sources ET binaires effectivement employés sur ROMEO, journaux de construction et données de scène. Le MANIFEST.json interne contrôle 374 fichiers. Extraire sur Linux ; les binaires CPU sont x86_64 et les binaires GPU aarch64/sm_90.
- candidats/ : sources retenues et intégration G, commits et SHA256. Les sources restent inchangées après la recherche.
- campagnes/ : archives natives contenant les dépôts Git, essais, sorties, diagnostics, confirmations et mémoire ; plans et protocoles protégés de chaque campagne. Le premier deferred échoué est distinct de deferred_r2.
- moteur/ : instantané du moteur gelé, identique dans les 22 lancements ; metadata/engine-file-manifests.json vérifie chaque fichier de chaque copie.
- mesures/ : mesures brutes de référence, mesures finales et environnements.
- scripts/ : acquisition, construction, protocoles, analyses et génération des livrables. Les chemins ROMEO correspondent à la campagne et doivent être adaptés pour une nouvelle installation.
- entree/ : classeur original inchangé ; licences/ : licences des dépôts sources disponibles.

Recalcul des livrables : placer les fichiers de mesures et metadata/analysis.json dans un dossier conforme à work/reference-study, puis exécuter analyze_comparison.py, build_report.py, build_dashboard.py et build_workbook.mjs. Le dernier requiert @oai/artifact-tool. L’analyse utilise uniquement la bibliothèque standard Python. Les protocoles CPU requièrent NumPy ; les cas GPU complémentaires torch/Triton/CUDA. Les versions exactes et hashes Spack sont dans les journaux et scripts de construction.

Pour rejouer les mesures, construire les références avec cpu_build.py / render_build.py et les scripts GPU, puis exécuter les scripts *_final_compare.py dans des allocations SLURM de l’architecture correspondante, avec les compilateurs et nombres de cœurs/GPU indiqués. Conserver la même allocation entre variantes d’un cas et les mêmes fichiers d’entrée. Les candidats candidats/*/manifest.json fournissent les empreintes attendues. Les fichiers d’entrée volumineux rendus sont inclus dans l’archive protégée.

Rejouer une recherche Forest demande un accès modèle autorisé et une installation de TreeQuest 0.3.2 ; les configurations et le moteur sont fournis, les identifiants du compte et du relais ne le sont pas. Ne pas remplacer les mesures finales par les meilleurs temps de recherche. Les compteurs de tokens natifs n’ont pas été audités.

Le CSV et les colonnes de calcul utilisent des nombres bruts ; les arrondis sont uniquement une présentation. Les lignes non reproduites restent vides/NR. Le changement publié→ROMEO ne mesure pas l’effet du matériel seul.
