# Sources des moteurs conservées

`commits/` contient les fichiers Git des 12 révisions testées, extraits sans modification : sources, tests, lanceurs, configurations, documentation et fichiers de dépendances. Les campagnes volumineuses du dépôt sont exclues, sauf la référence CUDA utilisée comme fixture de test ; leurs données sont dans le dossier principal.

`deployed/` contient les sources Python exactes des sept moteurs réellement embarqués. Quatre diffèrent de tous les commits. Ces archives conservent le moteur, pas la totalité du payload de déploiement ni une nouvelle exécution de Mother. Chaque archive possède un manifeste de fichiers. Le manifeste extérieur conserve aussi l’identité de moteur vérifiée.
