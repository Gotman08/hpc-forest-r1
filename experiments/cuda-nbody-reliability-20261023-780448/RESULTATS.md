# Test réel de 30 minutes — Luna Max — 780448

**Le programme final est correct et confirmé, mais le lancement est perturbé par une panne de transport. Il ne démontre pas une amélioration de la performance ou de la régularité du système.**

Le job a utilisé un GH200 ARM, quatre CPU et 16 Go sur ROMEO le 23 octobre 2026, de 05:01:40 à 05:26:02, heure de Paris. La cible du contrôleur était de 30 minutes. Le temps effectif de campagne est de **23 min 23 s**, dont **13 min 18 s avant la clôture de recherche**. Le temps alloué effectivement consommé est de 24 min 22 s, préparation comprise. Il reste donc **6 min 37 s de cible inutilisées** ; la cause de clôture est `infrastructure_error`, pas un refus d'admission budgétaire.

## Résultat confirmé

| Programme | Moyenne confirmée (ms) |
|---|---:|
| Original de cette campagne | 1,852645 |
| Meilleur arbre retenu pour confirmation | 1,043852 |
| G final, également meilleur confirmé | **1,009931** |

G final est **1,8344× plus rapide que l'original**. Les trois programmes ont cinq échantillons frais chacun. Le calcul reprend les temps d'événements CUDA des tailles 4096, 8192 et 16384 : moyenne géométrique par échantillon, puis moyenne des cinq échantillons. Les 21 fichiers de construction, correction et mesure de confirmation ont été transférés individuellement avec vérification d'empreinte ; leurs résultats ont été recalculés localement. La correction conserve 11 cas, les masses exactes et le protocole GPU/oracle CPU antérieur.

Le commit confirmé est `bf84c9ea310475793e0958952105462e04354640`. Les deux fichiers exportés ont été comparés octet pour octet à ce commit. `git fsck --full` termine sans corruption ; deux arbres non référencés sont signalés. L'export contient le kernel device et son contrat de lancement, pour le harnais existant ; l'original utilisateur est conservé dans `input/`.

## Recherche et assemblage

Mother a choisi **N=3**. Ce choix provient du modèle, pas du lanceur. Les trois sujets ont été examinés pendant un appel de critique de **85,88 s**, après la planification initiale de **126,19 s**. Ces deux durées font partie des 30 minutes.

| Arbre | Essais admis | Valides mesurés | Incorrects | Erreurs d'infrastructure | Meilleur temps de recherche (ms) |
|---|---:|---:|---:|---:|---:|
| T1 | 3 | 2 | 0 | 1 | 1,037837 |
| T2 | 2 | 0 | 1 | 1 | — |
| T3 | 3 | 2 | 0 | 1 | 2,751189 |

Les scores des trois erreurs d'infrastructure sont absents. L'essai incorrect a un score nul. Les variantes lentes restent disponibles. Aucun nouvel essai de recherche n'a été créé après la clôture.

Les **19 appels natifs** enregistrés demandent tous `gpt-6-luna`, effort `max` : une planification, une critique, dix appels de code des arbres (dont les étapes internes et les réponses tardives), cinq décisions de sélection et deux générations d'intégration. Le nombre d'appels ne doit donc pas être confondu avec les huit essais de recherche admis.

Les cinq décisions de Mother sont acceptées : `read`, `read`, `integrate`, `integrate`, `finish`. Les consultations du premier tour restent utilisables au second. La même conversation relie planification, critique et assemblage. La première intégration modifie le kernel et le lancement, mais est plus lente que son programme de base. La seconde repart du meilleur arbre et modifie seulement `launch.json` ; c'est elle qui devient G final. La confirmation préserve la possibilité de retenir le meilleur arbre si la combinaison régresse.

## Incident et portée de la validation

Le relais s'est arrêté après trois échecs de téléchargement de `forest-plan.json`. Le contrôleur a ensuite cessé de recevoir les signes de vie et a classé trois essais admis comme erreurs d'infrastructure. Cette erreur ferme la recherche, même lorsqu'il reste du temps. Le détail réseau initial n'est pas conservé par le message d'erreur du relais : on ne peut pas attribuer la panne à une cause précise du serveur.

Le relais a été reconnecté avec le même programme, le même reçu, la même session et les réponses déjà enregistrées. L'échéance n'a pas été repoussée et les essais abandonnés n'ont pas été réintroduits dans les scores. Les réponses tardives restent dans les preuves. L'assemblage et la confirmation ont terminé ; `pipeline_complete=true` décrit cette fin de pipeline, **sans annuler `search.status=infrastructure_error`**.

Cinq ensembles de diagnostics n'avaient pas été téléversés à la sortie du relais. Leurs quinze fichiers ont ensuite été copiés avec vérification d'empreinte, sans nouvel appel de modèle ni nouvelle allocation. Le reçu initial et le reçu de récupération sont conservés séparément.

La critique, la mémoire, les consultations et les décisions sont exercées en réel. La fiabilité globale et l'utilisation complète des 30 minutes restent non validées. La robustesse du relais est maintenant un problème observé à traiter : la lecture répétée d'un plan figé peut arrêter le service, et la fin du signal de vie transforme cet incident en clôture de toute la recherche. Les traces justifient ce diagnostic de fonctionnement ; elles ne prouvent pas qu'une campagne sans incident aurait retrouvé la meilleure optimisation.

## Comparaison descriptive avec les campagnes précédentes

| Campagne | Meilleur confirmé (ms) | Accélération / son original | Essais / valides |
|---|---:|---:|---:|
| 776048 — meilleure historique | 0,099877 | 18,58× | 31 / 28 |
| 776290 — précédente | 0,853836 | 2,15× | 27 / 24 |
| **780448 — ce test** | **1,009931** | **1,83×** | **8 / 4** |

Le nouveau résultat est **10,11× plus lent que la meilleure campagne**, et **18,28 % plus lent que la précédente**. Le source initial, l'énoncé, le protocole, le modèle et la cible matérielle déclarée sont conservés. Le moteur change, N passe de quatre à trois et la panne réduit fortement la recherche. On ne peut pas isoler l'effet des améliorations avec ce seul lancement. Le comparateur strict garde trois groupes distincts et n'annonce aucune régularité à partir de leurs effectifs unitaires.

## Preuves

- `results.json`, `registry.sqlite3`, `confirmation-audit.json` : résultats et recalculs.
- `comparison.json`, `native-audit.json` : comparaison descriptive et identités des appels.
- `transport-incident.json`, `relay.log`, `relay-resume-1.log` : interruption et reconnexion.
- `worker-finished.json`, `diagnostic-recovery.json` : fin du relais et récupération des diagnostics.
- `submission.zip`, `optimized/src/` : sources confirmées et paramètres de lancement.
- `evidence.zip`, `evidence-manifest.json`, reçus de transfert : journaux, sources et empreintes.

La préparation utilise le moteur figé au commit `2ee6125`. Le raccordement du lanceur a passé 24 tests ciblés et Ruff avant lancement. Aucun correctif du moteur ni réglage d'optimisation n'a été injecté pendant la campagne. Les nouveaux fichiers de preuves sont commités localement ; aucun push.
