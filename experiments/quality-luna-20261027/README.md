# Test réel des corrections avec Luna Max

Première campagne pilote du 27 octobre 2026, interrompue après la découverte d'un défaut du schéma des citations. Voir `INTERRUPTION.md`. La campagne corrigée est dans `../quality-luna-20261027-r2` ; aucun speedup final n'est revendiqué ici.

## Conditions fixées avant les recherches

- Un seul moteur Forest, même version corrigée dans les quatre exécutions.
- GPT-6 Luna, effort `max`, pour tous les rôles LLM ; aucun mélange de modèles.
- GEMM CPU et Black–Scholes, chacun avec et sans le conseiller TabPFN corrigé.
- Même plan initial, créé précédemment par Luna, dans les deux conditions de chaque problème. Aucun code optimisé ni exemple du conseiller provenant des campagnes précédentes n'est importé.
- Nouvelles bases, mémoires, identifiants et conversations ; graine 307.
- 5 400 secondes de recherche et 7 200 secondes de bout en bout par exécution. Le coût intégral du plan initial est imputé de la même façon aux deux conditions.
- Même recherche AB-MCTS-A gaussienne. Les interventions ultérieures de Mother restent autonomes et sont enregistrées.
- TabPFN : 94 variables disponibles avant génération, contexte de l'arbre courant, cible fondée sur les temps mesurés, validation chronologique avec parents distincts et marge empirique. Le conseiller peut s'abstenir ; aucune intervention n'est forcée.
- Les algorithmes candidats, leurs directions d'optimisation et les décisions pendant la recherche ne sont pas fournis par l'opérateur.

Les quatre recherches utilisent chacune une allocation de cinq CPU x86 sur ROMEO. Le worker OAuth et le contrôleur fonctionnent sur le nœud de calcul, sans relais sur le PC. Les programmes livrés sont ensuite remesurés ensemble, séquentiellement, sur une allocation commune, sur les entrées enregistrées et les entrées réservées. Les nœuds peuvent être partagés avec d'autres travaux.

## Vérifications déjà effectuées

Le moteur utilisé est celui de `docs/VALIDATION-QUALITE-20261027.md` : 1 142 tests Python réussis, trois ignorés, neuf tests d'interface réussis. Les nouveaux scripts d'audit ont aussi vérifié les unités de la cible et refusé une cible incohérente. Les quatre configurations ne diffèrent que par l'activation du conseiller et leurs chemins isolés.

Le test préalable ROMEO 786341 a réussi sur romeo-c022 : chargement du véritable TabPFN 3.5 et prédictions avec les 94 variables, en 10,56 secondes. Il utilise exclusivement des données synthétiques de qualification ; elles ne sont jamais importées dans les recherches. Cette qualification ne constitue pas une mesure du gain de performance.

| Étape | Job SLURM |
|---|---:|
| Qualification | 786341 |
| GEMM sans conseiller | 786342 |
| GEMM avec conseiller corrigé | 786343 |
| Black–Scholes avec conseiller corrigé | 786344 |
| Black–Scholes sans conseiller | 786345 |
| Remesure commune et audits | 786346 |

## Preuves et reproduction

`protocol.json` fixe les budgets, les conditions, les entrées et les empreintes du moteur. `assigned-arms.json` conserve les identifiants et les empreintes des charges utiles. `pipeline-arguments.json`, `prepared.json` et `submission.json` conservent les commandes exactes et les reçus SLURM. `qualification-receipt.json` et `preflight-local.json` documentent les vérifications préalables. Les scripts du sous-dossier `reproduction` reprennent le protocole contrôlé existant ; `prepare_quality_luna.py` et `finalize_quality_luna.py` préparent ce nouveau pilote sans modifier le moteur.

Une paire par problème permet de vérifier le fonctionnement réel et de décrire les différences observées. Elle ne permet pas de conclure à une supériorité fiable du conseiller. Les erreurs, abstentions et non-livraisons restent dans les résultats ; les décisions alternatives non exécutées n'ont pas de performance connue.
