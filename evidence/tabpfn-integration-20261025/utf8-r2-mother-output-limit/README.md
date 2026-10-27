# UTF-8, répétition 2, conseiller désactivé : livraison interrompue

Le job 784228 a mesuré 20 essais de recherche corrects dans ce bras, mais n'a pas
livré de code confirmé. Le second appel du contrôle Mother
`active-mother-790b285cf16745419cf16a3ae28328f7` a duré 925,544 s puis a renvoyé
`Incomplete response returned, reason: max_output_tokens`.

Ce retour incomplet ne fournit pas la preuve de continuité attendue pour la
conversation native. Le contrôleur refuse alors de remplacer ou de rejouer
Mother dans une nouvelle conversation et arrête le parcours avec
`Mother steering lost its native receipt; cannot replace or replay her conversation`.
Le temps total du bras est 1 295,550 s ; un appel a une consommation de tokens
inconnue. Celle-ci ne doit pas être remplacée par zéro.

Le message observé concerne la limite de sortie de Luna. Ces traces n'établissent
pas une panne réseau. TabPFN est désactivé dans ce bras. Aucun opérateur n'a repris
la conversation, confirmé un candidat à sa place ou remplacé cette exécution.

Les résultats de recherche sont conservés dans l'archive originale et figurent
dans la trajectoire secondaire. L'absence de livraison confirmée reste un échec :
aucun speedup final n'est déclaré pour ce bras. Les preuves compactes sont dans
`receipt-diagnostic.json` et `controller.log`.
