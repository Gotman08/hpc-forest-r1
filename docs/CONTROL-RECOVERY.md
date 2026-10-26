# Mother : reprise vérifiée et clôture explicite

Cette correction conserve un seul moteur Forest, sa politique TreeQuest et ses
critères de correction. Elle concerne le protocole de contrôle, pas les
algorithmes produits. La campagne associée est décrite dans
[`experiments/control-recovery-20261026`](../experiments/control-recovery-20261026/README.md).

## Pannes constatées

Les journaux du comparatif TabPFN du 25 octobre ont montré trois problèmes :

1. Un événement natif `collab_tool_call / wait` avec liste de destinataires vide
   était traité comme une délégation interdite, alors qu'aucun agent n'avait été
   lancé ni contacté.
2. Une réponse de pilotage terminée par `max_output_tokens` faisait perdre la
   continuité de Mother malgré un identifiant de conversation natif vérifiable.
3. Une revue sans décision valide pouvait épuiser ses tentatives, laisser la
   clôture en attente et être déclarée comme une fin de recherche. Certains
   arbres disposaient encore de temps et d'essais protégés.

## Règles de reprise

Le parseur ne tolère l'attente vide que pour Mother et pour la structure exacte
sans destinataire, état d'agent, prompt ou champ inconnu. Une véritable
délégation ou un autre outil reste interdit.

Seule une fin native explicite pour limite de sortie autorise une continuation
de pilotage. L'UUID et la chaîne des reçus sont vérifiés ; le tour incomplet reste
compté, son résultat n'est pas appliqué et sa consommation inconnue reste
inconnue. Le tour suivant a un nouvel identifiant de requête et reprend le même
fil natif. Il consomme le budget ordinaire de tentatives et doit encore être
admissible. Une coupure réseau ou une fin ambiguë n'autorise ni rejeu ni
remplacement silencieux de Mother.

Les citations d'une revue d'hypothèses sont limitées aux preuves effectivement
visibles. Un refus précise la cause ; Mother peut utiliser l'opération de lecture
existante pour consulter une autre preuve.

Après la revue bornée d'une clôture restée en attente, le contrôleur peut rouvrir
les arbres déjà existants et admissibles. Il conserve leurs objectifs, leurs
parents, leurs mesures, leurs protections et la réserve finale. Une même
récupération sans preuve nouvelle ne boucle pas. Les analyses encore requises
ne sont pas contournées. Un blocage résiduel devient une erreur explicite
`unresolved_control_stall`, jamais un succès silencieux.

Une clôture réellement validée, l'épuisement des arbres ou l'approche de la
réserve finale peuvent toujours arrêter la recherche. Le budget autorisé n'est
donc pas une durée minimale à consommer.

## Vérification

`test_control_recovery.py` vérifie les événements natifs, les reçus, l'absence de
rejeu, les tentatives bornées et les réserves. `test_active_pipeline.py` exerce
aussi la reprise avec compilation C, TreeQuest, analyse, intégration et
confirmation indépendantes. Les appels LLM de ces tests sont simulés ; les essais
de performance sur ROMEO utilisent réellement GPT-6 Luna, effort max.

Les campagnes comparées sont neuves et ne reçoivent aucune aide algorithmique
manuelle. TabPFN reste un conseiller optionnel du même moteur. Les journaux
permettent de distinguer les plafonds autorisés, les ressources consommées, les
reprises, les raisons d'arrêt et les gains effectivement remesurés.
