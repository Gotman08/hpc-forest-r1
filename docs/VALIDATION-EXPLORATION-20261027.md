# Exploration mesurée et diversité — 27 octobre 2026

État : **validation et campagnes ROMEO terminées le 28 octobre 2026**. Huit recherches, huit livraisons correctes, remesure commune et audits complets. Le débit d'essais corrects augmente face à R3 ; les speedups finaux restent variables et aucun bénéfice de sélection de TabPFN n'est démontré. Voir le [rapport final](../experiments/exploration-luna-20261027/RESULTATS.md).

## Changements du moteur

Un seul Forest conserve sa politique TreeQuest et les mêmes règles de correction, de budget et de confirmation. Le modèle des campagnes reste `gpt-6-luna`, effort `max`, sans mélange.

- Une revue de la source ayant déclenché une protection de progrès autorise les essais suivants déjà prévus. Chaque descendant moins rapide ne redemande plus la même revue. Une nouvelle amélioration déclenche une nouvelle revue ; la clôture exige toujours une analyse des descendants restants.
- Mother reçoit normalement un lot de deux bilans nouveaux, ou un bilan accompagné d'un lot d'essais nouveaux. Un seul arbre disponible et une revue de fermeture restent prioritaires. Un simple changement de compteur sans nouveau bilan ne déclenche plus Mother.
- Lorsque l'archive est activée, les générateurs reçoivent jusqu'à 6 000 caractères d'extraits de sources mesurées, avec empreinte et lignes, ainsi que les six derniers essais de leur arbre. Les sources restent limitées à cet arbre et aux imports explicitement autorisés par Mother. Les variantes correctes plus lentes peuvent servir d'inspiration.
- Les demandes distinguent une nouvelle piste depuis la base d'un perfectionnement du parent choisi. Elles demandent un mécanisme et un test vérifiables, sans fournir d'optimisation spécifique à GEMM ou Black–Scholes.
- Les bilans comptent les textes de code distincts, les expansions depuis la base et les identités des parents. Ces nombres ne prouvent pas une diversité algorithmique.

Les versions de contrat sont `hpc-forest-active-v5-batched-exploration` et `forest-diversity-archive-v2-source-context`. Les campagnes anciennes restent conservées ; les nouvelles utilisent des répertoires et sessions indépendants.

## Vérification locale

Deux régressions ont été reproduites avant correction : revue répétée d'un descendant sans progrès, rappel de Mother sur un compteur sans nouveau bilan. Les tests ajoutés vérifient aussi la revue d'un progrès ultérieur, la clôture, la disponibilité d'un seul arbre, la portée des imports, les empreintes de source et les extraits bornés.

La première suite complète (`evidence/exploration-full-20261027/`) a donné 1 162 succès, un échec et trois exclusions. L'échec était une attente de fermeture après seulement quatre puis deux essais par arbre dans un scénario concurrent. La trace a montré cinq refus corrects de fermetures devenues périmées : de nouveaux résultats étaient arrivés pendant la décision. Aucune fermeture prématurée n'a été acceptée.

Le scénario demande désormais une suspension et le drainage avant la fermeture, avec un plafond de test permettant cette séquence. Les assertions de fermeture revue, de citations, de correction, de conversation unique et d'absence d'essai encore en attente restent obligatoires ; aucun test de correction des programmes de campagne n'a changé. Une première tentative de modification du scénario a été interrompue après découverte d'une erreur d'indentation dans le test ; ces traces sont conservées dans `exploration-closure-full-20261027`. Le scénario corrigé passe dans `exploration-20261027/adviser-closure-fixed.xml`.

La revalidation finale dans `evidence/exploration-final-full-20261027/` donne **1 163 succès, zéro échec et trois exclusions**, en 1 389,5 s avec le wrapper de validation. Les empreintes avant/après sont identiques. Deux exclusions concernent les liens symboliques POSIX de préservation/relocalisation, la troisième l'environnement optionnel Sakana-M ; elles ne concernent pas la politique AB-MCTS-A utilisée ici.

Le moteur préparé pour ROMEO est inchangé depuis la première suite : seule la séquence du test a été corrigée. Les campagnes ont été soumises après le succès du test corrigé, des 52 tests ciblés, de Ruff et des neuf tests d'interface, pendant cette dernière suite complète ; ce calendrier est conservé dans `validation-before-launch.json`. Les tests de parcours compilent et exécutent leurs programmes de contrôle ; leurs transports de modèles simulés ne constituent pas des appels réels à Luna.

## Comparaison ROMEO préenregistrée

Étude : `experiments/exploration-luna-20261027/`.

- Deux problèmes : GEMM CPU et Black–Scholes.
- Deux répétitions indépendantes, graines 307 et 409 ; deux conditions par répétition, TabPFN désactivé/activé : huit recherches.
- Même moteur corrigé, même archive activée, mêmes plans initiaux rédigés antérieurement par Luna, mêmes entrées et budgets dans les deux conditions. Aucun ancien candidat ou exemple TabPFN n'est importé.
- 5 400 secondes de cible de recherche, plafond de temps facturé 7 200 secondes ; mêmes réserves de confirmation. Le coût de TabPFN fait partie du budget.
- Deux vagues de quatre allocations CPU à cinq cœurs et 8 Go : quatre cœurs pour le contrôleur et les mesures, un pour le worker. Luna utilise OAuth directement depuis ROMEO.
- Tous les codes finaux sont remesurés séquentiellement sur une même allocation avec le protocole enregistré puis les entrées réservées. Les nœuds ne sont pas exclusifs ; le bruit matériel reste une limite.

Indicateurs : résultats corrects livrés, speedups remesurés, essais évalués, textes corrects distincts, provenance des parents, appels et durées des contrôles, expositions aux sources archivées, interventions réelles de TabPFN et raisons d'arrêt.

Les différences avec l'étude R3 décrivent l'effet observé du lot entier. Les paires de cette nouvelle étude comparent l'activation de TabPFN ; la condition n'est pas masquée aux modèles et leurs sorties restent variables. Deux répétitions par problème ne suffisent pas à prouver une supériorité générale.

## Résultats exécutés et audités

Les jobs 786906–786913 et la remesure 786914 sont terminés sans erreur. Les huit recherches produisent **639 essais corrects sur 642**, sans essai non évalué ni échec d'infrastructure. Les huit codes livrés passent aussi les vérifications sur les entrées réservées. Tous les arrêts ont le motif `final_reserve_or_deadline`, sans clôture terminale par Mother.

La moyenne passe de 48,25 essais corrects par recherche dans R3 à 79,875 (+65,5 %). Le rendement agrégé par heure imputée passe de 34,32 à 56,03 (+63,3 %). Ce sont des comparaisons historiques descriptives du lot entier, avec archive activée dans les deux nouvelles conditions mais désactivée dans R3.

TabPFN effectue 13 appels : neuf refus de calibration sur GEMM, trois refus de classement sur Black–Scholes et un avis validé sur GEMM. Cet avis conserve le choix initial pour marge insuffisante. Aucun réordonnancement n'a donc lieu. La seconde recherche Black–Scholes avec conseiller ne fait aucun appel prédictif et livre pourtant un code sensiblement plus lent ; l'attribuer à un parent choisi par TabPFN serait incorrect.

L'[audit final](../experiments/exploration-luna-20261027/results/final-verification.json) vérifie les 1 300 appels natifs en Luna Max, les sources du moteur inchangées, les huit codes livrés sans retouche et les empreintes des transferts. Les [résultats CSV](../experiments/exploration-luna-20261027/results/arms.csv), les [sources livrées](../experiments/exploration-luna-20261027/delivered-codes/) et le [rapport détaillé](../experiments/exploration-luna-20261027/RESULTATS.md) conservent les succès comme les régressions.
