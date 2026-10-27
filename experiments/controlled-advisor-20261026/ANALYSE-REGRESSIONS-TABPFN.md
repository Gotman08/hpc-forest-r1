# Pourquoi certaines recherches avec TabPFN livrent un code plus lent

Analyse du 27 octobre 2026, fondée sur les **30 recherches terminées de la tentative 2**, leurs décisions, les sources livrées et la remesure commune sur ROMEO. Aucun changement du moteur, aucune nouvelle recherche et aucune nouvelle mesure n'ont été effectués pour ce diagnostic. Les trente sources livrées ont été copiées à l'identique dans le dossier d'analyse, avec leurs empreintes SHA-256.

**Conclusion : la régression observée sur Black–Scholes vient immédiatement de programmes finaux moins performants. Le conseiller ne s'exécute pas dans ces programmes. En amont, sa représentation du problème et sa validation sont insuffisamment adaptées, tandis que Mother et les analystes ne garantissent pas une exploration efficace des mécanismes coûteux. Les données ne permettent pas de répartir causalement la perte entre ces composants.**

Ce résultat ne signifie pas que TabPFN dégrade tous les cas : il améliore la moyenne de GEMM et gagne une des trois paires Black–Scholes. Une initialisation identique de Mother ne fixe pas ses décisions suivantes ni les générations Luna.

**1. Ce qui a réellement été comparé**

Il s'agit toujours d'un seul Forest, avec GPT-6 Luna effort max dans tous les rôles LLM. Les conditions sont des réglages expérimentaux du conseiller :

| Condition | Contexte du conseiller | Validation |
|---|---|---|
| `off` | Conseiller désactivé | — |
| `current` | Campagne courante | Classement historique des gains |
| `data` | Même arbre uniquement | Classement historique des gains |
| `validation` | Campagne courante | Validation des valeurs prédites, parents distincts et calibration |
| `both` | Même arbre uniquement | Validation renforcée |

Deux problèmes CPU, trois répétitions par condition, mémoires neuves et même plan initial Mother par problème. Plafonds identiques de 90 minutes de recherche et 120 minutes de bout en bout, préparation imputée. **Plafonds égaux ne signifie pas durées consommées égales**, ni nombres égaux de générations ou de jetons.

Les codes ont été remesurés après les recherches sur le même nœud ROMEO, avec le même protocole, GCC 14.2 et les mêmes options de compilation. Les entrées réservées n'ont pas servi à la sélection du gagnant. Les trente livraisons passent les vérifications enregistrées. Aucun échec d'infrastructure de candidat n'est recensé pour cette tentative.

Les recherches partageaient un nœud avec des CPU distincts ; la remesure commune réduit le biais matériel sans supprimer toutes les variations de fréquence et de charge externe. Les dix fichiers moteur utilisés pour expliquer les mécanismes correspondent aux empreintes du moteur testé : [vérification](analysis-20261027/engine-source-check.json).

**2. L'ampleur de la régression, sans confondre speedup et durée**

Moyennes géométriques de trois recherches. Plus le speedup est grand, plus le code est rapide.

| Condition | GEMM : entrées de recherche | GEMM : réservées | Black–Scholes : recherche | Black–Scholes : réservées |
|---|---:|---:|---:|---:|
| Sans conseiller | 86,33× | 68,75× | 12,75× | 13,86× |
| Conseiller actuel | 90,78× | 77,10× | 10,20× | 11,11× |
| Données du même arbre | 89,02× | 72,02× | 9,04× | 9,83× |
| Validation renforcée | 85,07× | 67,46× | 8,46× | 9,17× |
| Deux changements | 93,76× | 75,51× | 6,29× | 6,84× |

Le conseiller actuel donne **+5,1 % de speedup moyen sur GEMM**, mais **−20,0 % sur Black–Scholes**. Cette dernière baisse équivaut à **environ +25,0 % de temps d'exécution**, car le temps varie comme l'inverse du speedup. Le résultat Black–Scholes est presque identique sur les entrées réservées : −19,9 % de speedup.

La moyenne masque une forte variation entre recherches :

| Black–Scholes | Sans conseiller | Conseiller actuel | Temps actuel / sans conseiller |
|---|---:|---:|---:|
| Répétition 1 | 13,84× | 5,47× | 2,53× : beaucoup plus lent |
| Répétition 2 | 12,22× | 16,47× | 0,74× : plus rapide |
| Répétition 3 | 12,26× | 11,79× | 1,04× : légèrement plus lent |

La mauvaise première répétition pèse fortement sur la régression moyenne. Pour GEMM, le conseiller gagne une paire sur trois sur les entrées de recherche : +21,1 %, −3,0 %, −1,1 %. Il gagne deux paires sur trois sur les réservées. Ce n'est donc ni une amélioration constante ni une régression générale.

Sources : [agrégats recalculés](analysis-20261027/condition-summary.csv), [détails par recherche](analysis-20261027/arm-diagnostics.csv).

**3. Le code Black–Scholes livré explique matériellement l'écart**

Dans la répétition 1, le code sans conseiller utilise des opérations AVX2 sur **huit flottants**, des logarithmes et exponentielles vectorisés avec réduction d'argument, et un polynôme évalué avec FMA. Le code avec conseiller utilise une famille **Float4, quatre flottants**, avec des approximations bornées et des traitements par voie. Son logarithme vectorisé est limité à `[0,5 ; 2]`, avec retour à `logf` en dehors. Les exponentielles ont également leurs domaines bornés et des replis scalaires.

Ces différences sont présentes dans les sources, indépendamment du nom donné aux stratégies. Elles sont compatibles avec une vectorisation moins efficace et davantage de travail scalaire ou de contrôle dans le code lent. **La part exacte de chaque mécanisme n'a pas été mesurée par profilage ou ablation** : on ne connaît notamment pas le nombre réel de déclenchements des replis scalaires. Le facteur deux entre largeurs de vecteurs ne constitue pas, à lui seul, une preuve d'un facteur deux en temps.

La différence se retrouve dans chacune des quatre configurations chronométrées. Moyenne de cinq échantillons, temps en millisecondes :

| Taille | Threads | Sans conseiller, r1 | Conseiller actuel, r1 | Rapport des temps |
|---|---:|---:|---:|---:|
| 32 768 | 1 | 0,12570 | 0,31904 | 2,54× |
| 32 768 | 4 | 0,03262 | 0,08003 | 2,45× |
| 262 144 | 1 | 1,02171 | 2,64074 | 2,58× |
| 262 144 | 4 | 0,25653 | 0,65127 | 2,54× |

Cela ne ressemble pas à un défaut uniquement lié au nombre de threads. Pour Black–Scholes, le coefficient de variation médian des cinq temps agrégés est de **0,14 %** sur les entrées de recherche ; le maximum est de 3,17 %. Les grandes différences persistent sur les réservées. Le bruit de mesure seul est donc une explication peu plausible de cet écart de 2,53×.

Deux autres codes révèlent des limites précises :

- `validation`, répétition 1, **3,20×** : le point d'entrée retourne directement vers `black_scholes_serial` lorsque `threads <= 1`. La voie optimisée ne traite donc pas les deux configurations à un thread. À 262 144 éléments et un thread, ce code prend **7,87 ms contre 1,02 ms** pour `off` r1. C'est une faiblesse de performance réelle malgré une sortie correcte selon les tests.
- `both`, répétition 2, **4,93×** : le bloc de huit valeurs conserve une boucle qui appelle `logf` individuellement pour chaque voie. Une partie de l'arithmétique est vectorisée, mais cette fonction coûteuse reste écrite sous forme scalaire. L'effet machine exact reste à confirmer par profilage.

À l'inverse, `current`, répétition 2, atteint **16,47×** avec une famille AVX2 à huit valeurs et déroulement sur seize éléments. Le conseiller n'empêche donc pas de trouver une bonne solution ; il ne rend pas cette découverte fiable.

Sources conservées : [r1 sans conseiller](analysis-20261027/delivered-sources/blackscholes-r1-off.cpp), [r1 conseiller actuel](analysis-20261027/delivered-sources/blackscholes-r1-current.cpp), [r1 validation](analysis-20261027/delivered-sources/blackscholes-r1-validation.cpp), [r2 deux changements](analysis-20261027/delivered-sources/blackscholes-r2-both.cpp), [r2 conseiller actuel](analysis-20261027/delivered-sources/blackscholes-r2-current.cpp). [Mesures par configuration](analysis-20261027/per-configuration-comparison.csv), [variabilité](analysis-20261027/measurement-variability.csv).

**4. Ce que le conseiller sait réellement, et ce qu'il ne sait pas**

TabPFN intervient avant la génération d'un enfant. Il reclasse jusqu'à huit propositions authentiques de TreeQuest dans le même arbre. Il ne génère pas le code, ne choisit pas directement les nouveaux objectifs de Mother et ne connaît pas encore la transformation que Luna réalisera.

Son entrée comporte **80 caractéristiques** : comptages lexicaux, marqueurs de vectorisation, quelques éléments de structure, groupes de deux tokens normalisés et historique des scores. Sur Black–Scholes avec `current`, le contexte médian contient **24 exemples**, dont **17 dans la partie ajustée pour la validation**. En limitant les données au même arbre, ces nombres deviennent **15 et 12**.

Ce vecteur ne décrit pas explicitement le chemin exécuté à un thread, la proportion de logarithmes scalaires, le taux de repli des approximations, les temps par configuration ou le mécanisme précis de la transformation suivante. Les identifiants sont normalisés ; un compteur d'intrinsics n'est pas une analyse du chemin critique. La présence d'opérations vectorielles dans le fichier ne garantit pas qu'elles accélèrent le travail dominant.

Le nombre de caractéristiques supérieur au nombre d'exemples ne prouve pas à lui seul un échec de TabPFN. Le problème observable est surtout **la pertinence et l'indépendance limitées des transitions disponibles**, face à une cible variable : le gain d'un enfant que Luna n'a pas encore écrit. Multiplier les enfants d'un même parent ne fournit pas autant de familles de code indépendantes.

Les poids de TabPFN sont déjà préentraînés et ne sont pas modifiés pendant cette campagne. Il utilise les observations disponibles en contexte. « Laisser plus longtemps » peut apporter des observations utiles, mais n'ajoute pas automatiquement les variables manquantes et ne transforme pas des exemples proches en expériences indépendantes.

Source : [construction des caractéristiques](analysis-20261027/engine-attempt-2/src/hpc_forest/advisor_features.py), [admission conseillée](analysis-20261027/engine-attempt-2/src/hpc_forest/advisor.py).

**5. La validation actuelle accepte des prédictions peu fiables**

La validation historique vérifie le classement des **gains** sur des transitions récentes. La décision réelle classe pourtant **score du parent + gain prédit**. Ces deux classements ne posent pas la même question. Cette validation n'exige pas non plus une erreur inférieure à la prédiction simple « l'enfant fera comme son parent », ni des parents distincts entre les deux parties. La chronologie est protégée, mais cela ne suffit pas à démontrer la capacité à généraliser entre familles de code.

Sur les **25 changements de parent observés dans Black–Scholes avec `current`** :

- huit enfants gagnent plus de 0,005 point de score par rapport au parent choisi ;
- cinq perdent plus de 0,005 ; douze restent dans cette bande ;
- l'erreur absolue moyenne de prédiction vaut **0,0356**, contre **0,0310** pour la prédiction « même score que le parent ».

Avec `data`, sur 29 changements, l'erreur est **0,0521 contre 0,0365** pour ce repère simple. Restreindre les données à un arbre ne répare donc pas automatiquement la prédiction ; ici, cela réduit aussi les exemples disponibles.

Ce sont des erreurs en **unités de score**, pas des pourcentages de temps. Cette comparaison concerne les enfants effectivement choisis : elle ne prouve pas que le parent initialement proposé par TreeQuest aurait donné un meilleur enfant, puisque cet enfant alternatif n'a pas été généré. Les gains d'un enfant ne prouvent pas non plus qu'un changement de parent était la meilleure décision.

Sur GEMM, ce diagnostic est meilleur : pour les 35 changements de `current`, l'erreur est **0,0685 contre 0,0937** pour le repère parent. Le conseiller peut donc capter une information utile dans certaines familles, sans garantie de gain final.

Sources : [diagnostic des 115 changements](analysis-20261027/selected-override-diagnostics.csv), [validation historique](analysis-20261027/engine-attempt-2/src/hpc_forest/advisor_worker.py), [validation renforcée](analysis-20261027/engine-attempt-2/src/hpc_forest/advisor_validation.py).

**6. La validation renforcée protège, mais reste pratiquement inactive**

Sur les deux problèmes réunis :

| Condition | Appels | Appels validés | Changements de parent |
|---|---:|---:|---:|
| Actuel | 151 | 121 | 60 |
| Même arbre | 89 | 68 | 55 |
| Validation renforcée | 179 | 0 | 0 |
| Deux changements | 147 | 11 | 0 |

Dans les deux dernières conditions, **326 appels n'ont produit aucun changement de parent**. Parmi eux, 271 sont rejetés faute de suffisamment de contexte indépendant ou d'exemples du même arbre ; sept autres faute de paires comparables. Trente-sept échouent aux critères de calibration ou de classement. Les onze validations restantes conservent le choix initial : six pour marge insuffisante, cinq pour prévision hors des limites possibles du score.

Cette inaction est préférable à une confiance injustifiée. Mais les appels ont tout de même un coût : le processus vérifie les poids, importe les bibliothèques et construit le modèle avant de constater certains manques de données déjà déterminables dans les métadonnées. La validation tardive gaspille donc du travail sans autoriser une décision.

Le temps comptabilisé au conseiller actuel est en moyenne de **151 secondes par recherche Black–Scholes**, et **197 secondes sur GEMM**. Dans la mauvaise répétition Black–Scholes r1, il représente 208 secondes sur 4 805 secondes écoulées, environ **4,3 %**. Ce cumul inclut la préparation des propositions ; ce n'est pas une mesure exacte du temps perdu par toute la forêt, qui comporte des tâches concurrentes. Il ne s'ajoute pas au temps du programme livré. Le worker protège les mesures par le verrou de l'évaluateur ; il peut cependant modifier le calendrier des admissions et des tâches.

**La forte baisse de `both` sur Black–Scholes ne peut donc pas être expliquée par de mauvais changements de parent : il n'y en a eu aucun.** Les coûts et le calendrier diffèrent, et les générations Luna ainsi que Mother restent variables. Cette campagne ne sépare pas ces effets.

**7. Un défaut du score affecte surtout les optimisations déjà très rapides**

Le moteur transforme le speedup `S` en score `q = S / (S + 1)`. C'est un score borné et monotone, mais les écarts se compriment quand le code devient rapide :

- à 80×, `q = 0,987654` ;
- à 100×, `q = 0,990099` ;
- le gain de score n'est que **0,002445**, inférieur au seuil fixe de **0,005** employé dans la validation historique et dans le changement de proposition.

Une différence de performance substantielle peut donc devenir trop petite à cette échelle. La validation renforcée ajoute une marge empirique égale au maximum de 0,005 et deux fois l'erreur moyenne ; cette marge n'est pas un intervalle de confiance statistique.

Sur GEMM, au moins 19 des 72 décisions validées de `current` contiennent une prévision brute hors de `[0,1]`. Dans 14 changements, la proposition choisie obtient un score prédit ramené artificiellement à **1** par le bornage. Cela signale une calibration insuffisante et peut créer des égalités artificielles. Ce phénomène n'apparaît pas dans les prévisions Black–Scholes examinées : **il ne faut pas l'utiliser pour expliquer sa régression**.

Sources : [score mesuré](analysis-20261027/engine-attempt-2/src/hpc_forest/evaluator.py), [bornes des prévisions](analysis-20261027/prediction-bounds.csv). Deux racines à prévision censurée n'ont pas de score parent reconstructible à partir de ces seuls exports ; les nombres de dépassements sont conservateurs. Les diagnostics parent/enfant utilisent le score réel au moment de la décision, sans assimiler une nouvelle racine au programme naïf.

**8. Mother et les analystes : une recherche active, mais pas toujours bien dirigée**

La première répétition Black–Scholes illustre la différence entre quantité et qualité d'exploration :

| Indicateur | Sans conseiller r1 | Conseiller actuel r1 |
|---|---:|---:|
| Essais de recherche | 38 | 59 |
| Arbres de recherche | 3 | 10 |
| Profondeur maximale | 3 | 3 |
| Appels de contrôle | 87 | 121 |
| Analyses de code complètes | 25 | 34 |
| Speedup remesuré | 13,84× | 5,47× |

Mother ouvre sept nouveaux arbres de recherche dans le mauvais cas. Plusieurs objectifs restent autour de la famille quatre voies et de ses combinaisons. Cela suggère une dispersion et une dépendance à la famille trouvée tôt : **davantage d'arbres et d'essais, mais pas de meilleure famille finale**. Ce n'est pas une preuve que l'ouverture d'un arbre cause la perte. Le taux d'essais repartant de la racine est même plus élevé dans `off` r1 : environ 76 % contre 66 %. La largeur seule n'explique pas tout.

À l'inverse, `current` r2 atteint 16,47× avec 32 essais et trois arbres. `both` r2 produit 85 essais et cinq arbres, mais seulement 4,93×. Ces observations contredisent l'idée qu'un plus grand nombre d'essais suffirait mécaniquement.

Les analystes ne sont pas absents : **738 analyses de code complètes** sont enregistrées. Les dossiers contiennent des sources, des différences et des diagnostics accessibles. Cependant, les extraits initiaux sont bornés à 8 000 caractères par fichier, 24 000 au total ; des lectures complémentaires sont nécessaires pour les parties omises. Une citation valide prouve la provenance, pas la qualité du diagnostic ni l'examen de tous les chemins d'exécution.

Plusieurs décisions de Mother indiquent explicitement que les résultats visibles sont agrégés et qu'un gain par configuration reste à établir. Le résumé des exemples met en avant le temps moyen et le score ; les détails peuvent être accessibles dans les diagnostics. **On ne peut pas affirmer que les modèles n'avaient aucun accès aux détails**, mais leur exploitation systématique n'est pas démontrée. Le chemin à un thread resté scalaire dans `validation` r1 montre pourquoi cette distinction compte.

Les 44 tâches d'analyste indisponibles se répartissent ainsi : 16 résultats sans mécanisme et citations bornées conformes, neuf citations hors des lignes/version fournies, sept références d'évidence non prises en charge, sept résultats `code_findings` invalides, cinq tentatives d'outil hors du périmètre autorisé. Huit réponses Mother citent également des preuves indisponibles. Ces rejets ont été récupérés : aucune Mother n'est déclarée définitivement cassée. Ils réduisent néanmoins le retour utile et mobilisent la boucle de contrôle. Ils existent aussi sans conseiller ; ils ne constituent pas un défaut propre à TabPFN.

Sources : [diagnostic détaillé et erreurs](analysis-20261027/diagnostic.json), [constitution du dossier analyste](analysis-20261027/engine-attempt-2/src/hpc_forest/active_analysis.py), [résumé Mother](analysis-20261027/engine-attempt-2/src/hpc_forest/active_snapshot.py), [accès aux diagnostics](analysis-20261027/engine-attempt-2/src/hpc_forest/observer_snapshot.py).

**9. Les fermetures précoces existent, mais ne sont pas la cause principale ici**

Sur trente recherches, 21 s'arrêtent pour préserver la clôture ou atteindre la limite de recherche ; neuf utilisent une clôture revue. Les deux plus courtes sont GEMM r2 `validation`, **38,04 minutes**, et Black–Scholes r2 `off`, **40,88 minutes**, hors coût commun de préparation.

La fermeture attend les travaux en cours et les rapports actualisés, protège certains essais et exige une disposition pour chaque hypothèse. Mais :

- `tested` exige une mesure citée dans le bon arbre, sans prouver automatiquement qu'elle teste précisément le mécanisme de l'hypothèse ;
- `budget` est refusé s'il reste du budget d'admission ;
- `rejected` peut être accepté sans nouvel essai réfutant l'hypothèse.

La clôture GEMM r2 `validation` comporte quatre hypothèses rejetées et trois déclarées testées. Celle de Black–Scholes r2 `off` comporte sept rejets et une hypothèse testée. La procédure protège la traçabilité ; elle ne prouve pas l'épuisement des possibilités d'optimisation.

Ce défaut mérite correction, mais **Black–Scholes `current` r1 a tourné 80,08 minutes et les trois recherches `both` environ 83 à 84 minutes**. Prolonger uniquement les fermetures les plus courtes ne répare donc pas la mauvaise famille de code de ces essais. La première comparaison Black–Scholes où le conseiller gagne inclut même le témoin arrêté à 40,88 minutes : ce gain doit être lu avec cette limite.

Source : [garde de fermeture](analysis-20261027/engine-attempt-2/src/hpc_forest/active_lifecycle.py), [décisions exactes des deux clôtures précoces](analysis-20261027/diagnostic.json).

**10. Ce qui est établi et ce qui reste à départager**

| Affirmation | Niveau de preuve |
|---|---|
| Certains codes livrés sont réellement plus lents sur ROMEO | Mesuré, confirmé sur les entrées réservées |
| Ils présentent des chemins scalaires ou une vectorisation différente | Vérifié dans les sources livrées |
| Ces mécanismes expliquent chacun une fraction précise du surcoût | Non mesuré : profilage/ablations nécessaires |
| Le conseiller est insuffisamment calibré dans certaines décisions | Observé ; diagnostic sur les enfants choisis seulement |
| La validation renforcée n'a changé aucun parent | Vérifié dans tous les journaux de décisions |
| Les analyses et fermetures comportent encore des fragilités | Vérifié dans les contrôles et décisions |
| TabPFN explique à lui seul les −20 % de speedup Black–Scholes | Non établi |
| Mother explique seule la baisse | Non établi : décisions et générations non séparément randomisées |
| Un modèle plus puissant ou simplement plus de temps suffira | Non testé |

Trois recherches par condition restent peu nombreuses. Les cinq chronométrages d'un même code ne deviennent pas cinq nouvelles recherches indépendantes. Les graines TreeQuest et le plan initial partagé ne reproduisent pas exactement les sorties Luna. Aucune significativité générale ni estimation fiable de l'effet sur d'autres programmes n'est revendiquée.

**11. Priorités proposées, sans les implémenter**

1. **Rendre le diagnostic matériel explicite pour Mother et les analystes.** Mettre les temps de chaque taille et nombre de threads à côté des chemins exécutés, des fonctions coûteuses et des replis. Demander un mécanisme, une preuve et un prochain essai discriminant, plutôt qu'une liste d'optimisations génériques. Conserver les contrôles de citations ; améliorer les dossiers et la réparation des réponses non conformes.
2. **Aligner la prédiction et sa validation sur la décision réelle.** Comparer systématiquement au repère « même résultat que le parent », tenir compte de la transformation envisagée et utiliser une échelle sensible aux gains de temps. Évaluer ces changements ; ne pas simplement baisser les seuils pour forcer TabPFN à intervenir.
3. **Éviter les appels dont l'invalidité est déjà connue.** Vérifier avant le démarrage du worker qu'il existe assez de parents indépendants et de paires utilisables. Si le conseiller ne peut pas se justifier, garder TreeQuest sans payer à répétition la même vérification coûteuse.
4. **Exiger une justification utile avant d'ouvrir ou de fermer une piste.** Comparer le coût d'un nouvel arbre au prochain essai discriminant dans un arbre existant. Relier une hypothèse déclarée testée à la modification effectivement mesurée. Distinguer convergence démontrée, rejet raisonné et simple manque de preuves, sans forcer des essais inutiles ni garantir artificiellement une profondeur.
5. **Isoler les responsabilités dans l'expérience suivante.** Faire d'abord un rejeu chronologique sur des transitions enregistrées, sans utiliser le futur, pour juger la calibration. Pour connaître la valeur des options non choisies, constituer séparément un ensemble de comparaisons où ces options sont effectivement évaluées. Puis répéter des recherches avec un témoin qui paie le coût du conseiller sans appliquer son classement, afin de mieux séparer coût/calendrier et décisions. Garder un plan initial commun, davantage de répétitions et de nouveaux problèmes, avec une politique d'arrêt fixée avant le lancement.

Le diagnostic prioritaire est donc **l'information utile et la qualité des décisions**, avant une augmentation aveugle de la durée ou un changement de modèle. Luna Max et un seul Forest peuvent être conservés pour tester ces corrections proprement.

**Reproduction et pièces jointes**

Le script [analyze.py](analysis-20261027/analyze.py) recalcule les tableaux à partir des exports de la tentative 2 et des mesures capturées. Il utilise uniquement la bibliothèque standard Python. Exécuter `python analyze.py` depuis son dossier ; l'option `--raw-dir` permet de recapturer les sources et échantillons depuis l'archive de résultats extraite. Il ne lance ni Forest ni un benchmark.

[Synthèse machine](analysis-20261027/diagnostic.json) · [sources et empreintes](analysis-20261027/sources-manifest.json) · [1 200 mesures par configuration](analysis-20261027/per-configuration-samples.csv) · [mesures communes enregistrées](analysis-20261027/measurements-registered.json) · [mesures réservées](analysis-20261027/measurements-reserved.json). Les données brutes et le rapport automatique restent conservés sans modification. Les archives complètes des trente recherches restent également sur ROMEO ; les pièces locales sont les exports et les résultats nécessaires à ce diagnostic.
