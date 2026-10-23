# Lanceur CUDA courant

`prepare_memory.py` prépare le nouveau scope `cuda-nbody-luna-max-memory-v1` avec
le moteur courant, le source original et le harnais mémoire actif. Il ne soumet
aucun job. Mother choisit N ; ce nombre n'est pas fixé dans le profil.
Les nouvelles préparations autorisent deux tours de critique du plan, déduits
du budget de la campagne. `--plan-review-calls 0` désactive cette critique pour
une comparaison explicite ; les payloads déjà préparés restent inchangés.

```powershell
python examples/cuda_nbody/prepare_memory.py --source C:/chemin/nbody_naive.cu --output C:/chemin/nouvelle-campagne --wall-seconds 1800
```

Le dossier de sortie doit être nouveau. `preparation.json` contient les
empreintes, le dossier distant unique, les ressources proposées et la commande
de lancement. Le vérificateur `protocol.py` est repris à l'identique du protocole
archivé le 21 octobre ; ses tests ne sont pas assouplis. L'extraction du kernel
supprime le host `main` et ajoute uniquement le lien `extern "C"` ; aucune
optimisation écrite par l'opérateur n'est injectée.

Après autorisation explicite de l'allocation et soumission de ce payload, le
relais `relay_memory.py` utilise `gpt-6-luna`, effort `max`, uniquement pour la
session, le job, le plan et le payload indiqués dans son reçu d'autorisation.
Il ne réutilise aucune ancienne session. Le modèle accède aux références
documentaires, aux lectures mémoire transmises par le contrôleur et à la
production structurée du code ; le contrôleur conserve les mesures GPU.
Le pilote vérifie les intégrations, la même conversation Mother et la
confirmation de G final avant d'annoncer la campagne complète.

Voir [le contrat mémoire](../../docs/MEMOIRE.md) pour les réglages et les limites.

`pilot.py` est le pilote du prochain payload CUDA, pour le scope
`cuda-nbody-luna-max-independent-v2`. Il utilise le moteur courant, appelle
`Controller.run()` sans checkpoint par vague et lit la durée dans le plan.
`cuda_evaluator.py` conserve le contrat de mesure CUDA N-corps historique :
événements CUDA, moyenne géométrique des trois tailles, trois répétitions de
recherche et cinq confirmations dans la configuration du payload.

Cette source est destinée à une **nouvelle préparation** avec un nouvel
identifiant de session, un nouveau dossier distant et de nouvelles empreintes.
Elle ne lance rien à la lecture ou à l'import. L'exécution reste réservée à une
allocation ROMEO explicitement autorisée et au relais Luna Max associé.

Le payload doit contenir `plan.json`, `settings.json`, `runtime-manifest.json`,
les sources originales importées dans `source/`, la validation protégée et
le moteur courant dans `project/src/`. Le plan déclare `wall_seconds`, le
nouveau scope et l'identité du modèle. La préparation et le préflight GPU
restent séparés du timer de recherche. Aucun ancien candidat optimisé ne doit
être importé pour résoudre le problème à la place des modèles.

Le contrat [d'export CUDA](../../docs/EXPORT-CUDA.md) est reconnu et figé lors
de l'import du kernel et de `src/launch.json`. Le pilote exige toujours la
fusion avec la même Mother, les reçus de toutes les paires et la confirmation
indépendante de G final avant d'annoncer `pipeline_complete=true`.

Les scripts et payloads de `experiments/cuda-nbody-20261021/` restent des
preuves historiques immuables. Ils ne sont pas remplacés par ce pilote.
