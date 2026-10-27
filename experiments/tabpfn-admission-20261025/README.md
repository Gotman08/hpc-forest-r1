# TabPFN au choix du parent — campagne longue

Un seul Forest, GPT-6 Luna avec effort max pour Mother, les arbres et les analystes.
Conseiller TabPFN-3.5 local sur ROMEO, poids inchangés, sans relais du PC.

Le [protocole](protocol.json) fixe deux programmes CPU, deux graines, deux conditions
par graine et des ordres inversés. Chaque condition dispose de 5 400 secondes pour
la recherche et de 7 200 secondes au total, confirmation comprise. Les arrêts
justifiés de Mother restent autorisés : une limite de temps n'est pas une durée
garantie. Mémoire et conversations neuves à chaque condition. Le coût du conseiller
consomme le même budget. Les nombres d'essais et les tokens réellement dépensés
sont rapportés ; ils ne sont pas forcés identiques.

Le conseiller reçoit les sources du parent et la trajectoire connue **avant**
génération. Il estime le gain du prochain enfant, puis compare les scores finaux
estimés (`score_parent + gain`). Aucun résultat futur ne sert de caractéristique,
aucune récompense prédite n'entre dans les arbres.

Le premier bras avec conseiller sert aussi à vérifier son invocation réelle.
La décision de lancer les autres paires dépend du raccordement et des tests,
pas des speedups observés. Les échecs et les arrêts restent dans le rapport.

Les oracles, entrées, compilateur, répétitions et métrique de temps sont ceux du
comparatif précédent. Seule la classification du timeout du sous-processus candidat
change : échec du candidat, pas panne d'infrastructure. Cette modification crée un
nouveau protocole pour les deux conditions ; aucun résultat ancien n'est remplacé.

La sélection reste expérimentale. Une validation chronologique sur quelques
exemples ou un gain sur deux répétitions ne prouve pas une supériorité générale.

Une [paire UTF-8 complémentaire](supplementary-protocol.json), répétition 3,
reprend les deux conditions et la graine 23 après l'échec technique du témoin
de la répétition 1. Elle utilise une copie vérifiée du même moteur figé, les mêmes
entrées et les mêmes plafonds. L'échec initial reste dans la cohorte principale ;
le résultat complémentaire est identifié séparément dans les CSV.

La campagne est terminée : [rapport final](RAPPORT.md) et
[CSV de remesure commune](results/common-comparison.csv). Dix bras, six livraisons,
quatre échecs de contrôle conservés ; aucun bénéfice général du conseiller
n'est établi. Le statut préparé du protocole reste son état au gel ; l'état final
figure dans [results/status.json](results/status.json).
