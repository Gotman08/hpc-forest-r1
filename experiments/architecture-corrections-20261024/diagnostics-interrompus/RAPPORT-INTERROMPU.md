# Diagnostics des campagnes interrompues 783743 et 783744

Ces deux campagnes ne constituent **pas une exécution complète de l'architecture** : une panne DNS du relais local a interrompu la recherche et empêché Mother de réaliser l'intégration finale G. Le moteur a néanmoins confirmé un candidat de secours sur ROMEO. Les programmes confirmés ont ensuite été remesurés avec leurs prédécesseurs dans des allocations dédiées, sans nouvel appel modèle.

| Programme | Ancien historique | Architecture active précédente | Candidat de secours confirmé | Gain sur précédente |
|---|---:|---:|---:|---:|
| UTF-8, moyenne | 13,362 µs | 29,332 µs | 9,007 µs | 3,257× |
| Mandelbrot, 1 thread, médiane | 49,064 ms | 150,090 ms | 563,362 ms | 0,266× |
| Mandelbrot, 4 threads, médiane | 12,369 ms | 37,575 ms | 140,964 ms | 0,267× |

Sept blocs par configuration. Jobs de remesure : 783899 et 783900. Les tableaux structurés donnent les valeurs non arrondies. Le ratio inférieur à un signifie une régression : le candidat Mandelbrot est environ 3,75 fois plus lent que celui de l'architecture précédente. Le candidat UTF-8 passe les 79 729 chaînes de l'audit externe ; le naïf documentaire échoue sur 5 773 de ces chaînes, tandis que la base réparée et les programmes Forest passent ce corpus.

## UTF-8 : effet observé des protections avant la coupure

La campagne commence avec trois arbres, ajoute T4 et une combinaison intermédiaire Gm1, et atteint 27 essais, dont 24 corrects. Les trois autres n'ont pas fourni un résultat correct mesuré avant l'arrêt d'infrastructure. Elle n'atteint aucune fermeture globale confirmée.

La première demande de fermeture acceptée survient à 640,2 s. Le meilleur résultat de recherche disponible à ce moment est de 10,635 µs. Après le drainage et les nouveaux bilans, le contrôleur diffère la fermeture pour les suites protégées et réactive T1 à T4. Dix-neuf évaluations correctes terminent après la première demande ; le meilleur résultat de recherche atteint 9,006 µs. Ce compte inclut les essais déjà en cours et l'intégration intermédiaire : ce n'est pas une mesure causale de l'effet de la protection seule.

Les 12 bilans acceptés sur 17 appels JEV citent des sources. Une revue ultérieure conduit Mother à rouvrir T1 pour examiner les frontières à 64 et 128 octets du meilleur candidat. Le candidat confirmé utilise une validation AVX-512BW par blocs de 64 octets et une gestion scalaire des queues. Son résultat positif ne valide pas une intégration finale qui n'a pas eu lieu.

## Mandelbrot : lire des sources ne garantit pas le diagnostic

Mother choisit deux arbres initiaux : OpenMP scalaire et SIMD exact. T1 réalise 18 essais, T2 quatre, puis une branche T3 en réalise trois. Sur les 25 essais, 20 sont corrects. La recherche reste concentrée sur les variantes d'ordonnancement OpenMP et le chemin sériel à un thread. Aucune fermeture globale n'est demandée ; l'arrêt vient du transport réseau.

Deux builds T2 échouent avec `target specific option mismatch` sur les intrinsics. Le troisième échoue parce que les attributs `target` sont placés après les signatures des définitions. Une demande de documentation ne produit ensuite aucune proposition de code. Les trois erreurs de compilation ont un score nul ; l'échec de génération garde un score absent.

Les 10 bilans JEV acceptés sur 16 appels citent des sources, mais le bilan T2 `active-analyst-74bb64a25aab48129197f24e156caf61` affirme à tort que `run` manque dans `6129065151374e33`. Les lignes 180–181 de l'extrait complet qu'il cite définissent déjà ce wrapper. L'extrait n'est pas tronqué. Ce même bilan identifie correctement que le wrapper ne transmet pas le nombre de threads au calcul SIMD, mais ne retrouve pas la cause réelle des erreurs de compilation.

La référence de source est valide ; son interprétation est fausse. Le contrôleur vérifie la provenance des citations, pas leur vérité sémantique. Le cas illustre aussi que davantage d'essais proches et davantage de revues ne remplacent pas une piste SIMD fonctionnelle.

## Portée

Les codes n'ont pas reçu d'aide algorithmique de l'opérateur. Les analyses ci-dessus sont faites après lecture des preuves et ne sont pas transmises aux recherches relancées. Les campagnes suivantes repartent de la source naïve, avec nouveaux registres et sessions. La règle de sélection de la comparaison principale reste la première campagne complètement achevée, sans choix d'après son speedup. Ces essais interrompus, leurs coûts, leurs candidats et leurs remesures restent conservés séparément.
