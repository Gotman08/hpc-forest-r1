# Étude contrôlée Forest / TabPFN

Recherches attribuées : 30 ; livrées : 30 ; erreurs d'audit : 0.

Luna Max pour tous les rôles LLM. Un plan initial commun par problème, conversations indépendantes.

| Problème | Contraste | Entrées | Paires valides | Ratio géométrique | Minimum–maximum |
|---|---|---|---:|---:|---:|
| blackscholes | both/data | registered | 3/3 | 0.696 | 0.492–1.110 |
| blackscholes | both/data | reserved | 3/3 | 0.696 | 0.490–1.106 |
| blackscholes | both/off | registered | 3/3 | 0.493 | 0.403–0.649 |
| blackscholes | both/off | reserved | 3/3 | 0.494 | 0.407–0.647 |
| blackscholes | both/validation | registered | 3/3 | 0.744 | 0.347–1.981 |
| blackscholes | both/validation | reserved | 3/3 | 0.747 | 0.345–2.019 |
| blackscholes | current/off | registered | 3/3 | 0.800 | 0.396–1.348 |
| blackscholes | current/off | reserved | 3/3 | 0.801 | 0.393–1.358 |
| blackscholes | data/current | registered | 3/3 | 0.886 | 0.270–2.354 |
| blackscholes | data/current | reserved | 3/3 | 0.885 | 0.271–2.373 |
| blackscholes | validation/current | registered | 3/3 | 0.829 | 0.585–1.127 |
| blackscholes | validation/current | reserved | 3/3 | 0.825 | 0.576–1.126 |
| gemm_cpu | both/data | registered | 3/3 | 1.053 | 0.957–1.238 |
| gemm_cpu | both/data | reserved | 3/3 | 1.048 | 1.000–1.149 |
| gemm_cpu | both/off | registered | 3/3 | 1.086 | 0.969–1.237 |
| gemm_cpu | both/off | reserved | 3/3 | 1.098 | 1.034–1.225 |
| gemm_cpu | both/validation | registered | 3/3 | 1.102 | 1.012–1.285 |
| gemm_cpu | both/validation | reserved | 3/3 | 1.119 | 1.012–1.253 |
| gemm_cpu | current/off | registered | 3/3 | 1.051 | 0.970–1.211 |
| gemm_cpu | current/off | reserved | 3/3 | 1.121 | 0.855–1.378 |
| gemm_cpu | data/current | registered | 3/3 | 0.981 | 0.826–1.116 |
| gemm_cpu | data/current | reserved | 3/3 | 0.934 | 0.774–1.220 |
| gemm_cpu | validation/current | registered | 3/3 | 0.937 | 0.762–1.069 |
| gemm_cpu | validation/current | reserved | 3/3 | 0.875 | 0.689–1.106 |

Un ratio supérieur à 1 favorise la condition située à gauche du contraste.

Les ratios ne remplacent pas les taux de livraison. Les écarts doivent être lus avec la dispersion des temps,
les erreurs d’infrastructure et les décisions de Mother. Ce tableau automatique ne suffit pas à attribuer
une régression à un composant ; les journaux et chronologies sont conservés pour cette analyse.
