# À faire — notes de conception HPC Forest

Note du 22 octobre 2026. Ces points consignent la discussion ; ils restent à mettre en œuvre.

## Améliorer progressivement le meilleur code après les recherches

À la fin des recherches des N arbres, prendre comme base le programme correct dont le temps mesuré en millisecondes est le plus faible. Conserver son code comme point de départ et lui apporter des améliorations ciblées issues des autres recherches, plutôt que demander une réécriture complète depuis zéro.

- [ ] Sélectionner le meilleur programme correct mesuré parmi les résultats des N arbres, avec un même protocole et une même cible de mesure.
- [ ] Reprendre exactement les sources de ce programme comme base de l'assemblage final.
- [ ] Consulter les idées et les variantes des autres arbres, y compris celles dont le programme complet est plus lent : une transformation peut devenir utile lorsqu'elle est adaptée au meilleur code.
- [ ] Faire proposer à Mother des modifications ciblées de cette base pour intégrer les idées complémentaires susceptibles de réduire encore le temps d'exécution.
- [ ] Compiler, vérifier la correction et mesurer chaque variante avec le protocole existant. Une combinaison constitue un nouveau candidat évalué ; ses gains ne sont pas supposés ni additionnés à ceux de ses sources.
- [ ] Conserver la modification seulement si le programme reste correct et devient plus rapide. Sinon, garder le meilleur code précédent.
- [ ] Après chaque amélioration retenue, utiliser ce nouveau meilleur code comme base pour essayer d'autres idées, selon le budget disponible.
- [ ] Soumettre le meilleur résultat à la confirmation indépendante et conserver la provenance des idées intégrées.

L'objectif est de profiter de la diversité des sujets explorés par les N arbres pour gagner encore en vitesse sur le meilleur résultat déjà obtenu. Toutes les idées disponibles peuvent être examinées ; leur intégration dépend de leur compatibilité et des mesures, sans obligation de toutes les ajouter.
