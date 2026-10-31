# Frontières de confiance

Déploiement pris en charge : **personnel et local**, sur machine de confiance,
avec accès ROMEO propre à l'utilisateur. Le serveur écoute en boucle locale.
Host, Origin et l'en-tête d'écriture limitent le rebinding DNS et les écritures
depuis une page tierce ; ce n'est pas une authentification multi-utilisateur.
Ne pas publier ce serveur sur Internet ou un réseau partagé.

L'import ne lance aucune commande. Traversées, liens, collisions et chemins
ambigus sont refusés ; les tailles sont bornées. L'original, ses empreintes,
le contrat et les validations sont conservés. Seules les sources autorisées
sont superposées à la copie évaluée. Documents et sorties restent des données.

La compilation et les programmes importés/générés **s'exécutent avec les droits
du compte ROMEO**. Les restrictions de fichiers et empreintes détectent certains
écarts ; elles ne sont pas un bac à sable OS. Un programme hostile sous le même
UID pourrait accéder à d'autres fichiers ou processus, y compris au profil
OAuth. Une offre pour plusieurs clients ou dépôts hostiles exige une séparation
de comptes/identités et un isolement supplémentaire vérifié.

Le protocole d'évaluation 2 ne stocke plus les réponses de confirmation : graines
tirées au moment de la confirmation, sorties de contrat recalculées par la
référence protégée. Sous le même UID, sans bac à sable, l'agent peut encore lire
les entrées et la référence et recalculer ces réponses : la mesure empêche la
lecture directe des réponses attendues, pas une triche délibérée en plusieurs
étapes. Pour un projet de l'application, la confirmation reste la commande de
test fournie et ses données.

Les variables contenant jetons, clés, mots de passe et agents SSH sont retirées
avant les commandes du protocole d'application. Cela réduit leur propagation
accidentelle sans isoler le système de fichiers. Les commandes shell sont celles
du contrat saisi, et s'exécutent uniquement après lancement autorisé.

OAuth reste dans le profil privé distant ; la connexion est vérifiée par la CLI
officielle. Forest n'exporte pas le fichier des jetons. Les bundles contiennent
le code produit, ses ressources et les entrées figées. L'interface ne recopie pas
le contenu brut des exceptions du connecteur. Un programme peut lui-même écrire
des secrets : les journaux, sauvegardes et archives brutes restent privés et ne
doivent pas être publiés sans examen.

Pour dsh-romeo, le bundle conserve uniquement l'adresse de la passerelle et le
chemin d'un fichier privé distant contenant sa clé. Cette clé est lue à l'appel
et passée dans l'environnement du client Codex ; elle ne figure ni dans ses
arguments ni dans les contrats. Le contrôleur ne reçoit pas cette clé par
l'environnement du worker. Comme le profil OAuth, le fichier reste accessible
aux programmes exécutés sous le même compte : ce mode suppose un code de confiance.

Les checkpoints locaux TreeQuest utilisent pickle et sont exécutables à la
lecture. Ne reprendre que ses propres campagnes de confiance. L'application
consulte SQLite en lecture seule sans charger ces checkpoints. Le rapport d'une
ancienne campagne TabPFN reconstruit sa filiation depuis les essais enregistrés.

Transactions, verrous et transitions conditionnelles empêchent les mises à jour
perdues et doubles soumissions dans les chemins testés. Une incertitude réseau
n'autorise pas une resoumission aveugle. Ces garanties ne couvrent pas corruption
matérielle, administrateur hostile, restauration manuelle incohérente ou perte
du stockage distant. Les tests démontrent des propriétés précises, pas une
absence absolue de panne.
