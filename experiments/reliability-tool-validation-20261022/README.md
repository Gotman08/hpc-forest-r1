# Validation en lecture seule du comparateur

`comparison.json` résulte du nouvel outil `hpc_forest.reliability.compare` appliqué aux registres préservés des campagnes 776048 et 776290. Leurs empreintes ont été comparées avant et après la lecture : fichiers inchangés. Aucun modèle ni GPU n'a été appelé.

Les reçus et échantillons confirment respectivement des accélérations de 18,5811× et 2,1484× par rapport à leur référence confirmée. Les résultats de recherche sont 28 programmes mesurés valides sur 31 essais et 24 sur 27. Dans la dernière campagne, deux programmes sont incorrects et un essai n'a pas de mesure ; cet essai n'est pas transformé en erreur de correction.

Le regroupement strict produit deux groupes d'une seule campagne : versions du contrôleur et identités de campagne différentes, entre autres. Le rapport ne les présente donc pas comme des répétitions démontrant la régularité. L'analyse comparative détaillée déjà conservée dans `../reliability-analysis-20261022-776048-776290/` justifie séparément la comparaison historique. Ce fichier valide la lecture et le calcul du nouvel outil, pas une amélioration expérimentale du moteur modifié.
