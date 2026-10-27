# Conditions matérielles et remesure complémentaire

Ajout préparé après admission des jobs 784224, 784228, 784229 et 784230,
avant livraison de leur premier bras et avant examen des résultats comparatifs.
Le protocole initial et les sources figées des campagnes ne sont pas modifiés.

Les quatre allocations ont été placées par SLURM sur `romeo-c021`. Les cœurs
alloués sont distincts, mais le nœud n'est pas réservé exclusivement à l'étude.
Les caches, la bande passante mémoire et la fréquence peuvent donc varier avec
la charge des autres allocations. Le verrou de Forest empêche son propre
conseiller de concurrencer ses mesures ; il ne verrouille pas le nœud entier.

La remesure commune prévue à la fin de chaque paire est conservée. En complément,
une fois les quatre recherches terminées, tous les codes livrés et le naïf de
chaque programme seront remesurés dans une nouvelle allocation unique, sans autre
recherche de cette étude en cours. Un même compilateur, les mêmes entrées et le
même protocole de confirmation s'appliqueront à tous les candidats d'un programme.
La nouvelle allocation ne sera pas présentée comme un nœud exclusivement réservé.

Ces mesures complémentaires seront rapportées séparément des résultats primaires
par paire. Aucun code ni paramètre de recherche ne sera adapté en fonction des
résultats. Un candidat non confirmé ou livré après le plafond commun sera exclu,
avec le motif enregistré. Les données brutes de confirmation seront conservées.

Les recherches de documentation externes sont désactivées dans les deux conditions,
conformément au défaut de l'application. Les analystes lisent le code et les preuves
internes ; les deux bras ont les mêmes outils et autorisations.

L'interrupteur active la collecte d'exemples et la file du conseiller, qui donne
priorité aux retours Mother/JEV déjà prêts, puis éventuellement les prédictions.
Le contraste porte sur cette option complète. Les écarts sans prédiction ayant
modifié l'ordre ne mesurent pas un bénéfice d'apprentissage ; ils peuvent notamment
venir de la génération stochastique et de l'ordonnancement des retours de contrôle.

## Diagnostic complémentaire sans intervention

Préparé avant clôture des premières recherches : pour chaque bras activé qui n'aura
effectué aucun appel, `replay_advisor.py` prendra les deux derniers codes corrects
distincts enregistrés. Leurs cibles mesurées seront retirées de la requête. Le
contexte sera limité aux exemples observés strictement avant la première capture
de ces deux candidats ; il faudra encore huit exemples antérieurs. Le worker
officiel conservera son filtre de validation interne et son plafond de 20 secondes.

Ce test rétrospectif n'affectera aucun choix de recherche. Son budget est séparé.
Sa précision éventuelle sur une seule paire par campagne sera rapportée comme
diagnostic, jamais comme amélioration du speedup ni comme validation statistique.
