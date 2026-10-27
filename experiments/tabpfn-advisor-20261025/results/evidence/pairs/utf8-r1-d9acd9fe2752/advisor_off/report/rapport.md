# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `6f9c4f0ce74717ef09cd45a562b631b84fef954e8227b40e569c9484403412c4`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 59, "tokens_used": 4196169, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4196169}`.
Coûts par phase : `{"search": {"slots": 50, "tokens_used": 3229085, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3229085}, "postprocess": {"slots": 5, "tokens_used": 967084, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 967084}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "da6e50b9382b4e1a", "outcome": {"binary_sha256": "93fe6a087b32fd89ae86cdb5221d7ff3d56010673639de83a579263700f9df92", "cache_key": "7a716ff1a2e51c51001c8c8fd3f0ec2d786917033efb5d9eacae7b5d34fc2a4b", "commit": "537cb31c9486e69a6a1bed49f26167213d94b594", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-5f5ab1610ad14fa0aa57d87feaa18372/campaign/logs/e1/da6e50b9382b4e1a/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-5f5ab1610ad14fa0aa57d87feaa18372/campaign/logs/e1/da6e50b9382b4e1a/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-5f5ab1610ad14fa0aa57d87feaa18372/campaign/logs/e1/da6e50b9382b4e1a/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-5f5ab1610ad14fa0aa57d87feaa18372/campaign/logs/e1/da6e50b9382b4e1a/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-5f5ab1610ad14fa0aa57d87feaa18372/campaign/logs/e1/da6e50b9382b4e1a/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-5f5ab1610ad14fa0aa57d87feaa18372/campaign/logs/e1/da6e50b9382b4e1a/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-pair-utf8-r1-d9acd9fe2752/forest-app-5f5ab1610ad14fa0aa57d87feaa18372/campaign/logs/e1/da6e50b9382b4e1a/confirmation/attempt-001/sample-4.log"], "mean_seconds": 7.744211336617083e-06, "reason": "", "score": 0.867341554299986, "status": "valid", "times": [7.98749189015578e-06, 7.669495832359585e-06, 7.671850438971335e-06, 7.661290789473689e-06, 7.730927732125026e-06], "tree_hash": "3298a639f69662e53d132189737a6ff901a24d12"}, "status": "confirmed"}`.

Commit retenu après confirmation : `98e0723d662bba09401a2d96abffd555bf1e42aa`.
Temps confirmé : 0.000007 s ; référence confirmée : 0.000051 s.
Réduction mesurée : 85.6%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | SIMD ASCII-span skipping with strict scalar fallback | In src/candidate.cpp, investigate SIMD block detection to skip ASCII spans, falling back to strict scalar UTF-8 validation where non-ASCII bytes occur. Use only instructions supported by the unchanged target/build, avoid out-of-bounds tail loads, and preserve exact validation at block transitions. Measure against baseline on valid mixed-width and ASCII inputs; pass all malformed-input checks and honor the thread budget. |
| T2 | Full-stream SIMD validation and supported-width comparison | Investigate full-stream SIMD validation: check leading-byte/continuation relationships, restricted second-byte ranges, chunk-boundary carry, and tails. Keep this distinct from T1’s ASCII detection and scalar fallback. With unchanged compiler flags and target, compare at least two supported vector widths when available; do not assume the widest is fastest. Preserve strict UTF-8 correctness, measure against baseline on valid mixed-width and ASCII inputs, and honor the thread budget. |
| T3 | Contrast table-driven and direct scalar validators | Investigate branch-reduced scalar validation without SIMD or bulk byte scanning. Contrast a compact table-driven byte-class/state DFA with a direct range-check state machine; preserve all scalar-value rules and safe bounds handling. Measure both against baseline on valid mixed-width and ASCII inputs, verify malformed-input correctness, and honor the thread budget. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 891697bb234c472f | T1 | search | valid | 0.000081 | 8a9d416fadbc |
| 94cf2e3cf68448b3 | T2 | search | valid | 0.000007 | 9e4cf53f69ef |
| 0c6872f3447448f4 | T3 | search | valid | 0.000130 | 3889671ad416 |
| 3f8d5dd3439948e2 | T3 | search | valid | 0.000096 | a270b4f24768 |
| db108321ddca4f94 | T1 | search | valid | 0.000058 | 1864fed4a737 |
| ae5ff4aaf4de45d3 | T1 | search | valid | 0.000069 | fe6e74a96456 |
| 511e9ebed15f4460 | T2 | search | valid | 0.000007 | 58716269804d |
| c1a1eaf4c8564e18 | T3 | search | valid | 0.000063 | 4f5887c4839c |
| e71cffc7fb35433f | T1 | search | valid | 0.000049 | 7cc245ba3dd8 |
| 2f817b06e2dd4eb1 | T3 | search | valid | 0.000054 | cb1d5a6555d1 |
| 0b465544c5264247 | T2 | search | valid | 0.000021 | 19dc40b28e5b |
| 90a5a6deaf4a45ec | T1 | search | valid | 0.000049 | 3cc694334c58 |
| d403b3f3c87c43ff | T3 | search | valid | 0.000072 | 5aa0094ef34f |
| c4798f1f00be4bdc | Gm1 | search | valid | 0.000007 | 98e0723d662b |
| dbc7faf6bb4a4214 | T1 | search | valid | 0.000061 | 579a82221eaa |
| 6057b4e129ab45b9 | T3 | search | valid | 0.000077 | cdbffe8b27c6 |
| e99e8f88b0a54069 | T2 | search | valid | 0.000009 | 5113f154ac8f |
| f3f86dd66ae44ca8 | T1 | search | valid | 0.000130 | c590c6c0853f |
| b1d6b68856624986 | T3 | search | valid | 0.000057 | 19985ce9cc40 |
| 740ebeb970554321 | G | postprocess | valid | 0.000009 | 4131837c6250 |
| da6e50b9382b4e1a | G | postprocess | valid | 0.000008 | 537cb31c9486 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
