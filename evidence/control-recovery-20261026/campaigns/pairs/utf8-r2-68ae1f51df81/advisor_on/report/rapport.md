# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `f8e647be0946591997735ef48334ff7aa305c9cfa872130d4c2b47cef95d7670`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 111, "tokens_used": 8430743, "tokens_reserved": 0, "unknown_usage_calls": 2, "bounded_usage_calls": 0, "exact_tokens_used": 8430743}`.
Coûts par phase : `{"search": {"slots": 102, "tokens_used": 7506351, "tokens_reserved": 0, "unknown_usage_calls": 2, "bounded_usage_calls": 0, "exact_tokens_used": 7506351}, "postprocess": {"slots": 5, "tokens_used": 924392, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 924392}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "a09ea21632e34944", "outcome": {"binary_sha256": "e341c542064bba7a4125c6c34cd5e32ba22412033bc54fe1203fff466e158e59", "cache_key": "2b34355d0bb7e00bbb2080c9631bc0a7119506e3b8c425809853c2453de97536", "commit": "3856d62a270c263cf60eefd66a576f43dad906ec", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-99b608026a724e8ebea3ef565caa9017/campaign/logs/e1/a09ea21632e34944/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-99b608026a724e8ebea3ef565caa9017/campaign/logs/e1/a09ea21632e34944/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-99b608026a724e8ebea3ef565caa9017/campaign/logs/e1/a09ea21632e34944/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-99b608026a724e8ebea3ef565caa9017/campaign/logs/e1/a09ea21632e34944/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-99b608026a724e8ebea3ef565caa9017/campaign/logs/e1/a09ea21632e34944/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-99b608026a724e8ebea3ef565caa9017/campaign/logs/e1/a09ea21632e34944/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r2-68ae1f51df81/forest-app-99b608026a724e8ebea3ef565caa9017/campaign/logs/e1/a09ea21632e34944/confirmation/attempt-001/sample-4.log"], "mean_seconds": 6.786456235304475e-06, "reason": "", "score": 0.8787421791219507, "status": "valid", "times": [6.793087734943062e-06, 6.783714543812107e-06, 6.785515858273133e-06, 6.783717450953491e-06, 6.786245588540583e-06], "tree_hash": "149b8b94a19b080cfa0244259694110817f00607"}, "status": "confirmed"}`.

Commit retenu après confirmation : `78794bce733db1d464b88e03df9e24f871718a22`.
Temps confirmé : 0.000006 s ; référence confirmée : 0.000049 s.
Réduction mesurée : 88.5%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | SIMD validation of all byte classes | Explore whole-buffer SIMD UTF-8 validation: classify byte roles and detect invalid continuation structure and restricted lead/second-byte combinations across blocks. Handle cross-block sequences and every tail length without out-of-range loads. Preserve the run signature, thread budget, input immutability, complete output write, and correctness for all byte sequences. Compile and measure only valid candidates on the official workload. |
| T2 | Block ASCII detection versus the existing scalar fast path | Explore word- or vector-width detection and skipping of all-ASCII blocks, compared directly with the baseline's existing bytewise ASCII fast path. When a block contains non-ASCII bytes, validate from the first such byte without skipping or misclassifying any sequence, then resume scanning at the next unread position if useful. Do not read past n or assume padding. Preserve all correctness and interface constraints; judge performance on the official mixed-width workload, where the benefit depends on actual ASCII-run lengths. |
| T3 | Branch-light scalar UTF-8 parser | Explore a distinct non-SIMD scalar approach, such as a compact byte-class DFA or branch-light code-point parser, to reduce per-byte branches and overhead on mixed-width data. Cover malformed continuations, overlong forms, surrogates, out-of-range values, and truncation at every boundary. Preserve all interface and memory constraints; retain only measured, correct improvements. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 6f57122e24924644 | T1 | search | valid | 0.000020 | dbe7683509e0 |
| 50a3241d1cce4d3d | T2 | search | valid | 0.000050 | f550322873b9 |
| 48f045f4096f4a8c | T3 | search | valid | 0.000084 | 7a1d96432ef7 |
| abb4a3c3f4c2496c | T2 | search | valid | 0.000052 | 1ddfd129240c |
| eaf456a777aa4873 | Gm1 | search | valid | 0.000021 | 1479efaf1766 |
| f2c94897a1ad4d3d | T1 | search | valid | 0.000012 | 96616cfce709 |
| d7fe828041a44734 | T3 | search | valid | 0.000065 | b321e8716143 |
| 9f4e06ae0a24470a | T2 | search | valid | 0.000056 | d62bd1294df7 |
| 8f7f959eba4e49c2 | T1 | search | valid | 0.000008 | 489806f4bd11 |
| fddfce42d94f45b6 | T3 | search | valid | 0.000123 | dfce5ae52e94 |
| 4d908f5519504a4f | T3 | search | valid | 0.000125 | 88079910a55a |
| 220dc5b47bb24be4 | T1 | search | valid | 0.000006 | cf04f3dad132 |
| 04e8c6a9dec240cd | T1 | search | valid | 0.000007 | 0f71786a8b71 |
| e7854ccce2194058 | T2 | search | valid | 0.000072 | 7597b17690ee |
| e87ff7c4cfe54f87 | T3 | search | valid | 0.000058 | a9be5c5f3cdd |
| 8f98816430e545a0 | T1 | search | valid | 0.000013 | 30992c63f4f6 |
| dcee33527d2b475b | T3 | search | valid | 0.000049 | 5113e9506e98 |
| d89fbfaeaf8a41b7 | T2 | search | valid | 0.000056 | 1124f3d87e4e |
| b2e31298d3d24b12 | T1 | search | valid | 0.000010 | 40453a38be66 |
| 46b7353e74814475 | T3 | search | valid | 0.000049 | a66279c02f39 |
| 91f2a30c2fd64762 | T3 | search | valid | 0.000131 | 71616ff5c0b3 |
| 3497d36ceee34236 | T2 | search | valid | 0.000062 | 277de7926741 |
| a93aba7cc0134fc9 | T1 | search | valid | 0.000010 | 727d42b7395b |
| afbef2effe644f6e | T3 | search | valid | 0.000097 | 32ab5a83eb8e |
| e7d42909331f41ff | T2 | search | valid | 0.000059 | d290060a44f5 |
| 6916018f7cb6461d | T1 | search | valid | 0.000012 | 4c1895f060a2 |
| 955260f43ddd41ca | T1 | search | valid | 0.000006 | 78794bce733d |
| 0ddf296923f947f9 | T1 | search | valid | 0.000008 | 07c4e0916394 |
| d65e63ffbbb54f5c | T1 | search | valid | 0.000007 | dcad0f4754fd |
| 2ab62656065d46aa | T1 | search | valid | 0.000010 | d4c9dbdc6387 |
| 0d02cbfb11a94993 | T1 | search | valid | 0.000010 | 0e173c961fde |
| 5024982f99554570 | T2 | search | valid | 0.000053 | 9557b94066c3 |
| 28d65fd1c6194d6a | T3 | search | valid | 0.000057 | 9f88fdd2b2a9 |
| c66b4c93f9444207 | T1 | search | valid | 0.000008 | 176c3868ecda |
| d056b1349ce14144 | T3 | search | valid | 0.000052 | d95561d230d2 |
| a09ea21632e34944 | G | postprocess | valid | 0.000007 | 3856d62a270c |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
