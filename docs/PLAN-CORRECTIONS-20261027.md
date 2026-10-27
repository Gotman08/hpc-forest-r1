# Corrections issues du diagnostic contrôlé du 27 octobre

Périmètre autorisé : améliorer le moteur existant, conserver un seul Forest et
Luna Max, vérifier localement. Les campagnes, sources livrées et mesures antérieures
restent des preuves immuables. Aucun gain ROMEO ne sera déduit des tests logiciels.

1. Conseiller : prévalidation des données avant tout sous-processus coûteux ;
   nouvelle politique par défaut fondée sur `log(1 + speedup)` ; validation de la
   valeur réellement utilisée, comparaison au repère parent, parents disjoints,
   chronologie stricte, marge empirique et absence de bornage artificiel à un.
   Les politiques historiques restent explicitement identifiées pour les études.
2. Données : résumé borné et traçable des mesures par configuration, accessible
   aux analystes et à Mother ; caractéristiques du parent enrichies avec ces
   mesures et les fonctions mathématiques scalaires/vectorielles. Aucune donnée
   du futur enfant ni d'une autre campagne. Nouvelle version du contrat de données.
3. Analyse : fournir le point d'entrée en plus des premiers extraits, les mesures
   détaillées et des identifiants de citation contraints ; expliciter l'analyse
   des chemins série/parallèle, queues et replis, sans suggérer une optimisation
   propre aux problèmes utilisés dans l'étude.
4. Pilotage : une hypothèse déclarée testée doit avoir une comparaison mesurée
   liée à ses sources, pas un essai arbitraire du même arbre ; un rejet nécessite
   une preuve de code/contrat explicite ou une comparaison. Les créations d'arbres
   doivent disposer de budget pour leur essai et leur analyse. Les décisions
   refusées restent récupérables par la boucle existante.
5. Vérification : régressions ciblées sur les données temporelles, les racines
   réutilisant un code optimisé, les grands speedups, l'absence d'appel inutile,
   les mesures par configuration et les décisions de fermeture. Puis pytest,
   Ruff et tests d'interface. Documenter les limites restantes et le nouveau
   contrat ; ne pas prétendre que ces tests prouvent un gain de performance.

Réalisation : les cinq points sont implémentés et vérifiés localement. Voir les
[corrections](CORRECTIONS-QUALITE-20261027.md) et la
[validation complète](VALIDATION-QUALITE-20261027.md). Les nouveaux gains ROMEO
ne sont pas mesurés par ce lot.
