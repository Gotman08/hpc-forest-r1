# Validation du conseiller au choix du parent

**Campagne terminée, 26 octobre 2026.** La suite technique passe et le nouveau
point d'intervention a été exercé sur ROMEO. Dix exécutions donnent six livraisons
confirmées et quatre échecs de Mother. Les six codes ont été remesurés ensemble.
Le bénéfice général du conseiller n'est pas démontré ; les résultats et les
limites sont détaillés dans le [rapport final](../experiments/tabpfn-admission-20261025/RAPPORT.md).

## Modification vérifiée

Un seul Forest conserve Mother, les arbres AB-MCTS-A, les analystes JEV et la
confirmation. Tous les rôles LLM utilisent `gpt-6-luna` avec effort `max`.
TabPFN intervient avant génération parmi des parents proposés par TreeQuest.
Un seul parent est engagé comme essai ; les autres propositions ne génèrent
aucun code.

Les 80 caractéristiques décrivent le parent immuable et son historique connu
avant génération. La cible est le gain mesuré de son prochain enfant ; le choix
compare le score connu du parent plus ce gain prédit. Les prédictions ne remplacent
jamais les récompenses mesurées. La file des générations terminées conserve le
même ordre avec et sans conseiller. Les poids de Luna et de TabPFN ne sont pas
réentraînés.

## Tests et gel des sources

- ROMEO, job **784271** : **1 072 tests réussis, 2 ignorés**, en 313,36 secondes.
  Les exclusions concernent un cas de chemins Windows et un environnement
  optionnel Sakana-M. Aucun échec.
- Les **90 fichiers Python du moteur** sont identiques entre la source testée,
  les cinq payloads récupérés et la source locale après la campagne :
  [audit final des empreintes](../evidence/tabpfn-admission-20261025/final-source-audit.json).
- Ruff a réussi **localement** sur les sources et les tests. Son journal distant
  le précise ; aucun passage de Ruff sur ROMEO n'est revendiqué.
- Neuf tests d'interface locaux passent, dont les libellés de choix de parent
  et la distinction avec les anciennes priorités de file.
- Six tests locaux d'audit, de courbes et de protocole passent après le gel.
  Deux tests de protocole étaient déjà dans la suite distante ; quatre concernent
  les nouveaux exports. Ces changements ne modifient pas le moteur des campagnes.

Les tests vérifient notamment les propositions TreeQuest réelles, le repli sur
la première proposition et son RNG, l'absence d'essais fantômes, la reprise, la
capture du parent avant génération et l'exclusion des observations futures.
Les réponses TabPFN simulées des tests ne prouvent pas un gain du modèle réel.

Les tentatives de validation 784267 et 784269 ont échoué avant la suite complète
à cause d'un environnement ou d'une archive de tests incomplets. La préparation
784268 a été arrêtée avant les campagnes LLM. Ces incidents sont conservés et
ne sont pas comptés comme réussites dans les
[preuves de validation](../evidence/tabpfn-admission-20261025/validation.json).

## Comparaison exécutée

Le premier appel réel du job 784270 a vérifié le raccordement : huit exemples,
80 caractéristiques, deux propositions et deux prédictions finies. La validation
chronologique utilisait cinq exemples antérieurs et trois réservés ; le choix
du parent a changé. Le lancement des autres paires dépendait de ce raccordement
et des tests, pas des speedups du pilote.
[Reçu du premier appel](../evidence/tabpfn-admission-20261025/first-inference.json).

Deux programmes CPU, UTF-8 et Mandelbrot, deux graines et des ordres inversés.
Chaque condition dispose de **90 minutes de recherche et de 120 minutes au total**,
confirmation comprise. Une paire UTF-8 complémentaire, graine 23, a été déclarée
après l'échec du premier témoin. Elle répète les deux conditions sur une copie
vérifiée du même payload, avec de nouvelles conversations et une mémoire vide.
Elle est identifiée séparément ; aucun échec n'est effacé.

Les cinq jobs 784270, 784273, 784274, 784275 et 784277 sont terminés.
Les configurations de chaque paire ne diffèrent que par le conseiller et les
identités des sessions isolées. Aucun conseil algorithmique manuel, ancien code
généré ou ancien résultat n'a été introduit pendant les essais.

Luna est appelé directement depuis ROMEO ; TabPFN et les programmes compilés
s'exécutent dans l'allocation. Aucun relais PC ne participe aux recherches.
Nœud `romeo-c021`, AMD EPYC 9654, un thread matériel par cœur : UTF-8 dispose
d'un cœur de calcul et un pour le client Luna ; Mandelbrot de quatre plus un.
Les campagnes concurrentes utilisent des cœurs distincts du même nœud partagé.
Le verrou TabPFN protège les mesures de sa campagne, pas les autres allocations.

La remesure finale **784366** a terminé avec code 0 sur ce même nœud, après toutes
les recherches de l'étude : six livraisons plus deux références naïves, recompilées,
vérifiées et mesurées cinq fois par régime. Cinquante lignes de mesures détaillées
ont des entrées et affinités déclarées cohérentes. Le nœud n'était pas exclusif.
L'affinité rapportée par le programme décrit son thread principal après liaison
OpenMP ; elle ne signifie pas que tous les threads Mandelbrot partagent un seul cœur.

## Résultats vérifiés

| Cas | Sans conseiller | Avec conseiller | Interprétation |
| --- | ---: | ---: | --- |
| UTF-8 r1 | échec | 6,85× | comparaison finale impossible |
| UTF-8 r2 | 4,28× | 3,08× | arrêt avant tout appel TabPFN |
| UTF-8 r3, complément | 6,11× | 7,08× | signal favorable isolé, durée consommée différente |
| Mandelbrot r1 | échec | échec | aucun code livré |
| Mandelbrot r2 | échec | 9,75× | comparaison finale impossible |

Le gain UTF-8 complémentaire est de 15,9 % de speedup, mais utilise 54,4 minutes
contre 27,1. L'égalité porte sur les plafonds autorisés, pas sur la dépense réelle.
Pour Mandelbrot, 9,75× agrège les régimes à un et quatre threads ; les résultats
séparés sont 4,88× et 19,46×.

L'audit recense **56 lancements**, **47 sélections avec prédiction validée** et
**34 changements de parent**. Il vérifie la chronologie capture → génération →
observation et l'absence de cible future dans les requêtes. L'erreur de prédiction
n'est calculée que sur les enfants réellement générés. Aucun résultat contrefactuel
n'est attribué aux propositions écartées.

## Échecs et fermetures conservés

UTF-8 r1 sans et Mandelbrot r2 sans : Mother a émis un appel natif `wait` hors
des outils autorisés, sans destinataire ni sous-agent lancé dans cet appel.
Le contrôleur a refusé la réponse malgré les options multi-agent désactivées.

Mandelbrot r1 sans et avec : réponse de Mother incomplète à `max_output_tokens`.
Les coûts en tokens concernés sont inconnus. Le contrôleur a arrêté la campagne
plutôt que de remplacer ou rejouer sa conversation sans reçu vérifiable.
[Causes et empreintes des quatre échecs](../evidence/tabpfn-admission-20261025/observed-worker-failures.json).

UTF-8 r2 avec : arrêt `no_admissible_work_after_idle_review`, quatre essais,
`closed=false`, clôture encore en attente, trois essais protégés restants et
environ 4 259 secondes disponibles avant le plafond de recherche au passage en
confirmation. Ses quatre exemples ne suffisaient pas à activer TabPFN.
[Relevé de cet arrêt](../evidence/tabpfn-admission-20261025/utf8-r2-on-early-stop.json).

UTF-8 r3 avec utilise également ce motif d'arrêt et conserve `closed=false`,
mais après 22 essais et consommation de toutes les protections. Le même motif
ne signifie donc pas le même niveau de sous-exploration.

Les sources sont restées figées pendant les campagnes. Ces problèmes de contrôle
limitent la comparaison ; les nouveaux speedups ne justifient pas une attribution
causale ou une supériorité générale de TabPFN.

## Archives et reproduction

Les cinq archives de campagne et l'archive de remesure sont rapatriées et vérifiées
par SHA-256. Une liste explicite de 441 fichiers de preuves conserve les mesures,
configurations, codes livrés et requêtes/réponses TabPFN dans
[campaigns](../evidence/tabpfn-admission-20261025/campaigns/).
Les poids, identifiants d'authentification, bases SQLite, espaces Git et transcriptions
natives brutes ne sont pas copiés dans cette sélection du dépôt.

La perte temporaire d'accès SSH est
[résolue](../evidence/tabpfn-admission-20261025/retrieval-resolved-20261026.json) :
elle n'a pas interrompu les recherches autonomes. Les ressources CPU/mémoire,
statuts terminaux et empreintes sont dans les
[reçus finaux](../evidence/tabpfn-admission-20261025/final-retrieval-and-efficiency.json).

[Protocole principal](../experiments/tabpfn-admission-20261025/protocol.json) ·
[Protocole complémentaire](../experiments/tabpfn-admission-20261025/supplementary-protocol.json) ·
[CSV final](../experiments/tabpfn-admission-20261025/results/common-comparison.csv) ·
[Audit des décisions](../experiments/tabpfn-admission-20261025/results/advice-audit.json) ·
[Rapport complet](../experiments/tabpfn-admission-20261025/RAPPORT.md)
