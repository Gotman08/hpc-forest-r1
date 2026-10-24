---
name: planifier-optimisation
description: Analyser un problème d’optimisation et définir les objectifs des arbres de recherche avant leur lancement.
---

Analyser le sujet, le code disponible, les contraintes et les mesures existantes.

Identifier l’objectif réel : latence, débit, mémoire, consommation ou autre
critère fourni. Respecter les exigences de correction et de précision du sujet.

Repérer les coûts probables et distinguer les observations mesurées des
hypothèses. Demander les informations techniques manquantes lorsqu’elles
peuvent changer la stratégie.

Choisir N objectifs de recherche adaptés au problème. Pour chacun, préciser :
- le mécanisme à explorer et sa justification ;
- le périmètre de modification ;
- les contraintes à préserver ;
- les observations permettant de juger le résultat.

Favoriser des objectifs complémentaires. Plusieurs approches d’un même coût
dominant peuvent être pertinentes : leur différence doit être explicite.

Adapter N au nombre de pistes utiles. Ne pas inventer des objectifs pour
atteindre un nombre prédéfini.

Transmettre le plan au contrôleur, qui lance les N arbres en parallèle.
