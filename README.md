# Forest

Forest optimise des programmes C, C++ et CUDA à partir d'essais compilés,
testés et mesurés. Mother prépare les pistes, les arbres utilisent la vraie
politique TreeQuest AB-MCTS-A, les analystes examinent les preuves, puis les
combinaisons sont évaluées et le résultat confirmé indépendamment.

Le modèle par défaut reste **GPT-6 Luna, effort max**, pour tous les rôles,
sans mélange activé. Un changement de cible, compilateur ou protocole exige
une nouvelle campagne. Aucun gain n'est garanti.

La version **0.2.0** retire le conseiller TabPFN. Les anciennes campagnes,
leurs résultats et le code du conseiller restent archivés et consultables.
La mémoire de preuves, Mother, les analystes et l'archive de programmes mesurés
restent dans le produit. Un ancien contrat n'est jamais converti à l'ouverture.

## Installer et ouvrir

Application personnelle locale ; exécution autorisée sur le compte ROMEO de
l'utilisateur. Python 3.11 minimum ; profil Windows Python 3.13 vérifié dans
les reçus de livraison. Dans un environnement virtuel neuf :

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-windows-py313.lock
.venv/Scripts/python -m pip install --no-deps .
.venv/Scripts/python -m hpc_forest.webapp
```

Ouvrir [l'application locale](http://127.0.0.1:8767). Le stockage par défaut est
`~/.hpc-forest/application`. La configuration ROMEO utilise des chemins et un
profil OAuth privé ; aucun jeton ne doit être placé dans le dépôt.
Voir [le parcours utilisateur](docs/APPLICATION.md) et [l'installation d'une wheel](docs/DISTRIBUTION.md).

## Préserver et reprendre

Une préparation ne peut créer qu'une mission. Une réponse de soumission perdue
déclenche une réconciliation du job existant. « Arrêter et confirmer » ferme
les admissions et laisse terminer les essais engagés avant la confirmation.
Fermer l'application n'arrête pas un job ROMEO ; le suivi reprend au démarrage.
Une restauration met les missions inachevées en attente de réconciliation.

```powershell
# Arrêter le serveur local avant la sauvegarde.
python -m hpc_forest.maintenance backup CHEMIN_APPLICATION NOUVELLE_SAUVEGARDE
python -m hpc_forest.maintenance verify-backup NOUVELLE_SAUVEGARDE
python -m hpc_forest.maintenance restore NOUVELLE_SAUVEGARDE NOUVEAU_STOCKAGE
```

Voir les [notes de migration et limites de reprise](docs/MIGRATION-0.2.md).
Les campagnes externes enregistrées dans l'application doivent aussi être
sauvegardées : la copie les répertorie mais n'en devient pas propriétaire.

## Développer

| Dossier | Responsabilité |
|---|---|
| `src/hpc_forest/search/` | Politique TreeQuest et transactions ask/tell |
| `src/hpc_forest/memory/` | Contrats, stockage et lecture des preuves |
| `src/hpc_forest/storage/` | Écritures atomiques, sauvegardes et restauration |
| `src/hpc_forest/webapp/` | Application, import, contrats, missions et ROMEO |
| `src/hpc_forest/support/` | Validation, sources bornées et budgets partagés |
| `src/hpc_forest/*.py` | Contrôleur, orchestration, évaluateur et adaptateurs |
| `tests/`, `tools/` | Régressions, vérification et fabrication |
| `docs/` | Utilisation, architecture, maintenance et décisions |
| `experiments/`, `evidence/` | Sources figées, résultats et reçus historiques |
| `artifacts/`, `work/` | Sorties locales conservées, hors distribution |

Les frontières et invariants sont décrits dans [ARCHITECTURE.md](docs/ARCHITECTURE.md).
Les sources historiques ne sont pas des instructions pour le contrôleur.

```powershell
python -m pip install -e ".[web,dev]"
python -m pytest
python -m ruff check src tests
node --test tests/test_web_frontend.mjs
python tools/check.py
python tools/build_release.py artifacts/release-NOUVEAU
```

Les tests locaux n'appellent aucun modèle hébergé et n'allouent aucun job HPC.
Les compilations nécessitent GCC/G++. Les contrôles intégrés vérifient que le
code est resté figé et enregistrent ses empreintes.

## Preuves et limites

Le [rapport de stabilisation 0.2](docs/VALIDATION-STABILISATION-20261028.md)
décrit les tests, l'installation isolée, les sauvegardes et leurs limites.

Le [rapport des huit recherches du 27 octobre](experiments/exploration-luna-20261027/RESULTATS.md)
conserve les résultats ROMEO et leurs limites. Ces mesures concernent leur
moteur figé, pas automatiquement la version 0.2.0. Les historiques antérieurs
restent indexés dans le [README archivé](docs/reference/README-0.1-20261028.md).

Forest exécute du code avec les droits du compte de calcul. Il ne fournit pas
un bac à sable contre du code hostile et ne doit pas être exposé comme service
multi-utilisateur. Voir [SECURITY.md](docs/SECURITY.md).

La distribution technique n'établit pas les droits commerciaux sur les codes
importés, sujets de concours, dépendances ou services. Voir les
[notices et points restant à vérifier](docs/THIRD-PARTY-NOTICES.md).
