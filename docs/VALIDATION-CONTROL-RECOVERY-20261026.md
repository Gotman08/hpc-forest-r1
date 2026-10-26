# Validation des reprises de Mother et de la clôture

Le moteur figé pour la campagne `control-recovery-20261026` a passé la suite
complète sur ROMEO : **1 095 tests réussis, 2 ignorés** (job `784647`, nœud
`romeo-c021`, 296,28 secondes pour pytest). Les deux exclusions concernent un
test propre à Windows et l'environnement AB-MCTS-M optionnel. La campagne utilise
AB-MCTS-A, dont les tests sont exécutés.

Le paquet de sources testé a l'empreinte
`d0ec26d273f3a16bdb5eb497bf6df55535c48f94b0c1bc15d27c010ac7e12d08`.
Les 90 empreintes de fichiers Python du moteur correspondent aux quatre paquets
de campagnes. La configuration conserve GPT-6 Luna, effort max, pour tous les
rôles LLM ; le mélange de modèles est désactivé.

## Contrôles complémentaires

- Sept scénarios de parcours complet passent sur ROMEO (`784646`) : compilation,
  vrai TreeQuest, intégration et confirmation, avec LLM simulé pour injecter les
  pannes de manière contrôlée.
- Le scénario de réouverture puis clôture passe aussi sous Windows : 74,21 s.
- Les 67 tests ciblés des contrats, reçus et corrections passent.
- Les neuf tests d'interface passent ; Ruff et `git diff --check` passent.

Les tests vérifient notamment l'attente native vide, le maintien de l'UUID de
Mother après une limite de sortie, l'absence de rejeu, les limites de tentatives,
les références aux seules preuves visibles et une nouvelle admission après une
réouverture. Les refus de véritables outils non autorisés et la réserve finale
restent vérifiés.

## Traces conservées

Les essais de validation intermédiaires ne sont pas masqués : le simulateur
introduit pour le nouveau scénario a d'abord accédé à SQLite depuis son fil
d'exécution secondaire, puis atteint son point de contrôle avant la clôture.
Il a ensuite été corrigé pour séparer explicitement les suspensions et la revue
de clôture, conformément au contrat existant. La quatrième tentative a aussi
rencontré une saturation du quota de fichiers pendant pytest. Le moteur est
identique entre ces tentatives et la validation finale ; seules les corrections
du scénario de test ont changé.

Les dossiers temporaires des validations terminées ont été sauvegardés avant
retrait de ROMEO. Les rapports et les empreintes restent disponibles, ainsi que
les sauvegardes locales complètes. Les campagnes de recherche historiques ont
été conservées. [Archives GitHub](ARCHIVES-20261026.md).

La validation de logiciel n'établit pas un gain de performance de TabPFN. Les
huit exécutions réelles ont livré un code, remesuré avec les anciennes livraisons
dans le job 784760. Les [résultats et limites](../experiments/control-recovery-20261026/RAPPORT.md)
séparent continuité du contrôle et performance des programmes. Le lot diversifié
révèle aussi un échec distinct de planification initiale de Mother sur Popcount :
la validation ne signifie pas que tous les appels LLM réussiront.

Les preuves finales sont dans
[`evidence/control-recovery-20261026/validation`](../evidence/control-recovery-20261026/validation).
