# Sakana AI dans Forest

Cette intégration conserve GPT-6 Luna avec effort `max` par défaut. Le choix de
Sol 6.1 ou Astra, et le mélange de générateurs, restent explicites. Les composants
ci-dessous améliorent les possibilités de recherche ; leur présence ne démontre
pas un meilleur speedup sur ROMEO. Il faut des campagnes comparables pour cela.

## Origine et portée

| Travail de Sakana | Intégration dans Forest |
| --- | --- |
| [TreeQuest / AB-MCTS](https://github.com/SakanaAI/treequest/tree/v0.3.2), [article](https://arxiv.org/abs/2503.04412) | Dépendance officielle `treequest==0.3.2`. AB-MCTS-A gaussien et bêta, AB-MCTS-M optionnel, MCTS classique de TreeQuest. Choix adaptatif du parent et du générateur par l'algorithme réel. |
| Témoins de l'article AB-MCTS | Échantillonnage indépendant et raffinement séquentiel : implémentations simples propres à Forest, identifiées comme témoins, jamais appelées AB-MCTS. |
| [ShinkaEvolve](https://sakana.ai/shinka-evolve/), [dépôt](https://github.com/SakanaAI/ShinkaEvolve) | Archive bornée de codes corrects diversifiés, sélection mesurée des générateurs, pistes réutilisables. L'archive est une adaptation propre à Forest ; le paquet ShinkaEvolve n'est pas embarqué. |
| ShinkaEvolve : îlots, croisement, recommandations et exécution asynchrone | Les arbres indépendants, partages autorisés par Mother, combinaisons G mesurées, analystes et ordonnanceur concurrent existaient déjà. Ils restent les propriétaires de ces fonctions. |
| [ALE-Bench / ALE-Agent](https://sakana.ai/ale-bench/) | Même séparation utile entre génération et évaluation externe ; Forest garde son contrat de correction et son protocole CPU/CUDA. Les scores de concours ne sont pas convertis en speedups. |

Les recherches sur la fusion de poids, l'entraînement et l'auto-modification d'un
agent ne sont pas des composants à importer dans cette application OAuth. Aucune
modification des poids, aucun deuxième superviseur et aucun service externe de
télémétrie ne sont introduits.

## Application

Dans **Préparation → Stratégie de recherche** :

1. Choisir la recherche. AB-MCTS-A gaussien reste le défaut.
2. Facultativement activer **Choix adaptatif entre plusieurs modèles** et cocher
   les générateurs supplémentaires, avec leur effort. Le modèle principal est
   toujours inclus. Mother, les analystes et les intégrations le conservent.
3. **Conserver des variantes différentes** active l'archive de diversité. Cette
   option est active pour les nouveaux projets ; les contrats historiques gardent
   leur ancien comportement.
4. Préparer le dossier puis vérifier le récapitulatif avant le lancement.

La politique, les modèles, les efforts et l'archive sont figés dans le ZIP, le
manifeste de lancement et la configuration de la campagne. Le worker vérifie les
identités autorisées ; il refuse un modèle absent, une réponse d'une autre identité
ou une tentative de changer de modèle dans la conversation persistante de Mother.
Une reprise ne transforme pas une campagne A en M, ni un groupe de modèles en un
autre. Une telle modification exige une nouvelle campagne.

Le suivi affiche le nombre d'essais depuis la racine, les raffinements, la
profondeur et les résultats par générateur. Les nœuds conservent séparément le rôle
de recherche, le parent de code et l'identité du générateur. La nouveauté du code
n'est pas un score de performance.

## Configuration du moteur

Extrait pour Luna seul avec archive :

```json
{
  "backend": "codex",
  "codex": {"model": "gpt-6-luna", "reasoning_effort": "max"},
  "search": {"algorithm": "ab-mcts-a", "distribution": "gaussian"},
  "evolution": {"enabled": true, "archive_size": 12, "inspirations": 3}
}
```

Pour autoriser le mélange, ajouter explicitement à `codex` :

```json
{
  "generator_pool": [
    {"model": "gpt-6-luna", "reasoning_effort": "max"},
    {"model": "gpt-6.1-sol", "reasoning_effort": "max"},
    {"model": "gpt-6-astra", "reasoning_effort": "max"}
  ]
}
```

TreeQuest reçoit des actions distinctes `rôle|modèle|effort`, utilise ses scores
mesurés et choisit une action au prochain essai. Le rôle reste par exemple `T1`,
quel que soit le modèle choisi. Les réparations d'un même essai gardent ce modèle.
Avec un seul modèle, les actions et les choix de parents de l'ancien AB-MCTS-A
sont conservés, pour une même suite de scores et une même graine.

Politiques acceptées :

| `search.algorithm` | Options | Usage |
| --- | --- | --- |
| `ab-mcts-a` | `distribution`: `gaussian` ou `beta`; `reward_prior`: null ou un nombre strictement entre 0 et 1 | Recherche adaptative ; prior laissé à TreeQuest par défaut. |
| `ab-mcts-m` | `reward_prior` | Modèle bayésien mixte de Sakana ; dépendances supplémentaires. |
| `standard-mcts` | `samples_per_action`: 2 par défaut ; `exploration_weight`: √2 | Témoin UCT à branchement fixé. |
| `repeated-sampling` | Aucune | Chaque essai repart de la racine. |
| `sequential-refinement` | Aucune | Chaque essai raffine le dernier essai évalué, même incorrect. |

Dans les deux témoins simples, un éventuel groupe de générateurs est échantillonné
uniformément. Il ne s'agit pas de sélection Thompson. Le mode binaire historique
reste distinct et ne se combine pas avec ce groupe de générateurs.

### AB-MCTS-M

Installer `hpc-forest-r1[sakana-m]` dans **l'environnement Python qui exécute la
recherche**. Le support reste optionnel : son coût de sélection est supérieur à A.
Forest fixe un seul processus de calcul du posterior et désactive l'élagage
interne de M, pour conserver la responsabilité des fermetures dans les contrôles
existants. Les décisions d'arrêt et la confirmation finale restent celles de Forest.

Le profil ROMEO doit déclarer `"search_algorithms": ["ab-mcts-m"]` après
installation et validation de ses dépendances. L'application refuse autrement la
soumission de ce mode. Le superviseur teste aussi l'import sur le nœud ; il ne
remplace jamais M par A en silence. Cette livraison n'installe pas automatiquement
ces dépendances sur ROMEO et ne réserve pas de nouvelle allocation.

Sous Windows, PyTensor peut dépasser la longueur maximale de chemin dans son
cache par défaut. Pour les tests de ce mode, un répertoire court, propre à
l'environnement, peut être défini par `PYTENSOR_FLAGS=compiledir=C:/chemin/court`.
Ne pas réutiliser un même cache entre versions de Python incompatibles.

## Archive de diversité

Un code entre dans le registre de diversité seulement après une évaluation
correcte, finie, avec un commit et un temps mesuré. La vue conserve le champion,
puis des variantes dont le texte diffère, jusqu'à sa capacité. Les variantes
évincées de la vue ne sont pas supprimées du registre.

L'empreinte utilise au plus 128 hachés de groupes de cinq jetons du code. Elle
donne un indice lexical approximatif ; elle ne prouve ni une différence
sémantique ni un potentiel de gain. Les doublons textuels exacts de la vue sont
regroupés. Aucun code proche n'est refusé, aucun score n'est modifié, aucune
réparation ou relance LLM supplémentaire n'est déclenchée.

Un générateur ou analyste voit ses propres variantes et les imports explicitement
autorisés. Mother peut consulter la vue de la forêt. Chaque entrée conserve son
identifiant d'essai, son commit, son protocole et ses chemins de source ; les
lectures de mémoire existantes donnent accès au code. L'archive ne remplace pas
la lecture du code par les analystes.

Les bilans actifs transmettent réellement cette vue à Mother et aux analystes,
avec des identifiants lisibles même hors de la première page du catalogue. Le
dossier de code de l'analyste peut inclure une ancienne variante de l'archive,
après le dernier essai, son parent et le meilleur comparateur. Les extraits
restent bornés ; les lignes omises nécessitent une lecture supplémentaire.

## Mesures, reprise et comparaison

- Une solution incorrecte reçoit zéro ; une panne ou un doublon garde un score
  absent. Les erreurs ne sont pas converties en observations du bandit.
- Un seul essai reste en attente par arbre, avec parallélisme entre arbres. Cela
  permet d'annuler un `ask` sans supprimer les observations d'autres essais ;
  TreeQuest 0.3.2 n'a pas d'API publique d'annulation.
- Une combinaison est un nouveau programme : elle est testée et mesurée. Son
  score ne vient pas d'une addition des performances de ses sources.
- Les témoins gardent les tests et les mécanismes de Forest, notamment la mémoire
  si elle est activée. Ils isolent la politique de choix du parent ; ils ne sont
  pas une reproduction complète des expériences du papier.
- Les sorties incluent `search-diagnostics.json`, `search-generators.csv`,
  `diversity-archive.json` lorsque activée, et les nouvelles colonnes des CSV.
- La commande existante `reliability` sépare machines, entrées, protocoles et
  stratégies ; les campagnes continuées et doublons ne deviennent pas des
  répétitions indépendantes. Le rapport identifie maintenant aussi la politique
  de recherche, le groupe de modèles et l'activation de l'archive.

Pour une comparaison scientifique, fixer matériel, entrées, protocole, modèle,
effort et budget ; répéter avec plusieurs graines et mémoire neuve. Comparer
temps total, appels/tokens, nombre d'essais corrects et speedup **confirmé**. Les
résultats par générateur dans une campagne adaptative restent descriptifs : les
modèles n'ont pas reçu les mêmes parents ni les mêmes programmes.

Les essais réalisés pour cette livraison sont détaillés dans
[la validation du 25 octobre 2026](VALIDATION-SAKANA-20261025.md).
