# Suivi de l’étude contrôlée

Achèvement vérifié le **27 octobre 2026 à 07 h 29 (Europe/Paris)**.

**Campagne terminée : 30 recherches livrées sur 30**, quinze pour GEMM et quinze
pour Black–Scholes. La remesure commune sur les entrées enregistrées et réservées
a terminé à **04 h 57 min 30 s**. Aucun échec de campagne et aucune erreur d’audit.
Toutes les recherches respectent leur plafond ; les deux plans initiaux et les
trente conversations Mother indépendantes sont vérifiés.

Le conseiller actuel donne un speedup moyen supérieur de **5,1 % sur GEMM** et
inférieur de **20,0 % sur Black–Scholes**, sur les entrées de recherche, par rapport
à Forest sans conseiller. Trois répétitions par condition : pas de supériorité
générale démontrée. La validation renforcée n’a autorisé aucun changement de parent.

[Résultats et limites](RESULTATS-TENTATIVE-2.md) ·
[CSV des trente recherches](results-attempt-2/comparison/arms.csv) ·
[Reçu de fin](results-attempt-2/completion.json).

L'[analyse détaillée des régressions](ANALYSE-REGRESSIONS-TABPFN.md) examine les
sources livrées, les décisions et les mesures existantes. Aucun nouveau benchmark
ni changement du moteur n'a été effectué pour ce diagnostic.

| Étape | Jobs ROMEO | État observé |
|---|---|---|
| Suite complète et conservation des fichiers de test | 785403 | Terminée, 1 118 tests réussis et deux exclusions prévues |
| Qualification du conseiller et de l’infrastructure | 785405 | Terminée, huit contrats vérifiés, OAuth natif disponible |
| Trois blocs GEMM | 785406, 785407, 785408 | Terminés, codes de sortie 0:0 |
| Trois blocs Black–Scholes | 785409, 785410, 785411 | Terminés, codes de sortie 0:0 |
| Remesure commune et tableaux comparatifs | 785412 | Terminée en neuf minutes, code de sortie 0:0 |

[Soumission exacte](submission-attempt-2.json) ·
[Corrections de stockage](AMENDMENT-03.md) ·
[Validation avant relance](VALIDATION-TENTATIVE-2.md).

## Conditions inchangées

Un seul Forest ; GPT-6 Luna, effort max, pour tous les rôles LLM. Chaque problème
garde son plan initial Mother gelé, commun aux quinze recherches correspondantes.
Les conditions sont `off`, `current`, `data`, `validation` et `both`, dans
l’ordre enregistré avant le premier lancement.

Le plafond reste de **90 minutes de recherche et 120 minutes de bout en bout
par condition**, préparation commune imputée. Les durées réellement utilisées
peuvent différer. La limite SLURM de 12 heures par bloc couvre les cinq recherches
et la conservation de leurs preuves ; elle n’augmente pas le budget de Forest.

Aucun code optimisé, résultat, échantillon TabPFN ou conversation de la tentative 1
n’est importé. Les 111 fichiers du moteur sont identiques par SHA-256.

## Audit des six démarrages réels

Lecture seule des registres le 26 octobre à 20:57:09 UTC :

- Les six plans initiaux correspondent exactement aux deux plans communs gelés.
- Les six conversations Mother sont distinctes entre elles et de la préparation.
- Chaque session commence avec zéro essai, document ou échantillon TabPFN,
  et aucun candidat importé.
- GPT-6 Luna, effort max, sans mélange de modèles, est enregistré pour chaque session.
- Chaque bloc dispose de cinq CPU distincts sur `romeo-c022`.
- Chaque recherche a créé des essais pour ses trois arbres.
- Les répertoires de travail sont persistants ; les états et contrôles de quota
  sont aussi enregistrés dans l’espace personnel.

Preuve : [audit des six démarrages](validation-attempt-2/first-six-starts.json).

Les CPU sont distincts, mais le nœud reste partagé : des interférences sur le
cache, la mémoire ou les fréquences demeurent possibles. Le nombre initial
d’essais ne constitue pas une comparaison de performance.

## Protection et exécution autonome

Les recherches, l’enchaînement et la remesure s’exécutent sur ROMEO sans relais du PC.
Les fichiers de travail ne sont plus stockés dans le petit `/tmp` local.
L’espace disponible et les quotas en fichiers et en octets sont vérifiés au
démarrage et toutes les 60 secondes.

Après chaque recherche, ses données sont archivées, vérifiées puis conservées
dans l’espace personnel avec maintien des chemins Git. Les états sont écrits
séparément. Une panne peut néanmoins interrompre la recherche ; la persistance
des données n’est pas une reprise automatique. Une non-livraison reste un échec
déclaré. Scratch et espace personnel partagent GPFS.

## Comparaison terminée

Le job 785412 a remesuré les codes livrés sur les entrées enregistrées puis sur
les entrées réservées. Les exports locaux contiennent :

- les speedups et taux de livraison, sans attribuer de score à un résultat absent ;
- les contrastes appariés par problème et répétition ;
- les interventions et refus du conseiller ;
- les décisions de Mother, arrêts, durées et erreurs d’audit.

Sortie distante :
`/scratch_p/nimarano/forest-romeo-oauth-20261025-51ab9260/controlled-common-measurements-attempt-2/`.

Le [comparatif final](results-attempt-2/comparison/RAPPORT.md) est disponible.
Les deux arrêts à 38 et 41 minutes et les tâches d’analyste indisponibles sont
explicitement conservés dans le [bilan](RESULTATS-TENTATIVE-2.md). Trois répétitions
par condition ne démontrent pas une supériorité générale du conseiller.

## Tentative précédente conservée

La tentative 1 a échoué après 33 à 35 minutes pour ses six premières recherches :
`No space left on device` dans le stockage local de `romeo-c021`. Les vingt-quatre
suivantes n’ont pas démarré. Aucun code final n’a été livré ; aucun speedup
comparatif valide n’en est déduit. Le nœud a ensuite été drainé par l’administration
pour saturation du stockage de SLURM.

[Résultats et preuves de la tentative 1](RESULTATS-TENTATIVE-1.md).

