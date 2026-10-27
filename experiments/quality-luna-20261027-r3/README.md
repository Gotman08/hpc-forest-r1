# Pilote Luna Max après correction de la reprise des admissions

État final : **4 programmes livrés sur 4, corrects sur les entrées prévues et
réservées**. Les recherches et la remesure commune se sont terminées le
27 octobre 2026. Tous les rôles LLM ont utilisé GPT-6 Luna, effort max,
directement sur ROMEO. Les 515 invocations natives ont été vérifiées.

[Rapport final détaillé](RESULTATS.md) · [Comparaison CSV](results/comparison.csv)
· [Temps par configuration](results/configuration-timings.csv).

| Problème | Sans conseiller | Avec conseiller | Entrées réservées, sans / avec |
|---|---:|---:|---:|
| GEMM CPU | 94,60× | 28,18× | 71,85× / 23,76× |
| Black–Scholes | 14,33× | 13,30× | 15,76× / 14,66× |

Les quatre arrêts protègent la confirmation ou respectent le budget, sans
blocage terminal ni fermeture finale anticipée pour convergence. TabPFN n'a
modifié aucun parent : aucun appel sur GEMM et un appel rejeté sur Black–Scholes
car moins bien calibré que la référence parent. Aucun gain du conseiller n'est
démontré par cette paire unique de recherches par problème.

La qualification réelle de TabPFN sur ROMEO a aussi réussi (9,37 secondes).
Ses données synthétiques ne sont pas importées dans les recherches.

| Étape | Job SLURM |
|---|---:|
| Qualification du runtime | 786456 |
| GEMM sans conseiller | 786457 |
| GEMM avec conseiller | 786458 |
| Black–Scholes avec conseiller | 786459 |
| Black–Scholes sans conseiller | 786460 |
| Remesure commune et audits, après les quatre recherches | 786461 |

Le moteur utilise `hpc-forest-active-v4-admission-liveness`. Une combinaison
intermédiaire épuisée ne peut plus être réactivée par `continue` ou `resume`.
Un conseil destiné à un arbre suspendu ne supprime plus sa revue d'inactivité.
Mother reçoit désormais le motif d'indisponibilité de chaque arbre. La limite
des citations d'analyste reste inchangée ; un refus indique maintenant la borne
et le nombre reçu pour permettre une correction dans le budget prévu.

Les [preuves de l'échec précédent](../quality-luna-20261027-r2/diagnostics/gemm-stall.json)
et les essais de cette tentative restent intacts. Les six nouveaux tests comptaient
cinq échecs avant correction et passent ensuite ; 67 tests ciblés ont réussi.
La [validation complète](../../docs/VALIDATION-REPRISE-20261027.md) a réussi :
1 151 tests passent, aucun échec, 3 tests ignorés pour des raisons d'environnement.
Les empreintes des sources et tests sont restées identiques pendant la suite.

Les quatre recherches comparent GEMM CPU et Black–Scholes, avec et sans
conseiller. GPT-6 Luna effort max est utilisé pour tous les rôles LLM. Un seul
Forest est conservé. Les plans initiaux, les entrées, la graine 307, les budgets
de 90 minutes de recherche et de 120 minutes imputées de bout en bout restent
identiques aux précédents. Chaque exécution possède une mémoire et des
conversations neuves. Aucun candidat ni conseil d'optimisation issu des essais
précédents n'est importé.

Les deux conditions ont exactement le même moteur et ne diffèrent que par
l'activation du conseiller. Les candidats livrés ont été remesurés ensemble,
séquentiellement, sur `romeo-c023`, avec les entrées de recherche et les réservées.
Une seule paire par problème ne permet pas d'établir une supériorité statistique.

## Preuves de lancement et incident conservé

Les [reçus de lancement](fresh-launch-receipts.json) confirment Luna Max, un
ensemble de générateurs alternatifs vide, des sessions distinctes et zéro essai,
document ou exemple du conseiller au départ. Les [allocations](allocation-receipts.json)
emploient des ensembles de CPU logiques disjoints sur `romeo-c022` ; cela ne
démontre pas l'équivalence NUMA ni l'absence de charge extérieure.

Les [premiers rapports d'analystes](live-analyst-proof.json) ont été acceptés dans
les quatre recherches. Un analyste Black–Scholes a demandé et cité la partie
manquante d'un fichier au-delà de l'extrait initial. Ces traces attestent la
lecture et la provenance des citations, pas toute la justesse de l'analyse.

Un appel d'analyste Black–Scholes sans conseiller a terminé en
`max_output_tokens` vers 18:17:50 UTC après environ quinze minutes. De nouveaux
appels ont ensuite été observés sans intervention de l'opérateur. Le
[journal de cet incident](diagnostics/blackscholes-off-output-limit.json) est
conservé. Son usage en tokens n'a pas été retourné : il reste marqué inconnu,
sans être imputé artificiellement à zéro. Les temps du programme et les temps
d'attente du modèle restent des mesures distinctes.

[Protocole et empreintes](protocol.json) · [Prévalidation locale](preflight-local.json)
· [Préparation SLURM](prepared.json) · [Script de reproduction](reproduction/prepare_quality_retry_r3.py).
