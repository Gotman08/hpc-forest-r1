# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `79762fade4997dfe229474dba7b8ea557ca8d1de5b33302ac6bc0c124eb48d68`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 54, "tokens_used": 3336199, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3336199}`.
Coûts par phase : `{"search": {"slots": 47, "tokens_used": 2836168, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2836168}, "postprocess": {"slots": 4, "tokens_used": 500031, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 500031}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "291f4924255b4453", "outcome": {"binary_sha256": "460869c3efec112a7f41bda9b56920a5a5caceaeb696039d3f082b630c376c59", "cache_key": "5e0c8f558e9fb2308c16ec01fa7e6af9455b3e3f70d7feee84d02bdcf5aa510e", "commit": "a6f9f14c72c03577230d088a2d344e63e6ea5a53", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-utf8-84bf5b1d844645aba6fb57b65acabefa/results-782964/reference-utf8/logs/e1/291f4924255b4453/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-utf8-84bf5b1d844645aba6fb57b65acabefa/results-782964/reference-utf8/logs/e1/291f4924255b4453/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-utf8-84bf5b1d844645aba6fb57b65acabefa/results-782964/reference-utf8/logs/e1/291f4924255b4453/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-utf8-84bf5b1d844645aba6fb57b65acabefa/results-782964/reference-utf8/logs/e1/291f4924255b4453/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-utf8-84bf5b1d844645aba6fb57b65acabefa/results-782964/reference-utf8/logs/e1/291f4924255b4453/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-utf8-84bf5b1d844645aba6fb57b65acabefa/results-782964/reference-utf8/logs/e1/291f4924255b4453/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-utf8-84bf5b1d844645aba6fb57b65acabefa/results-782964/reference-utf8/logs/e1/291f4924255b4453/confirmation/attempt-001/sample-4.log"], "mean_seconds": 2.9277784860680114e-05, "reason": "", "score": 0.6278251732714317, "status": "valid", "times": [2.9292981549815503e-05, 2.9279324626865677e-05, 2.9270170552147247e-05, 2.9271112000000015e-05, 2.927533557457212e-05], "tree_hash": "206a0213cfcd377707168a338044f02608b16b79"}, "status": "confirmed"}`.

Commit retenu après confirmation : `82341ab1a2285183c063c89651d20d00a3887b05`.
Temps confirmé : 0.000029 s ; référence confirmée : 0.000049 s.
Réduction mesurée : 40.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Whole-stream SIMD UTF-8 validation with cross-block state | Primary hypothesis: SIMD masks validate UTF-8 constraints across the whole buffer, unlike T2's ASCII-span locator. Explore block classification, shifted continuation requirements, restricted second-byte checks, cross-block state, and a bounded tail. Compare relevant SIMD variants only when supported by the frozen target and unchanged build; do not alter flags or add runtime environment probing. Keep the supplied scalar implementation as a control, and report any useful hybrid as a distinct variant rather than excluding it. Preserve exact scalar-value validation, ABI, output, and thread budget. Use the official mixed-width n=65536 timing for performance and official ASCII/malformed checks for correctness, paying particular attention to vector boundaries and truncations where covered. Record failed variants. |
| T2 | SIMD-assisted ASCII-run skipping with a scalar slow path | Primary hypothesis: vector high-bit scans can skip ASCII spans while the existing strict scalar decoder handles non-ASCII code points. The benefit depends on the actual official mixed-width input containing useful ASCII spans; do not assume this or use synthetic-only results as evidence for the scored workload. Start decoding at a known code-point boundary and treat the first high-bit byte as input to validate—not as an assumed lead, since it may be a stray continuation. Keep loads and tails within n. Preserve exact validity, ABI, output, and thread budget. Measure the official mixed-width n=65536 workload and run the official ASCII/malformed correctness checks, especially for boundaries. Report this approach separately from T1's whole-buffer validation; label any hybrid distinctly and record failed variants. |
| T3 | Branch-reduced scalar UTF-8 decoding | Primary hypothesis: reducing scalar decoding control flow or dependencies helps the mixed-width workload; the supplied baseline already has an ASCII fast path, so do not assume ASCII scanning is the only scalar cost. Compare the baseline decoder with compact-state/DFA or reduced-branch scalar variants, measuring each under the official mixed-width n=65536 workload and checking official ASCII/malformed correctness. Keep scalar decoding as the focus, but do not treat that focus as a ban on useful correctness-preserving experiments; label any hybrid separately from pure-scalar results. Preserve exact validity, ABI, output, bounds, and thread budget. Report failed variants. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| c557b10fc09a4c93 | T1 | search | runtime_failed | — | d0c3f4b8024a |
| 5e2fba8baac84b46 | T2 | search | valid | 0.000060 | e462e4ebcc5e |
| e87168de8c614fc4 | T3 | search | valid | 0.000056 | d8192d9e4127 |
| 0350732002f14eaa | T2 | search | valid | 0.000078 | ab761c21ee66 |
| d66449d1d846490e | T2 | search | valid | 0.000081 | 31438879ffe9 |
| ec1a08dc37a84021 | T3 | search | valid | 0.000050 | 76c28bd3e2bc |
| 31112ea757f04c4a | T2 | search | valid | 0.000040 | b2dc211dc601 |
| db2837fca4e14fa6 | T3 | search | valid | 0.000062 | 9c3908196283 |
| 1a132d62e8224843 | T2 | search | valid | 0.000044 | 289c8e6de03e |
| da46c43f3da04f42 | T3 | search | valid | 0.000079 | 895c332b2184 |
| 1bef6299446e4809 | T1 | search | valid | 0.000058 | 60f22e5b2f0d |
| 1e47ac10752b48cc | T3 | search | valid | 0.000099 | 923a33d9d298 |
| 2a1cadb39bf54deb | T2 | search | valid | 0.000065 | ad721572bde0 |
| 0eeba011b99c4165 | T1 | search | runtime_failed | — | 849edd98622a |
| bc5196115d0740b7 | T2 | search | valid | 0.000048 | d6a68f2f8727 |
| cd2a550c3b714843 | T2 | search | valid | 0.000055 | a8766660c5ca |
| 6af9a1e290384d22 | T2 | search | valid | 0.000049 | 12ac4e044f33 |
| 24d80931a28445a0 | T2 | search | valid | 0.000068 | 8006c88638f8 |
| 1b0aac66208e4315 | T1 | search | valid | 0.000030 | 82341ab1a228 |
| 99d98d0fd9484ad9 | Gm1 | search | valid | 0.000056 | 362ffe80bfe4 |
| 291f4924255b4453 | G | postprocess | valid | 0.000030 | a6f9f14c72c0 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
