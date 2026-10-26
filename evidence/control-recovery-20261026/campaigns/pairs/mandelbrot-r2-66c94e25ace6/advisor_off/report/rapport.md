# Rapport de campagne HPC Forest

État : `confirmed`.

Méthode : `H` ; génération : `codex`.
Protocole : `d3a16dc79b6473a9c37115ca41545787422973566fbdb20bfc0c46746ffe5953`.
Recherche : `ab-mcts-a/gaussian`. Générateurs autorisés : `[]` (liste vide : modèle principal uniquement).
Les fichiers search-diagnostics.json et search-generators.csv décrivent les essais ; ils ne constituent pas un classement contrôlé des modèles.

Ces mesures concernent uniquement cette machine et ce protocole. Une démonstration avec recettes C ne mesure pas la qualité d'un LLM ni la supériorité de H sur U.

Coûts enregistrés : `{"slots": 134, "tokens_used": 10007038, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 10007038}`.
Coûts par phase : `{"search": {"slots": 127, "tokens_used": 9515026, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 9515026}, "postprocess": {"slots": 3, "tokens_used": 492012, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 492012}, "confirmation": {"slots": 4, "tokens_used": 0, "tokens_reserved": 0, "unknown_usage_calls": 0, "bounded_usage_calls": 0, "exact_tokens_used": 0}}`.
Confirmation obligatoire de G final : `{"eligible_for_promotion": true, "experiment_id": "04284277e85b4ff3", "outcome": {"binary_sha256": "90fc9f24b543c90173cd7275ee8e28fed6fd933b9ea129579d7560211b792f3a", "cache_key": "0e051e7c03a19681eab5fff8cf0fe4bac84319e1791e059c1b6da71983474144", "commit": "e73a769a03f2411d1afb0a177441828c7ba800dc", "correct": true, "logs": ["/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-fae2d6d4c1d44b6cbecf7ba1bc44b2a3/campaign/logs/e1/04284277e85b4ff3/confirmation/attempt-001/build.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-fae2d6d4c1d44b6cbecf7ba1bc44b2a3/campaign/logs/e1/04284277e85b4ff3/confirmation/attempt-001/correctness.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-fae2d6d4c1d44b6cbecf7ba1bc44b2a3/campaign/logs/e1/04284277e85b4ff3/confirmation/attempt-001/sample-0.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-fae2d6d4c1d44b6cbecf7ba1bc44b2a3/campaign/logs/e1/04284277e85b4ff3/confirmation/attempt-001/sample-1.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-fae2d6d4c1d44b6cbecf7ba1bc44b2a3/campaign/logs/e1/04284277e85b4ff3/confirmation/attempt-001/sample-2.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-fae2d6d4c1d44b6cbecf7ba1bc44b2a3/campaign/logs/e1/04284277e85b4ff3/confirmation/attempt-001/sample-3.log", "/gpfs/scratch/nimarano/forest-romeo-oauth-20261025-51ab9260/control-recovery-mandelbrot-r2-66c94e25ace6/forest-app-fae2d6d4c1d44b6cbecf7ba1bc44b2a3/campaign/logs/e1/04284277e85b4ff3/confirmation/attempt-001/sample-4.log"], "mean_seconds": 0.1519183136544821, "reason": "", "score": 0.7877825500009836, "status": "valid", "times": [0.15196227441054166, 0.15188992953405725, 0.1518409713561249, 0.15201574967514866, 0.15188264329653803], "tree_hash": "67cc5bc941e5f7a83bc5ef3469bf6d6d0e942dfc"}, "status": "confirmed"}`.

Commit retenu après confirmation : `38c7f6a9ac3b2dcd6df534faf704eff5f45d1c49`.
Temps confirmé : 0.150804 s ; référence confirmée : 0.563943 s.
Réduction mesurée : 73.3%. Référence conservée : non.

Mother a choisi **3 arbres AB-MCTS**, exécutés tous en parallèle à chaque passe.

| Arbre | Sujet | Objectif Mother |
|---|---|---|
| T1 | Parallélisme OpenMP et répartition de charge | Remplacer le parcours sériel par une région/parallèle OpenMP qui respecte explicitement threads; comparer une répartition par lignes ou blocs de lignes, et static contre guided/dynamic seulement si l’équilibrage justifie le surcoût. Garder un chemin adapté à threads=1, éviter le dépassement du budget et préserver les expressions de coordonnées, le calcul par pixel et l’écriture de toute la sortie. Valider les petits cas et bornes décalées; rapporter correction et temps à 1 et 4 cœurs. |
| T2 | Calcul SIMD exact entre pixels | Explorer un kernel SIMD masqué sur des pixels adjacents, avec une voie de queue scalaire. Pour chaque lane, conserver l’ordre des mises à jour, le test strict > 4.f et le compte exact; ne pas utiliser de raccourci de membership, de précision réduite ni de réassociation/fusion qui change les résultats. Établir ce que permet la compilation inchangée avant de retenir des intrinsics spécifiques. Comparer les performances à 1 et 4 cœurs et valider tous les cas de correction. |
| T3 | Déroulage mesuré du kernel scalaire autonome | Évaluer le déroulage modéré (par exemple par 2 ou 4) du kernel scalaire sur le parcours complet, comme candidat autonome, sans dépendre de l’implémentation SIMD de T2. Chaque itération doit conserver son test d’échappement strict au même point avant la mise à jour; ne pas omettre de test ni changer les opérations flottantes ou les expressions de coordonnées. Comparer au kernel scalaire non déroulé, mesurer à 1 et 4 cœurs, et valider exactement les petits cas et bornes décalées. Rapporter séparément si cette variante pourrait être utile comme fallback après mesure. |

| Expérience | Rôle | Phase | État | Temps mesuré (s) | Commit |
|---|---|---|---|---:|---|
| ec9887deb30346ad | T1 | search | valid | 0.283500 | be38aa66cc0b |
| 8ab54d0d70f447d8 | T2 | search | valid | 0.303527 | 9b98a5466e22 |
| fbc071c182b047ae | T3 | search | valid | 0.537625 | 5763df58ec51 |
| e2513ef0033742e8 | T3 | search | valid | 0.353544 | bf8498b29acf |
| 728bf991259941dd | Gm1 | search | valid | 0.151682 | 1eef4fb2c889 |
| 6b831c87ac6840fa | T1 | search | valid | 0.363135 | 3eb3982004b0 |
| 97daf8bc82c0449b | T4 | search | valid | 0.151843 | ce7445deb0ff |
| 8d1f6c43613c4716 | T2 | search | valid | 0.191682 | e16b94127ab2 |
| 0605fe06064048ac | T4 | search | valid | 0.151724 | d13e8416cced |
| 619853cf3c8f4b8f | T1 | search | valid | 0.305159 | 80389fe06223 |
| 5a9681985b1b4b15 | T2 | search | valid | 0.155237 | ae4dfda78f53 |
| d3e58c31225b42ac | T3 | search | valid | 0.350363 | f4f724844f9d |
| 6c4c3f2b9d58494a | T4 | search | valid | 0.151992 | d4f8c6c3be7b |
| 5cdcc99235db422d | T1 | search | valid | 0.282685 | 15dd343b9c2b |
| be2c8f1f05f44acc | T2 | search | valid | 0.299777 | 81e5b1938111 |
| 3897d0393d924a0f | Gm2 | search | valid | 0.155215 | 03db806e3c64 |
| 839b144dc2b2469e | T3 | search | valid | 0.355448 | 805188c06657 |
| 745f9806f16541f1 | T4 | search | valid | 0.151927 | 4b893dad8f98 |
| 065bd101076c4451 | T1 | search | valid | 0.282324 | 089c19a584d5 |
| be997d02a12243ea | T2 | search | valid | 0.374121 | 108fd0f21e87 |
| ac45245c9e034d07 | T3 | search | valid | 0.344845 | bd1bb4760f0b |
| 111bd4fbc2b442ac | T4 | search | valid | 0.151718 | 145652480adb |
| 13fec9952fcc45b1 | T1 | search | valid | 0.362969 | d0593e7e7fb9 |
| 6d55461fa0b54d7b | T2 | search | valid | 0.150905 | 38c7f6a9ac3b |
| c3a4ee517fcc43b2 | T3 | search | valid | 0.278576 | 6c550e8700ce |
| 3c58ab4416af4af7 | T4 | search | valid | 0.153002 | 7b65fe395d84 |
| ac4e0e9de5864435 | T1 | search | valid | 0.282235 | b8b14279320e |
| 204c1bacca474010 | T2 | search | valid | 0.297800 | e2e57c6fa58b |
| cb89c5f9a7044e45 | Gm3 | search | valid | 0.151716 | 38d764032877 |
| 914e89007ca04154 | T3 | search | valid | 0.275599 | f9b58011305e |
| f906298427bc49ed | T3 | search | valid | 0.268767 | 0a45e48bc862 |
| 03f6692472244845 | T3 | search | valid | 0.353612 | 2f27a6d8bb68 |
| aac5acf3b8a84374 | T2 | search | valid | 0.360921 | 2bbba026fb30 |
| 546555fa2a6942ec | T3 | search | valid | 0.345170 | c0d478b8829d |
| 05b6d5848b14493e | T3 | search | valid | 0.268584 | 1857a0fd3f2d |
| 0fb7f8d392fc4c69 | T3 | search | valid | 0.344772 | 3193d1603650 |
| 4e57fee0f1b1413d | T3 | search | valid | 0.353535 | bd81da25614e |
| 037ddfee12c74da0 | T3 | search | valid | 0.344727 | 77a4c3c29281 |
| d008a811780246b0 | T4 | search | valid | 0.151989 | 123e344f2a75 |
| 885bf76accf346b2 | T1 | search | valid | 0.283149 | 94749d092977 |
| 3f9e2085fe04428c | T2 | search | valid | 0.154457 | a32d3f8afb84 |
| 5f526466f2cb4389 | T1 | search | valid | 0.282387 | af6f62b8e468 |
| fdee6b291b3148ad | T2 | search | valid | 0.152357 | e83013622c01 |
| b9d91046b97b420b | T4 | search | valid | 0.151808 | c86e6cfe005e |
| e3e823278b524b9e | T1 | search | valid | 0.290731 | bdf906b80f02 |
| 04284277e85b4ff3 | G | postprocess | valid | 0.151855 | e73a769a03f2 |

Les confirmations utilisent d'autres cas de correction et des tours de mesure entrelacés. Les doublons n'ajoutent aucune observation à TreeQuest. Les erreurs d'infrastructure gardent un score absent. Voir experiments.json pour les temps bruts, les sources et les journaux.
