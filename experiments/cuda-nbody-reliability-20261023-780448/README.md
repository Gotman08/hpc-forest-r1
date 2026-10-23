# CUDA N-body — Luna Max — fiabilité — job 780448

Campagne neuve autorisée par « test mtn avec 30min Luna MAX ». Moteur figé au commit `2ee6125b7e716faac2a4551f347156f4f1e71e11`, cible de campagne 1 800 secondes, un GPU GH200 ARM, quatre CPU et 16 Go. L'allocation SLURM de deux heures est une limite de protection, pas une durée de recherche demandée.

Mother choisit N, critique son plan (jusqu'à deux appels, comptés dans le budget), puis les arbres indépendants utilisent TreeQuest AB-MCTS-A. Mémoire active et assemblage guidé par mémoire. Tous les appels utilisent `gpt-6-luna`, effort `max`. Les modèles produisent les sources et le contrôleur compile, vérifie et mesure.

L'original utilisateur, l'énoncé et le protocole sont conservés. L'énoncé est identique à celui de 776290 ; le vérificateur est identique octet pour octet. Aucun candidat, résultat ou sujet d'optimisation historique n'est transmis. `input-audit.json` contient ces vérifications et les empreintes.

Les métadonnées de préparation et de soumission sont archivées ici ; les résultats confirmés seront ajoutés après la fin du job. Le payload, le reçu d'autorisation et les échanges natifs complets restent dans le dossier de travail local `../../../../work/cuda-memory-reliability-20261023`. Aucune publication Git.
