# Étude contrôlée Forest / TabPFN

Recherches attribuées : 8 ; livrées : 8 ; erreurs d'audit : 0.

Luna Max pour tous les rôles LLM. Un plan initial commun par problème, conversations indépendantes.

| Problème | Contraste | Entrées | Paires valides | Ratio géométrique | Minimum–maximum |
|---|---|---|---:|---:|---:|
| blackscholes | corrected/off | registered | 2/2 | 0.539 | 0.239–1.217 |
| blackscholes | corrected/off | reserved | 2/2 | 0.529 | 0.231–1.213 |
| gemm_cpu | corrected/off | registered | 2/2 | 0.634 | 0.530–0.757 |
| gemm_cpu | corrected/off | reserved | 2/2 | 0.707 | 0.638–0.784 |

Un ratio supérieur à 1 favorise la condition située à gauche du contraste.

Les ratios ne remplacent pas les taux de livraison. Les écarts doivent être lus avec la dispersion des temps,
les erreurs d’infrastructure et les décisions de Mother. Ce tableau automatique ne suffit pas à attribuer
une régression à un composant ; les journaux et chronologies sont conservés pour cette analyse.
