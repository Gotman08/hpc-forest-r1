# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `bda1b91f48246adb71c8a465f2e578aac375e5fa1edbff391315abe98c92f5d7`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 100, "tokens_used": 7477183, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 7477183}`.
Coûts par phase : `{"search": {"slots": 92, "tokens_used": 6765296, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 6765296}, "postprocess": {"slots": 4, "tokens_used": 711887, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 711887}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "0b968c20c65e410c", "outcome": {"binary_sha256": "2c39443b4e1312475d941e104e5682f20f830f0b54cfae1a90920c49b1c277bb", "cache_key": "5b5b7fc904b42cb7065d0267422baaebf9324a9a493c5f1d6af5391fd9af33f0", "commit": "6b3517ef7f55f91efcad6739a192c57db74f7cef", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-f3de68bd4599429d894b874cf649395a/campaign/logs/e1/0b968c20c65e410c/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-f3de68bd4599429d894b874cf649395a/campaign/logs/e1/0b968c20c65e410c/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-f3de68bd4599429d894b874cf649395a/campaign/logs/e1/0b968c20c65e410c/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-f3de68bd4599429d894b874cf649395a/campaign/logs/e1/0b968c20c65e410c/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-f3de68bd4599429d894b874cf649395a/campaign/logs/e1/0b968c20c65e410c/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-f3de68bd4599429d894b874cf649395a/campaign/logs/e1/0b968c20c65e410c/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-f3de68bd4599429d894b874cf649395a/campaign/logs/e1/0b968c20c65e410c/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.07579966639223254, "reason": "", "score": 0.881509000142668, "status": "valid", "times": [0.07589971030633766, 0.07577395242527422, 0.0757617028683143, 0.07578349210525127, 0.07577947425598522], "tree_hash": "315d8a0a80952e3e75028566ed47081778c10886"}, "status": "confirmed"}`.

Commit retenu après confirmation : `6b3517ef7f55f91efcad6739a192c57db74f7cef`.
Temps confirmé : 0.075800 s ; référence confirmée : 0.563909 s.
Réduction mesurée : 86.6%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Scalar OpenMP work distribution | Explore OpenMP parallelization of the scalar pixel computation, respecting threads as a maximum CPU-thread budget and keeping a low-overhead one-thread path. Compare row/tile partitioning and scheduling choices to balance pixels with variable iteration counts. Preserve the recurrence and coordinate calculation; check exact outputs on the standard and shifted-bound cases and benchmark one and four cores. |
| T2 | Exact SIMD for pixel recurrences | Explore SIMD across adjacent pixels using only instructions supported by the actual build and target. Compare the scalar implementation with masked lockstep SIMD and, where practical, an alternative divergence strategy such as lane compaction or scalar cleanup; report when a strategy is not available rather than assuming an ISA. Preserve exact per-pixel counts and floating-point behavior, use a scalar fallback when necessary, and validate outputs on standard and shifted-bound inputs. Measure at one and four cores; do not assume SIMD wins merely from wider lanes. |
| T3 | Verified reflected-row reuse | Explore a general conjugate-symmetry fast path: compute the existing float y coordinates for paired rows and reuse a row only when the pair is exactly reflected. Verify count equivalence against independently computed rows under the supported floating-point behavior; fall back to computing both rows whenever equivalence is not established. Do not assume particular bounds. Compare enabled and disabled paths on symmetric and shifted/asymmetric inputs at one and four cores, including detection and copying overhead. Report the isolated result; any combination with parallel scheduling must be measured separately. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| f439e089fe8248fb | T1 | search | valid | 0.282033 | 436107b991ba |
| 433067d4a3bc4e86 | T2 | search | valid | 0.203198 | 323eda3a8746 |
| 4dd8f55476c34063 | T3 | search | valid | 0.565196 | 30200ac6c0ec |
| c73b1dfe21224744 | T1 | search | valid | 0.282801 | 7cf4121df529 |
| af2177f2ce084f56 | T2 | search | valid | 0.189206 | 341221585be7 |
| 7df7e11caf0947ed | T3 | search | valid | 0.563469 | e4cce4573708 |
| 91ecd40af78844f1 | T1 | search | valid | 0.282436 | e646d76677f4 |
| 989bddf162d64a0d | T1 | search | valid | 0.283101 | 5cc90af95e8b |
| c51d5e39faa24a9e | T1 | search | valid | 0.305036 | 0e1f0bfd977a |
| 2952de2ee6b84c7f | T2 | search | valid | 0.119182 | abadd4d6142e |
| 3c6f49c591d34727 | T3 | search | valid | 0.565029 | 30ac47f6d814 |
| 2745f280c2044bf5 | T1 | search | valid | 0.282209 | bb08fe994239 |
| 6d94c9a751624276 | T2 | search | valid | 0.096373 | 197d7c7ee955 |
| 43ef703941224cfa | T1 | search | valid | 0.282384 | a99aa266aaac |
| 86bc6af5264b4fa5 | T3 | search | valid | 0.564631 | c1b2fd93a96e |
| fd15970bae5f4ce7 | T2 | search | valid | 0.363971 | 83c5d176066a |
| bafa61e51e2a44e2 | Gm1 | search | valid | 0.075857 | 313f5327026d |
| bd2d0b4106e64ee0 | T2 | search | valid | 0.157345 | 92f908835b61 |
| 1dbaa150dab74cae | T4 | search | valid | 0.075831 | 2b2955e8e649 |
| 9d684e1a75a14d34 | T4 | search | valid | 0.075760 | ba1abf7b137a |
| 511e22298c6b442d | T4 | search | valid | 0.075812 | 9c96e0b22410 |
| d9d2dd5e70814339 | T4 | search | duplicate | — | cbd89caa6eda |
| 552d169a461d4cdd | T4 | search | valid | 0.075787 | 49c08a7ee8ff |
| 8ea231e153b14f6c | T4 | search | valid | 0.076259 | 6217596bcf66 |
| bbdc42997e0b4899 | T4 | search | valid | 0.075798 | abde117f6065 |
| aca698742c324b6d | T4 | search | valid | 0.075860 | 022dff7e2f49 |
| 1e484f2c2e8549ed | T4 | search | valid | 0.075781 | 9f1125c7e8cd |
| 23d14d3e6f0444b8 | T4 | search | valid | 0.075823 | 819e7510cf12 |
| 5670dc7d1fc14630 | T4 | search | valid | 0.075855 | 3055338632c4 |
| 5470a756c2c44483 | T4 | search | valid | 0.075823 | 46652064957e |
| 0b968c20c65e410c | G | postprocess | valid | 0.075836 | 6b3517ef7f55 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
