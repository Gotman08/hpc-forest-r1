# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `539ed7847179c5a7779a517d6fc5d0e48f32b20de27a43e7f1d2f4cc4871b150`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 115, "tokens_used": 10224115, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10224115}`.
Coûts par phase : `{"search": {"slots": 106, "tokens_used": 9307286, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 9307286}, "postprocess": {"slots": 5, "tokens_used": 916829, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 916829}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "4b573129ece54252", "outcome": {"binary_sha256": "57cb253da0d1228cf6d239563a16f3fd7e2fde07e38a1e7ed8c7e258ee3ffdc6", "cache_key": "e68b44d1133a18451d9aa4d7b21fd344699d76832ff895ec519e13c68462d161", "commit": "8e02f00a425ce4878744702b71299675ddba81ef", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-8d4577f977e94165b3b008a0775578f2/campaign/logs/e1/4b573129ece54252/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-8d4577f977e94165b3b008a0775578f2/campaign/logs/e1/4b573129ece54252/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-8d4577f977e94165b3b008a0775578f2/campaign/logs/e1/4b573129ece54252/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-8d4577f977e94165b3b008a0775578f2/campaign/logs/e1/4b573129ece54252/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-8d4577f977e94165b3b008a0775578f2/campaign/logs/e1/4b573129ece54252/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-8d4577f977e94165b3b008a0775578f2/campaign/logs/e1/4b573129ece54252/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-utf8-r1-21612544cf49/forest-app-8d4577f977e94165b3b008a0775578f2/campaign/logs/e1/4b573129ece54252/confirmation/attempt-001/sample-4.log"], "mean_seconds": 9.005163754258359e-06, "reason": "", "score": 0.848788457392271, "status": "valid", "times": [9.056951453887437e-06, 9.061137781629115e-06, 9.054219027640673e-06, 8.8021991510006e-06, 9.051311357133969e-06], "tree_hash": "8106672e6814205950861938e7c151107d7ea404"}, "status": "confirmed"}`.

Commit retenu après confirmation : `2194dc6f8a62eb422a2e91a5c2865db45815de1c`.
Temps confirmé : 0.000008 s ; référence confirmée : 0.000051 s.
Réduction mesurée : 84.9%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Portable word-at-a-time ASCII-run skipping | Explore a portable word-at-a-time ASCII-run fast path: inspect only complete in-bounds words (for example, loaded via memcpy), fall back to scalar handling when a word contains a high bit, and handle the tail without overreading. Do not use SIMD in this track, keeping it distinct from T2. Preserve exact UTF-8 validation and output behavior for arbitrary lengths. Measure whole-call time on the mixed-width workload and ASCII case, and check malformed-input correctness. |
| T2 | SIMD structural UTF-8 validation | Explore actual blockwise SIMD validation that classifies every byte, checks UTF-8 lead/continuation relationships and special boundary restrictions, and carries state across blocks. This is not merely a vectorized ASCII probe. Verify ISA and compiler support in the actual build; retain a correct fallback and handle block boundaries and tails without overreads. Measure whole-call time and verify all correctness cases. |
| T3 | Branch-reduced scalar DFA | Explore a scalar byte-class/state-transition DFA as an alternative to the baseline's code-point branches; compare processing every byte with retaining the existing scalar ASCII fast path before entering the DFA. Keep tables immutable and avoid per-call setup or scratch unless its cost is included. Preserve all scalar-value constraints and arbitrary-length behavior; measure whole-call time on mixed-width input and verify ASCII and malformed cases. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| 87f9284ffcd34996 | T1 | search | valid | 0.000067 | 3599f1b98ff3 |
| a176626f50b74c34 | T2 | search | incorrect | — | 2c46940eddb6 |
| 7e364f8363ae41fb | T3 | search | valid | 0.000114 | 3360e5d89279 |
| 284def73e5044618 | T3 | search | valid | 0.000108 | a86258c49ba3 |
| 7becb78937834acb | T1 | search | valid | 0.000091 | aad2cbb77b4b |
| efeab32d183e402a | T3 | search | valid | 0.000108 | e9a2791565b1 |
| 37e4f1271c1b4312 | T2 | search | valid | 0.000117 | 8656496a558b |
| d0450c7459fb4a67 | T1 | search | valid | 0.000052 | 4b18828b5095 |
| 6a45d45c52214e25 | T1 | search | valid | 0.000058 | b1759c93815b |
| abb8039f96c34d19 | T3 | search | valid | 0.000076 | 712dbce7adf7 |
| e4cfaf10d83e49a7 | T2 | search | valid | 0.000015 | 9dcf52175f96 |
| 0ce701789b0b4413 | T1 | search | valid | 0.000059 | 10f5edca940a |
| 870f216c939946f9 | T3 | search | valid | 0.000129 | cb1921319603 |
| 9fcd6d496a88476e | T3 | search | valid | 0.000107 | 4cc381dc6611 |
| 252f2df2e92845d7 | T2 | search | valid | 0.000017 | af3ef95569cb |
| 9845c280a5b9470b | T3 | search | valid | 0.000114 | 1703078dd246 |
| 2d904f1d0358489a | T2 | search | valid | 0.000019 | 2443722ff9f6 |
| e60aea2c5e104dae | T2 | search | valid | 0.000014 | bfddd41985ec |
| 694e0f90fff54814 | T2 | search | valid | 0.000019 | c36a7ba9c0b6 |
| 383b1ad1071140e2 | T2 | search | valid | 0.000016 | 19726225eaf1 |
| 86bba94d93a44398 | Gm1 | search | valid | 0.000017 | 95cb46117ec2 |
| 92a1d89edf0f4d0a | T2 | search | valid | 0.000020 | 274b7298813d |
| 56b11f7a80c240c9 | T2 | search | valid | 0.000009 | 1577c7c9611e |
| 10af6b2f274a44e1 | T2 | search | valid | 0.000016 | db5ec466fcac |
| 20ca34d8b3354115 | T2 | search | valid | 0.000009 | 1b9948450ade |
| c010a29976a44129 | T2 | search | valid | 0.000008 | 2194dc6f8a62 |
| f1b538a7599d43c1 | T2 | search | valid | 0.000016 | 010c688a4dc4 |
| 0851e0cf26e349b6 | T2 | search | valid | 0.000010 | 175a35ce16c9 |
| 41c2d0becde54b6c | T2 | search | valid | 0.000010 | 9537592f0e99 |
| 35db33c04d3d4edc | T2 | search | valid | 0.000011 | ecf8aa4e3a03 |
| b890816d15064f7e | T2 | search | valid | 0.000009 | 135c5c526311 |
| 4b573129ece54252 | G | postprocess | valid | 0.000009 | 8e02f00a425c |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
