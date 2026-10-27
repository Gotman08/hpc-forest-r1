# Validation de la reprise après un conseil non exécutable

La tentative R2 avec GPT-6 Luna Max a révélé un blocage réel sur GEMM. Mother
demandait `continue Gm3` pour répéter une confirmation ; cette intégration avait
déjà consommé son unique essai autorisé. L'action acceptée effaçait la revue
d'inactivité, alors que tous les arbres de recherche étaient suspendus. Le
contrôleur ne pouvait ni admettre de travail ni déclencher sa reprise normale.
Il a terminé avec `unresolved_control_stall`, sans livrer de programme.

Les preuves originales sont conservées dans
[gemm-stall.json](../experiments/quality-luna-20261027-r2/diagnostics/gemm-stall.json)
et [le résultat terminal](../experiments/quality-luna-20261027-r2/diagnostics/gemm-failure-result.json).
TabPFN n'avait produit aucune prédiction ni changé de parent dans cette recherche.

## Correction vérifiée

- `continue` et `resume` refusent les rôles réellement indisponibles, avec leur
  motif enregistré, notamment `checkpoint_limit`.
- Un conseil à un arbre suspendu conserve la revue d'inactivité ; une action
  qui reprend effectivement le travail peut la lever.
- Mother voit le motif d'indisponibilité de chaque arbre dans son état partagé.
- Le refus d'un rapport d'analyste indique la borne inchangée de 1 à 4 citations
  et le nombre reçu. Le prompt rappelle également la limite de 3 conclusions.

Le contrat est `hpc-forest-active-v4-admission-liveness`. Les limites d'essais,
récompenses et vérifications des programmes n'ont pas été assouplies.

## Résultats logiciels du 27 octobre 2026

| Vérification | Résultat |
|---|---|
| Six nouveaux tests sur la reproduction du défaut | Avant : 5 échecs, 1 réussite ; après : 6 réussites |
| Régressions ciblées après correction | 67 réussites, 17,19 secondes |
| Suite Python complète | **1 151 réussites, 0 échec, 3 ignorés**, 1 154 collectés |
| Temps pytest | 19 min 29,70 s ; processus complet 19 min 30,92 s |
| Sources/tests pendant la validation | 183 fichiers suivis, empreintes inchangées |
| Ruff sur les sources et tests | Réussi |

Les trois tests ignorés concernent deux opérations de liens symboliques POSIX
non exécutables dans cet environnement Windows et le mode facultatif AB-MCTS-M
sans ses dépendances. Les recherches présentes emploient AB-MCTS-A. Un
avertissement Starlette/httpx subsiste dans un test web réussi. Les neuf tests
JavaScript de la [validation précédente](VALIDATION-QUALITE-20261027.md)
couvrent l'interface, inchangée dans cette correction.

Preuves : [résultat complet](../evidence/admission-recovery-full-20261027/result.json),
[manifeste des empreintes](../evidence/admission-recovery-full-20261027/manifest.json),
[journal pytest](../evidence/admission-recovery-full-20261027/pytest.log),
[JUnit](../evidence/admission-recovery-full-20261027/pytest.xml),
[reproduction avant correction](../evidence/admission-recovery-20261027/regression-before.log),
[tests ciblés après correction](../evidence/admission-recovery-20261027/regression-after.log),
[Ruff](../evidence/admission-recovery-20261027/ruff.log).

## Validation réelle distincte

Le [pilote R3](../experiments/quality-luna-20261027-r3/README.md) compare GEMM CPU
et Black–Scholes avec/sans conseiller. Les quatre recherches ont démarré sur
ROMEO à 17:34 UTC avec le moteur corrigé et gelé, GPT-6 Luna effort max dans
tous les rôles LLM, le même plan initial par problème et des mémoires neuves.
La qualification du runtime TabPFN a réussi. Aucun résultat de ce contrôle
synthétique n'est fourni aux recherches.

Les quatre recherches sont terminées : quatre programmes livrés, tous corrects
sur les entrées prévues et réservées lors de la remesure commune 786461. Les
515 invocations natives auditées demandent Luna Max. Les quatre arrêts sont
`final_reserve_or_deadline`, sans blocage terminal ni clôture finale anticipée
pour convergence. Un `continue Gm1` non exécutable a bien été refusé ; une
revue d'inactivité Black–Scholes a automatiquement rouvert T3.

Un appel d'analyste a néanmoins atteint sa limite de sortie après 905,56 s ;
Forest a poursuivi et livré. Ce coût résiduel et son usage en tokens inconnu
restent consignés. TabPFN n'a changé aucun parent, avec un seul appel réel
rejeté par la calibration. Les tests logiciels prouvent les invariants de
reprise, pas un gain de speedup. Voir les
[résultats détaillés et leurs limites](../experiments/quality-luna-20261027-r3/RESULTATS.md).
Les tentatives R1 et R2 restent identifiées et conservées, y compris leurs échecs.
