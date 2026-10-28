# Migration vers Forest 0.2

Point de retour complet : `4f6bd15f011511fb7ea93b1ac939aca2f9a81e56`.
Les campagnes et résultats existants restent en place. L'application consulte
les registres sans désérialiser leurs checkpoints TreeQuest.

## Retrait de TabPFN

Les anciennes clés `advisor` et `advisor_runtime`, y compris `enabled: false`,
sont rejetées pour une nouvelle exécution. L'ouverture ne convertit pas une
campagne. Les mesures et décisions historiques restent visibles. Les poids
TabPFN ne sont ni chargés ni supprimés sur ROMEO.

Un ancien projet propose **Créer une copie sans conseiller**. L'action crée une
nouvelle identité, copie les octets vérifiés et conserve documents et filiation
`migration_from`. Les préparations anciennes gardent leur contrat original.

```powershell
python -m hpc_forest.maintenance migrate-config ancien.json nouveau.json
```

Le reçu adjacent conserve l'empreinte de la source et les clés retirées.
Les destinations doivent être nouvelles. Les autres réglages sont conservés :
ni modèle, ni tests, ni cible ne changent. Un profil ROMEO avec `advisor_runtime`
doit être sauvegardé puis corrigé explicitement avant un nouveau lancement.

## Sauvegarde et restauration

Arrêter le serveur puis exécuter `maintenance backup SOURCE DESTINATION`.
Le verrou empêche une copie pendant l'utilisation par la nouvelle application.
Les anciennes versions ne connaissaient pas ce verrou : leur arrêt préalable
est indispensable. La copie SQLite inclut les transactions validées du WAL.
Chaque fichier est vérifié par taille et SHA-256, chaque base par
`integrity_check`. Une copie interrompue sans manifeste complet n'est pas validée.

`maintenance restore SAUVEGARDE NOUVEAU_DOSSIER` vérifie d'abord les fichiers,
refuse un dossier existant, copie puis vérifie les octets. Les liens des vues
internes sont adaptés au nouveau chemin. Les campagnes externes restent des
références répertoriées : elles nécessitent leur propre sauvegarde. Vérifier
aussi les téléchargements et références avant de considérer une restauration
comme utilisable. Ne pas effacer les originaux.

Les missions inachevées restaurées attendent en `recovery_required`.
**Reprendre le suivi** réconcilie uniquement leur identité distante. Sans
identité, une nouvelle préparation explicite est nécessaire. Les missions
terminées ne se relancent pas.

L'ancienne migration additive `tokens_settled` conserve désormais une sauvegarde
SQLite vérifiée avant changement de schéma. Le rapport ouvre le registre en
lecture seule et ne déclenche pas cette migration.

## Arrêt et reprise

Avant soumission, l'arrêt annule la mission. Après soumission, l'intention est
enregistrée, transférée et liée à la mission/session. Le moteur ferme les
admissions aux points de contrôle, attend les essais engagés puis intègre et
confirme. Le délai dépend des essais et appels engagés. Fermer l'application
ne vaut pas demande d'arrêt.

Une panne réseau retarde transfert et suivi. Un ancien moteur figé sans arrêt
propre est signalé comme tel. Panne du nœud, expiration SLURM/OAuth et échec
de génération ne déclenchent aucune nouvelle allocation automatique.
La reprise du suivi n'est pas une promesse de reprise du calcul.

## Imports internes

Les composants de recherche sont regroupés sous `hpc_forest.search` et ceux de
mémoire sous `hpc_forest.memory`. Par exemple, `search_policy` devient
`search.policy`, `binary_search` devient `search.binary` et `memory_store` devient
`memory.store`. `from hpc_forest.search import Search` reste valide. Les commandes
publiques restent disponibles ; les intégrations utilisant ces anciens modules
internes doivent adapter leurs imports. Les scripts d'expérience archivés se
reproduisent avec leur révision et leur environnement d'origine.
