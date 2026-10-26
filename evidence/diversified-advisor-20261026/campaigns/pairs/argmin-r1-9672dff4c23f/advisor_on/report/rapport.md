# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `a0797f97b7cf49869c1dd7edaca043a19603d2924e85f4dd2e0292ef0f106d2b`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 119, "tokens_used": 8882159, "tokens_reserved": 0, "unknown_usage_calls": 2, "bounded_usage_calls": 0, "exact_tokens_used": 8882159}`.
Coûts par phase : `{"search": {"slots": 110, "tokens_used": 7853323, "tokens_reserved": 0, "unknown_usage_calls": 2, "bounded_usage_calls": 0, "exact_tokens_used": 7853323}, "postprocess": {"slots": 6, "tokens_used": 1028836, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 1028836}, "confirmation": {"slots": 3, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "8c56c2c3bab54ef3", "outcome": {"binary_sha256": "8ef8205195d7e0f5959c169509a0bcc126f9ad5a33f0ad4476b9921ee8f49cb0", "cache_key": "427bf683146adee0028f6f59c69c8dced29f40ab19fd4db8220ed89afc1ac0e3", "commit": "d24486090fefa014ffc8f6f39ec116c4286b6a3f", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-a89bb3abd9f14a2fb5c4177df8bf6dd5/campaign/logs/e1/8c56c2c3bab54ef3/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-a89bb3abd9f14a2fb5c4177df8bf6dd5/campaign/logs/e1/8c56c2c3bab54ef3/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-a89bb3abd9f14a2fb5c4177df8bf6dd5/campaign/logs/e1/8c56c2c3bab54ef3/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-a89bb3abd9f14a2fb5c4177df8bf6dd5/campaign/logs/e1/8c56c2c3bab54ef3/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-a89bb3abd9f14a2fb5c4177df8bf6dd5/campaign/logs/e1/8c56c2c3bab54ef3/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-a89bb3abd9f14a2fb5c4177df8bf6dd5/campaign/logs/e1/8c56c2c3bab54ef3/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/diversified-advisor-argmin-r1-9672dff4c23f/forest-app-a89bb3abd9f14a2fb5c4177df8bf6dd5/campaign/logs/e1/8c56c2c3bab54ef3/confirmation/attempt-001/sample-4.log"], "mean_seconds": 1.3796205601257242e-06, "reason": "", "score": 0.8659840641603987, "status": "valid", "times": [1.3783414999795575e-06, 1.3806597818812193e-06, 1.3772625010953102e-06, 1.3848966387428256e-06, 1.3769423789297081e-06], "tree_hash": "be3c834e37f3bafb152a5262f5afd4bd0a50fd23"}, "status": "confirmed"}`.

Commit retenu après confirmation : `d24486090fefa014ffc8f6f39ec116c4286b6a3f`.
Temps confirmé : 0.000001 s ; référence confirmée : 0.000009 s.
Réduction mesurée : 84.5%. Référence conservée : non.

Mother a choisi **2 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Independent scalar reductions | Explore compiler-friendly C++17 scalar scans using multiple independent local minimum/index accumulators and a final tie-aware merge. Focus on scalar recurrence independence, unrolling, and branchless or conditional updates; do not add explicit SIMD intrinsics. Report whether the compiler auto-vectorizes the result. Keep the scan single-threaded, support every valid n without input-size specialization, and preserve the smallest index on ties. Record failed attempts; validate correctness and compare native wall time for both timed sizes. |
| T2 | SIMD argmin reduction | Explore explicit single-thread SIMD argmin methods for contiguous int32 input, contrasting a one-pass lane-wise value/index reduction with a vector minimum followed by a search for its earliest occurrence. Use only instructions supported by the target build, handle arbitrary lengths and tails, and preserve correctness for ties and extreme values. Do not use OpenMP or specialize to test values. Measure both timed sizes, including any extra-pass cost, and record failed attempts. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 1385123a51a0409c | T1 | search | valid | 0.000007 | be6e8cd9d4a7 |
| d9348458e27441f3 | T2 | search | valid | 0.000003 | ff001c507e12 |
| 19c58ede48b74304 | T1 | search | valid | 0.000008 | 014301e47e48 |
| 3c478eef9d334d0a | T2 | search | valid | 0.000004 | 86252d8a4807 |
| 7f6216369b99496d | T1 | search | valid | 0.000016 | c0bb532225f3 |
| 2a8e006fc589409c | T1 | search | valid | 0.000006 | 99df0b6b40da |
| e051ef73530a459f | T2 | search | valid | 0.000002 | 549f0cb7456f |
| 12b0d595b0774e78 | T3 | search | valid | 0.000002 | b1bf47b735dc |
| bbdb9cbfd68b456e | T1 | search | valid | 0.000005 | f9040512e0e6 |
| bc19e8f8e7e54f86 | Gm1 | search | valid | 0.000002 | 1ed04dbb545b |
| 7e9a0990cf7b4b12 | T3 | search | valid | 0.000001 | 4ac7fe7c01d6 |
| 12489cc4f7d64db6 | T4 | search | valid | 0.000002 | e6840ac15306 |
| 395aff5ae5554094 | T2 | search | valid | 0.000007 | 25d202fc321c |
| 1f17c4c3dec0492d | T3 | search | valid | 0.000002 | e3025dae3eb3 |
| 9805cc2b78a5486f | T3 | search | valid | 0.000001 | e8c9106ff417 |
| 33612c3d195747bc | T3 | search | valid | 0.000002 | d2c83f2466a0 |
| 9675d7ea467543a8 | T3 | search | valid | 0.000001 | 4531859ad7a7 |
| 9d0f8d150c42436b | T3 | search | valid | 0.000001 | 46a1b0cad848 |
| cc9739f7907c48df | T2 | search | valid | 0.000004 | 530eef083d6c |
| b90cddb6f10448d4 | T2 | search | valid | 0.000002 | 4a23f73730b4 |
| fb6f021d8f994c66 | T2 | search | valid | 0.000002 | 326a414e383f |
| c524289fe4544aaa | T2 | search | valid | 0.000003 | 628869fd7b36 |
| 6b730529618844d8 | T3 | search | valid | 0.000001 | 24824ead93ab |
| bacb3e377673456f | T3 | search | valid | 0.000001 | a5f68eae04cc |
| 353e3bead39d491e | T3 | search | valid | 0.000002 | 4a2d466c311f |
| 1c2d3568abe6414d | T3 | search | valid | 0.000002 | b5c79e217325 |
| c632cda645fc4666 | T3 | search | valid | 0.000001 | da2ac067278a |
| 744e5d3624f945ae | Gm2 | search | valid | 0.000002 | f9cb681fdc15 |
| d786f1399a994aaa | T4 | search | valid | 0.000002 | b8a3deb56ca2 |
| 66a5bbe1dec240d7 | T1 | search | valid | 0.000004 | 5f6ce8c101d2 |
| 23a27774ecf6424f | T4 | search | valid | 0.000002 | 373d5dff0315 |
| d799c2befa174476 | T1 | search | valid | 0.000005 | 38d838ff0f0d |
| 15f6a5bd7a834a51 | T2 | search | valid | 0.000005 | 448fc4c77fe9 |
| f67e7b9c0d2f4cf3 | T3 | search | valid | 0.000002 | 53f86ee4e293 |
| 2fba4f06e0be4dbb | T2 | search | valid | 0.000002 | 19fbceb6db59 |
| c95ed4d40bbf4254 | T3 | search | valid | 0.000001 | 6c4c543b4d86 |
| bfc0864f1b4e4bf8 | T2 | search | valid | 0.000003 | bef5c6f48878 |
| afde88b3bdef4e61 | T3 | search | valid | 0.000002 | 9de5c48deae3 |
| a18eb5e13e754597 | G | postprocess | valid | 0.000001 | bbdbc7ac199c |
| 8c56c2c3bab54ef3 | G | postprocess | valid | 0.000001 | d24486090fef |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
