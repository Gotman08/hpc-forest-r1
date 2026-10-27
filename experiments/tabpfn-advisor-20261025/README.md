# Comparaison Forest avec / sans TabPFN

**État : comparaison terminée, bénéfice prédictif non démontré.** Les jobs 784224,
784228, 784229 et 784230 ont exécuté huit recherches : sept livraisons confirmées
et un échec Mother conservé. Les quatre essais activés ont effectué zéro appel
TabPFN, faute de plusieurs candidats déjà prêts à départager. La remesure commune
784264 et le diagnostic réel séparé 784265 sont terminés.

Le [rapport détaillé](RAPPORT.md) présente les speedups, temps, arbres, arrêts,
limites et codes livrés. Les données sont dans [results/](results/) et l'état final
dans [study-status.json](study-status.json). Le champ d'état de `protocol.json`
décrit le moment de sa préparation ; il est conservé avec les premiers échecs de
précontrôle. Voir aussi la [validation logicielle](../../docs/VALIDATION-TABPFN-20261025.md).

## Protocole préparé avant les résultats

Le fichier [protocol.json](protocol.json) fixe deux répétitions de recherche pour
UTF-8 et Mandelbrot. Dans chaque paire, seul `advisor.enabled` change. Ordre sans /
avec, puis avec / sans ; graine TreeQuest 23 puis 61. Les générations Luna restent
stochastiques : une graine TreeQuest n'assure pas des réponses LLM identiques.

- Luna `gpt-6-luna`, effort `max` partout, mélange désactivé ; Mother, JEV et
  TreeQuest AB-MCTS-A gaussien identiques dans les deux conditions.
- Codes initiaux, validation et entrées historiques conservés dans `inputs/`,
  avec empreintes. Aucun code optimisé historique ni conseil de l'opérateur
  n'entre dans la recherche ou dans le contexte TabPFN.
- Base et conversations neuves par bras. UTF-8 : 65 536 octets, un thread.
  Mandelbrot : 1 024, paramètre 512, protocole à un et quatre threads conservé.
- Les deux bras d'une paire s'exécutent successivement dans la même allocation
  CPU ROMEO, avec le même compilateur GCC et la même affinité. Le worker OAuth
  utilise un cœur distinct des cœurs de mesure. Le conseiller partage le verrou
  des mesures et s'exécute entre celles-ci.
- Budget cible de recherche : 1 800 secondes par bras, conseiller inclus. Le mode
  existant `finish-started` pouvant dépasser cette cible, un plafond indépendant
  et identique de 3 600 secondes couvre tout le parcours, confirmation comprise.
  Le temps effectivement consommé et tout dépassement de la cible seront rapportés.
- Comparer le meilleur programme confirmé avant le plafond commun, ainsi que le
  meilleur résultat correct disponible à la même échéance de recherche. Un bras
  sans livraison confirmée est un échec de livraison, pas un temps nul ni un gain.
- Remesurer les codes retenus des deux bras et le naïf ensemble, avec les mêmes
  entrées et le même protocole de confirmation ; conserver chaque répétition et
  l'ordre des mesures. Ne pas comparer directement des chronométrages de nœuds
  ou de nombres de threads différents.

Les réglages copiés dans `inputs/*/settings.json` sont les **configurations
historiques de provenance**, pas des commandes prêtes à relancer. La préparation
du lancement les a adaptées au protocole ci-dessus, a figé le moteur, les sessions
neuves et le SHA-256 des poids, et a vérifié les empreintes de la suite de validation
distante. Aucun ancien mailbox ni relais PC n'a été repris.

## Critères de lecture

Les [conditions matérielles et la remesure complémentaire](MEASUREMENT-ADDENDUM.md)
précisent le partage du nœud entre allocations. Les scripts dans `reproduction/`
figent les sources, exécutent les paires avec le worker natif, puis exportent les
mesures sans modifier la recherche. `probe_runtime.py` est explicitement un test
sur données synthétiques ; son résultat n'est jamais un speedup de Forest.

Comparer speedup confirmé, temps total, générations et codes corrects, échecs,
appels du conseiller, changements d'ordre, coût et motifs d'arrêt. Les prédictions
restent séparées des mesures. Au moins huit exemples comparables et plusieurs
candidats déjà prêts sont nécessaires avant qu'un avis puisse agir.

Zéro appel validé ou zéro changement d'ordre signifie que cette expérience n'a
pas exercé le rôle du conseiller ; cela ne prouve ni un gain d'apprentissage ni
une inutilité générale de TabPFN. Deux répétitions constituent un premier essai
comparatif, pas une démonstration statistique. SGEMM CUDA n'est pas assimilé à ces
cas CPU : une extension nécessitera son runtime ARM et son protocole GPU conservé.
