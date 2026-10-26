# Vérifications du lot diversifié

- Le moteur est celui validé sur ROMEO par **1 095 tests réussis et 2 ignorés** dans le [lot de contrôle](../../docs/VALIDATION-CONTROL-RECOVERY-20261026.md), avec les 9 tests d'interface complémentaires.
- Les six paquets vérifiés conservent chacun les mêmes **90 empreintes de fichiers du moteur**, GPT-6 Luna effort max, les plafonds enregistrés, l'ordre déclaré et les entrées figées. Les entrées réservées ne sont pas présentes dans les paquets de recherche : [audit des paquets](results/payload-audit.json).
- Chaque prétest actif accepte le naïf et rejette une sonde sans calcul. Le prétest GEMM initial rejeté reste conservé et l'amendement précède toute recherche GEMM.
- Les douze conditions ont une mémoire initiale neuve. Les six comparaisons de configurations ne trouvent de différence que dans l'activation du conseiller et les identifiants isolés de sessions.
- Le job commun 784761 termine avec code 0 pour les distributions enregistrée et réservée. Les **onze livraisons** passent leurs contrôles ; la douzième condition n'a livré aucun code. Aucun speedup ne lui est attribué.
- Les 520 lignes de mesures détaillées conservent les mêmes empreintes d'entrée et affinités déclarées entre candidats. Les commits livrés sont identiques avant et après le test réservé ; aucun code n'est sélectionné à nouveau sur ces résultats.
- Les deux tests de l'export de remesure passent : séparation des tailles/régimes et absence de score pour un code incorrect sur les entrées réservées. Ruff passe sur les scripts de reproduction des deux nouveaux lots.
- La dispersion est exportée sans retirer de rondes. Elle est élevée pour Stencil, qui ne permet pas de conclure à un avantage du conseiller.
- Les téléchargements des dix jobs de paire et des deux remesures sont vérifiés par SHA-256. Les archives de publication contiennent un manifeste par fichier et font l'objet d'un contrôle des motifs d'identifiants avant envoi.

Ces vérifications ne transforment pas une paire de recherches par famille en preuve de supériorité statistique, et ne corrigent pas rétroactivement l'échec initial de Mother sur Popcount.
