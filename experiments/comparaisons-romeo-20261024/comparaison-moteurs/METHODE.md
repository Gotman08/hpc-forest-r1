# Comparaison des moteurs et des programmes CUDA

Cette étude complète le [rejeu des 124 programmes historiques](../comparaison-historique/RAPPORT.md) par de nouvelles recherches réalisées avec les sept états du moteur effectivement déployés. Les essais unitaires de douze révisions Git restent consultables dans le premier rapport. Une suite de tests et une nouvelle recherche avec un modèle mesurent des choses différentes.

## Conditions fixées

- Programme initial : le même noyau N-body naïf, avec lancement `256 / 256 / 0`.
- Modèle demandé : `gpt-6-luna`, effort `max`, via le même exécutable local Codex. Le nom du modèle est fixé ; la version interne du service n'est pas figée.
- Budget configuré : 1 800 secondes, politique `finish-started`, jetons observés sans plafond. Les calculs déjà engagés peuvent dépasser l'échéance ; cet éventuel dépassement fait partie des résultats.
- Graine du moteur : 23. Cette graine ne fixe pas l'échantillonnage du modèle.
- Une nouvelle session et une mémoire vide pour chaque campagne. Aucun programme optimisé historique n'est introduit dans la recherche.
- Une allocation indépendante par moteur : un GPU GH200, quatre CPU, 16 Gio ; CUDA/NVRTC 12.6.3 et CMake 3.30.5, identifiés par les mêmes empreintes Spack.
- Protocole CUDA inchangé, SHA-256 `3311797eec4fec382991af5fe8f8fedb76bdaa068facfe1258f688e051ffeb74`.
- Onze cas de recherche, onze cas de confirmation ; graines 20261021 et 20261022. Les fichiers d'entrée et les sorties de référence des 21 campagnes ont des empreintes identiques. Les empreintes des manifestes correspondent à celles du contrôle préalable et l'oracle CPU indépendant a réussi partout : [preuve entre les trois séries](protocol/all-series-input-equivalence.json).
- Performance : moyenne géométrique des temps CUDA-event pour N=4096, 8192 et 16384 ; dix lancements de chauffe et cent lancements chronométrés par taille. Trois répétitions pendant la recherche, cinq pour la confirmation.

## Sept états réellement utilisés

| État historique | Comportement conservé |
|---|---|
| 772923 | Recherche par vagues, Mother persistante, assemblage par paires |
| 774157 | Arbres indépendants, assemblage par paires |
| 775521 | Mémoire persistante, première politique de réserve, deux tours d'assemblage autorisés |
| 775815 | Première correction de réserve, deux tours d'assemblage autorisés |
| 776048 | Réserve corrigée, jusqu'à seize tours d'assemblage |
| 776290 | Correction de décision d'admission |
| 780448 | Fiabilité, mémoire enrichie et critique budgétée du plan |

Les sources Python, les ressources du moteur, les pilotes et les vérificateurs sont copiés à l'identique depuis les paquets historiques. Quatre états intermédiaires ne correspondent pas exactement à un commit Git : remplacer ces paquets par le commit le plus proche aurait testé un autre moteur. Les empreintes originales et les fichiers inchangés sont consignés dans `protocol/<état>/source-identity.json`.

Les consignes, paramètres de mémoire et outils disponibles conservent les différences historiques. Les deux premiers états disposent des outils ROMEO côté modèle en plus de la documentation ; les cinq suivants ont accès à la documentation. On compare donc des versions complètes du système. Les effets individuels de chaque changement ne sont pas isolés.

## Trois séries conservées séparément

Les jobs 780639 à 780645 constituent une première série, conservée intégralement. Des réponses du modèle ont été calculées puis leur transfert a échoué ; les journaux signalent notamment des RPC expirés, des connexions SDK fermées et des conflits de concurrence sur les fichiers. Les reprises de relais réutilisent les réponses mises en cache et gardent l'échéance initiale. Elles ne transforment pas une campagne interrompue en campagne réussie.

Cette série a produit 38 essais enregistrés, dont 17 essais CUDA valides. Certaines solutions de recherche ont ensuite été confirmées. Aucun des sept assemblages n'a satisfait tout le protocole final. Le message d'export « Packaging requires the mandatory final G confirmation » signale cette absence de confirmation de G ; il ne signifie pas que tous les programmes produits sont incorrects.

La seconde série est enregistrée dans [relance-controlee](relance-controlee/protocol/study-design.json). Elle utilise les mêmes sept paquets historiques et de nouvelles sessions, avec un adaptateur de transport commun : une connexion MCP partagée, deux transferts simultanés au maximum, une seule liste de répertoire à la fois, des signaux de présence espacés de 30 secondes et une borne de 180 secondes pour les RPC de fichiers. Les algorithmes de recherche, les consignes, les vérifications et la génération restent ceux des paquets historiques. Le test préalable a vérifié 14 transferts concurrents : [résultat](relance-controlee/protocol/transport-probe.json).

La connexion partagée n'a pas supprimé les attentes de transfert : certaines opérations sont restées en file plusieurs dizaines de secondes et des signaux de présence ont encore expiré. Quatre jobs sur sept ont terminé avec un code système nul, mais une recherche interrompue peut néanmoins produire un assemblage et un export final réussis. Ce résultat ne rend donc pas S2 équivalente à une campagne sans incident.

La troisième série, jobs 780687 à 780693, est enregistrée dans [serie-atomique](serie-atomique/protocol/study-design.json). Elle conserve les mêmes moteurs, nouvelles sessions, modèles et paramètres de calcul. L'adaptateur utilise une connexion MCP persistante par campagne. Les petits messages UTF-8 (au plus 65 536 octets) sont écrits avec les API officielles atomiques `file_create` et `file_replace`, avec empreinte SHA-256 attendue pour le remplacement. L'empreinte renvoyée est comparée au contenu local et le fichier local est vérifié de nouveau après transfert. Les téléchargements et fichiers plus gros conservent le transfert SCP vérifié. Aucun verrou de concurrence n'est contourné.

Le test préalable de S3 a vérifié 21 opérations (création, remplacement, téléchargement pour sept fichiers) en environ 7 secondes. Les reçus et configurations publiques sont archivés. Les sources des moteurs et leurs décisions ne sont pas modifiées par l'adaptateur. Ces changements portent sur plusieurs paramètres de transport ensemble ; ils ne prouvent pas une cause technique unique des incidents antérieurs. Les durées d'opération et d'attente sont enregistrées pour rendre leur influence visible.

Les archives de retour de S3 excluent les grands tableaux binaires `output-*.bin` pour réduire les transferts. Ces tableaux restent sur les allocations de travail distantes ; les sources, bases SQLite, journaux numériques, mesures, empreintes, décisions et résultats structurés sont conservés localement.

## Interprétation des résultats

Un **essai** est un programme enregistré par le contrôleur. Un **appel natif** est une invocation locale du modèle ; un essai peut en demander plusieurs, par exemple pour une réparation guidée par le banc de validation. Les jetons d'entrée incluent déjà les jetons lus en cache : ces deux colonnes ne doivent pas être additionnées.

Les événements `turn.completed` de la version locale de Codex rapportent le compteur total du fil, y compris les appels antérieurs lors d'un `exec resume`. La comparaison recalcule donc les différences de compteurs entre invocations d'un même fil. Les compteurs bruts restent dans les colonnes `reported_*` et `native_cumulative_usage`. La correspondance avec `total_token_usage`, distinct de `last_token_usage`, est vérifiée sur une session de cette étude : [preuve de sémantique](protocol/codex-token-counter-semantics.json). Les coûts enregistrés par les moteurs historiques restent inchangés ; leur addition des compteurs bruts peut surestimer les jetons d'une Mother persistante. Le budget des présentes campagnes est configuré en observation des jetons, sans plafond ; cette correction porte sur l'analyse, pas sur les décisions exécutées.

Les états « programme valide », « recherche terminée », « G confirmé », « meilleur candidat confirmé » et « export réussi » sont présentés séparément. Une erreur d'infrastructure n'est pas une preuve d'erreur numérique du programme.

Le rejeu commun des nouveaux programmes utilise un seul GPU, cinq blocs à ordre aléatoire (graine 20261023), une référence avant et après chaque bloc et les mêmes 22 cas de correction. Il inclut les programmes validés dans au moins une phase des trois séries, ainsi que les gagnants historiques comme points de comparaison. Chaque couple exact noyau/configuration de lancement n'est rejoué qu'une fois ; toutes ses origines sont conservées. Un programme qui échoue au contrôle complet de 22 cas est conservé comme échec et ne reçoit pas de classement de performance.

Chaque mesure de bloc est la moyenne géométrique des trois tailles, puis le résultat final est la moyenne arithmétique des cinq mesures de bloc. Les dix mesures de référence servent au calcul de l'accélération et à l'examen de la dérive. Les résultats par taille, par bloc et par cas numérique restent disponibles, ainsi qu'un recalcul indépendant des agrégats.

Une recherche neuve par état constitue une observation, pas une estimation fiable de la probabilité de retrouver une optimisation. Les résultats du modèle, le temps de ses réponses et les choix de pistes peuvent varier. Les comparaisons de vitesse des programmes remesurés sont plus directement interprétables que le classement des moteurs sur une seule campagne.
