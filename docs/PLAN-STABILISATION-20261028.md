# Stabilisation de Forest — 28 octobre 2026

Point de retour : `4f6bd15f011511fb7ea93b1ac939aca2f9a81e56`, synchronisé avec
`origin/main` à l'ouverture du chantier. L'arbre de travail était propre.
Le nom reste Forest. Le développeur de ce chat et les modèles du produit sont
distincts : Forest conserve GPT-6 Luna, effort max, sans mélange par défaut.

## Périmètre et décisions

La demande autorise l'implémentation et les choix techniques réversibles.
Le processus du skill `ameliore` est adapté à cette autorisation : plan écrit,
lots vérifiés, aucune nouvelle demande d'approbation du plan, aucune publication.
Aucune allocation ROMEO n'est nécessaire aux premiers lots.

- Un seul produit et un seul moteur ; les archives ne sont pas des variantes
  installables du produit.
- Retirer le conseiller TabPFN, son runtime, ses propositions alternatives et
  ses contrôles. Garder Mother, les analystes, la mémoire de preuves, l'archive
  de codes mesurés et la politique TreeQuest réelle.
- Une ancienne campagne conserve son contrat. La consultation doit fonctionner
  sans charger les checkpoints exécutables. Une configuration incompatible doit
  être refusée explicitement ; la migration prépare une nouvelle campagne.
- Les sources, validations, résultats, journaux et worktrees historiques sont
  conservés. Les tests de correction des campagnes ne sont pas modifiés.
- Déploiement pris en charge : application personnelle locale et exécution de
  code de confiance dans le compte ROMEO de son utilisateur. Aucun service
  multi-utilisateur ou isolement hostile n'est présumé.

## Constats initiaux

TabPFN est couplé à la configuration, à `Search.ask`, aux deux ordonnanceurs,
au contrôleur, aux rapports et au formulaire d'application. La base de
l'application dispose d'une contrainte d'unicité par préparation, mais les
mises à jour lisent puis réécrivent un document entier. L'écriture JSON utilise
un fichier temporaire fixe sans synchronisation sur disque. Les reprises
distantes distinguent déjà une soumission incertaine d'un échec certain.
L'arrêt propre n'est pas encore proposé par l'interface.

Deux instances existantes ont été repérées : ports 8767 et 8768, stockages
`work/application-state` et `work/application-sakana-state` de l'espace du
23 octobre. Leur inventaire et leur sauvegarde précèdent toute consolidation.

## Lots et vérification

1. **Conseiller retiré** : enlever les chemins actifs et la dépendance ; archiver
   le code et les tests spécifiques ; lecture historique et refus explicite des
   anciens réglages ; tests de sélection TreeQuest, de contrats et d'interface.
2. **Persistance** : primitives d'écriture atomique durables ; transactions des
   mises à jour ; verrou d'instance ; sauvegarde SQLite cohérente et restauration
   vérifiée ; tests de panne, concurrence et reprise de soumission incertaine.
3. **Parcours** : arrêt explicite, reprise sûre et diagnostics ; frontières de
   confiance des fichiers, commandes, journaux et secrets ; tests API, navigateur
   et parcours complet avec connecteur simulé. Tout test ROMEO supplémentaire
   éventuel aura un objectif borné et un reçu séparé.
4. **Distribution** : conventions de dossiers et responsabilités ; installation
   depuis une wheel propre, dépendances figées, CI, notes de migration, notices
   et limites de licence ; suite Python, Ruff et tests JavaScript complets.

Les preuves préciseront ce qui est testé, ce qui ne l'est pas, et les limites de
restauration et d'exécution. Les résultats de performance existants ne seront
pas attribués au nouveau code sans mesure.

## Avancement

Les quatre lots sont implémentés. Le conseiller et ses tests sont archivés avec
leurs empreintes ; les imports de recherche et de mémoire sont regroupés. Les
tests ciblés de persistance, migration et arrêt passent, ainsi que les tests du
paquet installé. Le parcours navigateur est vérifié jusqu'au téléchargement et
à la migration d'une copie. Les deux stockages sont sauvegardés et regroupés,
avec préservation de la variante de contrat et des dossiers originaux.

La validation est terminée : passage complet puis reprise ciblée d'un test
d'archive, soit 1 114 cas validés et trois exclusions documentées. La CI est
configurée mais n'a pas été exécutée sur le service. Aucun nouveau job ROMEO,
push ou acte de publication n'a été réalisé. Les preuves finales et les limites figurent dans
[le rapport de validation](VALIDATION-STABILISATION-20261028.md).
