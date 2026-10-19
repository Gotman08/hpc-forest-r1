# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `1a3b2dda5e0ae276a96f8d5f7a2c98cd20a54261637d0385f5da73591cbe510d`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 14, "tokens_used": 266005, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 266005}`.

Commit retenu après confirmation : `eff240aead9d5cc67869f66a0ded91d56747f3d2`.
Temps confirmé : 0.020058 s ; référence confirmée : 0.080102 s.
Réduction mesurée : 75.0%. Référence conservée : non.

| Expérience | Rôle | État | Temps de recherche (s) | Commit |
|---|---|---|---:|---|
| b8f2c96bf81d4c93 | A | valid | 0.056388 | 534d5a1bca00 |
| a7de01e57ae3474e | B | valid | 0.033434 | 6bb1d75de577 |
| 18200cbb7f174a97 | C | valid | 0.031027 | 5428b8a74d31 |
| 520fcb5259304aa9 | A | valid | 0.062016 | 4129722a303d |
| c9812ab370824cc1 | B | valid | 0.020607 | 877c6ae327f6 |
| b5fb0a78f9904af2 | C | valid | 0.030127 | 1369e6ab5dbe |
| 8768334437d34eae | G | valid | 0.020066 | ab586fcc8471 |
| 24a86c44dc3148e2 | G | valid | 0.020251 | eff240aead9d |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
