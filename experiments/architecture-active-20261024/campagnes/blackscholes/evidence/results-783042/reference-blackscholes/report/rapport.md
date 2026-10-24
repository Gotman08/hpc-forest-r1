# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `d7f38e463c3dd8d635c1439aab7f7a5104b52740bbc33434c1cdcd378c563b40`.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 55, "tokens_used": 3380219, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3380219}`.
Coûts par phase : `{"search": {"slots": 45, "tokens_used": 2054322, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 2054322}, "postprocess": {"slots": 7, "tokens_used": 1325897, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1325897}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "d292122d81db4200", "outcome": {"binary_sha256": "116df1b47c3c284e24fa2332d294247eb26d39d75a0cf816fafbeeececf1af2d", "cache_key": "09eb7a587d60605c03f76e6f38c87ab795f0cbda94362daf00992a365b60c58d", "commit": "df241383ba65d11b118d2af0b5ad88b7f9f2acf4", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-active-blackscholes-748a382c279447d6b51e9e502de62594/results-783042/reference-blackscholes/logs/e1/d292122d81db4200/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-active-blackscholes-748a382c279447d6b51e9e502de62594/results-783042/reference-blackscholes/logs/e1/d292122d81db4200/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-active-blackscholes-748a382c279447d6b51e9e502de62594/results-783042/reference-blackscholes/logs/e1/d292122d81db4200/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-active-blackscholes-748a382c279447d6b51e9e502de62594/results-783042/reference-blackscholes/logs/e1/d292122d81db4200/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-active-blackscholes-748a382c279447d6b51e9e502de62594/results-783042/reference-blackscholes/logs/e1/d292122d81db4200/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-active-blackscholes-748a382c279447d6b51e9e502de62594/results-783042/reference-blackscholes/logs/e1/d292122d81db4200/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-active-blackscholes-748a382c279447d6b51e9e502de62594/results-783042/reference-blackscholes/logs/e1/d292122d81db4200/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.0006804099708578714, "reason": "", "score": 0.91712074800768, "status": "valid", "times": [0.0006807326717793787, 0.0006800388812970655, 0.0006815295201926237, 0.0006802889191923712, 0.0006794598618279177], "tree_hash": "fe8926c3c73cb6c3d90855481eaaa82477c41d78"}, "status": "confirmed"}`.

Commit retenu après confirmation : `df241383ba65d11b118d2af0b5ad88b7f9f2acf4`.
Temps confirmé : 0.000680 s ; référence confirmée : 0.007529 s.
Réduction mesurée : 91.0%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | OpenMP scaling and overhead within the threads budget | In src/candidate.cpp, compare the serial baseline with an OpenMP outer loop using the passed threads value as a hard CPU budget; start with static scheduling and retain a serial path for one thread or small n. Avoid thresholds tied to published test values. Measure available valid n/thread cases under the frozen protocol, verify complete output writes and varied-input correctness, and report overhead as well as any gain. Preserve correct variants for later combination even if they lose in isolation. |
| T2 | Compiler-vectorized versus explicit SIMD execution | Keep threading unchanged and compare the ordinary per-option loop as compiled by the frozen build with an explicit x86-intrinsics kernel. Use only ISA supported by the frozen target/build, with compile-time guards and a scalar fallback; do not change compiler flags or add runtime environment/ISA probing. Preserve the supplied Black-Scholes computation and CND coefficients. If vector math requires altered rounding, validate it against tolerance on varied inputs and retain a correct fallback. Measure each route separately so G can test combinations with T1 and T3. |
| T3 | Isolated scalar arithmetic rewrites and combination candidates | Keep this tree scalar-focused. Test sharing sqrtf(T) and Horner evaluation of the supplied CND polynomial as separate changes and in combination; preserve the formula and coefficients, and validate rounding on varied inputs. Judge changes by measured correctness and time rather than assuming the compiler does or does not already combine operations. Retain correctness-passing rewrites that are slightly slower alone if they could enable a later measured combination with T1 or T2. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 5a4a1b95ee1f4182 | T1 | search | valid | 0.001430 | 3bf1b8961b08 |
| 36f181e3b1bb46f9 | T2 | search | valid | 0.005631 | 4b828ba9be07 |
| 69cd3b4f03c544ba | T3 | search | valid | 0.008214 | 9b795ccfe4b6 |
| 9d9339dc29f64dbe | T3 | search | valid | 0.007254 | c3feda35fa17 |
| 5742ad4218cf4186 | T1 | search | valid | 0.001408 | 52eef6a95d7a |
| 3b9fd1eef6f24d23 | T2 | search | valid | 0.002662 | 2d8af76f9a7c |
| 39dadc45c96d4f9a | T3 | search | valid | 0.008066 | 71024b0ae322 |
| 2aa2ab21a5d441a8 | T1 | search | valid | 0.001450 | 67d7ac7ebb7d |
| b3fb38ff0cc6421c | T3 | search | valid | 0.007276 | c320d51fc82c |
| 177f51a5add24f07 | T2 | search | valid | 0.004742 | d9179d9bfa93 |
| 0c6303ef4f6e4edd | Gm1 | search | valid | 0.001060 | 9a3c8f43d773 |
| d20af62fb894467a | T1 | search | valid | 0.001404 | 4c7fa1e94cdb |
| 1d09829bdb624c1d | T3 | search | valid | 0.007309 | 29b487ae8f4d |
| 9510f389ac514516 | T2 | search | valid | 0.002750 | c9d5e70d8cdf |
| 2a2949b870444487 | T1 | search | valid | 0.001401 | 7fc09bd00438 |
| b778fbac2a074024 | Gm2 | search | valid | 0.000710 | 387ad7d3931f |
| 0684b59f3b3e45a0 | T1 | search | valid | 0.001407 | 48ffb39194f0 |
| 59b38b1ef6c34b39 | T2 | search | valid | 0.005599 | 0a9ced4fc1e8 |
| 9060f22bb95c440f | T1 | search | valid | 0.001446 | 2cfb664f067f |
| 4a0323b543e8448d | T2 | search | valid | 0.002809 | 09445c3a0171 |
| 67b612a043274c67 | T1 | search | valid | 0.001428 | a5895d662bd1 |
| 8cb9755ab4f240c3 | G | postprocess | valid | 0.000694 | a35a45d844b4 |
| d292122d81db4200 | G | postprocess | valid | 0.000682 | df241383ba65 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
