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

Le contrôleur et le client Codex tournent dans l'allocation SLURM. Les modèles
OpenAI utilisent la connexion ChatGPT distante ; DeepSeek utilise la passerelle
dsh-romeo et ses GPU déjà alloués sur ROMEO. Après soumission, le PC affiche le
suivi sans relayer les appels au modèle.

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
| GPT-6.1 Terra | low, medium, high, xhigh, max, ultra |
| GPT-6 Sol | low, medium, high, xhigh, max, ultra |
| GPT-5.6 Sol / Terra | low, medium, high, xhigh, max, ultra |
| GPT-5.6 Luna | low, medium, high, xhigh, max |
| GPT Daybreak Blue | low, medium, high, xhigh, max, ultra |
| DeepSeek V4.1 Flash 1017 · dsh-romeo | none, low, high, max |

Les choix OpenAI suivent le catalogue local Codex consulté le 29 octobre 2026.
La disponibilité réelle est vérifiée dans le profil distant lors du lancement.
Les efforts DeepSeek suivent le [lanceur dsh-romeo](https://github.com/wolf75222/dsh-romeo/blob/main/bin/dsh-romeo) ;
`none` désactive sa réflexion. Les menus proposent les efforts propres au modèle.
Le choix principal s'applique à Mother, aux analystes et aux intégrations.
L'option de mélange permet aussi d'ajouter des générateurs OpenAI et DeepSeek,
chacun avec son effort. Ces choix restent figés dans la mission ; les modifier
nécessite une nouvelle préparation. Les campagnes historiques gardent leur modèle réel.

### dsh-romeo : DeepSeek sur ROMEO

Forest utilise le [fournisseur compatible Codex de dsh-romeo](https://github.com/wolf75222/dsh-romeo/blob/main/docs/clients.md)
via l'API Responses. Les conversations persistantes, sorties structurées,
contrôles et outils autorisés de Forest conservent leur chemin habituel.
Il n'est pas nécessaire d'installer DeepSeek Harness dans le job Forest.
Le modèle servi est `dsh-deepseek-v4.1-flash-1017-1m`.

Sur le serveur ROMEO actuel, imposer un schéma JSON dans l'API peut empêcher
DeepSeek d'appeler les outils MCP. Forest transmet donc le schéma dans les
consignes du modèle et valide chaque réponse localement avec JSON Schema,
y compris les champs obligatoires, types, valeurs autorisées et bornes.
Une réponse invalide n'est pas acceptée comme proposition.

1. Installer et configurer dsh-romeo selon sa documentation. Démarrer son modèle
   séparément lorsque vous souhaitez allouer ses GPU. Forest ne lance ni
   `dsh-romeo --launch`, ni `--stop`, ni une allocation d'inférence implicite.
2. Sur ROMEO, relever l'adresse de la passerelle déjà active et enregistrer sa
   clé dans un fichier privé, accessible depuis le nœud de calcul :

   ```sh
   /apps/romeotools/romeollmtool/romeollmtool gateway status
   umask 077
   mkdir -p ~/.config/forest
   /apps/romeotools/romeollmtool/romeollmtool gateway show-key > ~/.config/forest/romeo-llm.key
   chmod 600 ~/.config/forest/romeo-llm.key
   ```

3. Ajouter au `romeo.json` de l'application cette section, en remplaçant les
   valeurs par l'adresse et le chemin absolu distants réels :

   ```json
   "dsh_romeo": {
     "base_url": "http://HOTE_PASSERELLE_ROMEO:PORT/v1",
     "api_key_file": "/home/VOTRE_COMPTE/.config/forest/romeo-llm.key"
   }
   ```

   L'hôte doit être joignable depuis les nœuds de calcul. `127.0.0.1:11318`
   désigne le tunnel du PC et ne convient pas au job autonome. Pour la passerelle
   rapide, utiliser le nom du nœud login qui l'héberge et son port configuré
   (11320 par défaut). Garder cette passerelle et le modèle actifs jusqu'à la
   finalisation de Forest. La clé elle-même ne doit jamais figurer dans le JSON.
4. Dans **Préparation → Modèle**, choisir **DeepSeek V4.1 Flash 1017 · dsh-romeo**,
   puis son effort. Enregistrer, préparer un nouveau dossier et lancer la mission.
   **Paramètres** indique si la connexion dsh-romeo est configurée. Au lancement,
   Forest vérifie `/v1/models` avec la clé distante. Une connexion indisponible
   reste un échec d'infrastructure, sans score et sans changement de fournisseur.

Une mission exclusivement DeepSeek ne demande pas de connexion ChatGPT.
Un mélange avec OpenAI vérifie les deux accès. L'URL et le chemin du fichier de
clé sont figés dans la mission ; la clé est lue uniquement au moment de l'appel
et transmise dans l'environnement du processus Codex, jamais dans ses arguments.

Pour le backend CLI local, utiliser [configs/dsh-romeo.toml](../configs/dsh-romeo.toml)
et l'environnement exporté par `dsh-romeo --env` (`DSH_ROMEO_BASE_URL`,
`ROMEO_LLM_KEY`) dans le même terminal que Forest. Le tunnel reste requis pour
ce mode local. Sous Windows, dsh-romeo s'utilise dans un environnement Linux
compatible ; l'application Forest native peut utiliser directement la
configuration distante ci-dessus.

La compatibilité de Forest est testée avec une passerelle HTTP locale synthétique
et des invocations Codex simulées. Le client local Codex 0.165.0-alpha.1.2 a aussi
été vérifié contre une API Responses synthétique : transmission des quatre efforts,
réponse structurée et reprise dans la même conversation. Aucun résultat d'inférence
DeepSeek réelle ou de campagne HPC n'est revendiqué par ces tests.

## Configuration ROMEO

Créer `romeo.json` dans le stockage de l'application à partir de
[romeo.example.json](romeo.example.json). Il désigne le connecteur MCP existant,
le répertoire de travail, le profil OAuth privé et les exécutables distants.
Il ne contient aucun jeton OAuth.

Les runtimes doivent déjà contenir les dépendances du moteur et le client Codex
pour l'architecture cible. Installer et compiler sur les nœuds de calcul, jamais
sur le login. Pour les modèles OpenAI, la CLI officielle vérifie la connexion
ChatGPT au démarrage du job ; les identifiants restent dans le profil privé distant.
DeepSeek utilise la connexion dsh-romeo décrite ci-dessus.

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

## Configurer la validation de l'exécution

Le formulaire de préparation propose **Configuration et validation**. Un contrat
optionnel fixe les CPU réservés, les processeurs physiques, le nombre maximal de
threads matériels par cœur et le placement. Il distingue cette allocation du
nombre de threads qui doivent réellement calculer. Le contrat actuel prend en
charge un nœud CPU ; MPI multi-nœuds et GPU nécessitent un autre adaptateur.

Par exemple, une allocation peut réserver 192 cœurs sur deux processeurs et
exiger 32 threads de calcul. `execution_validation.required_threads` exprime
cette exigence, indépendamment de `cpus_per_task`. Les valeurs ne sont pas liées
à un problème particulier. Le mode `not_required` vérifie les ressources sans
imposer le parallélisme ; `gnu_openmp_required` exige une équipe GNU OpenMP
observée avec la taille, le placement et le travail CPU demandés.

Les exigences sont figées avant la campagne et reprises dans la configuration
distante. Une exécution instrumentée séparée observe les équipes, leur affinité
et leur temps CPU hors synchronisations interceptées. Les mesures officielles
s'exécutent sans cette instrumentation. Les boucles combinées et les sections
utilisent des points d'entrée distincts de la [bibliothèque GNU OpenMP](https://gnu.googlesource.com/gcc/+/trunk/libgomp/loop.c),
également couverts par la sonde. Un point d'entrée explicitement non pris en
charge reste sans score. Le temps CPU seul ne prouve pas qu'une instruction
contribue au résultat : les travaux artificiels doivent être exclus par revue
des sources. La justesse continue d'être contrôlée par les tests protégés.

Les fiches de mission, d'essai et de résultat affichent séparément les exigences,
l'allocation observée et la preuve du programme. Les campagnes antérieures sans
contrat restent « parallélisme non vérifié ». L'original séquentiel peut servir
de référence ; il ne peut pas devenir le gagnant d'une campagne qui exige du
calcul parallèle. Une autre configuration exige une nouvelle campagne.

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

