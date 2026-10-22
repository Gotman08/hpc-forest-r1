# CUDA N-body — Luna Max — arbres indépendants — job 774157

**Le pipeline a terminé, G final est confirmé et les exports sont valides. La durée cible de 30 minutes reste sous-utilisée : exécution réelle 25 min 07 s.**

La campagne neuve utilise le N-body original, un GPU GH200 ARM ROMEO, quatre CPU, TreeQuest 0.3.2 et uniquement AB-MCTS-A. Aucun ancien candidat optimisé n’a été fourni aux modèles. Le plafond de tokens est absent de la recherche, des réparations et de la fusion. Les sources embarquées correspondent aux 97 fichiers couverts par les 686 tests locaux réussis.

| Arbre | Essais admis | Valides mesurés | Profondeur admise / valide | Meilleur en recherche (ms) |
|---|---:|---:|---:|---:|
| T1 | 2 | 1 | 1 / 1 | 1.106310 |
| T2 | 9 | 9 | 3 / 3 | 0.136367 |
| T3 | 7 | 7 | 2 / 2 | 0.962585 |

Total : 18 essais de recherche, 17 programmes valides mesurés, 1 programme incorrect, 0 erreur d’infrastructure. 27 appels natifs Luna Max ont été vérifiés, réparations et Mother comprises.

**Parallélisme et progression indépendante.** Les trois processus natifs ont été observés simultanément. 136 échantillons montrent des arbres à des numéros d’essai différents en génération simultanée. Le premier associe T1 au premier essai et T2 au deuxième essai. Les événements du contrôleur confirment un seul essai non terminé par arbre et la terminaison de tous les essais admis. Les mesures GPU restent exclusives.

**Mother et fusion.** Une seule conversation native, `01a15ff7-fe72-7cf0-8cc1-120f90f5caf6`, relie la planification initiale et toutes les continuations de fusion. Deux étapes de fusion deux par deux ont demandé trois appels natifs, dont une réparation de G final. Aucun nouvel essai de recherche n’a été créé après la clôture. La compaction Codex CLI reste automatique ; aucun événement effectif de compaction n’a été observé sur ce lancement.

| Programme | Temps confirmé, métrique combinée (ms) |
|---|---:|
| Référence originale | 1.847213 |
| Première fusion, retenue par le contrôleur | 0.118800 |
| G final | 0.118861 |

G final est environ **15.54×** plus rapide que la référence. Chaque programme confirmé possède cinq échantillons frais. La métrique est la moyenne des cinq moyennes géométriques des temps d’événements CUDA pour N = 4096, 8192 et 16384. Compilation, transferts et démarrage des processus sont exclus. Le protocole protégé conserve 11 cas de correction par phase, un oracle CPU FP64 et des données différentes en confirmation. Les journaux des trois programmes confirmés ont été rapatriés et recalculés indépendamment.

**Exports.** `exports/G-final-confirme.zip` contient les sources du commit confirmé de G final, `d03b3c48cb44ae96743978e193917906182b009d`, ses paramètres de lancement et son reçu de confirmation. `exports/meilleur-confirme.zip` conserve l’export natif du contrôleur pour le premier G, `5ccc99221db417330f56c5a7e7c16b72a0c8016b`. Les empreintes des fichiers ont été comparées au commit exact et à la proposition native finale ; les objets Git transférés ont passé `git fsck`. Il s’agit du kernel device CUDA et de son contrat de lancement pour le harnais NVRTC, avec le fichier original utilisateur préservé.

**Durée : réserve encore trop prudente.** La recherche s’est clôturée après 21 min 38 s, avec 8 min 22 s restantes. Le contrôleur réservait 7 min 02 s pour la finalisation ; le prochain essai T2 était estimé à 2 min 00 s et a été refusé. La fusion réelle a pris 2 min 45 s, la confirmation 0 min 44 s, et l’archive moins d’une seconde. La durée finale est 25 min 07 s, soit 4 min 53 s inutilisées. Le test valide le parallélisme, la conversation Mother et la confirmation/export de G final ; il ne valide pas une utilisation complète des 30 minutes. Aucune correction du moteur ni relance n’a été faite après observation de ce résultat.

**Skills, documentation et ROMEO.** Les liaisons et contenus des six skills ont été vérifiés pour chaque appel, avec leurs traces déclaratives. Les deux serveurs MCP ont été configurés et observés pour Mother, les trois enfants et la Mother reprise. Treize consultations de documentation ont été observées, neuf par Mother en préparation et quatre par T3. Aucun appel métier au MCP ROMEO n’a été observé : accès disponible et utilisation effective sont distingués dans les audits. Le contrôle additionnel « appels aux deux serveurs observés » est donc négatif ; les 46 autres assertions de l’audit principal passent. Les 12 assertions de fusion et tous les contrôles GPU passent.

Les preuves détaillées sont conservées dans `evidence/`, les audits JSON et `protocol/`. Le bundle Git conserve les programmes et leurs parents de recherche. Aucun commit ni push n’a été exécuté.
