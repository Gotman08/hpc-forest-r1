# Exemple embarqué : multiplication de matrices C/OpenMP

La source canonique est embarquée avec le paquet dans `src/hpc_forest/assets/matmul/`. `hpc-forest init` la copie dans un dépôt de campagne neuf. La validation indépendante se trouve dans `src/hpc_forest/assets/validation/` et est copiée dans `trusted/`, hors du dépôt des candidats.

La tâche génère ses entrées à partir d'une taille et d'une graine. Elle imprime un checksum et, sur demande, toute la matrice pour l'oracle Python. Les temps sont mesurés sur le processus complet. Cette tâche synthétique sert au contrôle de la chaîne ; elle n'est pas un sujet officiel de concours.

Commande d'un binaire compilé : `solution 256 17 4` ; oracle : `solution 17 19 2 full`.
