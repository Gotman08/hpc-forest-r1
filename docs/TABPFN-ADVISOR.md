# TabPFN dans Forest

Forest conserve un seul moteur : Mother, les arbres TreeQuest, les analystes JEV,
le contrôleur, l'évaluation et la confirmation. TabPFN est un conseiller optionnel
du contrôleur. Luna Max reste le modèle des rôles LLM ; activer le conseiller ne
change ni le modèle ni l'effort et n'active pas le mélange de générateurs.

## Rôle effectivement intégré

Version `forest-tabpfn-advisor-v3-runtime-evidence` : le conseiller intervient
**avant la génération**, au choix du parent d'un nouvel essai. Forest demande
jusqu'à huit propositions à la véritable politique AB-MCTS-A de TreeQuest,
toutes à partir du même arbre mesuré, puis retire les doublons parent/action.
Ces propositions sont des aperçus : seul le choix retenu est enregistré comme
essai et reçoit ensuite un résultat. Elles ne sont pas huit générations de code.

La politique courante `runtime_calibrated_v2` prédit le gain de
**valeur = log(1 + speedup mesuré)** du prochain enfant par rapport au parent.
Le choix compare la valeur du parent plus le gain prédit. Le programme incorrect
a une valeur nulle ; une panne n'a aucune cible. Les valeurs finales prédites
impossibles (négatives ou non finies) sont refusées, sans les ramener artificiellement
à un. Un gain prédit négatif reste possible : il annonce une dégradation du parent.
Passer de 80× à 100× reste distinguable. Le score mesuré borné utilisé par
TreeQuest est inchangé : ces valeurs sont propres au conseiller.

Les politiques `gain_rank_v2` et `decision_calibrated_v1` restent des sélections
explicites pour les ablations historiques. Il s'agit de réglages du même conseiller,
pas d'un autre moteur. Une reproduction exacte conserve également le moteur
archivé, puisque le contrat v3 enrichit les caractéristiques.

L'ordre de traitement des générations terminées est désormais identique avec
et sans conseiller. Mother, JEV, les vérifications, la clôture et la confirmation
restent dans le même Forest. TabPFN ne rédige pas de code et n'ajoute aucun conseil
algorithmique aux prompts. Il s'applique aux arbres indépendants AB-MCTS-A ; les
politiques incompatibles sont refusées à la validation de configuration.

La [première expérience](../experiments/tabpfn-advisor-20261025/RAPPORT.md),
conservée, utilisait la file des candidats déjà prêts et n'avait produit aucun
appel en ligne. Ses résultats ne mesurent pas cette nouvelle intervention.

## Données et apprentissage

- TabPFN **3.5**, bibliothèque `tabpfn==9.2.0`, régression locale sur CPU, quatre
  estimateurs et une graine fixée. L'interpréteur et le SHA-256 du fichier de poids
  `.safetensors` sont fixés avant le lancement.
- Les 94 caractéristiques décrivent le **code immuable du parent** et l'état
  disponible avant génération : comptages lexicaux, imbrication des blocs,
  opérations de bits, comparaisons, largeur des intrinsics, OpenMP, alignement,
  signatures de voisinages de tokens, profondeur, score connu, descendants déjà
  testés, gains/échecs antérieurs et budget restant. S'ajoutent six comptages
  d'appels mathématiques/déclarations vectorielles et huit résumés des temps par
  configuration : couverture, dispersion, gains minimum/moyen/maximum et différence
  entre les configurations série et parallèle. Les comparaisons exigent les mêmes
  paramètres et identités d'entrée. L'absence de diagnostic est explicite, jamais
  remplacée par un temps nul. Les commentaires et chaînes
  ne se transforment pas en opérations fictives. Ces signaux statiques ne sont
  pas une compréhension sémantique complète du programme ni une analyse AST.
- Un exemple est une transition : caractéristiques du parent avant génération,
  puis `valeur_enfant_mesurée - valeur_parent_connue`. Un échec de candidat avec un
  vrai score nul est informatif. Une panne, annulation ou duplication sans nouvelle
  récompense n'ajoute pas de cible. Le code de l'enfant n'entre jamais dans ses
  propres caractéristiques de prédiction. Les racines créées depuis une variante
  optimisée utilisent le score mesuré de cette variante, pas celui du code naïf.
- Le contexte reste limité à la campagne, au protocole et à l'epoch : aucune
  fusion de matériels ou d'entrées différents. Les identités et empreintes des
  parents et les dates de capture/observation sont conservées. Plusieurs enfants
  distincts d'un même parent restent plusieurs observations ; les commits enfants
  identiques sont dédupliqués.
- Huit exemples permettent seulement de sortir du préchauffage ; une décision
  validée demande davantage de preuves. Les derniers exemples du même arbre
  constituent une validation chronologique : au moins six observations, trois
  parents distincts et trois paires distinguables. L'ajustement exige au moins cinq
  observations plus anciennes provenant d'au moins trois autres parents. Un même
  code parent ne peut apparaître dans les deux parties. Aucun résultat observé
  après la capture d'un exemple de validation ne sert à son ajustement.
- La validation examine les **valeurs des enfants**, comme la décision finale,
  et doit battre le repère « même valeur que le parent » en erreur absolue moyenne,
  avec une précision de classement supérieure à 0,5. La marge de changement est
  `max(log(1,01), 2 × erreur moyenne de validation)`. Cette marge empirique n'est
  **pas un intervalle de confiance ni une preuve statistique de supériorité**.
- Les effectifs, parents distincts et paires disponibles sont vérifiés **avant**
  le lancement du worker. Un refus `validation_preflight_rejected` conserve le
  premier choix TreeQuest sans importer Torch, lire les poids ou lancer TabPFN.
- Les exemples persistent dans la base de campagne et se rechargent à la reprise.
  Aucune mémoire d'une autre campagne n'est importée. Les poids de TabPFN et de Luna
  ne sont pas entraînés : TabPFN conditionne ses prédictions sur les nouveaux exemples.

Les contrats du contrôle actif et des données sont figés dans une nouvelle campagne.
Un ancien contexte n'est pas reconverti en v3. La reprise avec un contrat incompatible
est refusée explicitement ; les anciens résultats restent consultables avec leur
version, leur cible et leurs caractéristiques enregistrées.

## Budget et replis

Le comportement par défaut reste désactivé. Lorsqu'il est activé, une opportunité
sur quatre conserve la première proposition de TreeQuest, pour l'exploration.
Un appel est plafonné à 20 secondes ; son délai est réduit par le budget disponible
avant la clôture et par l'enveloppe du conseiller (5 % du budget cible par défaut).
Les imports, la lecture des poids, la validation et l'inférence font partie du délai.
La capture des caractéristiques et l'enregistrement des exemples sont également
comptés dans les diagnostics et réduisent l'enveloppe des appels suivants.
Tout ce temps consomme aussi le temps réel de la campagne, sans rallonger son budget.

Échec, délai dépassé, mauvais poids, réponse incohérente, validation insuffisante,
absence de runtime ou manque d'exemples : première proposition TreeQuest et motif
enregistré. Les appels utilisent un sous-processus borné, un seul thread CPU et
aucun GPU. Ils prennent le même verrou que les mesures de leur campagne : aucune
inférence ne peut concurrencer son benchmark ou son contrôle du harness. Ce verrou
n'isole pas les autres campagnes du même nœud. Si la cible est occupée,
le conseiller renonce immédiatement à son appel. Le téléchargement des poids
pendant la campagne est interdit.

## Activation

L'application affiche une case « Conseiller TabPFN · expérimental ». Elle reste
indisponible tant que le profil ROMEO ne déclare pas un runtime installé et vérifié.
Le fichier de connexion du serveur, et non le dossier envoyé par l'utilisateur,
contient les chemins du runtime. Exemple de fragment du profil CPU :

```json
{
  "advisor_runtime": {
    "python": "/chemin/venv/bin/python",
    "model_path": "/chemin/poids/tabpfn-v3.5-20260909.safetensors",
    "model_sha256": "SHA256_REEL_DU_FICHIER_EN_64_CARACTERES_HEXADECIMAUX"
  }
}
```

Le contrat de campagne utilise `"advisor": {"enabled": true}`. La configuration
du moteur reçoit le même fragment `advisor_runtime`. Les paramètres sont figés
avec le lancement ; le worker refuse un poids dont l'empreinte a changé. Le réglage
du conseiller n'est pas ajouté au cahier des charges transmis aux LLM, afin de ne
pas leur donner des consignes différentes entre les conditions avec et sans conseil.

L'installation de la bibliothèque ne suffit pas. La bibliothèque officielle exige
une acceptation de licence et une authentification **Prior Labs** pour télécharger
les poids 3.5. L'OAuth OpenAI sert à Luna et ne donne pas cette autorisation.
Effectuer cette démarche via [Prior Labs](https://ux.priorlabs.ai), puis provisionner
les poids hors campagne avec le mécanisme officiel. Aucune clé ni aucun poids ne
doit être ajouté au dépôt. Les conditions de licence applicables restent celles
de [Prior Labs](https://github.com/PriorLabs/TabPFN).

## Preuves disponibles

`report/advisor.json` conserve le résumé et les décisions. `advisor-decisions.csv`
exporte les candidats, les exemples disponibles, le choix, le motif et le temps
consommé. Chaque appel conserve sa requête et sa réponse ; les prédictions sont
distinctes des scores réellement mesurés. L'application affiche appels, changements
de parent, coût et dernier état. Une opportunité unique ne nécessite pas d'inférence.
Un appel validé peut conserver le même parent ; les deux compteurs sont distincts.

Les tests déterministes simulent explicitement les réponses du modèle. Ils vérifient
le raccordement et les invariants, **pas les gains de TabPFN**. Les résultats réels
et le blocage éventuel sont détaillés dans
[VALIDATION-TABPFN-20261025.md](VALIDATION-TABPFN-20261025.md) pour la première version.
La campagne du nouveau point d'intervention est terminée :
[rapport final et CSV](../experiments/tabpfn-admission-20261025/RAPPORT.md),
[validation technique](VALIDATION-TABPFN-ADMISSION-20261025.md).
Elle compte dix exécutions, six livraisons, 56 lancements du conseiller et
34 changements de parent. Les échecs de Mother, les fermetures précoces et
le faible nombre de paires complètes empêchent de démontrer un bénéfice général.
