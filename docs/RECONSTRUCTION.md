# Décisions de reconstruction

La base retenue est le R1 figé, dont le manifeste vérifie 89 fichiers. Le noyau
générique plus récent ne contient pas toutes ses protections de harnais et de
réserve de confirmation ; il n'est donc pas substitué à cette base.

Les modifications sont limitées aux responsabilités suivantes :

- Une lecture bornée et déterministe des sources, commune à la mère, aux requêtes
  de génération et aux contrôles de développement. Les liens de sources sont
  refusés et un dépassement n'est jamais tronqué.
- Un schéma de proposition indépendant des transports et un seul constructeur
  des messages pour les transports natif et Ollama ; le bloc dupliqué est supprimé.
- Une définition partagée des échéances de recherche et de génération, utilisée
  par le contrôleur, le registre, le harnais et le transport.
- Des validations numériques communes : booléens, nombres non finis, comptes
  négatifs et phases inconnues sont refusés avant de modifier un budget.
- Une commande de vérification qui transmet explicitement le nouveau chemin
  d'import aux sous-processus, sans modifier l'environnement historique.
- La prise en charge des chemins longs dans chaque commande Git sous Windows,
  sans modifier la configuration Git globale ou celle des dépôts utilisateurs.

L'échelle de score, les liens de parenté, la politique TreeQuest, les données de
confirmation et la distinction erreur d'infrastructure / programme incorrect
restent inchangés. Aucun gain de vitesse du contrôleur n'est revendiqué sans mesure.

Le premier contrôle de la copie a produit 190 réussites, trois sauts pour GCC/G++,
et un échec d'import dans un sous-processus qui chargeait le projet générique.
Le même test passe lorsque les imports sont explicitement rattachés à cette copie.
Les deux reçus sont conservés dans artifacts/ ; cette erreur ne devient pas un
échec du modèle ni un résultat scientifique.

Le premier contrôle ciblé après factorisation a détecté deux différences de
messages entre transports, liées à la copie indépendante du constructeur dans
Ollama et au traitement des fins de ligne Windows. Le constructeur et le schéma
sont désormais partagés ; les tests d'égalité historiques restent inchangés et
passent dans le contrôle ciblé suivant.

La première suite complète de la reconstruction a détecté une limite de longueur
de chemin de Git dans un snapshot de développement. L'appel Git utilise maintenant
core.longpaths uniquement pour la commande en cours ; une régression dédiée vérifie
des chemins d'objets Git de plus de 260 caractères et l'absence de réglage persistant.
Le répertoire de travail passé à Git reste inférieur à cette limite : un essai
supplémentaire a montré que l'initialisation de Git avec un répertoire lui-même
plus long n'est pas prise en charge par le Git installé, même avec ce réglage.

La suite complète suivante passe : 237 tests et trois sauts GCC/G++. Le pilote
natif demandé ensuite ajoute onze vérifications de son autorisation et de son
manifeste ; la suite complète correspondante passe avec 248 tests et trois sauts.
Sa préparation n'admet aucun ancien essai. Un premier démarrage ARM passe les
15 contrats de compilation/exécution puis refuse l'alias de chemin scratch avant
tout appel modèle. La comparaison des chemins est corrigée par résolution des
deux côtés ; Ruff et les onze tests du pilote passent ensuite. Ce démarrage et son
échec sont conservés, et un nouveau dossier porte le démarrage corrigé.
