# Pourquoi 776290 est 8,55 fois plus lent que 776048

Analyse du 22 octobre 2026, fondée sur les payloads figés, les bases SQLite ouvertes en lecture seule, les requêtes natives, les pages mémoire réellement montrées à Mother et les différences Git des programmes évalués. Aucune modification du moteur, du protocole ou des anciennes campagnes ; aucune nouvelle allocation GPU. Les observations détaillées et les différences exactes figurent dans [evidence.json](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/experiments/reliability-analysis-20261022-776048-776290/evidence.json).

Le facteur mesuré est **8,5489**. La cause principale visible est une différence de couverture de la recherche dès le choix des sujets. La récolte mémoire et le dialogue de sélection présentent aussi des défauts concrets qui réduisent les chances de rattrapage. Les deux campagnes ne suffisent pas à mesurer la fréquence de ces résultats ni à garantir qu'une correction donnée retrouvera le meilleur programme.

## 1. Ce qui a effectivement changé

| Élément | 776048, meilleure campagne | 776290, dernière campagne |
|---|---:|---:|
| Modèle et raisonnement | Luna Max | Luna Max |
| Arbres choisis par Mother | 4 | 4 |
| Essais de recherche | 31 | 27 |
| Programmes de recherche valides | 28 | 24 |
| Premier essai de l'arbre le plus prometteur | 0,151833 ms | 0,976558 ms |
| Meilleur programme avant intégration | 0,132813 ms | 0,889680 ms |
| Meilleur programme confirmé | **0,099877 ms** | **0,853836 ms** |
| Référence originale confirmée | 1,855817 ms | 1,834409 ms |
| Clôture de la recherche | 20 min 39,371 s | 20 min 39,413 s |
| Durée totale | 27 min 08 s | 28 min 21 s |
| Demandes de sélection rejetées | 1 | 4 |
| Temps de ces demandes rejetées | 45,33 s | 187,06 s |

Le programme original, le harnais, le compilateur annoncé, les skills, le schéma initial, le message système et le texte du problème sont identiques. Les observations automatiques ne sont pas identiques : chaque lancement possède sa mesure de référence, ses identifiants et ses chemins. La référence est même 1,15 % plus rapide sur le dernier lancement ; ces mesures ne suggèrent pas une dégradation générale du matériel expliquant un facteur 8,55. Cela ne remplace pas une comparaison des deux programmes sur une même allocation.

La comparaison des manifestes trouve **un seul fichier Python du moteur modifié** : `independent_budget.py`. La modification permet d'admettre une intégration supplémentaire avec une décision obligatoire, en réservant séparément les lectures facultatives. Les deux autres fichiers différents, `plan.json` et `settings.json`, ne diffèrent que par les identifiants, chemins et date de campagne.

Cette modification ne change ni le choix initial des sujets, ni AB-MCTS, ni le code de récupération mémoire. La dernière exécution n'a d'ailleurs pas admis de troisième intégration. L'écart des clôtures de recherche est de **0,042 seconde**. Présenter les 28 min 21 s comme une amélioration démontrée de l'efficacité de recherche était donc trop fort : davantage de temps a été consommé en finalisation, sans meilleure exploration constatée.

## 2. La différence majeure précède la fusion

Dans 776048, Mother ouvre un arbre consacré à la répartition des contributions d'une même sortie entre plusieurs threads, avec réduction des résultats partiels. Son premier essai atteint déjà 0,151833 ms ; son troisième atteint 0,132813 ms.

Dans 776290, ce sujet est remplacé par la diffusion des données entre threads d'un warp. Le code généré réutilise les chargements, mais chaque thread accumule encore toutes les contributions de sa sortie. Deux sujets traitent alors surtout de la réutilisation des mêmes données, l'un par mémoire partagée, l'autre par diffusion entre threads. Ce sont des implémentations différentes, mais leur distinction ne couvre pas automatiquement une autre répartition du calcul.

Le facteur est déjà **6,70 avant toute fusion**. Les quatre essais supplémentaires de la bonne campagne ne constituent donc pas une explication suffisante : cette campagne avait découvert une voie beaucoup plus rapide dès le premier essai de l'arbre concerné.

Ces mécanismes sont décrits pour expliquer les programmes archivés. Ils ne sont pas ajoutés aux instructions du système. Cette lecture structurelle n'est pas un profilage matériel permettant d'attribuer précisément les cycles à chaque cause.

Le contrôleur vérifie actuellement que deux intitulés ou objectifs ne sont pas textuellement identiques. Il ne vérifie pas leur diversité de mécanisme. Les sujets sont ensuite figés pour la campagne. AB-MCTS explore les candidats produits sous ces objectifs ; il ne remplace pas lui-même le portefeuille de sujets choisi par Mother. Voir [mother.py](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/src/hpc_forest/mother.py:103) et [la préparation de la forêt](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/src/hpc_forest/mother.py:267).

## 3. La mémoire masque des résultats pertinents

La recherche mémoire vide trie les faits par rôle, puis essentiellement par récence. Elle mélange expériences, instantanés de développement et leçons. Le catalogue contient le sujet et le nombre d'enregistrements, mais pas un bilan fiable des résultats de chaque arbre. Voir [memory_retrieval.py](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/src/hpc_forest/memory_retrieval.py:93).

Au premier tour de sélection de 776290, Mother reçoit le dernier essai incorrect de T4. Sa page suivante contient l'instantané incorrect du même essai. Pourtant, T4 possède **trois programmes valides**, mesurés à 1,814647, 1,021009 et 0,984958 ms. Aucune de ces trois expériences n'apparaît dans ces deux pages. Mother écrit ensuite « T4 est incorrect » et refuse de reprendre son idée arithmétique. Elle généralise ainsi le résultat d'un essai à un sujet entier, sans bilan factuel permettant de corriger cette conclusion.

À l'inverse, dans 776048, le dernier essai T4 est valide et visible. Il mesure 1,089936 ms, bien moins performant que la meilleure base à 0,132813 ms. Mother adapte néanmoins son idée et produit une première intégration à 0,100528 ms. **Un programme lent isolément a effectivement fourni une transformation utile à un autre programme.** Un classement limité aux meilleurs temps aurait pu perdre cette contribution.

Le système fournit déjà séparément la meilleure référence globale. Il ne s'agit donc pas de perdre un champion existant de la campagne ; il s'agit de mal représenter les idées complémentaires disponibles. Corriger cette présentation ne prouve pas que les idées de T4 auraient rendu 776290 aussi rapide que 776048.

## 4. Les deux intégrations ne font pas le même travail

Les différences Git sont explicites :

| Campagne | Première intégration | Deuxième intégration |
|---|---|---|
| 776048 | Modification arithmétique provenant de T4 sur la structure de calcul de T3 | Nouvelle simplification arithmétique, vérifiée indépendamment |
| 776290 | Noyau T2 identique ; bloc et sorties par bloc passent de 256 à 32 | Noyau identique ; ces paramètres passent de 32 à 64 |

Changer les paramètres de lancement constitue une vraie optimisation mesurable. En revanche, compter ces deux sorties comme deux associations d'idées donnerait une image trompeuse de la récolte. Dans 776290, les deux intégrations ont `idea_ids=[]` et une seule source. La seconde vient du repli du contrôleur après épuisement des demandes de sélection.

Il faut donc distinguer dans les rapports : nouveau programme évalué, réglage de lancement, changement du noyau, combinaison de transformations de plusieurs arbres et copie exacte. La validité d'un programme et la nouveauté de l'expérience sont deux faits différents.

## 5. Le dialogue de contrôle perd du temps et des références

Mother demande quatre fois `finish` au deuxième tour de 776290. Trois demandes sont rejetées parce que `base_id` ou `source_ids` ne sont pas vides. Le schéma JSON autorise ces valeurs, mais le validateur Python les refuse pour cette action. Le message « Finish requires an already evaluated integration » est trompeur ici : une intégration a déjà été évaluée ; le problème vient des champs inutiles à vider. Le même défaut apparaît une fois dans 776048. Voir [le schéma et sa validation](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/src/hpc_forest/integration_policy.py:26).

Une autre demande est rejetée pour un identifiant « non vu » : `2b123bd88aec470e`. Mother a pourtant lu sa source au tour précédent. Le contrôleur initialise un nouvel ensemble `seen` à chaque tour d'assemblage, alors que la conversation native continue. Il oublie donc l'autorisation issue d'une consultation antérieure. Cette demande contenait aussi des champs incompatibles avec `finish` ; conserver l'identifiant n'aurait pas suffi à la rendre valide. Voir [initialisation de seen](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/src/hpc_forest/integration_policy.py:130).

Ces quatre demandes représentent **187,06 secondes**. Le repli impose ensuite un nouvel épisode de génération même si un programme intégré valide existe déjà. Accepter un arrêt bien formé aurait évité ce gaspillage, mais n'aurait pas à lui seul découvert une meilleure optimisation.

Un essai T4 a également été rejeté au stade de génération parce qu'une leçon citait une preuve non vue ou étrangère à son contexte. Le format du commentaire mémoire et celui du code candidat sont couplés : une leçon optionnelle invalide peut empêcher l'évaluation du code. Nous ne savons pas si ce code aurait été correct ou rapide. Voir [memory_contract.py](C:/Users/nicol/Documents/Codex/2026-10-20/new-chat/outputs/hpc-forest-r1/src/hpc_forest/memory_contract.py:129).

## 6. Améliorations génériques, dans l'ordre

### D'abord corriger les défauts observables sans chercher une optimisation particulière

1. **Produire un bilan factuel par arbre.** Nombre de tentatives valides, incorrectes et non évaluées ; meilleur programme ; dernier résultat ; références d'approches différentes et de leurs conditions d'application. Un essai incorrect ne doit jamais devenir le statut global d'un sujet ayant des programmes valides. Les hypothèses du modèle restent séparées des mesures du contrôleur.
2. **Rendre les actions de Mother non ambiguës.** Contrat distinct selon `read`, `integrate` ou `finish`, erreurs indiquant le champ précis, puis réparation limitée du format. Un identifiant optionnel dans une demande d'arrêt ne doit pas provoquer plusieurs appels inutiles. Un repli de génération reste nécessaire pour la première intégration obligatoire ; après une intégration valide, l'échec d'une sélection facultative doit avoir un traitement explicite, pas systématiquement provoquer une nouvelle copie.
3. **Conserver les preuves consultées côté contrôleur.** Registre durable par conversation, campagne, protocole et identité du programme. Cela n'impose pas de remettre tous les identifiants dans le contexte. La provenance et les restrictions de visibilité restent vérifiées ; aucun identifiant inconnu n'est accepté simplement parce que le modèle le cite.
4. **Séparer le code et les leçons optionnelles.** Une annotation invalide est isolée et signalée. Le code reste soumis à toutes les règles de fichiers autorisés, compilation, correction et mesure avant admission. Une leçon rejetée n'est jamais enregistrée comme une preuve.

Fichiers principalement concernés : `memory_retrieval.py`, `memory_context.py`, `memory_contract.py`, `integration_policy.py`, `codex_mailbox.py`, puis leurs tests.

### Ensuite réduire la dépendance au premier plan de Mother

5. **Faire critiquer automatiquement les hypothèses communes du plan avant de figer les sujets.** Une proposition autonome puis une critique indépendante peuvent identifier des sujets qui ne diffèrent que par leur formulation ou un détail d'implémentation. Les thèmes et les solutions proviennent toujours du code étudié et du modèle. Aucune liste de recettes N-body n'est injectée. Le coût de cette critique doit entrer dans les 30 minutes et être comparé au temps de recherche qu'elle consomme.
6. **Décrire un problème à explorer sans enfermer trop tôt l'arbre dans une seule recette.** Conserver une identité de sujet et plusieurs hypothèses possibles. Le modèle doit pouvoir remettre en cause une hypothèse de son sujet et produire du code différent. Les différences réelles, la nouveauté et les dépendances servent d'observations ; les choix de branches restent ceux de TreeQuest AB-MCTS. N demeure variable. Une variante lente mais nouvelle ou complémentaire reste archivée, et ne déclenche pas à elle seule l'abandon d'un arbre.
7. **Demander un minimum de couverture avant une conclusion globale.** Mother peut décider sous contrainte de temps, mais le contrôleur doit exposer ce qui n'a pas été consulté. Une conclusion du type « aucune idée utile dans cet arbre » doit être confrontée aux résultats factuels et aux variantes non examinées. Ce garde-fou peut provoquer une lecture ciblée ou signaler une conclusion incertaine, sans forcer une fusion arbitraire.

Fichiers concernés : `mother.py`, le contrat des sujets et `memory_retrieval.py`; les observations et rapports doivent distinguer nouveauté, progrès mesuré et compatibilité supposée. Les éventuels outils de profilage automatique doivent fournir des observations et être budgétés, sans choisir à la place du modèle une transformation gagnante.

### Garder un contexte borné pour N arbres

Le bilan de tous les arbres reste en stockage. Mother reçoit des pages de taille bornée et, pour une grande forêt, une vue agrégée des familles de transformations et des zones encore non examinées. Le classement tient compte de la diversité, de la validité, des conditions de compatibilité et de la performance, sans éliminer les idées lentes. Les lectures détaillées sont ciblées. Le registre des preuves consultées demeure dans la base, pas dans un prompt contenant 600 programmes.

La limite actuelle de 12 000 caractères s'applique à un paquet mémoire, pas à tout l'historique natif. Tout ajout au plan ou aux résumés doit donc avoir un coût explicite en taille de contexte et en temps. Réserver davantage de mémoire brute ne corrigerait pas à lui seul une sélection qui généralise le dernier échec à un sujet entier.

## 7. Comment démontrer une fiabilité améliorée

Les 742 tests précédemment réussis vérifient le fonctionnement du logiciel ; ils ne mesurent pas la probabilité de trouver une bonne optimisation en 30 minutes. Aucun de ces tests n'a été relancé pour cette analyse documentaire.

Les régressions locales prioritaires peuvent reproduire les défauts sans GPU ni appel au modèle : arbre contenant des variantes valides suivi d'un échec ; preuve consultée encore utilisable au tour suivant ; arrêt après une intégration déjà évaluée avec erreur de champ précise ; séparation d'une leçon invalide et de l'évaluation du code ; détection d'une copie exacte en considérant aussi le contrat de lancement. Les contextes doivent rester bornés pour plusieurs tailles de forêt, notamment jusqu'à 600 arbres.

L'évaluation des performances doit ensuite comporter plusieurs campagnes indépendantes par version, avec le même budget total, la même source initiale, les mêmes ressources et le même protocole. Comparer la médiane, les mauvais résultats, la proportion de campagnes améliorant la référence, le temps avant le premier progrès et le nombre de transformations distinctes réellement évaluées. Le meilleur résultat isolé ne suffit pas.

Deux comparaisons répondent à deux questions différentes :

- Des reprises contrôlées à partir de plans et d'archives déjà produits automatiquement isolent la qualité de la récolte et du dialogue. Elles doivent être présentées comme des reprises, pas comme de nouvelles découvertes autonomes.
- Des campagnes neuves, sans ancien candidat ni bonne optimisation fournie, évaluent la robustesse de l'ensemble : planification, recherche et assemblage.

Pour attribuer un effet, changer un groupe de mécanismes à la fois. Les résultats de cette analyse ne justifient ni de remplacer AB-MCTS, ni de fixer N, ni de fournir manuellement le noyau gagnant. Ils justifient de rendre les faits visibles, les décisions exécutables et la diversité de recherche moins dépendante d'une seule première proposition.
