# Validation avant lancement

## Moteur

Job ROMEO **784833** : **1 108 tests réussis, 2 exclus**, zéro échec.
Les exclusions concernent un contrôle spécifique à Windows et l'environnement
optionnel AB-MCTS-M ; la campagne utilise AB-MCTS-A.

Les **111 fichiers** du paquet moteur testé sont identiques par SHA-256 dans les
six charges utiles de recherche. Preuves : `validation/pytest.xml`,
`validation/pytest.log`, `validation/tested-source-hashes.json` et
`validation/verification.json`.

Contrôles locaux : Ruff valide `src`, `tests` et les scripts de l'étude ;
les **9 tests d'interface** passent. Les tests ajoutés couvrent le filtrage par
arbre avant limitation du contexte, les dates de disponibilité, la séparation
des parents, la calibration, les prédictions hors domaine, l'immuabilité du plan,
la conservation des non-livraisons dans les contrastes et les archives de blocs.

## Incidents conservés

- Job **784822** : quota de fichiers atteint pendant la création des répertoires
  temporaires des tests ; aucune conclusion de validation n'en est tirée.
- Job **784832** : 1 094 réussites, 12 échecs d'export ZIP causés par les dates 1970
  de l'archive préparée par l'opérateur. Correction des dates de l'archive de test,
  sans modification de la logique de Forest ; suite complète relancée avec succès.
- Préparation GEMM **784823** : valide au premier essai, 138,538 s imputées.
- Préparation Black–Scholes **784824** : champ `G` vide, 94,429 s conservées et imputées.
- Préparation Black–Scholes **784831** : valide ; coût total imputé 213,575 s.

Les versions et journaux de ces tentatives sont conservés dans le répertoire de
travail de l'étude. Les campagnes historiques sont intactes.

## Limite de ces vérifications

La réussite des tests établit le respect des contrats logiciels vérifiés. Elle
ne démontre pas que le conseiller améliore les résultats. Ce point dépend des
trente recherches, de leur remesure et de l'analyse des interventions réelles.
