# Validation de la relance — tentative 2

Le 26 octobre 2026, avant soumission des trente recherches.

## Tests

- **ROMEO : 1 118 tests réussis, deux exclusions prévues**, en 304,14 s.
  Job **785403**, `COMPLETED`, code de sortie `0:0`.
- Exclusions : régression des chemins Git propre à Windows et environnement
  facultatif AB-MCTS-M. La campagne utilise AB-MCTS-A.
- **Neuf tests d’interface réussis** localement.
- Tests ciblés locaux : 13 réussis, deux exclusions POSIX sur Windows.
  La suite complète sur ROMEO inclut ces tests POSIX.
- Ruff sur `src`, `tests` et les scripts de reproduction : réussi.
  `git diff --check` : aucune erreur.

Preuves : [journal pytest](validation-attempt-2/pytest.log),
[JUnit](validation-attempt-2/pytest.xml),
[code de sortie](validation-attempt-2/pytest-exit.txt),
[empreintes du code testé](validation-attempt-2/tested-source-hashes.json).

Les six archives de recherche contiennent le même moteur et les mêmes scripts
de reproduction que l’archive de test complète. Les 111 fichiers du moteur sont
aussi identiques à la tentative précédente :
[vérification des sources](validation-attempt-2/source-verification.json).

## Tests du stockage

La suite couvre les quotas en fichiers et en octets, les délais de grâce GPFS,
la marge requise avant lancement, la conservation de l’original en cas de panne
de copie ou de modification concurrente, la vérification des liens physiques,
la continuité des worktrees Git après conservation et les rapports en l’absence
de recherche démarrée.

Les anciens fichiers temporaires de tests ont été conservés et leurs archives
vérifiées, sans déplacer les campagnes historiques. Les fichiers du test complet
785403 ont eux aussi été archivés puis conservés dans l’espace personnel :
58 387 entrées, archive SHA-256
`c5f76c2f8fce27fd230f90ca2837242b20a627405ab14e1dafd9384bff41631d`.

## Qualification dans l’allocation ROMEO

Job **785405**, `COMPLETED`, `0:0`, en 51 s :

- OAuth natif Codex connecté ; aucun relais du PC.
- Huit requêtes de qualification ont respecté leur contrat :
  deux problèmes × deux périmètres de données × deux validations.
- Les refus de validation attendus sont conservés comme refus.
  Ce test de fonctionnement ne mesure aucun gain prédictif.
- Environ 150 652 fichiers encore disponibles sous le quota scratch au contrôle
  de lancement ; le seuil requis est de 110 000.
- Quota personnel disponible : environ 1,33 million de fichiers et 19,14 Go.

Preuves : [qualification](validation-attempt-2/qualification.json),
[dimensionnement](validation-attempt-2/qualification-efficiency.json).

## Démarrage réel

Les six blocs **785406 à 785411** ont démarré sur `romeo-c022`.
L’audit en lecture seule vérifie onze propriétés, toutes satisfaites : six
démarrages, plans communs identiques, conversations Mother séparées, conversation
de préparation séparée, sessions distinctes, Luna Max partout, mémoire neuve,
CPU distincts, cinq CPU par bloc, stockage persistant et état de quota séparé.

[Audit réel](validation-attempt-2/first-six-starts.json) ·
[Script de l’audit](validation-attempt-2/audit_start.py) ·
[Scripts et reçus de soumission](submission-attempt-2.json).

Cette validation confirme le fonctionnement testé et le démarrage. Elle ne
garantit pas l’achèvement des trente recherches, l’absence de panne future ni
une amélioration des résultats par TabPFN.
