# Archives complètes conservées localement

Les sources du moteur, exemples, tests, rapports, registres de campagne,
résultats confirmés et exports CUDA sont versionnés. Les quatre `evidence.zip`
listés dans [local-evidence-manifest.json](local-evidence-manifest.json) restent
intacts dans leurs dossiers d'origine, mais sont exclus de Git parce qu'ils
contiennent les reçus locaux `authorization.json` déjà exclus séparément par
la politique du dépôt.

Les attributs Git de ce dossier désactivent la conversion automatique des fins
de ligne afin de préserver les octets des preuves et leurs empreintes.

Le manifeste conserve la taille et l'empreinte SHA-256 de chaque archive.
Cette exclusion ne signifie pas qu'un secret d'accès a été trouvé : elle
évite de publier indirectement les attestations d'autorisation au sein des
archives. Les exports `submission.zip` et les deux exports confirmés de la
campagne 774157 ne contiennent pas ces reçus et sont versionnés.

Une copie Git seule ne contient donc pas tous les échanges natifs ni tous
les instantanés présents dans les archives locales. Conserver ces fichiers
avec les sauvegardes de l'espace de travail pour une restauration complète.
