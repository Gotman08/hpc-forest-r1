# Validation réelle des générations de Forest

Le 25 octobre 2026, le job **784118** sur **romeo-c040** a terminé en **24 min 11 s**, avec le code de sortie `0:0`. Le test confirme plusieurs enfants par candidat et plusieurs générations dans les arbres, avec leur affichage fidèle dans l’application.

| Arbre | Variantes distinctes | Correctes | Profondeur maximale après Départ | Maximum d’enfants d’un même candidat |
| --- | ---: | ---: | ---: | ---: |
| T1 | 13 | 13 | 2 | 2 |
| T2 | 10 | 10 | 3 | 3 |

Les **23 variantes de recherche** ont des sources différentes. Deux essais d’intégration G, également corrects, portent le total à **25 essais**. Les intégrations sont présentées séparément des arbres.

## Conditions et autonomie

- Modèle de tous les rôles : **GPT-6 Luna**, effort **max**.
- Même programme de somme des nombres premiers, mêmes trois fichiers et mêmes tests que le job précédent `784095`. Les empreintes sont dans `conditions.json`.
- Contrat : compilation `g++ -O2 -std=c++17 main.cpp -o program`, tests `python3 tests/check.py ./program`, mesure `./program 20000`, seul `main.cpp` modifiable.
- Le seul paramètre de contrat changé est le budget : **10 → 30 minutes**. Nouvelle session et mémoire indépendante. Mother a librement choisi deux arbres, contre trois lors du premier test.
- CPU ROMEO x86_64, GCC 14.2.0, allocation de 2 cœurs et 8 Gio. Le calcul et le worker s’exécutent sur ROMEO, sans relais d’inférence sur le PC.
- L’assistant a préparé, lancé et audité le test. Il n’a envoyé aucun conseil ni code optimisé aux arbres pendant la campagne, ni imposé leur filiation. Aucune modification du moteur n’a été faite pour obtenir ces ramifications.
- Le moteur figé pour ce lancement contient les corrections d’infrastructure et d’interface déjà réalisées après le premier smoke test. Les sept fichiers différents figurent dans `conditions.json` : ce n’est pas une ablation strictement limitée au budget.

## Filiation et affichage vérifiés

`verification.json` contient **neuf contrôles réussis** : campagne terminée, pipeline complet, plusieurs générations, plusieurs enfants corrects d’un même candidat, absence de parent manquant et de cycle, héritage des commits parents, modification effective des sources descendantes, concordance des liaisons SVG avec le registre et identité du modèle.

Exemples vérifiables dans `filiations.csv` :

- T1 : `9c11a7d183eb4d25` → `5fe21186f8954287` et `8bee816055e44dbb`.
- T2 : `8dddfc6b73a5417e` possède trois enfants ; la chaîne `8dddfc6b73a5417e` → `acf58c10700f4c86` → `04866b8ae0d0406f` atteint trois générations après le départ.

Les positions et tracés observés dans l’application sont conservés dans `graph-dom.json`. Les 23 sources sont dans `variants/`. `verify.py` refait le contrôle en lecture seule avec la même campagne disponible dans l’application locale.

## Clôture et résultat

Forest a enregistré **neuf décisions de pilotage**. Des suspensions prématurées ont été rejetées lorsque l’exploration protégée ou des résultats plus récents exigeaient de poursuivre. T1 a ensuite été suspendu après treize variantes correctes.

La recherche s’est arrêtée avec `budget_exhausted` pour conserver sa réserve d’intégration et de confirmation, avant l’échéance maximale de 30 minutes. Les deux essais G et la confirmation finale se sont terminés normalement. Le ZIP téléchargé a été vérifié : archive intacte, tests et README inchangés, `main.cpp` identique au candidat confirmé.

| Exécution | Essais de recherche | Temps initial confirmé | Temps optimisé confirmé | Speedup |
| --- | ---: | ---: | ---: | ---: |
| Précédente, job 784095 | 3 | 38,831 ms | 4,023 ms | 9,653× |
| Ce test, job 784118 | 23 | 38,863 ms | 3,996 ms | 9,726× |

La petite différence de speedup ne démontre pas une amélioration significative : l’objectif de ce test est de valider les générations et les filiations. Les mesures individuelles, la comparaison et les liens sont fournis dans `mesures.csv`, `comparaison.csv` et `filiations.csv`.

L’efficacité CPU SLURM est de 2,6 % (75 secondes CPU, pic mémoire de 520,8 Mio) ; le temps total inclut les échanges avec le modèle. Les deux cœurs gardent le worker séparé du processus mesuré.

![Arbres réellement générés et confirmés](application-multigenerations.png)

[Ouvrir les arbres dans l’application locale](http://127.0.0.1:8767/#/mission/campaign/5fa5222633434f39869d6342741cf4f6)
