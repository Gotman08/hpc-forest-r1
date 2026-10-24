# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `60701819194467cdb9363487a220a098ef1e1f71bb3acc9d24c5e9d4a81fcf99`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 38, "tokens_used": 2587408, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2587408}`.
Coûts par phase : `{"search": {"slots": 33, "tokens_used": 2165075, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2165075}, "postprocess": {"slots": 2, "tokens_used": 422333, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 422333}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "d441ab81063e4ce5", "outcome": {"binary_sha256": "dc2df861f592df6471ef36ca671c2515b7dfe1bccd2136170db0c5dd86f3cd44", "cache_key": "6886535e024b488d0a440abfc4c757848901eadd92b56ec11cfdd3fb4192ed1f", "commit": "e010b8557ecc33ef9bb4bc3ca9e3472460d5bd7c", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-reduction-control-v3-f9e20ee24ccd438aa9eba977b3012400/results-782623/reference-reduction/logs/e1/d441ab81063e4ce5/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-reduction-control-v3-f9e20ee24ccd438aa9eba977b3012400/results-782623/reference-reduction/logs/e1/d441ab81063e4ce5/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-reduction-control-v3-f9e20ee24ccd438aa9eba977b3012400/results-782623/reference-reduction/logs/e1/d441ab81063e4ce5/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-reduction-control-v3-f9e20ee24ccd438aa9eba977b3012400/results-782623/reference-reduction/logs/e1/d441ab81063e4ce5/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-reduction-control-v3-f9e20ee24ccd438aa9eba977b3012400/results-782623/reference-reduction/logs/e1/d441ab81063e4ce5/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-reduction-control-v3-f9e20ee24ccd438aa9eba977b3012400/results-782623/reference-reduction/logs/e1/d441ab81063e4ce5/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-reduction-control-v3-f9e20ee24ccd438aa9eba977b3012400/results-782623/reference-reduction/logs/e1/d441ab81063e4ce5/confirmation/attempt-001/sample-4.log"], "mean_seconds": 6.957567930221558e-06, "reason": "", "score": 0.8697885226826925, "status": "valid", "times": [6.8755197525024415e-06, 7.022079825401306e-06, 7.200639843940735e-06, 6.829439997673035e-06, 6.860160231590271e-06], "tree_hash": "66bc24638ad6ac4c3708d73e313ce88f8a5d64e8"}, "status": "confirmed"}`.

Commit retenu après confirmation : `e010b8557ecc33ef9bb4bc3ca9e3472460d5bd7c`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000046 s.
Réduction mesurée : 85.0%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Warp-first block reduction | Using AB-MCTS, isolate the block-local reduction mechanism: replace the modulo/shared-memory tree with a warp-first reduction and cross-warp combine while retaining the 128-element tile and recursive host-stage structure where feasible. Do not assume signed int32 partial sums are safe merely because the final sum fits; use exact intermediate arithmetic (e.g. wider partials) or a rigorously correct modular representation and final conversion. Preserve tail handling, ABI, default stream, scratch bounds, and every valid n (including n=0 if valid under the official domain). Report failed attempts, correctness results, and repeated full-program timings; this is a hypothesis about local reduction cost, not a proven bottleneck. |
| T2 | Fewer launches with a two-pass hierarchy | Using AB-MCTS, focus on the conventional multi-kernel hierarchy: vary tile/grain size and partial-count/finalization strategy to test lower-launch-count designs, including but not assuming a two-pass design wins. Avoid repeating a broad warp-reduction sweep already assigned to T1; use a straightforward correct CTA reduction unless tuning it is necessary to realize a hierarchy. Preserve exact arithmetic for all valid inputs, including safe intermediate sums, uninitialized scratch, tails, ABI, and default-stream behavior. If n=0 is valid, produce the empty sum. Report failures, correctness, and repeated full-program timings, then compare against the supplied baseline without treating one launch-count hypothesis as the result. |
| T3 | Single-launch cooperative reduction | Using AB-MCTS, investigate the distinct cooperative single-kernel path: resident CTAs compute grid-stride partials, synchronize grid-wide, and one CTA writes the result. The CUDA 12.6.3 guide documents the needed cooperative launch/grid synchronization, but that does not establish effective runtime support or performance on this measured target; validate the actual launch and include host-side setup/query costs in full-program timings. Ensure residency-safe configuration, exact intermediate arithmetic, no reliance on initialized scratch or atomics, and correctness for every valid n (including n=0 if valid). Record unsupported, incorrect, or slower attempts; only return a correctly validated candidate. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 908efebec59a4521 | T1 | search | valid | 0.000030 | 9c67996d8abe |
| e96edce9d9ec4d81 | T2 | search | valid | 0.000008 | 94f6a7a68f9e |
| 7cc900b704cd4e56 | T3 | search | valid | 0.000762 | 06f75e48cffe |
| 96a97d28d7554665 | T2 | search | valid | 0.000007 | b7b6bb424a0a |
| f5b882300c2342ad | T1 | search | valid | 0.000030 | 574cd555f665 |
| 314e27e661354e26 | T2 | search | valid | 0.000018 | ae1f18b547e2 |
| d5b847c36d6e4175 | T3 | search | valid | 0.000762 | f71465f42863 |
| 5d7bc2e7147748c2 | T1 | search | valid | 0.000030 | dbc88907216c |
| fade80309bb740c1 | T2 | search | valid | 0.000008 | 0966686eb2eb |
| 757c3f5e842e4e10 | T2 | search | valid | 0.000010 | 61c6625bda52 |
| 961e140170124e37 | T1 | search | valid | 0.000030 | eeaadf0b8caf |
| d441ab81063e4ce5 | G | postprocess | valid | 0.000007 | e010b8557ecc |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
