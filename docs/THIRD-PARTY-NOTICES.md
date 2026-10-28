# Dépendances et droits à vérifier

Ce document inventorie la provenance technique. Il n'attribue pas de licence
au code propre de Forest et n'autorise aucune publication. Le dépôt ne contient
pas encore de licence générale définissant sa redistribution. Ce choix revient
aux titulaires des droits avant toute diffusion externe.

Les inventaires [Windows](dependencies-windows.json) et
[Linux](dependencies-linux.json) donnent les versions, métadonnées de licence
et SHA-256 des fichiers de licence trouvés dans l'environnement installé.
L'inventaire Linux applique ses marqueurs aux versions disponibles ; les octets
de ses distributions Linux n'ont pas été inspectés ici. Les métadonnées seules
ne remplacent pas une lecture des notices réellement distribuées.

| Composant | Licence déclarée ou source vérifiée | Usage |
|---|---|---|
| TreeQuest 0.3.2 | [Apache-2.0, Sakana AI](https://github.com/SakanaAI/treequest/blob/main/LICENSE) | Politique réelle AB-MCTS |
| FastAPI | [MIT](https://github.com/fastapi/fastapi/blob/master/LICENSE) | API locale |
| SDK MCP Python | [MIT](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE) | Transport du connecteur |
| NumPy, SciPy | BSD et notices de composants incorporés, voir inventaires | Calcul scientifique de TreeQuest |
| Uvicorn, Starlette, HTTPX, pypdf | BSD-3-Clause dans les métadonnées installées | Serveur, tests, extraction |
| python-multipart | Apache-2.0 dans les métadonnées installées | Téléversement |
| certifi | MPL-2.0 dans les métadonnées installées | Certificats de confiance |

Les sources des trois premières licences ont été consultées le 28 octobre 2026.
Leurs liens de branche peuvent évoluer ; les inventaires locaux conservent les
empreintes des fichiers de licence installés. La liste n'est pas une analyse
juridique exhaustive de toutes les dépendances transitives et bibliothèques
binaires. Les distributions Python conservent leurs propres notices.

TabPFN ne fait plus partie des dépendances ni du paquet courant. Son code
d'intégration et ses essais sont conservés dans l'archive de retrait ; cette
archive n'est pas incluse dans la wheel. Les conditions applicables à une
reproduction historique doivent être examinées avec son environnement d'origine.

Les programmes importés, sujets de concours, jeux de données, documents et
résultats gardent leurs provenances et droits propres. Les inclure dans un
bundle d'exécution privé n'établit pas un droit de redistribution commerciale.
L'utilisation de Codex, d'OAuth, des modèles et de ROMEO relève aussi des comptes,
autorisations et conditions applicables. Leur compatibilité avec une future offre
commerciale doit être vérifiée avant son lancement.
