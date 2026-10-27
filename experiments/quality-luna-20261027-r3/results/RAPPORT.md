# Étude contrôlée Forest / TabPFN

Recherches attribuées : 4 ; livrées : 4 ; erreurs d'audit : 0.

Luna Max pour tous les rôles LLM. Un plan initial commun par problème, conversations indépendantes.

| Problème | Contraste | Entrées | Paires valides | Ratio géométrique | Minimum–maximum |
|---|---|---|---:|---:|---:|
| blackscholes | corrected/off | registered | 1/1 | 0.928 | 0.928–0.928 |
| blackscholes | corrected/off | reserved | 1/1 | 0.930 | 0.930–0.930 |
| gemm_cpu | corrected/off | registered | 1/1 | 0.298 | 0.298–0.298 |
| gemm_cpu | corrected/off | reserved | 1/1 | 0.331 | 0.331–0.331 |

Un ratio supérieur à 1 favorise la condition située à gauche du contraste.

Les ratios ne remplacent pas les taux de livraison. Les écarts doivent être lus avec la dispersion des temps,
les erreurs d’infrastructure et les décisions de Mother. Ce tableau automatique ne suffit pas à attribuer
une régression à un composant ; les journaux et chronologies sont conservés pour cette analyse.
