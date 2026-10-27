# Corrections du conseiller et du contrôle actif

Ces modifications répondent au [diagnostic de la tentative contrôlée 2](../experiments/controlled-advisor-20261026/ANALYSE-REGRESSIONS-TABPFN.md).
Un seul Forest est conservé. GPT-6 Luna effort max reste le modèle par défaut de
tous les rôles LLM ; aucun mélange de modèles n'est activé. Aucun candidat des
campagnes précédentes ni leurs tests de correction n'a été modifié.

| Défaut observé | Correction du moteur |
|---|---|
| Score du conseiller saturé aux grands speedups | Valeur `log(1 + speedup)` propre au conseiller ; récompense mesurée TreeQuest inchangée |
| Validation du gain alors que la décision compare la valeur finale | Même cible de valeur pour la prédiction, la validation et le classement ; repère parent obligatoire |
| Prévisions supérieures à un ramenées à un | Pas de plafond artificiel sur la valeur logarithmique ; rejet des valeurs négatives/non finies |
| Appels inutiles faute de parents/paires indépendants | Prévalidation avant tout worker ou chargement des poids |
| Temps agrégés cachant une configuration lente | Détails par taille, threads et identité d'entrée, avec provenance des journaux |
| Début du fichier masquant le point d'entrée tardif | Extraits répartis entre les variantes et incluant `run`/`main` lorsqu'identifiable |
| Citations fabriquées ou hors extrait | Schéma de réponse lié aux IDs, fichiers, SHA et bornes de lignes effectivement exposés |
| Citation d'analyste perdue hors de la première page du catalogue Mother | Extraits cités revérifiés et fournis à Mother avec leurs mesures ; les autres lignes exigent une lecture explicite |
| « Hypothèse testée » fondée sur un essai arbitraire du même arbre | Comparaison directe entre source de l'hypothèse et enfant mesuré, code changé et citations des deux programmes |
| Rejet d'hypothèse sans preuve | Base explicite : comparaison mesurée ou contradiction de source/contrat citée ; avis seul refusé |
| Nouvel arbre sans temps pour l'analyser | Vérification du coût essai + analyse + décision Mother, y compris les créations encore non démarrées |
| Ancienne campagne interprétée selon de nouveaux défauts | Valeurs par défaut figées à la création, contrats versionnés et reprise incompatible refusée |

La nouvelle politique du conseiller est `runtime_calibrated_v2`, son contrat de
données `forest-tabpfn-advisor-v3-runtime-evidence`. Le contrôle actif utilise
`hpc-forest-active-v4-admission-liveness` après les corrections révélées par les
appels réels à Luna. TabPFN reste optionnel ; ses anciens réglages sont
disponibles explicitement pour les ablations, dans le même composant.

Les huit caractéristiques temporelles utilisent seulement les mesures déjà
disponibles du parent et du programme de référence. Les six nouvelles
caractéristiques de code sont des comptages statiques, pas un profileur ni une
compréhension sémantique complète. Les temps détaillés sont des diagnostics : ils
ne remplacent jamais les récompenses du véritable évaluateur.

Les modèles choisissent toujours eux-mêmes les transformations et hypothèses.
Les consignes ajoutées portent sur la méthode d'analyse (chemins exécutés,
configurations, preuves, incertitudes), sans imposer une optimisation SGEMM ou
Black–Scholes ni injecter les solutions gagnantes de la campagne passée.

La garde de fermeture vérifie la provenance, la filiation et le changement de
source. Elle ne démontre pas mathématiquement que l'interprétation du modèle est
correcte. Une contradiction source/contrat reste un jugement argumenté ; la
performance et la correction demeurent mesurées indépendamment. Les demandes
refusées sont conservées dans le journal et la récupération existante peut
réouvrir l'exploration dans le budget disponible.

Validation et limites : voir [le rapport initial](VALIDATION-QUALITE-20261027.md)
et la [validation actuelle du contrôle v4](VALIDATION-REPRISE-20261027.md).
Les tests logiciels ne mesurent pas un gain de speedup. La
[campagne réelle Luna Max](../experiments/quality-luna-20261027-r3/README.md)
compare le conseiller activé et désactivé avec budgets comparables et mémoires
neuves. Les résultats antérieurs restent inchangés.

La première tentative réelle a exposé un alias partagé entre les champs du
schéma de citation : spécialiser le SHA remplaçait aussi les valeurs autorisées
de l'identifiant et du chemin. Le modèle recevait donc des contraintes
incompatibles avec le validateur. Chaque propriété est maintenant indépendante.
Trois tests reproduisent le défaut à travers le schéma natif effectivement
envoyé au modèle. Les essais interrompus, la réponse réelle et les preuves
avant/après sont conservés dans [le dossier d'interruption](../experiments/quality-luna-20261027/INTERRUPTION.md).

Un second défaut a ensuite été reproduit sur GEMM : `continue` accepté pour une
intégration déjà épuisée effaçait sa revue d'inactivité sans pouvoir admettre du
travail. Les actions `continue` et `resume` respectent maintenant les limites
enregistrées ; un simple conseil à un arbre suspendu conserve la revue en cours.
Le motif d'indisponibilité est exposé à Mother. La validation des citations reste
stricte, mais son erreur précise maintenant « 1 à 4 citations » et le nombre
reçu. Voir [le pilote de validation suivant](../experiments/quality-luna-20261027-r3/README.md).
