# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `d30856c3f6581af0850cebf7b46861fafcd7bf6c5c8e6fc1c7317f84366e3ecb`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 49, "tokens_used": 2374253, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2374253}`.
Coûts par phase : `{"search": {"slots": 41, "tokens_used": 1688672, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1688672}, "postprocess": {"slots": 5, "tokens_used": 685581, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 685581}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "667ebe0536654fcf", "outcome": {"binary_sha256": "c0b20e583b660e5e1e8efa911e3d56b129d7cf6e4eab6484691b6b8554c0f951", "cache_key": "e358dd6f5e8e159e63b1accf84fd3d20aadfd50bde7270cabed12e466453efa4", "commit": "d4f53092f054684d6e71de1b338014a1ff06108b", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-softmax-4404c2b6a13c42989f9c7c7e042d7509/results-782963/reference-softmax/logs/e1/667ebe0536654fcf/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-softmax-4404c2b6a13c42989f9c7c7e042d7509/results-782963/reference-softmax/logs/e1/667ebe0536654fcf/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-softmax-4404c2b6a13c42989f9c7c7e042d7509/results-782963/reference-softmax/logs/e1/667ebe0536654fcf/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-softmax-4404c2b6a13c42989f9c7c7e042d7509/results-782963/reference-softmax/logs/e1/667ebe0536654fcf/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-softmax-4404c2b6a13c42989f9c7c7e042d7509/results-782963/reference-softmax/logs/e1/667ebe0536654fcf/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-softmax-4404c2b6a13c42989f9c7c7e042d7509/results-782963/reference-softmax/logs/e1/667ebe0536654fcf/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-softmax-4404c2b6a13c42989f9c7c7e042d7509/results-782963/reference-softmax/logs/e1/667ebe0536654fcf/confirmation/attempt-001/sample-4.log"], "mean_seconds": 4.171200022101402e-05, "reason": "", "score": 0.8361016464613947, "status": "valid", "times": [4.1919998824596406e-05, 4.118400067090988e-05, 4.182400181889534e-05, 4.1919998824596406e-05, 4.171200096607208e-05], "tree_hash": "d711b43b64884f5d305874fda08e8e2ce9100557"}, "status": "confirmed"}`.

Commit retenu après confirmation : `d4f53092f054684d6e71de1b338014a1ff06108b`.
Temps confirmé : 0.000042 s ; référence confirmée : 0.000213 s.
Réduction mesurée : 80.4%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Direct fused one-row-per-CTA kernel | Implement the direct, non-streaming Triton design with one program/CTA owning one complete row: masked load, stable max/exp/sum, and normalized store. Compare with the official tutorial and explore configurations for this one-row mapping only. Do not switch to multi-row CTAs or streaming loops. Support arbitrary valid widths and tails, preserve the stated accuracy and input/output requirements, and retain only correctness-passing measured improvements. |
| T2 | Grouped multi-row-per-CTA kernel | Test CTAs that compute multiple independent complete rows using per-row reductions. Explore rows-per-CTA and only the layout/warp choices needed for this grouped mapping; do not repeat T1’s one-row configuration search or use streaming or split-row algorithms. Compare against T1’s best measured direct one-row result and the official candidates. Support arbitrary valid shapes and tails and preserve the stated accuracy and input/output requirements. |
| T3 | Streaming online reduction to reduce live row state | Explore a single-CTA-per-row streaming softmax that processes column tiles while maintaining a numerically stable running maximum and rescaled sum, then rereads tiles to produce normalized output. This tests whether reducing live per-row state outweighs extra input traffic for the performance shape. Support arbitrary widths and tails, preserve the stated accuracy and input/output requirements, and retain the approach only if official measurements justify it. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| c93f04514d4b4c33 | T1 | search | valid | 0.000042 | f64b8ef0d8c0 |
| 3f02e8083fe74e59 | T2 | search | valid | 0.000043 | cbc5b17b0fad |
| 22383847f36e4e69 | T3 | search | valid | 0.000070 | 44582f1a6500 |
| dffb0dea1f304972 | T3 | search | valid | 0.000106 | 77fb1ecbd321 |
| 18a32bea3657424d | T1 | search | valid | 0.000042 | 9f1c3e077f76 |
| 33a5fc87ad6d40db | T2 | search | valid | 0.000043 | 1a2ea391972a |
| 66b06aaca4904b57 | T3 | search | valid | 0.000060 | d840ffdf3021 |
| c85175aa6f3943de | T2 | search | valid | 0.000043 | e9ff5423ec02 |
| 75a8bbda3db643d5 | T3 | search | valid | 0.000058 | aa585a20a9f4 |
| 7035a0aa44b64d57 | T1 | search | valid | 0.000041 | 5f94cb3c61cc |
| 1087d7e03fea4861 | T2 | search | valid | 0.000043 | 46bb17205a18 |
| 619063e5341f46b5 | T3 | search | valid | 0.000056 | 9878286ad483 |
| 87a952fb6cf140e0 | T1 | search | valid | 0.000042 | 64473670b608 |
| 6ef39c989c114d87 | T3 | search | valid | 0.000049 | 9321af7578e5 |
| 066627659fe340df | T1 | search | valid | 0.000044 | ed33fd1a5b17 |
| 3425905c04ab47b4 | Gm1 | search | valid | 0.000042 | ecca65b84229 |
| 667ebe0536654fcf | G | postprocess | valid | 0.000042 | d4f53092f054 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
