# Historique comparé de HPC Forest

Commencer par le [tableau de bord interactif](TABLEAU-DE-BORD.html), ou lire le [rapport détaillé](RAPPORT.md).

Le dossier couvre 19 commits, 7 campagnes, 138 essais et 124 programmes CUDA distincts rejoués. Les 124 programmes passent les contrôles de correction ; chacun dispose de cinq mesures fraîches. Les versions du moteur font l’objet de vérifications fonctionnelles distinctes. Aucune nouvelle recherche avec Mother n’a été lancée.

- `sources/` : tous les programmes rejoués, sans modification.
- `diffs/` : les changements de chaque essai par rapport à sa base.
- `tables/` : comparaisons CSV, y compris les échecs et les mesures par taille.
- `gpu/` : journaux, contrôles et échantillons du job 780574.
- `engines/` : archives des révisions et des moteurs réellement embarqués.
- `engine-tests-isolated/`, `regression-tests/` : résultats des tests et diagnostics.
- `protocol/` : provenance, vérifications et reçus d’exécution.

Pour auditer ou refaire les calculs, consulter [REPRODUCTION.md](REPRODUCTION.md). Pour ouvrir le tableau de bord depuis l’archive ZIP, extraire tout le dossier et conserver les sous-dossiers à côté du fichier HTML. Le tableau de bord fonctionne sans réseau.
