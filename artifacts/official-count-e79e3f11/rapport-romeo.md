# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `50e056e0b2688f27054c6dc1eea373547e04146c6331ffcf3e05bb0110eb5f13`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 14, "tokens_used": 258687, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 258687}`.

Commit retenu après confirmation : `d19ec46455b43d04a6811a9199cf10eb05abce7a`.
Temps confirmé : 0.022809 s ; référence confirmée : 0.080815 s.
Réduction mesurée : 71.8%. Référence conservée : non.

Recherche : `binary-greedy` ; au plus deux enfants par nœud. La branche écartée reste archivée et n'est plus développée.

| Expérience | Rôle | État | Temps de recherche (s) | Commit |
|---|---|---|---:|---|
| 95c5b375ca624bc8 | A | valid | 0.073721 | 9e46c6c53d34 |
| 9979bdae80534d42 | B | valid | 0.053780 | fd8e3833ff3b |
| 63b2973af4fa4f83 | C | valid | 0.109762 | 0a26e5639b54 |
| 97b103d05aca4f1e | A | valid | 0.023048 | 3221005039d7 |
| 84159e4d3c71456b | B | valid | 0.047878 | 6bf0000cf030 |
| 0bbb90f759334420 | C | valid | 0.025910 | 8c1c006d9a7a |
| 1cbc8a5bd4e64fc4 | G | valid | 0.023226 | d19ec46455b4 |
| 734e0f07541d476d | G | valid | 0.023380 | 01e07da269ef |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
