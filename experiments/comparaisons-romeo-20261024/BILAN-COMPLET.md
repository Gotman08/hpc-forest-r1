# Historique complet des moteurs et des programmes CUDA

L’étude est terminée : les versions du moteur, les codes produits, leurs diagnostics et leurs mesures sont conservés avec les sources exactes. Le dépôt de travail n’a pas été modifié.

**291 programmes distincts** ont été rejoués : les 124 retrouvés dans les campagnes historiques et les 168 produits par les nouvelles campagnes, avec une référence initiale commune. **290** réussissent les contrôles de tous leurs rejeux. Les programmes identiques ne sont comptés qu’une fois, même s’ils apparaissent dans plusieurs campagnes.

Le programme exclu avait réussi le jeu de confirmation de S2 / 775521, mais échoué sur le jeu de recherche. Le rejeu reproduit cette différence : une composante hors tolérance à N=16384. Il reste documenté avec ses sources et ses diagnostics, sans mesure de vitesse classée.

## Où lire les résultats

- [Tableau de bord des nouvelles campagnes](comparaison-moteurs/TABLEAU-DE-BORD.html) : filtres par moteur et série, progression, sources, différences de code, appels et événements.
- [Rapport des comparaisons](comparaison-moteurs/RAPPORT.md) : classement, répétitions, gagnants historiques et nouveaux, effets de chaque assemblage.
- [Comportements et diagnostics expliqués](comparaison-moteurs/COMPORTEMENTS.md) : réserves de temps, plans, réparations, erreurs numériques, mémoire et transport.
- [Historique des 19 commits et tests des 12 révisions](comparaison-historique/RAPPORT.md), avec le [tableau de bord des 124 programmes historiques](comparaison-historique/TABLEAU-DE-BORD.html).
- [Catalogue unifié des 291 programmes](comparaison-moteurs/tables/catalogue-unifie.csv) : correspondance entre les deux études, empreintes et toutes les origines.

## Ce qui a été exécuté

Les sept états du moteur réellement déployés ont chacun été relancés trois fois depuis le même programme initial, soit **21 nouvelles campagnes, 225 essais enregistrés et 389 appels natifs**. Les deux premières séries ont révélé des incidents de transport. La troisième constitue la comparaison principale : 134 essais de recherche, dont 121 valides, et 15 assemblages valides. Les sept programmes finaux sont confirmés ; six exports aboutissent. L’ancien exporteur du septième attend des fichiers absents du paquet CUDA, mais ses sources et ses résultats ont été récupérés.

Les sept campagnes historiques ajoutent 138 essais. Les suites de tests de 12 révisions représentent **8719 tests collectés** : **8711 réussites** et **8 échecs ou erreurs**, dont les causes et les éventuelles répétitions sont conservées. Les commits documentaires ne sont pas assimilés à de nouveaux moteurs ; quatre états déployés intermédiaires sont identifiés par leur archive exacte, faute de commit identique.

Les deux rejeux GPU totalisent **1510 échantillons de temps**, **4530 mesures par taille** et **6621 contrôles de cas**, références et programmes remesurés compris. Chaque programme classé dispose de cinq répétitions et réussit les deux jeux de correction. Les comparaisons directes utilisent des mesures du même rejeu.

## Résultat de la nouvelle comparaison commune

Le programme sélectionné le plus rapide vient de **772923 — Vagues / paires** : **0,083213 ms**, soit **22,22×** la référence. L’état le plus récent, 780448, obtient **0,592180 ms** dans cette campagne.

| État | Gagnant historique remesuré | Nouveau gagnant remesuré | Accélération du nouveau |
|---|---:|---:|---:|
| 772923 — Vagues / paires | 0,113190 ms | 0,083213 ms | 22,22× |
| 774157 — Arbres indépendants / paires | 0,118552 ms | 0,093721 ms | 19,73× |
| 775521 — Mémoire / réserve initiale | 0,697122 ms | 0,137762 ms | 13,42× |
| 775815 — Première correction de réserve | 0,525592 ms | 0,592769 ms | 3,12× |
| 776048 — Réserve et assemblage adaptatifs | 0,099665 ms | 0,639299 ms | 2,89× |
| 776290 — Correction d’admission | 0,852576 ms | 0,328067 ms | 5,64× |
| 780448 — Fiabilité et critique du plan | 1,007912 ms | 0,592180 ms | 3,12× |

Ces valeurs décrivent les codes effectivement trouvés. Il n’y a qu’une nouvelle campagne sans incident de transport par état : elles ne démontrent pas qu’un moteur retrouve systématiquement un meilleur code. Les plans, le nombre d’arbres et les fonctionnalités historiques diffèrent aussi.

## Améliorations et limites établies

- **Arithmétique CUDA :** dans le nouvel assemblage de 772923, le passage à `rsqrtf` réduit la latence de **33,73 %** par rapport à son parent, avec **5/5 blocs** plus rapides. Le patch et les deux codes sont conservés. Le premier rejeu avait mesuré 24,40 % sur une autre base historique ; ces pourcentages concernent leurs bases respectives.
- **Certaines transformations ralentissent :** dans le premier rejeu, le passage à deux cibles par thread du candidat historique 780448 allonge le temps de 70,79 %. Une transformation présentée comme une optimisation n’est pas considérée comme un gain sans mesure.
- **La correction de réserve engage davantage de travail :** 775521 réserve environ 52 minutes alors qu’il en reste 28 et ne lance que trois essais de recherche. Les versions suivantes explorent davantage. Cela améliore le comportement d’admission observé, sans garantir le meilleur noyau.
- **La mémoire et la critique ont des effets fonctionnels vérifiés :** les tests avant/après montrent la présence des résultats mesurés dans les résumés, la conservation du code sans leçons facultatives et la correction de la réserve pour une grande forêt provisoire. Leur effet causal sur la vitesse du meilleur CUDA n’est pas isolé.
- **Les erreurs restent visibles :** sept missions de la série principale réussissent après un contrôle local échoué. Les refus de génération, les sorties numériques incorrectes, les copies exactes et les erreurs d’export sont distingués dans les tables.
- **Le comptage des jetons est défectueux dans les sept moteurs figés :** ils additionnent à nouveau des compteurs cumulatifs lors des reprises. Le contre-exemple est exécuté sur leurs sources. Les tableaux corrigent ce comptage ; les moteurs eux-mêmes restent inchangés.

La stabilité du dernier rejeu est documentée : étendue des contrôles de référence **0,609 %**, coefficient de variation médian **0,374 %**. Les petits écarts doivent être lus avec cette dispersion. Aucun profilage matériel n’a été effectué pour attribuer les écarts aux registres, à l’occupation ou à la mémoire.

## Vérification et reproduction

[Méthode, conditions et limites](comparaison-moteurs/METHODE.md) · [Instructions de reproduction](comparaison-moteurs/REPRODUCTION.md) · [Couverture vérifiée des deux études](comparaison-moteurs/protocol/study-coverage.json) · [Les huit mêmes programmes remesurés dans les deux rejeux](comparaison-moteurs/tables/reperes-entre-rejeux.csv).

L’archive de livraison `historique-moteurs-et-cuda.zip` regroupe les deux études, les sources, les diagnostics, les capsules des moteurs et les scripts d’analyse. Son index précise les archives brutes volumineuses exclues du ZIP, conservées séparément dans les dossiers locaux. Les fichiers livrés et l’archive ont des empreintes SHA-256.
