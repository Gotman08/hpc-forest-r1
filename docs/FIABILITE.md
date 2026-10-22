# Fiabilité de la recherche autonome

Les cinq chantiers suivent l'analyse des campagnes 776048 et 776290. Les améliorations portent sur le fonctionnement générique du système : aucune optimisation propre à N-body, aucun candidat précédent ni ancien résultat ne sont introduits dans une nouvelle recherche. TreeQuest AB-MCTS et N variable sont conservés. Les tests de correction des programmes restent protégés.

## 1. Représentation factuelle de la mémoire — intégré

Chaque entrée du catalogue présente les nombres de programmes mesurés valides, incorrects et non mesurés, ainsi que le meilleur programme, le dernier essai et une autre version valide distincte, même plus lente. Ces faits proviennent des résultats du contrôleur, indépendamment des leçons du modèle. Les instantanés de développement ne sont pas comptés comme des essais de recherche supplémentaires.

Le catalogue est visible dès le contexte initial de chaque mission. Un arbre ne voit que ses données et la référence autorisée ; Mother voit les résultats de la campagne courante. Toutes les alternatives restent accessibles par recherche et lecture exacte. Le représentant alternatif évite un programme identique lorsque son empreinte est connue ; il ne constitue pas une preuve de différence sémantique.

Les pages sont bornées par leur taille JSON réelle. Si les faits occupent davantage de place, la page contient moins de sujets et renvoie un offset explicite. Les identifiants et les nombres ne sont jamais tronqués. La limite concerne chaque paquet mémoire, pas l'historique natif complet. La pagination est testée jusqu'à 600 arbres.

## 2. Décisions et consultations — intégré

Le schéma ne propose que les actions disponibles au tour courant. `finish` arrête la sélection après une intégration évaluée ; le contrôleur choisit le programme à confirmer. Les anciens champs d'identifiants sans effet sur cet arrêt sont normalisés et cette normalisation est tracée. Une sélection épuisée ne force plus un nouveau programme lorsqu'une intégration valide existe déjà.

Les consultations sont conservées dans SQLite par campagne, protocole et conversation Mother. Un identifiant lu au tour précédent reste utilisable sans recopier tous les identifiants dans le contexte. Le nombre de résumés vus et non vus reste explicite ; avoir vu un résumé ne signifie pas avoir examiné toutes ses variantes.

Les adaptateurs natif et Ollama isolent les leçons optionnelles invalides, conservent les leçons recevables et enregistrent les motifs de rejet. Le code passe toujours par les validations de fichiers, compilation, correction et mesure. Une demande de lecture incohérente reste rejetée.

## Étapes suivantes

3. Ajouter une critique automatique et budgétée du plan initial, sans recette d'optimisation fournie par l'opérateur.
4. Donner aux arbres des observations sur les approches déjà essayées et distinguer les transformations réelles des copies ou réglages de lancement.
5. Fournir une comparaison de régularité entre campagnes indépendantes, avec médiane, mauvais résultats et fréquence d'amélioration, sans confondre tests fonctionnels et qualité de recherche.

Chaque lot vérifié est enregistré dans un commit local distinct. Une nouvelle campagne GPU ou une publication Git nécessite une demande explicite.
