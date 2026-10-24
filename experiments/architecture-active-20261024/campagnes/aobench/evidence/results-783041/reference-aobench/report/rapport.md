# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `f5a8a354b5dad39ce9b2a10e3ae7298aa04e78b6b4c952819d46769648849559`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 32, "tokens_used": 1528459, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1528459}`.
Coûts par phase : `{"search": {"slots": 24, "tokens_used": 958461, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 958461}, "postprocess": {"slots": 5, "tokens_used": 569998, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 569998}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "68c82b80512f4deb", "outcome": {"binary_sha256": "b7bc629ad9c249e1f4bcc517a877dbfc6601f2a37453604833b913161c5d659d", "cache_key": "bd35b106a5f4d4c1c8678decdc67013c974d657fb724963a7862afab8fe85630", "commit": "48dcc6921267272ba437fd5dadc7d3a268fb6d0c", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-aobench-6f673bcf1f384d98a4d546901684121e/results-783041/reference-aobench/logs/e1/68c82b80512f4deb/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-aobench-6f673bcf1f384d98a4d546901684121e/results-783041/reference-aobench/logs/e1/68c82b80512f4deb/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-aobench-6f673bcf1f384d98a4d546901684121e/results-783041/reference-aobench/logs/e1/68c82b80512f4deb/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-aobench-6f673bcf1f384d98a4d546901684121e/results-783041/reference-aobench/logs/e1/68c82b80512f4deb/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-aobench-6f673bcf1f384d98a4d546901684121e/results-783041/reference-aobench/logs/e1/68c82b80512f4deb/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-aobench-6f673bcf1f384d98a4d546901684121e/results-783041/reference-aobench/logs/e1/68c82b80512f4deb/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-aobench-6f673bcf1f384d98a4d546901684121e/results-783041/reference-aobench/logs/e1/68c82b80512f4deb/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.36036870130801263, "reason": "", "score": 0.9063205191544588, "status": "valid", "times": [0.35922337274597393, 0.3611046807376351, 0.36013939723572796, 0.3600088470107609, 0.3613672088099653], "tree_hash": "cbb509e223be6a81e57a40c72019ea22d8ea73f5"}, "status": "confirmed"}`.

Commit retenu après confirmation : `3949609f0bf6ec2860952ca97a34c106e71bcf11`.
Temps confirmé : 0.358447 s ; référence confirmée : 3.486458 s.
Réduction mesurée : 89.7%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Thread-safe OpenMP pixel parallelism and independent sampling | Explore OpenMP parallelization of independent pixels or scanlines in src/candidate.cpp, with the requested `threads` as a hard maximum and no writes shared between workers. Replace the shared `drand48` state with a suitable per-logical-sample or per-pixel independent uniform PRNG stream so scheduling and thread count cannot introduce races or reuse correlated streams. Preserve the existing ray math and sample counts: nsubsamples squared primary rays and all 64 ambient rays at each hit. Compare sensible loop granularities/schedules, including the 1-core case, and report correctness plus repeated timings for every official performance configuration. Do not alter other files or the ABI. |
| T2 | Isolated scalar primary-ray and pixel-output experiments | Optimize only the scalar primary-ray/per-pixel path in src/candidate.cpp, leaving the ambient-occlusion ray-generation/intersection kernel, RNG sequence, and thread scheduling unchanged. Measure invariant hoisting and local scalar accumulation/write-once changes separately against the original, then measure their combination; do not assume combined gains are additive. Preserve geometry and all primary samples, and check any rounding changes against the required RMSE and absolute-mean thresholds. Run all official correctness cases and repeated timings at each performance configuration so the result remains useful when considered for integration with the other tracks. |
| T3 | Ambient-ray generation and intersection throughput | Investigate ambient-ray generation and intersection throughput in src/candidate.cpp while keeping this separate from primary-ray traversal and OpenMP scheduling. Contrast the cost of scalar direction generation (for example, paired sin/cos only if supported by the frozen build) with batched/compiler-vectorized or intrinsic sphere/plane intersections; measure isolated variants before combinations. Preserve the uniform independent sampling distribution, random consumption where possible, all 64 rays per hit, geometry, and hit/root conditions. Do not use early-outs that omit required intersection work or unverified ISA instructions; retain a build-valid fallback if needed and do not inspect the runtime environment. Report correctness and repeated timings for all official configurations, including nsubsamples=3. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 9706e210240a448f | T1 | search | valid | 0.461350 | a22c2e2d7166 |
| 6e9a100a4acf4e32 | T2 | search | valid | 3.493595 | d7c5f699b469 |
| fec679fa77874855 | T3 | search | valid | 3.348743 | facf6403efab |
| 6cb6e4147f1041c0 | T2 | search | valid | 3.526254 | 61622624be7f |
| 8009bfed7f554326 | T1 | search | valid | 0.464144 | ab1738badac1 |
| d2f45735907842e1 | T3 | search | valid | 3.493764 | 9df497da63be |
| 3ccd59ba1be241b8 | T2 | search | valid | 3.516903 | 5c856207914e |
| 0703cf2a788f48ee | T1 | search | valid | 0.734679 | d5c55f4ea72d |
| 56b0d98c1a6f439f | T3 | search | valid | 2.860869 | 053a951763b7 |
| 187778ebb7bb4a38 | T1 | search | valid | 0.465263 | 0dcaf4d99be0 |
| a7899f33b9cf4d5b | Gm1 | search | valid | 0.358794 | 3949609f0bf6 |
| 68c82b80512f4deb | G | postprocess | valid | 0.359474 | 48dcc6921267 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
