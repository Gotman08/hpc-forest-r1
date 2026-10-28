# Application — exécution autonome sur ROMEO

Le parcours **dépôt → lancement ROMEO → confirmation → téléchargement** est raccordé.
L'interface classique à cinq écrans conserve les arbres à la craie. Le produit
et son moteur portent le nom Forest.

Le thème sombre est activé par défaut. Le bouton **Mode clair / Mode sombre**
en haut à droite change l’apparence sans interrompre une saisie. Le choix est
mémorisé dans le navigateur et conservé lors des prochaines ouvertures.
La palette sombre utilise des fonds anthracite, des textes blanc cassé et des
accents bleus et verts. Les arbres conservent leur tableau noir dans les deux
thèmes, avec des durées claires sur des étiquettes noires.
L’en-tête garde uniquement ce bouton ; le modèle et la cible restent visibles
dans le contrat et les détails de mission.

Le contrôleur et le client Codex authentifié par OAuth tournent dans l'allocation
SLURM. L'inférence reste hébergée par OpenAI : les poids ne sont pas installés sur
ROMEO. Après soumission, le PC affiche le suivi sans relayer les appels au modèle.

## Démarrer

Python 3.11 ou plus récent, dans un environnement virtuel :

```powershell
python -m pip install -e ".[web]"
python -m hpc_forest.webapp --data "C:/mes-donnees/forest-app" --port 8767
```

Ouvrir http://127.0.0.1:8767. La commande `hpc-forest-app` et le script
`scripts/start-application.ps1` sont équivalents. Le serveur écoute seulement
sur l'interface locale. Ctrl+C l'arrête sans supprimer les projets ni interrompre
les jobs déjà soumis. Aucune compilation JavaScript n'est nécessaire.

L'option répétable `--campaign C:/campagnes/existante` inscrit un dossier contenant
`registry.sqlite3` en lecture seule. Les inscriptions persistent au redémarrage.

## Parcours

1. **Projet** : déposer fichier, dossier ou ZIP ; joindre spécifications et données.
   L'original et ses empreintes sont conservés. La détection CMake/Make propose
   des commandes sans utiliser le LLM.
2. **Préparation** : renseigner compilation, tests, commande mesurée, résultat
   attendu, périmètre modifiable, cible, durée, modèle et effort. « Contrat prêt »
   indique un formulaire complet, pas des tests déjà réussis. Préparer fige les
   entrées ; **Lancer sur ROMEO** soumet le job.
3. **Mission** : suivre job, nœud, synchronisation, arbres, variantes, sources et
   mesures. Les combinaisons sont mesurées séparément. Analystes et décisions
   affichent uniquement les preuves reçues. Les durées disposent de leur propre
   espace dans les arbres ; les graphes larges se parcourent par défilement.
4. **Résultats** : temps confirmés, projet retenu, rapport et CSV. Le code devient
   téléchargeable après confirmation indépendante et finalisation. L'absence
   de gain est affichée explicitement. Deux graphiques comparent les temps
   confirmés et présentent les essais corrects, incorrects et sans verdict.
   Une comparaison non confirmée reste vide et un aperçu tronqué est signalé.
5. **Historique** : retrouver projets, dossiers préparés, missions et campagnes
   existantes, avec leurs états respectifs. La pagination propose 10, 25 ou
   50 entrées par page ; la recherche et les filtres reviennent à la première page.

## Modèles et efforts

Le défaut reste **GPT-6 Luna · max**.

| Modèle | Efforts |
|---|---|
| GPT-6 Luna | low, medium, high, xhigh, max |
| GPT-6.1 Sol | low, medium, high, xhigh, max, ultra |
| GPT-6 Astra | low, medium, high, xhigh, max, ultra |

Ce catalogue correspond au client Codex de ROMEO vérifié le 25 octobre 2026.
Le choix s'applique à Mother, aux générateurs, aux analystes et aux intégrations.
Il reste figé dans la mission. Le changer nécessite une nouvelle préparation.
Les campagnes historiques conservent leur modèle réel.

## Configuration ROMEO

Créer `romeo.json` dans le stockage de l'application à partir de
[romeo.example.json](romeo.example.json). Il désigne le connecteur MCP existant,
le répertoire de travail, le profil OAuth privé et les exécutables distants.
Il ne contient aucun jeton OAuth.

Les runtimes doivent déjà contenir les dépendances du moteur et le client Codex
pour l'architecture cible. Installer et compiler sur les nœuds de calcul, jamais
sur le login. La CLI officielle vérifie la connexion ChatGPT au démarrage du job ;
les identifiants restent dans le profil privé distant.

Le profil validé est **CPU x86_64, GCC 14.2.0**, deux cœurs et 8 Gio : un cœur
pour le contrôleur et les programmes, l'autre pour le client du modèle. Les
mesures utilisent un cœur et une thread OpenMP/BLAS. Les attentes du modèle
expliquent une faible utilisation CPU de l'allocation.

Le GPU exige un profil ARM compatible, avec Python, Codex et CUDA.
**Le parcours GPU n'a pas été validé par cette livraison.** Sans profil,
l'option reste désactivée ; un runtime x86_64 ne fonctionne pas sur GPU ARM.

La durée choisie est le budget Forest. L'allocation réserve 30 minutes de plus
pour terminer les travaux admis et confirmer. Un superviseur impose une limite
avant la fin de l'allocation. La recherche peut s'arrêter plus tôt selon sa
politique de réserve. Aucun gain ni nombre d'essais n'est garanti. Les tokens
sont comptabilisés, sans plafond monétaire implémenté par l'application.

## Contrat du projet

Cette version accepte des sources C/C++/CUDA et des commandes explicites de
compilation, vérification et mesure. La commande mesurée commence par le chemin
relatif de l'exécutable ELF produit, par exemple `./program 20000`.
Un noyau CUDA isolé doit avoir un programme hôte et des tests.

Les commandes tournent dans une copie du projet avec les modifications autorisées
superposées. Les tests et le contrat sont conservés dans le répertoire protégé.
Seuls les fichiers sources existants explicitement autorisés sont modifiables.
Le moteur utilise un préfixe interne `src/` ; l'archive livrée restaure les chemins
initiaux et conserve les tests et autres fichiers du projet.

Les cahiers des charges TXT, Markdown, PDF textuel ou DOCX sont extraits comme
données de conception, avec une limite totale de 60 000 caractères. Un document
illisible n'est pas ignoré silencieusement. Les pièces jointes de test sont
accessibles par leur nom dans `$FOREST_ATTACHMENTS` ; les commandes doivent les
référencer pour qu'elles soient effectivement utilisées.

La correction signifie que la commande de test fournie réussit ; sa couverture
détermine la portée de cette validation. La mesure porte sur la commande de
benchmark complète, shell et démarrage du programme compris, mais exclut le
démarrage de l'adaptateur Python. Ce n'est pas automatiquement le temps d'un
noyau CUDA seul. Référence et candidats partagent le contrat et la machine.

Un projet à plusieurs modules peut conserver ses fichiers de configuration,
ses bibliothèques intégrées et son système de compilation. Les dépendances
externes doivent être disponibles sur la cible ou construites par la commande
prévue ; l'application ne les installe pas automatiquement. Les fichiers
protégés ne sont pas tous transmis au modèle : le contexte source contient
les fichiers du périmètre modifiable. Les interfaces nécessaires à la compréhension
doivent donc être prises en compte explicitement.

Limites actuelles pour les projets complets : l'import ne conserve pas les
droits d'exécution POSIX, les liens sont refusés et la planification de Mother
refuse un contexte source dépassant 128 000 caractères. Un préfixe modifiable
qui contient aussi des fichiers de build doit être remplacé par une sélection
explicite des sources. Le dépôt accepté n'est donc pas une garantie que sa
recherche pourra démarrer. La reconstruction d'un projet importé et son
optimisation autonome sont des étapes distinctes.

## Conservation et reprise

Stockage par défaut : `~/.hpc-forest/application/`.

```text
application.sqlite3                  projets, contrats et suivi
projects/<id>/source/                fichiers initiaux
projects/<id>/attachments/           documents
prepared/<id>/input.zip              entrées figées
missions/<id>/bundle.zip             moteur et entrées figés
missions/<id>/slurm-plan.json        script et ressources exacts
missions/<id>/view-<id>/             preuves reçues et résultat
romeo.json                          chemins de connexion et runtimes
```

Chaque mission possède une mémoire et un répertoire neufs. Aucun contexte d'une
autre recherche ni jeton OAuth n'est copié. Les SHA-256 sont vérifiés à la
préparation, au transfert et sur le nœud. Le moteur distant reste figé si le
dépôt local évolue pendant le calcul.

Le plan SLURM est contrôlé avant soumission. Un index persistant interdit deux
lancements du même dossier. Après une réponse réseau perdue, l'application
recherche le job existant ; elle ne répète pas une soumission à l'aveugle.

Le superviseur exporte une sauvegarde SQLite cohérente et les sources consultables.
Suivi et transferts reprennent au redémarrage du serveur local. Une erreur de
lecture du scheduler ne prouve pas un échec ; un transfert retardé ne devient
pas un succès fictif. Une fois reçus, les livrables restent disponibles localement.

**Limite :** panne du nœud, expiration SLURM/OAuth ou perte du processus distant
n'entraînent pas de nouvelle allocation automatique. L'échec est signalé et
les preuves sont conservées. Cette version assure l'indépendance du PC et
la reprise du suivi, pas une tolérance à toutes les pannes du calculateur.

Import : 2 000 fichiers, 64 Mio transférés, 256 Mio décompressés, 32 Mio par fichier.
Liens, traversées et collisions sont refusés ; métadonnées Git et caches ignorés.
Les commandes ne s'exécutent que dans le job après lancement, jamais à l'import.
Les brouillons non enregistrés restent dans l'onglet ; les contrats sauvegardés
survivent au redémarrage.

Les registres sont consultés en lecture seule, sans désérialiser les checkpoints
TreeQuest. Affichage limité à 3 000 essais, 100 événements et 1 000 évaluations ;
sources : 200 fichiers de 256 Kio par variante. Au-delà de 3 000 essais, le CSV
est désactivé pour éviter de présenter un export partiel comme complet.

L'application personnelle contrôle l'hôte, l'origine des écritures et les tailles
des requêtes. Elle n'est pas conçue pour l'exposition publique ou plusieurs utilisateurs.

## Vérifier

Les contrôles ci-dessous utilisent les fixtures du produit. Les reçus et
anciens calculs restent dans les archives locales de leur propriétaire.

```powershell
python -m pip install -e ".[web,dev]" httpx
python -m pytest
python -m ruff check src tests
node --test tests/test_web_frontend.mjs
python -m build --wheel
```

Les tests locaux utilisent des connecteurs simulés, sans allocation ni modèle.
Les exécutions réelles et leurs identifiants sont documentés séparément.

## Arrêter, sauvegarder et restaurer

« Arrêter et confirmer » annule une mission encore non soumise. Après soumission,
le moteur 0.2 ferme les admissions, termine les essais engagés puis effectue la
confirmation. Une demande et sa transmission sont conservées séparément ; une
réponse réseau perdue n'autorise ni une nouvelle mission ni une resoumission.
Les anciens moteurs figés restent inchangés et ne prennent pas en charge cette
commande. « Reprendre le suivi » réconcilie un job connu, sans nouvelle allocation.

Une seule instance peut utiliser un stockage donné. Arrêter le serveur local
avant une sauvegarde. La commande de maintenance vérifie SQLite et les fichiers,
puis restaure uniquement vers un répertoire neuf. Les missions inachevées passent
en attente de réconciliation. Les campagnes externes sont répertoriées et doivent
être sauvegardées séparément. Voir [MIGRATION-0.2.md](MIGRATION-0.2.md).

Les contrats contenant l'ancien conseiller sont consultables mais refusés pour
un nouveau lancement. L'interface propose une copie migrée du projet, en laissant
les sources et contrats historiques intacts. Le défaut reste Luna Max.

Suites possibles : profil GPU ARM, reprise distante après panne du nœud et
limites de coût. La stabilisation n'ajoute pas de nouvelle mesure de performance
ROMEO et ne valide pas un service pour plusieurs utilisateurs.

