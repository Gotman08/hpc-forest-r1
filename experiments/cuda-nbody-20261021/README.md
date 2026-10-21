# Campagne CUDA N-corps du 21 octobre 2026

Archive du test réel Luna MAX (`gpt-6-luna`, effort `max`) sur un GPU GH200 ROMEO.
Le fichier fourni est conservé dans `input/nbody_naive.cu`; les transformations
ont été produites par Mother et ses enfants, sans optimisation opérateur.

- 4 arbres AB-MCTS-A parallèles, 3 passes, 12 programmes de recherche valides.
- Même conversation Mother, 3 fusions par paires et G final confirmé sur 5 mesures.
- Objectif GPU confirmé : référence 1,848762 ms, G final 0,112061 ms (16,50×).
- L'objectif agrège N=4096, 8192 et 16384; il ne mesure pas le temps total de l'application.
- Cible de 30 minutes; confirmation achevée en 21 min 31 s. Réserve encore prudente.
- Le job 772923 a échoué à l'export standard (Makefile/run.sh absents).
  `evidence/confirmed-sources.zip` récupère à l'identique l'archive déjà créée.
  Le statut brut `pipeline_complete=false` est préservé.
- 16 consultations documentaires; MCP ROMEO chargé, sans appel par les modèles.

Consulter [le rapport](RAPPORT.md), [le résumé](summary.json),
[les temps CUDA bruts](gpu-audit.json) et [le code confirmé](resultat/src/nbody_kernel.cu).
Les 21 journaux de confirmation contiennent les mesures par taille et les contrôles.
Les originaux complets du travail restent conservés dans le dossier local de campagne.
Les conversations natives, configurations d'authentification et reçus d'autorisation
ne font pas partie de cette archive publique.

## Sources et protocole gelés

`payload.tar.gz` est la charge utile exacte envoyée avant le test (81 fichiers,
SHA-256 `2819a3b48b41ba6620779f78bad77b3aa39c6d4804089e7a54a2e8352cc33876`).
Elle contient les sources du moteur, les réglages, l'entrée originale, le harnais
CUDA/NVRTC et le protocole de validation. `protocol/` expose les scripts du cas
pour lecture sans extraire l'archive. Le harnais dérive de la copie locale
`agentic-cuda-optimizer`, commit `1e9464da54dfc651337a97c3643bfeefec712bc1`,
conservée et identifiée par les empreintes de la charge utile.

Ce dossier est un instantané historique, pas le lanceur GPU générique du projet.
Les scripts de préparation et de relais conservent les chemins et le scope du test.
Les chemins absolus présents dans les reçus décrivent la machine du test et ne sont
pas des valeurs à réutiliser sur une autre installation. Préparer une nouvelle
campagne, avec de nouveaux chemins et reçus, pour toute nouvelle exécution.
Ne pas réutiliser l'autorisation ni relancer les appels natifs de cette campagne.

La validation possède 11 cas par phase, des entrées distinctes pour la confirmation,
un contrôle de toutes les sorties par rapport au kernel d'origine et un oracle CPU
FP64 pour valider cette référence. Les temps sont mesurés par événements CUDA,
avec 10 échauffements et 100 lancements par taille. Compilation et transferts exclus.
Les tests de l'adaptateur (17) et du moteur (659, Ruff réussi) sont référencés ici.

Le snapshot conserve les résultats négatifs et incidents de transfert, ainsi que
les récupérations sans nouvelle inférence ni allocation HPC. Les vérifications
de calcul, le succès de l'export standard et l'utilisation effective des MCP
restent des faits distincts.
