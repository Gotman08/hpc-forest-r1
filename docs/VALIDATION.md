# Validation de la reconstruction R1

Les 89 fichiers de la base historique ont été vérifiés avant copie, puis revérifiés
après les changements. Les originaux restent identiques à leur manifeste.

La validation initiale, avant le mode binaire, passe avec **252 réussites et trois sauts GCC/G++** :
[reçu](../artifacts/checks-20261019T185817-189666Z/result.json).
Les régressions du pilote comprennent un cas qui franchit réellement le garde
d'allocation avec deux
chemins désignant le même dossier, sans aucun appel modèle :
[JUnit](../artifacts/native-smoke-regressions.xml). Les 32 vérifications ciblées
finales du pilote et du transport passent après correction du champ de résultat
dans le rapport : [JUnit final](../artifacts/final-receipt-regressions.xml).
Ruff passe sur src, tests et tools.

La [wheel](../artifacts/dist/hpc_forest_r1-0.1.0-py3-none-any.whl) a été reconstruite
avec le backend setuptools local. Ses 38 fichiers de paquet sont identiques à
leurs sources. Il n'y a eu aucune installation dans l'environnement historique.

## Correction du sujet choisi

Le premier sujet choisi à tort était la multiplication de matrices synthétique embarquée. Ce
contrôle utilise Luna MAX pour la mère et les fils, quatre cœurs ARM64, aucun GPU,
un worker séquentiel et un registre neuf. Il conserve TreeQuest 0.3.2, la mère de
préparation et de synthèse, le harnais de développement borné et la confirmation
indépendante.

Pour rester court, son ordonnancement prévoit une mission A, B, C, puis G, au lieu
des deux missions de chaque rôle du R1 historique. La recherche web n'est pas
activée. Son plafond est de 900 secondes, dont 120 réservées à la confirmation,
et 1,5 million de tokens. Ce pilote ne peut donc pas servir à comparer les modèles
ou les performances scientifiques des campagnes anciennes.

Le premier démarrage ARM a passé les 15 contrats de compilation et d'exécution,
puis a refusé une comparaison textuelle entre les alias scratch avant tout appel
modèle. Ses [journaux](../artifacts/luna-smoke-648e0ba9/romeo.err) et son
[JUnit ARM](../artifacts/luna-smoke-648e0ba9/arm-contracts.xml) restent conservés.
Le démarrage corrigé de cet exemple a produit quatre programmes valides et deux
plans de mère, avec six appels et 72 591 tokens exacts. L'indicateur final du script
lisait state au lieu du champ status du contrat Outcome ; les sorties originales
et la vérification corrigée sont séparées dans son [audit](../artifacts/luna-smoke-4e742c25/audit.json).
Ces résultats synthétiques ne répondent pas à la demande de sujet officiel et ne
servent pas à la comparaison R1.

Le pilote conforme à la demande porte sur **2023-count**, « Number of Ways to
Traverse a Grid ». La source initiale, le contrat de correction, le compilateur,
les paramètres de mesure, la graine, le harnais, le budget et l'ordonnancement sont
identiques à la référence Luna MAX historique :
[vérification des conditions](../artifacts/official-count-5f1e1aa8/comparison-reference.json).
Le job 757288 est terminé avec un code de sortie nul, puis le worker local a
transféré ses diagnostics et s'est fermé normalement. Les huit candidats sont
valides, les deux interventions de la mère sont reçues et la confirmation retient
le candidat G2. Les onze appels Luna MAX incluent une réparation de compilation
dans B1 ; leur consommation exacte de 266 005 tokens correspond au registre.
Aucun échec d'infrastructure ni dépassement de budget n'est enregistré.

| Mesure confirmée | R1 historique Luna MAX | R1 reconstruit Luna MAX |
| --- | ---: | ---: |
| Source initiale | 80,360 ms | 80,102 ms |
| Programme retenu | 8,053 ms | 20,058 ms |
| Réduction du temps | 89,979 % | 74,959 % |

Le nouveau résultat est inférieur de 15,020 points de réduction du temps sur cet
essai. Une exécution par version, sur des allocations distinctes, ne permet pas
de conclure à une supériorité générale d'un moteur. Le chiffre de 88,2 % évoqué
pendant la conversation vocale n'était pas étayé et est retiré. Aucune mesure
historique ni solution optimisée ancienne n'a été fournie aux modèles.

La vérification locale du [registre](../artifacts/official-count-5f1e1aa8/registry.sqlite3)
en lecture seule confirme son intégrité, les temps bruts, le commit retenu et
l'empreinte de l'évaluation de confirmation :
[audit final](../artifacts/official-count-5f1e1aa8/audit.json),
[rapport ROMEO](../artifacts/official-count-5f1e1aa8/rapport-romeo.md),
[reçus des transferts vérifiés](../artifacts/official-count-5f1e1aa8/transfers.json).
Les préalables ARM passent avec 29 tests :
[JUnit ARM](../artifacts/official-count-5f1e1aa8/arm-preflight.xml).

Les sept requêtes des rôles A/B/C, réparation comprise, n'incluent aucun code,
message, document partagé ou résultat d'une autre branche spécialisée. Elles
conservent les consignes de la mère et leurs propres observations. G reçoit les
sources archivées pour l'intégration prévue dans R1. Les journaux des onze appels
demandent tous Luna MAX et ne contiennent aucun appel d'outil ou d'autre agent :
[audit des contextes](../artifacts/official-count-5f1e1aa8/isolation-audit.json),
[audit des générations](../artifacts/official-count-5f1e1aa8/generation-isolation-audit.json).
La lecture du programme retenu montre une récurrence générale avec scan NEON et
une alternative combinatoire selon le nombre d'obstacles, sans réponses de tests
codées en dur ni appel réseau. Ces observations ne donnent pas accès au routage
interne du fournisseur et ne prouvent pas une conformité universelle à l'énoncé.

Le recadrage continu par la mère reste une proposition à discuter ; il n'est pas
implémenté dans cette reconstruction. La création et la poursuite des nœuds
restent pilotées par TreeQuest et par les limites du contrôleur, avec la variante
binaire optionnelle décrite dans [son rapport](ARBRE-BINAIRE.md). Cette variante
est validée par 294 tests locaux et 70 préalables ARM. Sa première comparaison
officielle donne 71,776 % de réduction du temps, contre 74,959 % pour le R1
reconstruit en AB-MCTS-A, sur une paire par arbre. La politique par défaut est
conservée.
