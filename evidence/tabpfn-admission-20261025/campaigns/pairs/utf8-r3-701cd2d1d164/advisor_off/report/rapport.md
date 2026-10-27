# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `661162422ec37b09dfcdc9357c1935405a7b77481ed3175922e493455089bf08`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 60, "tokens_used": 4406146, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 4406146}`.
Coûts par phase : `{"search": {"slots": 51, "tokens_used": 3755969, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 3755969}, "postprocess": {"slots": 5, "tokens_used": 650177, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 650177}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "47a0804a1b874e1d", "outcome": {"binary_sha256": "dcd45d0b91b370a4c7f860188d4226992b22093d31a385843aa210199a8963d5", "cache_key": "dc5164d806cc27af8573cca3c8021d563225b18e0c9ab97d1f4b232f80b77f13", "commit": "45a6856b37484c95c4035c55a565bb031e024a47", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-4a75e5bd082144e3be38a5c22bafa9d6/campaign/logs/e1/47a0804a1b874e1d/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-4a75e5bd082144e3be38a5c22bafa9d6/campaign/logs/e1/47a0804a1b874e1d/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-4a75e5bd082144e3be38a5c22bafa9d6/campaign/logs/e1/47a0804a1b874e1d/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-4a75e5bd082144e3be38a5c22bafa9d6/campaign/logs/e1/47a0804a1b874e1d/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-4a75e5bd082144e3be38a5c22bafa9d6/campaign/logs/e1/47a0804a1b874e1d/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-4a75e5bd082144e3be38a5c22bafa9d6/campaign/logs/e1/47a0804a1b874e1d/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/tabpfn-admission-utf8-r3-701cd2d1d164/forest-app-4a75e5bd082144e3be38a5c22bafa9d6/campaign/logs/e1/47a0804a1b874e1d/confirmation/attempt-001/sample-4.log"], "mean_seconds": 1.0099080685939766e-05, "reason": "", "score": 0.8343354478403929, "status": "valid", "times": [1.0099188865183383e-05, 1.0098679598865473e-05, 1.0100052167747168e-05, 1.0099818089636991e-05, 1.0097664708265811e-05], "tree_hash": "2dc297bfb57896c76ebd20fae191ea7d32140bb8"}, "status": "confirmed"}`.

Commit retenu après confirmation : `91391e09f4943bf2924c8a472b587434af6618e2`.
Temps confirmé : 0.000008 s ; référence confirmée : 0.000051 s.
Réduction mesurée : 84.1%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | SIMD validation across input blocks | Explore full block-wise x86 SIMD UTF-8 validation in src/candidate.cpp: validate leading-byte classes, continuation relationships, special second-byte bounds for E0, ED, F0, and F4, and cross-block sequences. Keep scalar handling limited to boundaries and tails rather than making ASCII skipping the main optimization. Do not assume unavailable compile-time ISA flags; ensure the candidate builds under the harness configuration, using an appropriate fallback if needed. Measure against the baseline on valid mixed-width n=65536 input and preserve correctness for ASCII and all malformed inputs, within the supplied thread budget. |
| T2 | Wide ASCII scanning with scalar UTF-8 fallback | Explore safe 64-bit word-load ASCII-run detection in src/candidate.cpp, then hand non-ASCII bytes to the existing-style scalar code-point validator. Keep this distinct from T1: do not implement full vector validation of UTF-8 constraints. Handle arbitrary lengths, tails, and code points crossing word boundaries without out-of-bounds reads or aliasing violations. Measure mixed-width and ASCII performance against the baseline, and preserve correctness for all UTF-8 inputs without exceeding the thread budget. |
| T3 | Table-driven scalar UTF-8 state machine | Explore a compact table-driven or DFA-style scalar validator in src/candidate.cpp that processes the input as a state machine, as a contrast to the code-point parser and SIMD approach. Ensure transitions reject invalid continuations, overlong forms, surrogates, out-of-range values, and truncation, and accept all valid UTF-8. Measure valid mixed-width n=65536 performance and verify ASCII and malformed correctness against the baseline. Keep an ASCII fast path separable so results can inform a later combination, but report the standalone DFA result too; respect the supplied thread budget. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 7353a1e4f69a412d | T1 | search | valid | 0.000019 | beff8cff179e |
| 0db5341188ee4205 | T2 | search | valid | 0.000053 | 2c3becd108c6 |
| 1c3f40b7609644e6 | T3 | search | valid | 0.000104 | 5c8f8a4d587c |
| 8343381169344d3a | T2 | search | valid | 0.000190 | 01ce2e9fdf35 |
| 2ade840c1cf5446f | T1 | search | valid | 0.000009 | 29df53c4553c |
| 90c73b64ccad4c0d | T3 | search | incorrect | — | 1dd74d06a4fc |
| 5b1d442fbf524d20 | T1 | search | valid | 0.000008 | 91391e09f494 |
| 62db23ff95a548c2 | T2 | search | valid | 0.000042 | a781d97dc7f3 |
| 6355efda94794b1e | T2 | search | valid | 0.000188 | 0b18ad90a4b1 |
| 694da96d0a274866 | T2 | search | valid | 0.000057 | 9b9b1c7c6fc7 |
| 220cdf1688224106 | T1 | search | valid | 0.000013 | 1985470a192c |
| b73617fb1325409b | Gm1 | search | valid | 0.000011 | 7434c417d711 |
| baeb805bb19142f3 | T2 | search | valid | 0.000042 | 5d4be42078af |
| f17f1154fb8b4f05 | T1 | search | valid | 0.000016 | 9d392765882c |
| c799461ada474a43 | T2 | search | valid | 0.000053 | df725b1c0f1e |
| 47a0804a1b874e1d | G | postprocess | valid | 0.000010 | 45a6856b3748 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
