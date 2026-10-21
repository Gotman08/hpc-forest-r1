# Références officielles pour Mother et les enfants

Les nouvelles campagnes `--mother-trees` exposent deux serveurs distincts aux
modèles : `romeo`, avec la configuration et le profil existants, et `hpc_docs`,
qui consulte les références techniques publiques. **La documentation du cluster
ROMEO reste dans son MCP actuel**, via `search_docs` et `read_doc`.

Mother dispose de `hpc_docs` pendant la planification. Les N enfants disposent
du même accès pendant leurs recherches AB-MCTS-A, tous en parallèle. La reprise
de la conversation originale de Mother conserve cet accès pendant l'assemblage
de G, y compris après la durée cible. Aucun outil documentaire ne peut lancer
de modèle, relancer les arbres ou modifier le protocole et les mesures.

Le relais active `features.code_mode_host` lorsque ces MCP sont exposés : le
client natif utilise ce mécanisme pour appeler leurs outils. Le shell local et
la délégation restent désactivés. Un serveur connecté ou un processus terminé
avec le code zéro ne suffit pas à prouver l'accès depuis le modèle. Une erreur
native « Code Mode is unavailable » est classée en échec d'infrastructure, même
si le modèle termine sa réponse JSON ; les tokens consommés restent enregistrés.

## Sources

Le catalogue livré est `src/hpc_forest/assets/documentation/catalogue.json`.
Son empreinte fait partie du nouveau plan de campagne.

| Identifiant | Références officielles |
|---|---|
| `cuda` | NVIDIA CUDA, NVCC, PTX et archives de versions : `docs.nvidia.com/cuda/` |
| `nsight` | NVIDIA Nsight Compute et Systems |
| `openmp` | Spécifications et exemples OpenMP, versions HTML et PDF |
| `mpi-standard` | Standards MPI Forum ; le PDF est normatif, le HTML facilite la consultation |
| `openmpi` | Documentation de l'implémentation Open MPI |
| `mpich` | Documentation MPICH et références des routines MPI |
| `arm-simd` | Arm ACLE, Neon et SVE sur le site officiel Arm Software |
| `intel-simd` | Intel Intrinsics Guide : SSE, AVX, AVX-512 et téléchargement officiel hors ligne |
| `gcc` | Manuels GCC, libgomp et archives par version |
| `clang` | Manuels Clang et LLVM, dont les versions publiées |
| `nvhpc` | Compilateurs C, C++ et Fortran du NVIDIA HPC SDK |

Le catalogue décrit des sources, pas des recettes d'optimisation. Les modèles
choisissent leurs recherches selon le code, le sujet et la cible de la campagne.
Ils doivent vérifier l'architecture, les extensions CPU, le compilateur et les
bibliothèques réellement disponibles. La page courante d'un éditeur peut décrire
une version de développement ; elle ne prouve pas la disponibilité sur ROMEO.

## Outils disponibles à chaque invocation

- `documentation_catalog()` présente les sources, les points d'entrée et la
  couverture déjà mise en cache.
- `search_documentation(query, source_id, max_results)` recherche les passages
  du corpus consulté et explore jusqu'à trois liens officiels pertinents issus
  des points d'entrée de cette source. La requête reste locale ; il n'y a aucun
  moteur de recherche généraliste ni service LLM supplémentaire.
- `read_documentation(url, start_line, line_count)` lit une référence officielle
  avec pagination. Les lignes sont celles du texte extrait. Les PDF conservent
  des repères de page, et leur texte peut être recherché.

Les modèles reçoivent les outils et leurs consignes pendant toute la campagne,
sans recopier les manuels complets dans chaque prompt. Chaque réponse fournit
l'URL de référence, la version identifiable, les empreintes du document et du
texte, la date de lecture et le type de preuve documentaire.

## Cache commun et preuves

Le relais conserve `documentation/index.sqlite3` et les documents bruts dans
`documentation/objects/`. Les processus des N enfants et de Mother utilisent
ce même dossier. La première lecture réussie d'une URL fixe son contenu pour la
campagne. Deux demandes simultanées de la même URL partagent son téléchargement
et son extraction ; les URL différentes restent consultables en parallèle.
Le cache persiste pendant la fusion et une reprise.

Les accès sont enregistrés avec l'identifiant de la requête native dans la table
`accesses`. `worker-ready.json` et chaque `invocation.json` indiquent le serveur
documentaire et l'empreinte du catalogue. Les événements MCP natifs conservent
également les appels, leurs résultats et les erreurs ; les tokens restent
comptabilisés par les événements natifs habituels.

Une page indisponible produit une erreur documentaire explicite. Les modèles
peuvent continuer à partir des documents déjà consultés. Aucune disponibilité
permanente des sites éditeurs n'est présumée.

## Périmètre des lectures

Les domaines **et les chemins** sont limités par le catalogue. Le lecteur vérifie
les redirections, impose HTTPS avec certificat vérifié et se connecte uniquement
aux adresses IP publiques préalablement résolues. Il n'utilise ni cookies, ni
identifiants, ni proxy authentifié. Les URL fournies par les modèles ne peuvent
contenir de paramètres, de mot de passe ou de chemin sortant du catalogue.

Le téléchargement hors ligne Intel possède une exception étroite : son endpoint
officiel fixe peut rediriger vers le chemin CDN signé de l'éditeur. Ces URL
temporaires ne sont pas exposées dans les références ou les reçus. L'archive est
lue en mémoire ; seule la donnée XML des intrinsics est décodée, y compris si
l'éditeur l'enveloppe dans une chaîne constante JavaScript. Aucun JavaScript,
visualiseur, exemple ou fichier de l'archive n'est exécuté ou installé.

Les fichiers, pages et passages ont des bornes de taille pour le transport et
la lecture. Cela n'ajoute aucun plafond global de tokens, de profondeur, de
cycles ou d'appels aux modèles. Les textes récupérés restent des données ;
leurs exemples ne remplacent ni les tests, ni les scores, ni la confirmation de G.

## Préparation et dépendances

Installer le complément du projet dans le Python du relais :

```powershell
python -m pip install -e ".[mcp]"
python tools/prepare_smoke.py --duration 30m --mother-trees
```

Le complément comprend le SDK MCP et `pypdf` avec le support des polices PDF.
Le relais active automatiquement
`hpc_docs` pour un nouveau plan portant le champ `documentation`, en gardant
`model_mcp` pour ROMEO. Le relais générique `codex_worker --mother-trees` active
également les deux accès. Le fichier utilisateur donné par `--codex-config`
continue de définir exclusivement la connexion ROMEO existante.

Les anciens plans sans `documentation` conservent leurs accès précédents.
Le démarrage refuse un changement de session, de catalogue ou de liaison
documentaire pendant une campagne. Une nouvelle configuration documentaire
se prépare dans un nouveau dossier de campagne.

Les tests utilisent des références simulées pour contrôler les frontières
réseau, l'extraction HTML/PDF/XML, le cache concurrent, les traces et les erreurs.
Des clients stdio réels vérifient le catalogue, la lecture partagée et la reprise
Mother. Les tests du contrôleur conservent le vrai TreeQuest, les compilations C
et la confirmation indépendante, avec les générations hébergées simulées.
