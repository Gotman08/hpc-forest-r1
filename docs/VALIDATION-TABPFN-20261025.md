# Validation TabPFN — 25 octobre 2026

Le [conseiller](TABPFN-ADVISOR.md) est intégré au contrôleur Forest existant.
Les huit recherches comparatives sont terminées : sept livraisons confirmées et
un échec Mother conservé. Aucun gain prédictif n'est établi : les quatre essais
activés n'ont rencontré aucune opportunité d'appel TabPFN. Voir le
[rapport complet et les CSV](../experiments/tabpfn-advisor-20261025/RAPPORT.md).

## Vérifications du code

| Vérification | Résultat |
| --- | --- |
| Suite Python complète après protection du verrou, job 784235 | **1 057 réussites, 2 tests ignorés, aucun échec**, 268,36 s |
| Suite Python complète sur ROMEO avant ajout du verrou partagé, job 784214 | **1 052 réussites, 2 tests ignorés, aucun échec**, 192,25 s |
| Première validation ciblée Linux, job 784210 | 38 réussites, 8,76 s |
| Parcours locaux : conseiller, boucles indépendante et active, application | 56 réussites, 148,03 s |
| Relance locale après protection du verrou de mesure, conseiller et application | 55 réussites, 27,56 s |
| Tests du heartbeat après correction de la synchronisation du test | 18 réussites, 11,95 s |
| Interface JavaScript | 9 réussites |
| Comptabilité de la comparaison et sélection chronologique du diagnostic | 8 réussites, 0,30 s |
| Ruff sur `src`, `tests` et les scripts de reproduction | Réussi |

Les deux tests ignorés sur Linux concernent les chemins longs de Git sous Windows
et le sampler optionnel AB-MCTS-M, dont les dépendances ne sont pas installées.
Le conseiller conserve AB-MCTS-A ; cette option n'est pas utilisée dans la comparaison.

Les tests déterministes remplacent les réponses hébergées par des fixtures explicites.
Ils vérifient les budgets, le repli sans modèle, la séparation des prédictions et
des scores, l'absence de données futures, la validation chronologique, les erreurs,
l'exclusion des échantillons non mesurés, le verrou des mesures, l'identité Luna,
la file sans barrière, les analystes, la clôture et la confirmation.

Une première passe Windows a été invalidée par des modifications du moteur pendant
son exécution : la protection d'identité de Forest a correctement refusé le mélange.
Les relances valides utilisent des sources figées. La première suite Linux complète
a révélé une course dans un test existant de heartbeat : un seul tour de boucle
asynchrone n'assurait pas la publication du fichier. Le test attend maintenant une
preuve de publication, sans modifier le comportement du worker ni les validations
des programmes. La suite Linux finale a été relancée entièrement.

L'audit des empreintes a ensuite identifié que le verrou partagé n'était pas dans
la photographie du job 784214. Les campagnes utilisent bien ce verrou, testé
localement. Une nouvelle suite complète, job 784233, a rencontré un disque `/tmp`
plein sur `romeo-c040` (erreur SQLite puis impossibilité de créer les fixtures).
Le job 784235 a validé exactement le moteur Python des campagnes avec des dossiers
temporaires neufs sur scratch : 1 057 réussites et aucun échec. Les erreurs de stockage et leurs preuves sont
conservées ; aucun résultat de la passe en erreur n'est présenté comme une validation.

Les rapports JUnit et les prétests sont dans
[`evidence/tabpfn-integration-20261025/`](../evidence/tabpfn-integration-20261025/).
Les comptes des différentes passes ne s'additionnent pas : certains tests ont été
relancés plusieurs fois. Les quatre comparaisons utilisent les mêmes 115 fichiers
de moteur figés ; les 89 sources Python correspondent à la suite complète finale.
Seul le libellé de l'interface signalant l'absence d'avis a changé ensuite, avec une
relance des neuf tests JavaScript. L'audit est dans `pair-engine-audit.json`.

## Véritable TabPFN sur ROMEO

Le premier essai, job 784207, a confirmé l'installation mais a échoué avant
chargement des poids avec `TabPFNLicenseError`. L'utilisateur a ensuite accepté la
licence Prior Labs et validé la connexion officielle. Le callback a été transmis
directement au nœud ROMEO par un tunnel SSH temporaire. La clé n'est jamais passée
dans la conversation ni dans le dépôt ; son cache reste privé sur le compte ROMEO.
Le tunnel a été fermé après la connexion.

Le job **784215** a vérifié l'acceptation de licence, téléchargé les poids officiels
et exécuté une vraie régression TabPFN-3.5 sur CPU : 16 exemples synthétiques,
26 caractéristiques, quatre estimateurs, prédictions finies. Chargement initial,
ajustement du contexte et prédiction : **5,749 s**, hors attente de connexion.
Ce test fonctionnel ne mesure pas une amélioration de Forest ni une précision
hors échantillon sur les programmes.

Le job **784231** a ensuite exécuté le worker réellement utilisé par Forest,
avec vérification des poids, validation chronologique, second ajustement et
prédictions : **6,332 s** pour le sous-processus complet, sous le plafond de 20 s.
Les 32 exemples de ce test sont explicitement synthétiques ; sa précision de
classement n'est pas une mesure de qualité sur les programmes. La preuve et les
requête/réponse sont dans `evidence/tabpfn-integration-20261025/real-worker-probe/`.

- Python 3.11.9, `tabpfn==9.2.0`, `torch==2.9.1+cpu`, nœud `romeo-c040`.
- Poids : `tabpfn-v3.5-20260909.safetensors`, 876 027 932 octets.
- SHA-256 : `ece4d67eadfea42eb0e610df5189bea60cb7f31073d81e9c7a019b76eacf0be3`.
- Poids figés ; aucun entraînement de Luna ni de ces poids pendant Forest.
- L'OAuth OpenAI sur ROMEO reste celui de Luna Max, distinct de Prior Labs.

## Comparaison des recherches

Le [protocole](../experiments/tabpfn-advisor-20261025/README.md) conserve les codes
et entrées historiques d'UTF-8 et Mandelbrot, avec deux répétitions et un ordre
inversé. Les jobs 784219, 784220, 784221 et 784222 ont été arrêtés au précontrôle,
avant génération : le script omettait `deadline=None` du constructeur de l'évaluateur.
Ce raccordement est corrigé dans les jobs **784224, 784228, 784229, 784230** :
les quatre précontrôles compilent, vérifient et mesurent correctement le naïf.
Les recherches et leurs remesures sont terminées. Une remesure supplémentaire de
tous les codes livrés, job 784264, a été faite après leur arrêt, sur `romeo-c021`.
L'audit des 70 mesures détaillées confirme les empreintes d'entrée et affinités du
fil principal identiques entre candidats comparables. Aucune suggestion
algorithmique de l'opérateur n'a été ajoutée aux programmes ou aux prompts.

Les essais activés ont collecté respectivement 17, 9, 15 et 23 codes corrects
distincts, pour 0,535 s de collecte au total, mais zéro appel et zéro changement
d'ordre prédit. Leur point d'intervention n'a pas été sollicité. Les différences
de speedup observées ne prouvent donc pas un effet d'apprentissage de TabPFN.

Le job 784265 a effectué trois appels réels supplémentaires sur des exemples
de ces campagnes, avec cibles masquées et contexte strictement antérieur.
Deux classements sont corrects, un incorrect ; un quatrième cas manque de contexte.
Les appels prennent 11,285 s, 5,475 s et 5,675 s. Le pic mémoire du job est 2 079,8 Mo.
Ce diagnostic rétrospectif n'a modifié aucune recherche et ne démontre aucun gain
en ligne. Ses preuves sont dans `results/evidence/offline-diagnostic/` de l'étude.

Deux incidents UTF-8 sont documentés : un candidat bouclant sur un octet est
classé infrastructure par le validateur historique, et un autre essai échoue
après une réponse Mother incomplète (`max_output_tokens`). Ce second bras n'a
aucun speedup final déclaré. Deux rapports d'analyste Mandelbrot invalides sont
également conservés ; ils ne sont pas comptés comme analyses réussies.

Le réglage par défaut de Forest reste sans conseiller ; son activation est
explicite. Le redémarrage automatique de l'application locale a
été refusé par le contrôle d'approbation, sans motif détaillé ; l'ancien serveur
est resté en place et devra être redémarré pour charger le nouveau backend.
