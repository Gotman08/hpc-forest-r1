# Préparer un programme CUDA

Ces scripts illustrent la préparation d’une nouvelle campagne CUDA à partir
de sources fournies par l’utilisateur. Ils contiennent le code de préparation
et de vérification ; les résultats et journaux de calcul restent locaux.

Exemple de préparation, dans un dossier neuf :

```powershell
python examples/cuda_nbody/prepare_memory.py --source C:/chemin/nbody_naive.cu --output C:/chemin/nouvelle-campagne --wall-seconds 1800
```

`preparation.json` décrit les empreintes des entrées, les ressources proposées
et les paramètres du futur lancement. Le modèle et l’effort sont figés dans
cette préparation ; la politique de recherche reste TreeQuest AB-MCTS-A.

La soumission et le relais nécessitent ensuite le compte, le profil et
l’autorisation explicite de l’utilisateur. Les sources, les tests, la cible
et le protocole doivent être définis avant toute mesure. Un changement de
contrat exige une nouvelle campagne.

Le [guide de l’application](../../docs/APPLICATION.md) décrit les prérequis
des profils CPU et GPU. L’[architecture](../../docs/ARCHITECTURE.md) présente
la séparation entre exploration, preuves, intégration et confirmation.
