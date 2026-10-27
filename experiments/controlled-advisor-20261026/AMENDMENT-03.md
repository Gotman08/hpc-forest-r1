# Amendement 03 — relance après l’échec du stockage local

Enregistré le 26 octobre 2026, avant les nouvelles recherches.

## Cohorte et budgets

La tentative 1 reste conservée : six recherches interrompues par ENOSPC et
vingt-quatre non démarrées. La tentative 2 est une nouvelle cohorte explicitement
reliée à la première par `retry_of`. Elle n’importe aucun essai, code optimisé,
échantillon TabPFN ou conversation de cette tentative.

Les deux plans initiaux Mother, les trois graines, l’ordre des cinq conditions,
les entrées, les oracles, GCC 14.2 et les paramètres de recherche sont identiques.
Les 111 fichiers du moteur sont identiques par SHA-256. GPT-6 Luna, effort max,
reste utilisé pour tous les rôles ; le mélange de modèles est désactivé.

Les plafonds restent **5 400 s de recherche et 7 200 s de bout en bout par
recherche**, avec le même coût de préparation commune imputé à chaque condition.
Chaque bloc utilise cinq CPU et 8 Gio. La limite extérieure SLURM passe à
12 heures pour couvrir les cinq plafonds et la conservation des preuves entre
recherches ; elle n’augmente pas le budget de Forest.

## Stockage et état

Les répertoires de travail, fichiers temporaires et caches sont explicitement
placés sur le scratch GPFS persistant. Ils ne sont plus placés dans `/tmp`,
qui partage le petit système de fichiers du nœud avec SLURM.
Le nœud de la tentative 1, `romeo-c021`, a été drainé par l’administration
avec le motif `SlurmdSpoolDir is full`.

Avant lancement et toutes les 60 secondes, le contrôleur externe vérifie
l’espace physique disponible **et** les quotas GPFS en octets et en fichiers.
Il conserve une marge et interrompt proprement une recherche si cette marge
devient insuffisante. Ce garde-fou ne garantit pas l’absence de panne du stockage.

L’état d’avancement et les reçus de fin sont aussi écrits dans un répertoire
privé de l’espace personnel, soumis à un quota distinct. Les données de travail
restent sur le scratch pendant la recherche.

Après l’arrêt des processus d’une recherche :

1. une archive complète est créée ;
2. son contenu est vérifié contre les empreintes de chaque fichier et les liens ;
3. une copie des données terminées est faite dans l’espace de conservation personnel ;
4. la copie et la source sont de nouveau vérifiées ;
5. le chemin initial devient un lien vers la copie conservée.

Une erreur de copie ou une modification détectée de la source empêche son retrait.
Les chemins Git restent utilisables, notamment pour ajouter les worktrees de
remesure. Les archives complètes et leurs empreintes sont conservées sur le scratch.
Les opérations de conservation entre recherches ne fournissent aucun temps de
recherche supplémentaire à un modèle.

Ces deux espaces partagent GPFS : cette disposition protège contre le stockage
temporaire du nœud et sépare les quotas, mais n’est pas une sauvegarde contre
une panne générale de GPFS.

## Quota libéré et validation

Deux anciens répertoires temporaires de tests ont été conservés selon la procédure
vérifiée, avec liens aux anciens chemins : 52 022 et 53 251 entrées.
Leurs archives ont aussi été téléchargées sur le PC avec vérification SHA-256.
Les répertoires des campagnes historiques n’ont pas été déplacés.

Une première opération de conservation trop lente, job 785399, a été annulée
avant tout déplacement. Son archive partielle est conservée. L’archivage natif
et la vérification séquentielle des liens Git ont permis au job 785402 de
terminer les deux conservations en 2 min 17 s.

Les nouveaux tests couvrent le quota de fichiers, la panne de copie, une source
modifiée pendant la copie, les liens physiques, la continuité des worktrees Git,
l’état écrit hors du répertoire de travail et les recherches non démarrées.
La suite complète est exécutée sur ROMEO avant soumission de la cohorte.

## Mesures et rapport

La remesure commune utilise les répertoires persistants et leurs archives
vérifiées ; elle ne reconstruit pas toutes les campagnes dans `/tmp`.
Elle s’exécute après la terminaison des six blocs, même si un bloc échoue.

Le rapport représente explicitement les recherches non démarrées et les recherches
interrompues ; l’absence d’un temps final ne provoque plus l’erreur d’addition
observée lors de la tentative 1. Aucune non-livraison ne reçoit de speedup.
L’étude n’est déclarée entièrement livrée que si les trente recherches ont livré
et que les mesures et audits ont terminé sans erreur.

