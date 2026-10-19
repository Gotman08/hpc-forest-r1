# Mode binaire optionnel

Le moteur conserve AB-MCTS-A par défaut. Le mode `binary-greedy` est une politique
distincte, activable à la création d'une nouvelle campagne. Les campagnes et
résultats existants conservent leur politique ; on ne bascule pas leur registre
en cours de route. Une copie des 81 fichiers de code et de documentation avant
cette modification est conservée dans
[la sauvegarde](../artifacts/before-binary-20261019T193705/source.zip).

## Activation

Dans la configuration du sujet :

```json
{"binary_tree": {"enabled": true}}
```

`false` conserve AB-MCTS-A. La commande `init` accepte aussi `--binary-tree` ou
`--no-binary-tree`, avec les mêmes sources et la même configuration officielle.
Le mode s'applique à chaque arbre spécialisé et à G séparément. Il accepte les
méthodes H et H-no-feedback ; U et l'énumération gardent leur politique historique.

## Déroulement

Chaque parent reçoit au plus deux enfants, gauche puis droit. Les deux essais
repartent du même commit parent. Leur compilation, leur correction et leur temps
sont évalués par le contrôleur, dans le budget habituel. La descente attend les
deux résultats, puis choisit le temps moyen le plus faible parmi les enfants
corrects avec une mesure finie strictement positive. Une égalité exacte conserve
la gauche. Seul le gagnant pourra recevoir de nouveaux enfants.

Les échecs de correction gardent un score nul. Les erreurs d'infrastructure,
doublons et interruptions gardent un score absent et ne deviennent pas des
observations de performance inventées. Si aucun enfant n'est admissible, cet
arbre s'arrête ; les autres arbres peuvent poursuivre. Les limites de profondeur,
de temps, de tokens et de tentatives restent appliquées. Une paire peut rester
incomplète à l'arrêt du budget.

Les nœuds écartés restent archivés avec leurs mesures et leur provenance. Un
parent plus rapide que ses descendants reste disponible pour la confirmation
finale, qui conserve les protections habituelles. La recherche est gloutonne :
une branche écartée pourrait avoir donné un meilleur descendant plus tard. Aucun
optimum global n'est promis.

Les observations des arbres spécialisés ne contiennent que leurs ancêtres ; le
frère et les branches écartées ne sont pas injectés dans leur contexte. G reste
l'intégrateur du protocole R1 et reçoit les productions archivées. La mère garde
sa préparation et sa synthèse ; son rôle de directrice n'est pas implémenté ici.

## Comparaison

`tools/prepare_smoke.py --subject 2023-count --binary-tree` prépare un nouveau
pilote officiel Luna MAX sans soumission ni appel modèle. Sans le drapeau, il
prépare AB-MCTS-A. Le pilote court conserve deux essais par rôle : une paire par
arbre. Pour étudier plusieurs niveaux en campagne complète, il faut prévoir plus
de paires dans le même ordonnancement pour les deux politiques.

`tools/compare_tree_reports.py reference/report/experiments.json
binaire/report/experiments.json --output comparaison.json` compare les gains
confirmés. Il vérifie les sources initiales, les budgets, le modèle configuré,
la graine, le compilateur, les conditions de mesure et les confirmations. Si ces
contrôles ne concordent pas, il ne désigne aucun gagnant. Les journaux natifs du
modèle complètent cette vérification de configuration. Une paire de campagnes
ne permet pas de conclure à une supériorité générale.

Les tests du sélecteur utilisent des temps de fixture pour vérifier sa logique ;
ils ne constituent pas des mesures HPC. Les résultats scientifiques du R1
précédent restent rattachés à leur essai AB-MCTS-A.

La validation logicielle complète passe avec 294 tests réussis et trois ignorés
faute de GCC/G++ sur Windows, ainsi que Ruff :
[reçu complet](../artifacts/checks-20261019T200045-293154Z/result.json).
Le paquet du mode binaire est conservé séparément de la wheel précédente, avec
39 fichiers de paquet comparés aux sources :
[reçu de construction](../artifacts/wheel-binary-verification.json).
Les 70 préalables ARM passent dans le pilote officiel :
[JUnit ARM](../artifacts/official-count-e79e3f11/arm-preflight.xml).
Le pilote officiel 757763 est terminé et son registre a été contrôlé en lecture
seule. Les huit candidats sont valides ; onze appels Luna MAX, dont une réparation
dans A2, comptabilisent 258 687 tokens selon les événements d'usage de la CLI.
Les réponses et les onze ensembles de diagnostics sont livrés ; le worker local
s'est fermé normalement. Les avertissements de rafraîchissement du catalogue et
une reconnexion interne de la CLI restent conservés dans l'audit.

| Mesure confirmée sur 2023-count | AB-MCTS-A | Binaire |
| --- | ---: | ---: |
| Source initiale | 80,102 ms | 80,815 ms |
| Programme retenu | 20,058 ms | 22,809 ms |
| Réduction du temps | 74,959 % | 71,776 % |

Le binaire est inférieur de 3,183 points de réduction du temps sur cette paire
de campagnes. AB-MCTS-A reste donc le défaut ; le mode binaire est conservé pour
les essais explicites. Ce pilote court couvre une paire par arbre : il ne permet
pas de départager généralement les deux recherches sur plusieurs niveaux.
Les tests locaux couvrent la descente sur plusieurs niveaux.

La topologie observée garde A2, B2, C2 et G1, et marque leurs frères comme écartés,
sans leur retirer leurs mesures. Les contextes A/B/C ne contiennent aucun code
ni mesure de leurs frères ; tous les appels observés demandent Luna MAX et aucun
appel d'outil ou d'autre agent n'apparaît. Le routage interne du fournisseur n'est
pas observable. Le code G1 retenu combine une formule combinatoire et une DP
scalaire générale, sans réponses de tests codées en dur ni accès réseau. Les
contrôles du sujet restent ceux de R1 ; aucun contrôle sémantique supplémentaire
imposant OpenMP n'a été ajouté.

[Comparaison des rapports](../artifacts/official-count-e79e3f11/comparison.json),
[audit des mesures et des générations](../artifacts/official-count-e79e3f11/audit.json),
[rapport ROMEO](../artifacts/official-count-e79e3f11/rapport-romeo.md),
[transferts vérifiés](../artifacts/official-count-e79e3f11/transfers.json).
