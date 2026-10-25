# Parcours autonome de l'application

Preuves du 25 octobre 2026. Le
[rapport de validation](../../docs/VALIDATION-APPLICATION-AUTONOME-20261025.md)
décrit les trois jobs et les limites de ce test.

- `input/` : dossier déposé dans l'interface, avec les 16 cas de correction.
- `projet-confirme.zip` : archive téléchargée dans l'application puis
  recompilée et vérifiée dans le job ROMEO 784097.
- `verification-livraison.json` : empreinte de l'archive et mesure confirmée.
- `execution.json` : résumé des jobs, modèles et reprise du suivi.
- `validation.json` et `validation-locale.txt` : suite initiale, corrections et
  relances ciblées, distinctes des trois exécutions réelles sur ROMEO.
- `mesures.csv` : essais téléchargés dans l'application ; les temps de recherche
  ne remplacent pas la mesure de confirmation dans `verification-livraison.json`.
- `rapport-original.md` : rapport initial téléchargé, conservé tel quel. Sa
  dernière phrase héritée du moteur affirme à tort que les cas de correction
  sont différents : ce projet réexécute la même suite fournie. `rapport.md`
  corrige cette description sans changer les résultats.
- `correction-rapport.json` : empreintes avant/après de cette correction et
  vérification que le registre de mesures n'a pas changé.

Le protocole et les tests restent fixes. Les temps comparent référence et
candidat sur le même nœud CPU, avec les mêmes arguments. Ce cas synthétique
vérifie le parcours applicatif et ne remplace pas les campagnes historiques.

Reproduire après import :

```text
Compilation : g++ -O2 -std=c++17 main.cpp -o program
Tests       : python3 tests/check.py ./program
Mesure      : ./program 20000
Modifiable  : main.cpp
Modèle      : gpt-6-luna
Effort      : max
Cible       : CPU
Durée       : 10 minutes
```
