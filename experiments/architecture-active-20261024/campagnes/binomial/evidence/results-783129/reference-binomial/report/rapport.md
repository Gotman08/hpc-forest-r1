# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `cbfb9198c27699b03b580064f2c92a1167e56e51e70234c3a39b58b239f7b244`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 35, "tokens_used": 2004476, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2004476}`.
Coûts par phase : `{"search": {"slots": 23, "tokens_used": 788740, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 788740}, "postprocess": {"slots": 9, "tokens_used": 1215736, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1215736}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "83a1c1876f744ea3", "outcome": {"binary_sha256": "ae0175762a89a70398a37e5796b76068d133137914eb5344e7303ade9b37bd72", "cache_key": "6770fb9e396a572bcee10d9dd1ce33b3d0823e91db489a6b11cb9fdfd089b467", "commit": "31263bbf1bcfe5752004c95543bac09bb9e01bc8", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-binomial_retry1-312b321a08ca4be29280208f0d9b648b/results-783129/reference-binomial/logs/e1/83a1c1876f744ea3/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-binomial_retry1-312b321a08ca4be29280208f0d9b648b/results-783129/reference-binomial/logs/e1/83a1c1876f744ea3/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-binomial_retry1-312b321a08ca4be29280208f0d9b648b/results-783129/reference-binomial/logs/e1/83a1c1876f744ea3/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-binomial_retry1-312b321a08ca4be29280208f0d9b648b/results-783129/reference-binomial/logs/e1/83a1c1876f744ea3/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-binomial_retry1-312b321a08ca4be29280208f0d9b648b/results-783129/reference-binomial/logs/e1/83a1c1876f744ea3/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-binomial_retry1-312b321a08ca4be29280208f0d9b648b/results-783129/reference-binomial/logs/e1/83a1c1876f744ea3/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-binomial_retry1-312b321a08ca4be29280208f0d9b648b/results-783129/reference-binomial/logs/e1/83a1c1876f744ea3/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.014437715367550442, "reason": "", "score": 0.9643667008150594, "status": "valid", "times": [0.014431943224866912, 0.014437548104745039, 0.014458933695560602, 0.014438264438649227, 0.014421887373930431], "tree_hash": "5d003dcb083b59a88dfc4bc784f805a0271f70cb"}, "status": "confirmed"}`.

Commit retenu après confirmation : `31263bbf1bcfe5752004c95543bac09bb9e01bc8`.
Temps confirmé : 0.014438 s ; référence confirmée : 0.390737 s.
Réduction mesurée : 96.3%. Référence conservée : non.

Mother a choisi **4 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Outer-loop CPU parallelism and thread-budget-aware dispatch | In `src/candidate.cpp`, investigate parallelizing the independent per-element pricing work and dispatch using the supplied `threads` budget. Explore a low-overhead serial path for small workloads and suitable work partitioning without hardcoding the environment's 40-thread setting or changing global OpenMP controls. Preserve complete output overwrite and correctness for every entry. Compare whole-call timings across the official workload and available `n`/`threads` cases, including parallel overhead, and record failed scheduling or threshold variants. |
| T2 | Reduce terminal-state power-function cost without changing endpoint convention | In `src/candidate.cpp`, focus only on generating terminal payoffs more cheaply than 64 repeated `powf` evaluations per input. Explore a recurrence or other general power-generation method while preserving all 64 terminal indices and their existing exponents `2*j-64` (`-64` through `62` by twos), the `max(0, X-S*upow)` floor, and the subsequent rollback. Validate varied inputs, especially values near payoff boundaries, against the fixed tolerance; record failed numerical variants and compare full-call timings. |
| T3 | Hoist invariant rollback coefficients and reduce per-state arithmetic | In `src/candidate.cpp`, focus on the rollback transition expression: explore hoisting input-invariant factors (including discount-related division) or equivalent arithmetic rearrangements to reduce work repeated across the 2,080 state updates. Keep the backward `j`/`k` update order and endpoint convention; retain only variants that satisfy the fixed tolerance on varied inputs. Report accuracy and whole-call timing rather than assuming algebraic equivalence guarantees acceptable rounding or speed. |
| T4 | SIMD mapping across independent options | In `src/candidate.cpp`, explore SIMD or batched execution across independent input elements (or another demonstrably distinct SIMD mapping) while leaving the baseline terminal-power generation and rollback arithmetic formulation unchanged, to avoid duplicating the other trees' subjects. Use only instructions/features supported by the actual compile target; available flags are not established here. Preserve every lane's output and correctness on varied inputs, and measure full-call performance including batching and scratch costs. Record ineffective or incorrect vectorization attempts. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| b9f90f30f9684579 | T1 | search | valid | 0.071596 | 44f7ab510902 |
| 0682a92da9224077 | T2 | search | valid | 0.304658 | 995311ac097b |
| 31838b58b6c34a43 | T3 | search | valid | 0.296472 | 6d8e903ef611 |
| 6ffd5d83eb5045bc | T4 | search | valid | 0.175008 | 878d86e2ba4e |
| 55e402f3863b4c72 | T3 | search | valid | 0.294283 | 22182f6f102b |
| 894bb9e1058c41aa | T1 | search | valid | 0.072476 | 8bf060e6f570 |
| 1dc5570ef1884777 | T2 | search | valid | 0.296868 | e4628fb6062e |
| 31c053d9f320458b | T3 | search | valid | 0.304291 | 416b9ab7f063 |
| 649a050361b14203 | T4 | search | valid | 0.391075 | a4ff14783f9d |
| 65b8f9b9574545c1 | T1 | search | valid | 0.071921 | e62c55ddd467 |
| 31acf205101441a9 | T2 | search | valid | 0.330778 | d892b6e9b3e5 |
| 90b739a8b59c4b0e | Gm1 | search | valid | 0.037432 | 05672dd3fb6f |
| 600ed5dcd12b4666 | G | postprocess | valid | 0.019241 | bc49abe6067a |
| 1e97ac568500465d | G | postprocess | valid | 0.018706 | 3fdd9abc8f66 |
| 83a1c1876f744ea3 | G | postprocess | valid | 0.014417 | 31263bbf1bcf |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
