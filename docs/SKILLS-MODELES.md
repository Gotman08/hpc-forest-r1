# Skills génériques de Mother et des enfants

Les nouvelles campagnes créées avec `--mother-trees` chargent les six skills
du projet selon le rôle et la phase. Ces instructions guident les décisions ;
elles ne prescrivent aucun algorithme, langage, matériel, sujet de recherche ou
nombre d'arbres. Les durées, la sélection AB-MCTS-A, le parallélisme des N arbres,
les autorisations et la confirmation restent sous le contrôle du programme.

| Phase | Skill propre au rôle | Skills communs |
|---|---|---|
| Planification de Mother | `planifier-optimisation` | Environnement, documentation, évaluation |
| Chaque sommet de chaque enfant | `conduire-experience-optimisation` | Environnement, documentation, évaluation |
| Reprise de la même Mother et assemblage de G | `integrer-optimisations` | Environnement, documentation, évaluation |

Les trois skills communs sont `inspecter-environnement`,
`consulter-documentation-technique` et `evaluer-performances`. Leurs fichiers
`SKILL.md` sont dans `src/hpc_forest/assets/skills/`. Ils font partie des paquets
Python et de la charge utile envoyée sur ROMEO.

Le relais charge explicitement le contenu complet des quatre skills applicables
dans les instructions système de **chaque invocation**, y compris les réparations
et chaque reprise de Mother pendant la fusion. La découverte automatique des
skills personnels reste désactivée : cette campagne utilise le corpus du projet.
Les MCP `romeo` et `hpc_docs` restent disponibles selon leurs liaisons existantes.
La documentation du cluster reste exclusivement dans le MCP ROMEO actuel.

Le plan et la configuration d'une nouvelle campagne figent l'empreinte des six
fichiers. Le relais vérifie les contenus, le rôle, la phase et les instructions
effectives avant l'appel natif. Un contenu manquant ou une empreinte différente
produit une erreur explicite. Préparer une nouvelle campagne après modification
des skills. Les anciens plans sans champ `skills` conservent leur contrat initial.
Pour une configuration créée par l'API Python, utiliser `model_skills.policy()`
dans `config["skills"]` avant `create_workspace`.

## Traces

Trois preuves distinctes sont conservées :

- **Chargement** : le manifeste `model_skills` de la requête et de
  `invocation.json` contient rôle, phase, noms, chemins et empreintes. L'empreinte
  des instructions effectivement transmises figure aussi dans le reçu.
- **Déclaration du modèle** : le champ structuré `skill_usage` demande une entrée
  pour chaque skill chargé, avec `applied` ou `not_needed`, une explication et
  les références pertinentes. Un rapport absent, incomplet ou incohérent est
  rejeté avant l'application du programme ou du plan. Ce champ d'audit est retiré
  avant la validation du contrat source/plan et ne devient jamais un score.
- **Actions observées** : les événements MCP natifs sont conservés séparément.
  Une déclaration de consultation ne constitue pas une preuve d'appel d'outil.
  Réutiliser un fait déjà vérifié peut être pertinent sans nouvel appel MCP.

Chaque appel produit `skills-usage.json` dans son dossier natif, également
transféré dans les diagnostics ROMEO. Les reçus suivent la réponse dans
`usage.model_skills`, les historiques de réparation et les événements du
contrôleur. Le rapport `report/experiments.json` les rassemble dans `model_skills`,
sans compter deux fois un appel présent dans plusieurs journaux.

Un reçu précise si le tour natif est terminé et si la déclaration est disponible
ou invalide. Le chargement prouve la transmission des instructions, pas leur
influence sur le raisonnement interne du modèle. Les gains restent à mesurer.
