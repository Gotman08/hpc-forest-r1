# Stockage temporaire et conservation des preuves

La validation 784822 a rencontré le quota strict de **1 500 000 fichiers** sur
le scratch utilisateur. Le volume occupé restait inférieur au quota en octets.
Les 48 302 entrées de cette validation ont été sauvegardées localement dans une
archive vérifiée avant de retirer uniquement son répertoire de tests temporaires.
Les campagnes historiques n'ont pas été supprimées.

Les nouvelles recherches seront exécutées dans un répertoire temporaire privé
du nœud de calcul, avec les mêmes sources, contrôles, compilateur et allocations
CPU. Une archive complète sera remplacée atomiquement sur le scratch persistant
après chaque essai terminé, puis à la fin du bloc. Le moteur ne reçoit aucun
résultat d'une autre condition. Le coût de compression entre essais n'est pas
du temps de recherche et n'augmente aucun budget d'essai.

Une panne du nœud peut perdre la partie du travail postérieure à la dernière
archive. La présence de cette archive ne constitue pas une preuve de reprise.
Toute recherche non terminée sera comptabilisée comme telle, sans remplacement
silencieux. La remesure finale utilisera les programmes livrés des archives,
une fois les six blocs terminés.
