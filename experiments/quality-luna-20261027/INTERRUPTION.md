# Première tentative interrompue : défaut du schéma des citations

Les recherches 786342 à 786345 ont été arrêtées volontairement après environ 5 min 20 s. Les journaux, les bases et les programmes sont conservés sur ROMEO et dans une archive vérifiée localement. Aucun résultat de cette tentative ne constitue une comparaison complète avec/sans TabPFN.

Le schéma JSON envoyé à GPT-6 Luna Max imposait la même empreinte SHA-256 dans trois champs qui devaient être distincts : `evidence_id`, `path` et `sha256`. Le modèle suivait ce schéma, puis le validateur de Forest rejetait logiquement les références. Les analyses détaillées du code produites par Luna ne pouvaient donc pas être admises.

Cause confirmée : `deepcopy` conservait l'alias du dictionnaire `TEXT` partagé par les trois propriétés. L'ajout successif de leurs valeurs autorisées remplaçait les trois par la dernière empreinte. La correction crée une propriété indépendante avant sa spécialisation. Les contraintes de provenance et de lignes restent strictes.

Les fichiers `defect-evidence/request.json` et `response.json` contiennent un exemple réel reçu sur ROMEO. Les nouveaux tests vérifient le trajet du schéma natif vers le validateur, pour l'analyste et Mother, ainsi que l'isolation des différentes références : trois échecs reproduits avant correction, trois réussites après.

Le contrat actif devient `hpc-forest-active-v3-citation-identities` afin d'imposer une nouvelle campagne. La reprise est enregistrée séparément dans `../quality-luna-20261027-r2`. Aucun candidat ni conseil de la tentative interrompue n'est importé dans ces nouvelles mémoires.

La phase de rapport 786346 a également révélé un défaut de gestion des interruptions : un résultat final absent provoquait une erreur d'audit. Le lecteur de rapport de la nouvelle tentative traite cette absence comme une non-livraison. Cette correction concerne le rapport, pas les décisions de recherche.

Archive complète : `quality-luna-20261027-interrupted-evidence.tar.gz`, SHA-256 `94ae4a6efebdca0d8369b23a8537bbded3d6607d441eb7c0d00ec783c3a18c6c`. Copie locale dans le dossier de travail `work/quality-luna-20261027/interrupted-evidence.tar.gz` du chat. Les originaux distants sont conservés.
