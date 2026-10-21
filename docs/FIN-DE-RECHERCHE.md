# Fin de recherche : terminer le travail engagé, puis intégrer

Les nouvelles configurations utilisent `completion.policy = "finish-started"`.
Elles utilisent une **durée cible configurable**, une **réserve adaptative**,
des **cycles répétés sans plafond d'essais** et la **confirmation obligatoire
de G final**. La même logique s'applique à 30 minutes, 2 heures, 5 heures ou
24 heures : aucune durée de phase n'est fixée à 27 ou 3 minutes.
Le timer limite l'admission de nouvelles missions de recherche. Il ne coupe plus
une mission déjà admise, ses réparations de développement ni son évaluation.
Cette politique s'applique au binaire et à AB-MCTS-A, sans changer leurs règles
de sélection.

## Déroulement

Le mode [forêt choisie par Mother](FORET-MOTHER.md) généralise A/B/C en N sujets
définis par le modèle. Tous les N arbres AB-MCTS démarrent ensemble à chaque
passe ; leur concurrence est N et ne se règle pas séparément. La première
passe continue la planification Mother déjà engagée. Les passes suivantes
utilisent la réserve adaptative avant d'admettre l'ensemble des N arbres.
Dans le profil natif v7, les N arbres poursuivent leurs passes AB-MCTS jusqu'à
la fermeture des admissions. **La conversation initiale de Mother reprend
ensuite pour assembler leurs meilleurs programmes mesurés deux par deux**.
Chaque assemblage est mesuré ; le dernier G est confirmé indépendamment. Cette
transition est définitive : aucun arbre ne peut être lancé ou relancé après
le retour à Mother. Il n'y a ni nouvelle mère de synthèse ni modèle G séparé.
Mother ne reçoit pas le temps disponible lors du choix de N. Le contrôleur
estime la durée des assemblages successifs dans sa réserve adaptative ; la
compaction de l'historique reste celle de Codex CLI dans la conversation initiale.
Les anciens profils conservent la séquence A/B/C et G ci-dessous.

1. Répéter les cycles A/B/C puis G tant qu'une nouvelle mission et la
   finalisation estimée tiennent dans le temps restant.
   Le profil natif utilise une profondeur illimitée et aucun quota de tokens.
2. À l'échéance, fermer les admissions. Les missions admises terminent leur
   génération, leur développement et leur mesure ; aucun nouveau fils de
   recherche n'est créé. Les lots ne dépassent pas le nombre de workers.
3. Fermer définitivement la recherche de cet epoch. Exécuter une **nouvelle
   synthèse Mother**, qui voit les dernières productions, puis **une mission G
   finale** sur l'ensemble des programmes corrects distincts archivés. Cette
   étape a lieu même si aucun G de recherche n'a pu démarrer. Si aucun fils
   n'est admissible, la référence validée sert de source à G.
4. Confirmer indépendamment la référence, les meilleurs candidats **et G
   final, quel que soit son rang**. Avec trois places ordinaires, cela donne
   au besoin quatre programmes : référence + deux finalistes + G final.
   Aucun finaliste n'est évincé pour ajouter G. Élire le meilleur programme
   confirmé, puis produire le rapport et `submission.zip`. Dans le pilote
   officiel, `DONE.json` est écrit après cette séquence, ou avec un échec
   explicite si une erreur empêche sa réussite.

La durée est `budget.wall_seconds`. À chaque admission, le contrôleur estime
le coût de la prochaine passe et de la finalisation complète. Dans le mode
Mother persistant, **les passes de recherche et les fusions sont estimées
séparément** :

- Une passe est chronométrée une seule fois, de la préparation des N contextes
  jusqu'à la fin des générations et des évaluations. Sa durée inclut déjà les
  attentes et les mesures sérialisées ; elle n'est pas multipliée par N.
  Les historiques distinguent les passes de tailles différentes.
- La prévision utilise la médiane des cinq dernières passes de même taille.
  Une réparation isolée n'impose donc plus son coût à toutes les admissions
  suivantes ; un ralentissement persistant fait remonter l'estimation.
- Chaque fusion utilise la médiane de ses cinq dernières durées observées
  (`mission:G`). Avant la première fusion mesurée, l'amorce est un appel
  nominal de 120 secondes, plus le coût observé d'une évaluation. Elle ne
  reprend ni la passe de recherche la plus lente ni le maximum de réparations
  possibles. Le coût total suit les `max(1, N−1)` assemblages à exécuter.
- La confirmation indépendante et l'archive restent réservées. La marge est
  de 25 % sur les travaux prévus, plus 10 secondes de sécurité.

Les anciennes politiques à arbres fixes conservent le maximum des douze
dernières durées observées. Ces valeurs restent des prévisions de temps,
jamais des délais d'annulation, et ne sont pas communiquées à Mother pour
choisir N.

Régression vérifiée sur les latences de la campagne 772311 : l'ancien calcul
réservait 709 s pour finir et refusait une quatrième passe avec encore
1 019 s disponibles. La nouvelle réserve est d'environ 334 s et la passe
suivante d'environ 260 s : elle est admise. En répétant ensuite la dernière
durée de passe observée, une simulation obtient six passes au lieu de trois
et une fin vers 27 min 45 s, fusions et confirmation incluses. Ce rejeu
teste l'ordonnancement ; il ne constitue pas un nouveau benchmark de modèle.

Exemple : pour une cible de 30 minutes, s'il reste 6 minutes et que le prochain
sommet est estimé à 2 minutes et la finalisation à 5 minutes, aucun nouveau
sommet n'est lancé. Si ces mêmes coûts sont observés dans une campagne de
5 heures, la réserve reste de 5 minutes ; elle ne devient pas un pourcentage
fixe des 5 heures. Les prévisions, leur détail et les temps observés sont
persistés dans le registre et exportés dans `report/experiments.json`.

Une mission engagée, Mother, G et les mesures de confirmation finissent même
après la durée cible. Le dépassement réel est enregistré. La durée d'un appel
modèle étant imprévisible, ce dépassement ne peut pas être garanti petit.
Les timeouts techniques des compilations et programmes candidats restent actifs.

## Temps, appels et consommations

La génération d'une mission admise et la phase Mother/G finale n'ont pas de
timeout applicatif de génération : les requêtes portent `expires_at = null` et
la politique explicite `finish-started`. Le délai de génération hérité de 600 s
ne les interrompt pas. Les appels et consommations restent enregistrés.

La phase `postprocess` possède au plus deux réservations par epoch : une pour
Mother et une pour l'épisode G. Le profil Mother v6 utilise une seule
réservation : la reprise de Mother produit directement le code G. L'épisode
conserve son nombre fini de
tentatives de développement ; il ne crée pas d'autres fils de recherche.

Les nouvelles configurations et le profil natif ne fixent aucun plafond
applicatif de tokens, ni global, ni par mission, ni par appel :

```json
{
  "budget": {
    "tokens": null,
    "mission_tokens": null
  },
  "completion": {
    "policy": "finish-started",
    "postprocess_tokens": null,
    "reserve_policy": "adaptive",
    "confirm_final_g": true
  },
  "schedule": {"cycles": null, "trials_per_role_per_cycle": 2, "integrations_per_cycle": 2}
}
```

`null` signifie illimité ; aucun énorme quota artificiel ne le remplace.
`budget.search_slots = null` retire aussi le plafond de sommets et
`budget.max_depth = 0` retire le plafond de profondeur. `confirmation_slots`
définit les finalistes ordinaires ; G final a sa place supplémentaire si besoin.
Une consommation supérieure à l'ancienne réservation de 196 608 tokens est
enregistrée sans rejeter le programme. Un usage final manquant reste déclaré
inconnu, sans inventer de borne ni bloquer les prochaines admissions ou
réparations. Les véritables erreurs de génération restent signalées.

`phase_costs` distingue recherche, post-traitement et confirmation ; `costs`
conserve le total des consommations établies et le nombre d'usages inconnus.
Le comparateur vérifie la politique de fin, les coûts séparés et la présence
de G final ; il refuse toujours une comparaison scientifique dont la
comptabilité est incomplète. Cette vérification ne bloque pas la recherche.

Les limites techniques de compilation, de correction et d'exécution d'un
programme candidat restent appliquées. Un programme incorrect ou bloqué ne
doit pas retenir indéfiniment l'évaluateur. Un G incorrect n'efface pas les
programmes corrects précédents : la confirmation peut conserver un ancêtre ou
la référence.
Un G incorrect est confirmé comme rejeté et ne peut pas gagner. Un G sans
programme commité est signalé comme indisponible : le pipeline ne prétend pas
avoir réussi sa confirmation. Une reprise ne relance pas Mother ou G.

## Relais et reprises

Le relais reste actif jusqu'à `DONE.json`, y compris après la fenêtre de
recherche. Il publie un signal de présence toutes les dix secondes pendant
l'inférence. Le contrôleur ne fixe pas de durée maximale au modèle tant que ce
signal continue ; une absence de signal pendant trois minutes est une panne de
relais explicite, avec usage déclaré inconnu si le compteur final manque.

Les demandes et réponses restent liées à leur session, nonce et empreinte.
Une réponse à une mission admise peut être reçue après l'échéance de recherche.
Les appels déjà engagés et la finalisation ne sont pas rejoués après une
interruption dont l'usage final est inconnu. Les protections de reprise et les
meilleurs programmes déjà enregistrés restent conservés.

La liste de confirmation et les résultats sont persistés. Le profil adaptatif
ne coupe pas les mesures à l'échéance globale. Une nouvelle invocation de
`confirm` ne reprend pas les appels modèles ni les mesures déjà enregistrées.
Pour les longues campagnes, les requêtes traitées sont déplacées dans
`mailbox/archive/requests/` : toutes les preuves sont conservées et la boîte
active ne dépasse plus sa limite de listing. Au-delà de 24 sources, toutes
leurs identités et mesures restent visibles ; les diffs détaillés portent sur
les deux meilleurs et deux plus récents programmes de chaque rôle, afin de ne
pas grossir indéfiniment les messages. L'archive des programmes reste complète.

## Campagnes nouvelles et historiques

Préparer un prochain pilote officiel Luna MAX :

```powershell
python tools/prepare_smoke.py --duration 2h
python tools/prepare_smoke.py --duration 2h --binary-tree
```

Remplacer `2h` par `30m`, `5h`, `24h`, etc. Ces commandes préparent le nouveau
scope `r1-official-luna-max-adaptive-v4`, sans plafond de cycles, d'essais,
de profondeur ou de tokens. Elles ne lancent ni modèle ni job.

Pour une campagne locale, `hpc-forest init campagne --duration 2h --backend codex`,
puis `hpc-forest run campagne` exécute aussi automatiquement la confirmation,
le rapport, `submission.zip` et `DONE.json`. Une exécution partielle avec
`--max-batches` conserve un checkpoint tant que la recherche peut continuer.

Le profil explicite `--depth-comparison` reste le contrat v3, à cycles finis et
réserve fixe de 120 secondes. Les configurations finies existantes conservent
leur contrat ; utiliser `--duration` lors d'une nouvelle initialisation pour
activer le nouveau fonctionnement.

Les campagnes et scopes historiques gardent leur contrat strict. Une
configuration gelée sans champ `completion` conserve la politique `hard` ;
aucun registre historique n'est converti et leurs quotas enregistrés sont
conservés. Un nouveau protocole demande une
nouvelle campagne et ne remplace pas les anciennes mesures.

L'absence de timer applicatif ne supprime pas les limites du serveur de modèle,
de la machine ou de SLURM. L'allocation d'hébergement doit couvrir la recherche,
sa fin de traitement, Mother/G et la confirmation ; une allocation SLURM de
30 minutes ne suffit plus à garantir cette séquence. Aucune allocation n'est
créée ou prolongée automatiquement par ce changement.
