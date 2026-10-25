# Forest : corrections des analyses et des fermetures — ROMEO

Toutes les recherches corrigées utilisent **GPT-6 Luna, effort max**, y compris Mother, les arbres, les analystes et l’intégration. Le moteur a été corrigé par Codex ; Luna est le modèle qui exécute les rôles pendant les expériences.

## Comparaison des programmes livrés

Les trois générations de programmes sont **remesurées dans une même allocation par cas**. La colonne « gain sur précédente » vaut temps de la version active précédente / temps de la version corrigée. Une valeur supérieure à 1 indique un programme corrigé plus rapide.

| Cas | Historique avant architecture active | Active précédente | Corrigée | Gain sur précédente | Plage des rapports par bloc |
|---|---:|---:|---:|---:|---:|
| SGEMM 4096² | 5.644 ms | 11.872 ms | 5.008 ms | 2.37× | 2.35–2.39× |
| UTF-8 65 536 octets, moyenne | 13.356 µs | 29.317 µs | 5.953 µs | 4.92× | 4.87–4.96× |
| Mandelbrot 1 thread | 49.126 ms | 150.316 ms | 151.364 ms | 0.99× | 0.99–0.99× |
| Mandelbrot 4 threads | 12.482 ms | 37.952 ms | 38.237 ms | 0.99× | 0.99–1.00× |

Les répétitions servent à observer la variabilité des mesures. Il n’y a **qu’une recherche stochastique par programme et par architecture** : elles ne démontrent pas une supériorité statistique de la stratégie.

## Ce qui a été corrigé

- Le JEV reçoit des extraits du dernier candidat de son arbre, de sa base et de comparateurs autorisés, avec différences, empreinte du fichier et lignes numérotées. Un rapport terminé doit citer le code exposé.
- Un premier candidat correct ou un progrès mesuré déclenche une revue et une courte suite protégée, bornée à deux essais et à une enveloppe estimée de 15 % du budget de recherche disponible au démarrage. La réserve d’intégration et de confirmation reste prioritaire.
- Un résultat nouveau invalide une décision d’arrêt prise sur des preuves périmées. Un progrès tardif peut réactiver un arbre suspendu.
- Une fermeture se fait en deux temps : arrêt des nouvelles admissions et fin des essais déjà admis, puis bilans à jour et nouvelle décision. Les hypothèses du dernier bilan doivent être examinées.
- Le contrôleur distingue fermeture revue, absence de travail admissible après revue et réserve/échéance. Une erreur d’analyste reste une analyse indisponible, sans score inventé.

Les citations prouvent la provenance des extraits, pas la justesse de l’interprétation du modèle. La sélection AB-MCTS et les récompenses mesurées conservent leur rôle.

## Recherche, arbres et arrêts

| Cas / version | Job recherche | Cible | Durée moteur | Essais validés par le protocole / total | Arbres initiaux + créés | Première fermeture acceptée | Fermeture confirmée | Motif final |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| SGEMM / historique | 781115 | 1800 s | — s | 14 / 15 | 2 + 0 | — | — | non instrumenté dans cette version |
| SGEMM / active précédente | 783179 | 1800 s | 1504.6 s | 18 / 18 | 3 + 2 | 1011.8 s | — | non instrumenté dans cette version |
| SGEMM / corrigée | 783357 | 1800 s | 1569.8 s | 13 / 13 | 3 + 0 | 685.3 s | — | final_reserve_or_deadline |
| UTF-8 / historique | 781330 | 7200 s | 7046.0 s | 63 / 63 | 2 + 0 | — | — | non instrumenté dans cette version |
| UTF-8 / active précédente | 782964 | 7200 s | 1979.7 s | 19 / 21 | 3 + 1 | 1798.0 s | — | non instrumenté dans cette version |
| UTF-8 / corrigée | 783901 | 7200 s | 6096.0 s | 45 / 45 | 3 + 3 | — | — | no_admissible_work_after_idle_review |
| Mandelbrot / historique | 781328 | 7200 s | 6862.8 s | 58 / 59 | 2 + 0 | — | — | non instrumenté dans cette version |
| Mandelbrot / active précédente | 783044 | 7200 s | 1873.0 s | 23 / 24 | 3 + 4 | 1613.3 s | — | non instrumenté dans cette version |
| Mandelbrot / corrigée | 783902 | 7200 s | 6882.5 s | 59 / 61 | 3 + 6 | — | — | final_reserve_or_deadline |

Le compte des essais validés reprend le protocole figé de campagne ; il ne garantit pas la correction sur toutes les entrées possibles. L’audit supplémentaire UTF-8 est présenté séparément. La durée moteur comprend planification, recherche et confirmation ; elle se distingue du temps d’exécution du programme livré. Les appels admis finissent même si la cible temporelle est atteinte. Les arbres créés incluent les intégrations intermédiaires, détaillées dans `trees.csv`. Dans la version active précédente, une seule décision fermait la recherche : la colonne de seconde confirmation ne s’applique pas.

| Cas corrigé | Meilleur temps de recherche avant la première demande acceptée | Meilleur mesuré ensuite | Évaluations correctes après cette demande |
|---|---:|---:|---:|
| SGEMM | 6.353 ms | 8.984 ms | 3 |
| UTF-8 | — | — | 0 |
| Mandelbrot | — | — | 0 |

| Cas corrigé | Première proposition de fermeture, même rejetée | Fermetures rejetées | Suspensions rejetées | Revues sans arbre actif |
|---|---:|---:|---:|---:|
| SGEMM | 645.2 s | 1 | 1 | 0 |
| UTF-8 | 1451.2 s | 2 | 7 | 2 |
| Mandelbrot | — | 0 | 5 | 2 |

Lorsque tous les arbres sont suspendus, le contrôleur peut aussi déclencher une revue sans demande explicite `close`. Cette revue bornée laisse une chance de réorienter la recherche avant de conclure qu’aucun travail n’est admissible. Les horaires sont dans `engines.csv`.

Les meilleurs temps des candidats autour de la demande acceptée proviennent de l’exploration, avant la confirmation et la remesure appariée. Ils incluent les essais déjà admis qui se terminent pendant le drainage et les intégrations intermédiaires, mais excluent G final. Ils ne suffisent pas à attribuer causalement un gain aux protections.

## Travail des analystes

| Cas / version active | Appels JEV | Bilans terminés | Bilans citant le code | Bilans citant le code du dernier candidat propre | Citations vérifiées | Lectures explicites de source | Analyses indisponibles |
|---|---:|---:|---:|---:|---:|---:|---:|
| SGEMM / précédente | 11 | 6 | 0 | 0 | 0 | 0 | 0 |
| SGEMM / corrigée | 12 | 5 | 5 | 4 | 21 | 0 | 1 |
| UTF-8 / précédente | 14 | 6 | 0 | 0 | 0 | 0 | 0 |
| UTF-8 / corrigée | 34 | 17 | 17 | 16 | 59 | 1 | 0 |
| Mandelbrot / précédente | 19 | 8 | 0 | 0 | 0 | 0 | 0 |
| Mandelbrot / corrigée | 44 | 21 | 21 | 18 | 79 | 0 | 0 |

Les nouvelles requêtes contiennent déjà du code : l’absence de lecture explicite supplémentaire ne signifie donc plus l’absence de source dans le contexte. Un dernier essai interrompu avant la proposition de code peut ne fournir aucune source propre à citer ; ce cas est distingué dans les données. Le dernier code est reconnu par chemin et SHA-256, même si le JEV cite la proposition archivée qui contient exactement ce fichier ; le comptage par identifiant exact reste aussi disponible dans le CSV. `analyst_reports.csv` conserve les mécanismes, hypothèses, incertitudes et citations ; `trials.csv` conserve les identifiants des avis transmis aux essais.

### Coût du contrôle et des analyses

| Cas / version active | Appels natifs totaux | Tokens connus normalisés | Appels avec usage inconnu | Somme des durées JEV | Somme des durées Mother aux jalons |
|---|---:|---:|---:|---:|---:|
| SGEMM / précédente | 48 | 3262349 | 0 | 299.0 s | 278.4 s |
| SGEMM / corrigée | 37 | 2872244 | 0 | 572.8 s | 292.6 s |
| UTF-8 / précédente | 61 | 3336199 | 0 | 496.8 s | 342.5 s |
| UTF-8 / corrigée | 136 | 11469066 | 0 | 2295.0 s | 1991.1 s |
| Mandelbrot / précédente | 68 | 4234462 | 0 | 653.6 s | 389.9 s |
| Mandelbrot / corrigée | 176 | 14053621 | 0 | 2548.1 s | 2411.7 s |

Les durées des appels peuvent se chevaucher avec la recherche : elles ne s’additionnent pas à la durée totale. Les tokens connus sont normalisés pour éviter de recompter les compteurs cumulés de Mother ; ils ne représentent pas un coût monétaire. Les phases détaillées sont dans `durees.csv`.

| Cas corrigé | Revues Mother indisponibles | Motifs |
|---|---:|---|
| SGEMM | 1 | Invalid hypothesis review (1) |
| UTF-8 | 1 | Invalid hypothesis review (1) |
| Mandelbrot | 1 | Mother decision is not bound to this forest snapshot (1) |

Ces revues n’ont produit aucune décision admise. Une confirmation finale réussie ne transforme pas une revue invalide en fermeture confirmée.

## Audit détaillé des cas

### SGEMM

Le moteur a réalisé 11 essais de recherche dans les trois arbres initiaux, puis deux essais d’intégration finale G. Les 13 programmes ont passé le protocole de correction. La politique AB-MCTS a conservé ses choix de parents ; aucun ancien gagnant n’a été fourni à la recherche.

À 560 s, une suspension T2 est rejetée parce que de nouveaux résultats sont arrivés. À 645 s, une fermeture est rejetée pour la même raison. La demande de fermeture acceptée à 685 s suspend les nouvelles admissions et laisse finir les essais en cours. Après les bilans, Mother choisit à 1 154 s de continuer T1 et de suspendre T2/T3. La réserve finale ne permet ensuite pas un nouvel essai de recherche : le motif réel est `final_reserve_or_deadline`, sans fermeture globale confirmée. Il faut donc distinguer la décision de continuer et l’admission effective d’un nouvel essai.

Le programme livré utilise des tuiles 64×64×64, un micro-bloc de 8×2 résultats par thread, des copies `cp.async` de 16 octets quand l’alignement le permet, et deux tampons en mémoire partagée. La version active précédente restait sur un bloc en registres 2×4 par thread sans tuilage partagé. L’intégration a combiné le tuilage T1 et le chargement asynchrone T3, puis essayé BK=64. La variante synchrone BK=64 avait régressé dans T1 (9,149 ms contre 6,353 ms pour BK=32), mais elle a fourni une modification réutilisable dans la combinaison finale. Cela illustre l’intérêt de conserver une variante correcte même si son gain isolé est négatif ; ce tirage ne prouve pas la contribution causale de chaque mécanisme.

Les cinq bilans JEV acceptés citent du code, avec 21 citations vérifiées. Ils distinguent notamment coalescence, shuffles, réutilisation et copies asynchrones des effets réellement mesurés. Une première analyse T1 a tenté un outil non autorisé : elle a été marquée indisponible et n’a pas donné lieu à un avis appliqué.

Une revue Mother intermédiaire est également indisponible : l’essai réel `4491615adb5c4f52` figure dans les bilans et hypothèses fournis, mais pas dans les références admises pour cette revue. C’est la même incohérence de contrat que celle décrite plus bas pour UTF-8. Une décision fraîche ultérieure permet néanmoins de poursuivre le déroulement jusqu’à l’intégration et à la confirmation.

**Limite observée :** le JEV T1 propose à nouveau BK=64 alors que l’essai synchrone correspondant était déjà mesuré dans son instantané ; Mother reprend cette suggestion. Le nouveau contrat garantit l’exposition du code et la validité des références, mais pas encore la détection sémantique des tests déjà réalisés. Cet essai redondant n’a pas été réadmis faute de budget. Les citations, à elles seules, ne suffisent donc pas à certifier un bon raisonnement expérimental.

### UTF-8

La boucle a achevé 44 essais de recherche (T1 : 8, T2 : 3, T3 : 8, T4 : 17, T5 : 7, Gm1 : 1) et un G final. Les trois arbres initiaux explorent AVX2, le saut de mots ASCII et une machine à états scalaire. Mother ouvre ensuite T4, validateur AVX-512BW par blocs de 64 octets, puis T5, son raccourci ASCII. Le gagnant confirmé `ee536e4c87ba48b9` traite deux blocs successifs par tour, conserve les continuations entre blocs et termine par une queue scalaire. Les chargements décalés exigent au moins 65 ou 129 octets restants. Le matériel fixe EPYC 9654 expose les instructions nécessaires ; ce résultat ne vaut pas pour une machine sans AVX-512.

Deux fermetures proposées à 1 451 et 1 745 s sont rejetées parce que de nouvelles mesures sont arrivées. Sept suspensions sont également rejetées. Le moteur enregistre neuf progrès, six admissions protégées et neuf suites ordinaires consommant les fenêtres de suivi. Deux revues sans arbre actif ont lieu à 3 757 et 5 498 s. Le meilleur T4 apparaît à environ 1 486 s : les nouvelles règles ont laissé l’exploration se poursuivre, mais les nombreuses variantes ultérieures ne battent pas ce gagnant. La durée moteur passe de 1 980 à 6 096 s, pour 45 essais au lieu de 21. Ce coût doit rester visible à côté du gain de vitesse du code livré.

Le résultat remesuré sur une même allocation est de 5,953 µs contre 29,317 µs pour l’active précédente et 13,356 µs pour l’historique, en moyenne sur sept blocs. Le G final est presque identique en vitesse (5,955 µs), sans bénéfice démontré sur le gagnant T4. Forest a conservé T4 après sa confirmation indépendante. Le naïf réparé atteint 49,868 µs ; un bloc initial plus lent est conservé dans les données, sans filtrage a posteriori.

Les 17 bilans JEV acceptés citent du code (59 citations vérifiées, 16 bilans citent le contenu du dernier candidat propre). Le JEV `active-analyst-1fb5155eae7d40e781161a4ca6ecbe2a` signale notamment le masque `bad_e0` inversé de `43cbf97bb4294abd` et le compare au prédicat correct d’ee536. L’audit supplémentaire après recherche confirme 314 erreurs sur 101 205 entrées, dont `E0 9F BF` suivi de 64 octets ASCII et des séquences F0 trop courtes en valeur Unicode. Le source inverse aussi `bad_f0`. Le premier corpus de 79 729 cas n’exposait pas ce défaut : des entrées courtes passaient par la voie scalaire. Le gagnant, le G final et les autres programmes Forest comparés passent les deux corpus. Le naïf documentaire échoue respectivement sur 5 773 et 9 602 entrées. Ce diagnostic intermédiaire n’entre pas dans le classement de vitesse et n’a pas été fourni au moteur en cours de recherche.

**Limites observées :** Mother réactive bien T4 après le signalement, mais demander un oracle ciblé via « continuer » ou « reprendre » entraîne des variantes de code ; cela ne crée pas une opération de diagnostic dédiée. Surtout, la dernière revue Mother échoue trois fois avec `Invalid hypothesis review` : elle cite les vrais essais `4486afb698cf461b` et parfois `9d132234d34448b6`, présents dans les arbres, rapports et hypothèses fournis, mais absents de la liste stricte `visible_evidence_ids` de cet instantané. Ce n’est donc pas une preuve inventée ; le dossier fourni et le contrat d’admission des références sont incohérents sur ce point. Le moteur termine par `no_admissible_work_after_idle_review`, puis intègre et confirme, sans fermeture globale confirmée. La réussite du pipeline ne signifie pas que cette revue de fermeture a réussi. Ce défaut résiduel est conservé dans les preuves ; le moteur de la campagne n’a pas été modifié après son lancement.

### Mandelbrot

La recherche réalise 60 essais (T1 : 25, T2 : 10, T3 : 2, T4 : 18 et cinq intégrations Gm à un essai chacune), puis un G final. Deux essais T3 échouent : le certificat intérieur `da0692abadcc4314` et la détection de cycles `4c0dd584e4254b11` produisent chacun six erreurs au contrôle n=32, avec un écart maximal de 17 itérations. Les sources modifient aussi l’organisation de la boucle scalaire ; ces traces seules ne permettent pas d’attribuer l’écart au certificat ou au cycle plutôt qu’aux autres changements et à leur compilation. Les échecs sont correctement éliminés.

T1 apporte le parallélisme OpenMP, mais reste autour de 0,282 s sur l’objectif géométrique. T2 teste quatre, deux puis huit voies. Les combinaisons Gm2–Gm4 atteignent environ 0,1453 s. Après une revue sans arbre actif à 3 334 s, Mother ouvre T4 à huit voies. Ses deux premiers résultats sont environ 0,159 et 0,150 s, moins bons que Gm2. À 3 796 s, deux demandes de suspension T4 sont rejetées au titre du progrès récent. Une admission protégée à 3 946 s produit le deuxième essai ; les suites atteignent ensuite 0,0926 s et 0,0754 s. Le contrôleur a donc effectivement conservé une piste initialement décevante, qui a progressé. Cette trajectoire observée n’est pas une expérience d’ablation prouvant à elle seule l’effet causal de chaque règle.

Le meilleur T4 `5447f3d842164cba` reçoit une confirmation à 0,08173 s. Le G final `671394cc17284d33`, confirmé à 0,08134 s, combine ses huit voies et ses écritures directes avec des tuiles dynamiques 32×8. C’est ce G qui est livré. L’objectif de recherche est une moyenne géométrique des mesures à un et quatre threads ; aucune de ces valeurs agrégées ne doit être étiquetée « temps quatre threads ».

La comparaison séparée donne **151,364 ms à un thread et 38,237 ms à quatre threads**, contre 150,316 et 37,952 ms avec l’architecture active précédente : régression d’environ 0,7 à 0,8 %. Le meilleur historique reste à 49,126 et 12,482 ms, soit environ trois fois plus rapide que la version corrigée. Le passage à quatre threads apporte environ 3,96× ; le défaut principal du programme livré n’est donc pas l’absence de parallélisme CPU. La recherche a coûté 6 882 s contre 1 873 s précédemment, sans dépasser ce code précédent.

Le diagnostic compilateur a été produit après les chronométrages avec les mêmes options, en ajoutant seulement le journal de vectorisation ; les binaires obtenus sont identiques aux binaires mesurés. Dans le gagnant corrigé, GCC vectorise l’initialisation (ligne 58, vecteurs de 32 octets), mais échoue sur la mise à jour des voies (lignes 73–74). Le code historique par blocs de 128 pixels vectorise aussi cette boucle de récurrence (lignes 34–36, vecteurs de 32/64 octets) et sa réduction d’activité. Les directives `omp simd` du code récent ne suffisent donc pas. Cette différence est un mécanisme cohérent avec l’écart mesuré ; les variantes diffèrent aussi par la taille des blocs, les écritures et l’ordonnancement, donc sa contribution exacte n’a pas été isolée.

Les 21 bilans JEV acceptés citent le code (79 citations, 18 bilans citent le dernier code propre). Un JEV distingue déjà une directive SIMD d’une preuve de vectorisation effective, et relève qu’une version T2 ignore le paramètre `threads`. Ces observations sont utiles. En revanche, les demandes de confirmation séparée à un et quatre threads sont souvent exprimées par `continue`, alors que cette action autorise de nouveaux programmes. Une réponse native contient même « Demander la clôture » dans sa justification avec l’action `continue` : l’incohérence provient de la décision produite par le modèle, pas d’une réécriture du relais. Le moteur n’exécute pas les intentions du texte libre à la place de l’action typée.

Aucune action globale `close` n’est finalement appliquée. Cinq suspensions sont rejetées, deux revues sans arbre actif ont lieu, puis la réserve finale arrête les admissions. Une revue Mother est aussi indisponible parce que sa réponse ne correspond pas à l’instantané demandé. Le motif final est `final_reserve_or_deadline`. Les protections évitent certains arrêts précoces, mais ne garantissent ni une bonne expérience proposée par Mother, ni un meilleur code final.

### Ce que cette campagne établit

Les protections d’exploration fonctionnent dans les traces et les JEV citent maintenant des sources vérifiables : 43 bilans sur les trois cas, 159 citations. SGEMM et UTF-8 dépassent la version active précédente ; Mandelbrot reste proche de celle-ci et nettement sous l’historique. Le prochain problème est concret : rendre cohérentes les références autorisées lors de la revue finale, distinguer un diagnostic d’une mutation, et exposer la vectorisation effective ainsi que les mesures par configuration aux analystes. Ces points restent ouverts dans le moteur testé ; les résultats ne doivent pas être présentés comme une architecture entièrement résolue.


## Speedups publiés et remesurés

Chaque ratio de cette table utilise le même code naïf comme dénominateur dans l’allocation de comparaison. Les valeurs publiées sont documentaires : le matériel, le compilateur et le protocole peuvent tous contribuer aux écarts. La remesure sur ROMEO ne mesure pas isolément l’effet du matériel.

| Ligne du tableau | Publié | Référence sur ROMEO | Historique Forest | Active précédente | Corrigée |
|---|---:|---:|---:|---:|---:|
| Mandelbrot — ISPC 1 cœur(s) | 6.21× | 9.26× | 11.48× | 3.75× | 3.73× |
| Mandelbrot — ISPC 4 cœur(s) | 20.28× | 37.32× | 45.72× | 15.04× | 14.92× |
| Validation UTF-8 aléatoire — minimum | 24.48× | 4.86× | 3.41× | 1.57× | 7.65× |
| Validation UTF-8 aléatoire — moyenne | 22.69× | 4.99× | 3.50× | 1.59× | 7.85× |
| Coalescence des accès mémoire globaux | 6.43× | 12.72× | 48.84× | 23.22× | 55.05× |
| Cache en mémoire partagée | 9.64× | 18.40× | 48.84× | 23.22× | 55.05× |
| Tuilage 1D | 27.43× | 33.95× | 48.84× | 23.22× | 55.05× |
| Tuilage 2D | 51.69× | 51.78× | 48.84× | 23.22× | 55.05× |
| Évitement des conflits de banques par linéarisation | 52.47× | 56.24× | 48.84× | 23.22× | 55.05× |
| Évitement des conflits de banques par décalage | 53.27× | 46.52× | 48.84× | 23.22× | 55.05× |
| Double tampon | 55.92× | 75.66× | 48.84× | 23.22× | 55.05× |
| Accès mémoire vectorisés | 59.02× | 62.78× | 48.84× | 23.22× | 55.05× |
| Autotuning | 63.82× | 62.38× | 48.84× | 23.22× | 55.05× |
| SGEMM CUDA naïf → meilleur kernel maison publié | 70.48× | 71.54× | 48.84× | 23.22× | 55.05× |
| SGEMM CUDA naïf → référence cuBLAS | 75.24× | 100.49× | 48.84× | 23.22× | 55.05× |

Pour UTF-8, le naïf documentaire échoue sur certaines entrées mal formées. Forest part du naïf réparé. Le speedup corrigé sur cette **base réparée** est 8.38× en moyenne. La table documentaire garde son dénominateur original et ne le présente pas comme un validateur universellement correct.

### Audit supplémentaire UTF-8

Oracle : décodeur UTF-8 strict de Python. Énumération exhaustive des chaînes de un et deux octets, séquences spéciales près des frontières SIMD, chaînes aléatoires et mutations déterministes. Le contrôle vérifie aussi les zones sentinelles et la conservation de l’entrée.

La variante `diagnostic_43cb_e0` est un candidat intermédiaire signalé par le JEV pour une possible inversion du test E0. Elle est auditée après la recherche et exclue des temps et des classements ; aucun résultat de cet audit n’a été transmis à Forest.

| Variante | Cas audités | Échecs |
|---|---:|---:|
| historical | 79729 | 5773 |
| repaired | 79729 | 0 |
| reference_avx | 79729 | 0 |
| old_selected | 79729 | 0 |
| previous_selected | 79729 | 0 |
| new_selected | 79729 | 0 |
| old_g | 79729 | 0 |
| previous_g | 79729 | 0 |
| new_g | 79729 | 0 |
| diagnostic_43cb_e0 | 79729 | 0 |

Un corpus élargi place les séquences spéciales aux offsets 0 à 132, avec des suffixes de 0, 7 ou 64 octets et toutes leurs troncatures. Il couvre notamment les traversées des frontières à 64 et 128 octets. Il a été ajouté après la découverte de variantes AVX-512 ; les entrées chronométrées et les validations de campagne restent figées.

| Variante | Cas du corpus étendu | Échecs |
|---|---:|---:|
| historical | 101205 | 9602 |
| repaired | 101205 | 0 |
| reference_avx | 101205 | 0 |
| old_selected | 101205 | 0 |
| previous_selected | 101205 | 0 |
| new_selected | 101205 | 0 |
| old_g | 101205 | 0 |
| previous_g | 101205 | 0 |
| new_g | 101205 | 0 |
| diagnostic_43cb_e0 | 101205 | 314 |

Ce corpus est plus large que les entrées chronométrées ; il ne constitue pas une preuve exhaustive pour toute longueur de chaîne.

## Protocole et limites

- SGEMM : matrices 4096² FP32, alpha = 0,5, beta = 3 ; GH200/Grace, CUDA 12.6.3, même pilote protégé et compilation pour SM90. Référence publiée sur RTX A6000. Neuf blocs alternant les variantes.
- UTF-8 : 65 536 octets, motif 0, un thread ; AMD EPYC 9654, mêmes sources, compilateur et pilote. Référence publiée sur Intel Skylake. Sept blocs ; audit de correction séparé.
- Mandelbrot : 1536 × 1024, 512 itérations ; un et quatre threads EPYC 9654. L’objectif de recherche est la moyenne géométrique des temps à un et quatre threads. Référence publiée sur iMac/Core i7 AVX. Sept blocs.
- Registre, session et mémoire neufs par programme, aucune solution historique importée et aucun conseil algorithmique de l’opérateur pendant les recherches. Les caches physiques des nœuds ne sont pas purgés.
- Compilation, correction et chronométrage sur les nœuds de calcul ROMEO. L’inférence passe par le service Codex via un relais local ; Luna ne tourne pas sur les GPU ROMEO.
- L’identité des entrées CPU est vérifiée par les empreintes enregistrées par le pilote. Le pilote SGEMM ne fournit pas d’empreinte des matrices : la comparaison vérifie ses propres empreintes, les mêmes dimensions et la même graine dans chaque bloc, sans inventer un hash d’entrée. Les neuf blocs SGEMM utilisent neuf graines distinctes.
- Les premiers jobs de diagnostic 783352, 783353 et 783354 ont été annulés après découverte du compteur de suivi non décrémenté hors enveloppe protégée. Le correctif est testé ; ces trois essais sont exclus des performances. Leurs traces et les archives vérifiées sont conservées.

Les deux premières campagnes CPU corrigées (783358 et 783359) ont perdu la continuité de Mother pendant une coupure réseau et une interruption du poste local. La première tentative de relance Mandelbrot (783481) n’a pas reçu son worker avant le délai de démarrage : une erreur de commande du lanceur, suivie de l’interruption locale, a retardé son lancement. Elle n’a fait aucun appel modèle. Ces tentatives sont archivées et exclues. La sélection retient la première campagne achevée avec le moteur figé, sans sélectionner selon le speedup.

Les relances CPU 783743 et 783744 ont ensuite rencontré une nouvelle panne DNS du relais local. Elles ont confirmé un candidat de secours, mais leur assemblage G est absent : elles sont exclues de la comparaison principale de la boucle complète. Leurs candidats ont été remesurés dans les jobs 783899 et 783900 et sont conservés dans l’[annexe des essais interrompus](diagnostics-interrompus/RAPPORT-INTERROMPU.md). Après confirmation par l’utilisateur du rétablissement de la connexion, les relances repartent avec une mémoire neuve. Le transport seul reçoit jusqu’à huit tentatives et une grâce maximale de 90 secondes ; il conserve les échéances plus courtes et ne rejoue aucun appel modèle. Les contrôles de reprise, d’intégrité et d’expiration de cette couche ont été vérifiés séparément.

| Tentative exclue | Cas | État SLURM | Durée allocation |
|---:|---|---|---:|
| 783354 | mandelbrot | CANCELLED by 100313 | 563 s |
| 783352 | sgemm | CANCELLED by 100313 | 568 s |
| 783353 | utf8 | CANCELLED by 100313 | 565 s |
| 783359 | mandelbrot | FAILED | 2008 s |
| 783481 | mandelbrot | FAILED | 604 s |
| 783744 | mandelbrot | FAILED | 3384 s |
| 783358 | utf8 | FAILED | 2532 s |
| 783743 | utf8 | FAILED | 3301 s |

## Validation et pièces

Suite logicielle : **895 tests, 0 échec, 0 erreur, 0 ignoré**. Ruff : passed.

- [Mesures et résultats complets](RESULTATS.json)
- [Comparaison des speedups](comparaison.csv) ; [mesures par bloc](mesures.csv).
- [Moteurs](engines.csv) ; [arbres](trees.csv) ; [essais](trials.csv) ; [durées](durees.csv).
- [Arrêts](stops.csv) ; [décisions](decisions.csv) ; [chronologie](chronology.csv).
- [Bilans JEV](analyst_reports.csv) ; [appels de contrôle](calls.csv).
- [Tentatives interrompues](tentatives-interrompues.csv).

Empreinte du manifeste du moteur exécuté : `104ac295acac4848996485ab7e2de4477da3dadfee98692e0101f175caf6fe14`.
