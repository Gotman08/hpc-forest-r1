# CUDA N-body — première correction du budget — job 775815

Cette relance intermédiaire a produit **24 essais de recherche sur trois arbres**, puis deux programmes d'intégration. Le meilleur confirmé mesure **0,523785 ms**, contre 0,698771 ms pour la première campagne mémoire et 0,118800 ms pour l'ancienne campagne 774157. L'ancien meilleur programme reste conservé.

La correction de la réserve a permis de poursuivre la recherche. La durée totale de **25 min 30 s** a toutefois laissé **4 min 30 s** disponibles : le pilote limitait encore la fusion à deux combinaisons. Ce résultat a conduit à séparer le nombre prévu de combinaisons du plafond autorisé, puis à lancer la campagne finale 776048. Le budget GPU des deux relances reste dans la limite cumulée de deux heures autorisée pour cette intervention.

Le protocole protégé et le code original sont inchangés. Les programmes proviennent d'appels natifs Luna Max et ont été compilés, vérifiés et mesurés par le contrôleur sur GH200. Le meilleur confirmé passe 11 cas de correction et possède cinq mesures fraîches. L'audit des exports, des journaux, des instantanés de développement et des objets Git a réussi. La version de ce lancement a passé 737 tests locaux et Ruff.

- [Export confirmé](submission.zip)
- [Audit indépendant](audit.json)
- [Comparaison intermédiaire](comparison.json)
- [Tests de cette version](verification.json)
- [Preuves archivées](evidence.zip)
- [Comparaison finale après correction du plafond](../cuda-nbody-memory-budget-20261022-776048/RESULTATS.md)

Le code du noyau est livré pour le harnais NVRTC avec son contrat de lancement. Les anciennes campagnes n'ont pas été modifiées. Aucun commit ni push du dépôt principal n'a été exécuté.
