# Reprise des tests réels avec GPT-6 Luna Max

Nouvelle campagne démarrée le 27 octobre 2026 après correction du défaut de schéma observé sur la première tentative. La correction et les preuves sont documentées dans `../quality-luna-20261027/INTERRUPTION.md`.

Les quatre recherches repartent de bases et de conversations neuves : GEMM et Black–Scholes, avec et sans TabPFN. Tous les rôles LLM utilisent `gpt-6-luna`, effort `max`. Le moteur est identique entre les conditions ; seul le conseiller est activé ou désactivé. Les plans initiaux Luna, les entrées, la graine 307, les 90 minutes de recherche et le plafond de deux heures imputées par exécution sont conservés. Aucun code ni conseil de la tentative interrompue n'est réinjecté.

| Étape | Job SLURM |
|---|---:|
| Qualification du runtime TabPFN | 786350 |
| GEMM sans conseiller | 786351 |
| GEMM avec conseiller corrigé | 786352 |
| Black–Scholes avec conseiller corrigé | 786353 |
| Black–Scholes sans conseiller | 786354 |
| Remesure commune et audits | 786355 |

GEMM avec conseiller s'est terminé sans livraison après 3 596 secondes :
`unresolved_control_stall`. Mother a demandé `continue` sur Gm3, une intégration
ayant déjà consommé son unique essai. Cette action était acceptée mais ne pouvait
produire de travail ; elle effaçait la revue d'inactivité et bloquait la reprise.
TabPFN n'avait effectué aucun appel ni changement de parent. Les preuves sont
dans [le diagnostic](diagnostics/gemm-stall.json) et
[le résultat terminal](diagnostics/gemm-failure-result.json). Le dernier
`progress.json` conservait un état intermédiaire « running » : le résultat
terminal et le registre font foi.

Les trois autres recherches ont livré un code confirmé dans le budget, avec un
arrêt `final_reserve_or_deadline`. La remesure commune est terminée : ses deux
étapes ont réussi et les audits ne présentent aucune erreur. Le job commun est
néanmoins marqué en échec parce que la condition de réussite globale exige
quatre livraisons sur quatre. La
[relance après correction](../quality-luna-20261027-r3/README.md) est un nouveau
pilote avec de nouvelles mémoires ; elle ne remplace pas cet échec dans les
résultats. Les comparaisons seront calculées sur les programmes effectivement
livrés, avec les mêmes entrées et la même allocation de mesure. Le conseiller
reste libre de s'abstenir si ses données ou sa validation sont insuffisantes.
Une seule paire par problème constitue un pilote de fonctionnement, pas une
preuve de supériorité statistique.

| Programme | Conseiller | Essais corrects / essais | Speedup sur entrées de recherche | Speedup sur entrées réservées |
|---|---|---:|---:|---:|
| GEMM CPU | désactivé | 51 / 51 | 71,14× | 36,36× |
| GEMM CPU | activé | 58 / 58 | Non livré | Non livré |
| Black–Scholes | activé | 80 / 81 | 13,21× | 14,32× |
| Black–Scholes | désactivé | 61 / 61 | 4,59× | 4,74× |

Les trois programmes livrés passent les vérifications de correction sur les
deux distributions. Ces speedups sont remesurés séquentiellement sur ROMEO,
par rapport au programme naïf correspondant. Les répétitions de chronométrage
ne sont pas des répétitions indépendantes de recherche.

TabPFN n'a effectué **aucune prédiction ni modification de parent** dans les
deux conditions activées. Les 26 prévalidations refusées sur GEMM et les 33 sur
Black–Scholes ont toutes pour motif `insufficient_independent_parent_context`.
L'ensemble de leurs données comporte respectivement 12 et 16 sources parentes
distinctes, mais le découpage chronologique sans parent commun, dans chaque
arbre, n'offre pas assez de groupes indépendants. Le surcoût total enregistré
du conseiller est respectivement de 2,55 et 4,12 secondes. Le meilleur résultat
Black–Scholes ne peut donc pas être attribué à des décisions de TabPFN.

[Résultats détaillés](results/RAPPORT.md) · [CSV des recherches](results/arms.csv)
· [Données brutes](results/analysis.json) · [Codes livrés inchangés](delivered-codes/manifest.json).

Le [CSV par configuration](results/configuration-timings.csv) détaille les deux
tailles et les deux nombres de threads (1 et 4) de chaque distribution. Ses
24 lignes reposent sur 120 chronométrages appariés par graine et SHA256 des
entrées ; les [preuves](results/configuration-timing-evidence.json) conservent
les chemins et empreintes des journaux. Ces rapports sont des analyses après
l'essai : ils ne changent ni le code livré ni la sélection.

La colonne `preflight_reason` du CSV original `results/adviser-decisions.csv`
est vide à cause d'une mauvaise clé dans l'exporteur de cette campagne. Le motif
existe dans `analysis.json`, dans `payload.validation.reason`. L'export
complémentaire [adviser-preflight.csv](results/adviser-preflight.csv) restitue
cette preuve sans remplacer les données originales ni modifier les recherches.

`protocol.json`, `assigned-arms.json`, `prepared.json` et `submission.json` conservent les empreintes, configurations et reçus de lancement. Le contrat actif est `hpc-forest-active-v3-citation-identities`. Les scripts de reprise sont dans `reproduction/prepare_quality_retry.py` ; les essais précédents restent intacts.
