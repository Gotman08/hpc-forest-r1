# Comparaisons ROMEO — rapports, sources et preuves

Cette archive rassemble les livrables existants de l'étude : tableaux CSV et
Excel, rapports, tableaux de bord, programmes, scripts de reproduction,
protocoles, diagnostics, schémas et preuves de validation. Ils sont publiés le
24 octobre 2026, sans nouvelle campagne ni nouveau calcul de speedup.

Commencer par le [bilan complet](BILAN-COMPLET.md), puis consulter :

- [les références publiées et remesurées](comparaison-references/RAPPORT.md)
  et leur [classeur Excel](comparaison-references/COMPARAISON.xlsx) ;
- [les reprises avec mémoire neuve](comparaison-reprises/RAPPORT.md), leur
  [protocole](comparaison-reprises/PROTOCOLE.md) et leur
  [classeur Excel](comparaison-reprises/COMPARAISON.xlsx) ;
- [l'historique des programmes CUDA](comparaison-historique/RAPPORT.md) ;
- [la comparaison des moteurs](comparaison-moteurs/RAPPORT.md) et
  [l'analyse de leurs comportements](comparaison-moteurs/COMPORTEMENTS.md) ;
- [le plan de la nouvelle architecture](plan-architecture-forest-luna-max.md),
  [les schémas](schema-forest-jev/README.md) et
  [la validation du premier lot](validation-lot1-luna-max/VALIDATION-ANALYSTES.md).

## Tableaux CSV principaux

Les 63 CSV principaux ci-dessous conservent leurs octets et valeurs d'origine.
Les exports détaillés des deuxième et troisième séries sont également présents.

| Dossier | Contenu | CSV |
| --- | --- | ---: |
| [comparaison-references](comparaison-references/) | Comparaison initiale : résultats publiés, références remesurées sur ROMEO, Forest et détails des arbres | 2 |
| [comparaison-reprises](comparaison-reprises/) | Reprises des 14 programmes peu explorés, comparaisons ancien/nouveau et historique des essais | 3 |
| [comparaison-historique/tables](comparaison-historique/tables/) | Historique des sept campagnes : essais, événements, intégrations et rejeu de 124 programmes CUDA distincts | 24 |
| [comparaison-moteurs/tables](comparaison-moteurs/tables/) | Comparaison des moteurs : campagnes, appels, diagnostics et rejeu commun des programmes | 34 |

## Les deux tableaux de speedups

- [Comparaison initiale — 62 configurations](comparaison-references/COMPARAISON.csv) :
  `published_speedup`, `reference_speedup` et `forest_speedup` mettent côte à côte
  le ratio publié, celui de la référence sur ROMEO et celui du candidat Forest.
  `final_g_speedup` conserve séparément le résultat de G.
- [Comparaison après reprises — 35 configurations](comparaison-reprises/COMPARAISON.csv) :
  `previous_reference_speedup` et `previous_forest_speedup` sont les anciennes
  mesures ; `reference_speedup`, `old_selected_speedup` et
  `new_selected_speedup` sont les remesures comparables. `new_vs_old` donne le
  rapport de vitesse nouveau/ancien. Les colonnes de G restent distinctes.

Les lignes représentent des configurations de programme, de taille et de
nombre de threads ; leur nombre n'est pas le nombre de programmes. Les deux
fichiers `DETAILS-FOREST.csv` décrivent les campagnes et leurs arbres.
[ESSAIS-FOREST.csv](comparaison-reprises/ESSAIS-FOREST.csv) contient les
892 essais enregistrés dans les reprises retenues, y compris leurs échecs.

## Conditions de comparaison

Lire ensemble les colonnes de matériel, compilateur, entrée, agrégation,
statut et notes. Un speedup publié sur un autre matériel n'isole pas l'effet
du système. Dans les reprises, chaque comparaison ancien/nouveau est mesurée
dans une même allocation, avec les mêmes entrées et compilateurs ; les limites
propres à chaque référence restent décrites dans les lignes du tableau.

Les reprises changent à la fois l'infrastructure, la capacité du contexte et
le budget de recherche. Elles ne démontrent pas séparément l'effet de chacun.
Une mémoire neuve est créée par programme ; la mémoire reste active entre les
essais d'une même campagne. Le nombre d'arbres est choisi par Mother.

Dans les tables des moteurs, les fichiers `comparaison-*` rassemblent les trois
séries de recherche. Les fichiers `<identifiant>-events.csv`,
`<identifiant>-trials.csv` et `native-*.csv` à ce niveau décrivent la première
série ; les séries suivantes sont distinguées dans les tables consolidées.
Les exports propres aux séries suivantes sont dans
[relance-controlee/tables](comparaison-moteurs/relance-controlee/tables/) et
[serie-atomique/tables](comparaison-moteurs/serie-atomique/tables/).

Les champs vides, les échecs et les diagnostics sont conservés. Un champ vide
ne doit pas être transformé en score nul. Les chemins locaux et distants dans
les cellules désignent les preuves d'origine.

## Sources et reproduction

- [124 programmes CUDA historiques](comparaison-historique/sources/), leurs
  [différences](comparaison-historique/diffs/) et
  [instructions de reproduction](comparaison-historique/REPRODUCTION.md).
- [Douze révisions Git testées](comparaison-historique/engines/commits/README.md)
  et [sept moteurs réellement déployés](comparaison-historique/engines/deployed/).
- [Sources des trois séries de moteurs](comparaison-moteurs/sources/),
  [deuxième série](comparaison-moteurs/relance-controlee/sources/) et
  [troisième série](comparaison-moteurs/serie-atomique/sources/).
- [Candidats des comparaisons initiales](comparaison-references/pieces-extraites/candidats/),
  [sources naïves, références et harnais](comparaison-references/pieces-extraites/references/protected-suites/),
  [scripts](comparaison-references/pieces-extraites/scripts/),
  [mesures](comparaison-references/pieces-extraites/mesures/) et
  [licences des sources importées](comparaison-references/pieces-extraites/licences/).
- [Pièces des reprises](comparaison-reprises/pieces-extraites/) : scripts,
  sources ancien/nouveau des comparaisons par paires, mesures, revues des
  modifications et métadonnées des campagnes.

Les scripts historiques sont des pièces de reproduction, avec les chemins et
identifiants de leur exécution d'origine. Leur publication ne les exécute pas.
Une nouvelle campagne exige de nouveaux chemins, sessions et allocations.
Sous Windows, utiliser un chemin de clone court ou activer `core.longpaths`
pour les sources et traces imbriquées.

Les tableaux de bord HTML restent consultables après téléchargement du dossier
en conservant ses sous-dossiers. GitHub affiche leur source ; les ouvrir dans
un navigateur pour utiliser leurs filtres.

## Périmètre de l'archive

Les archives originales de preuves restent locales quand elles contiennent des
sessions, autorisations, environnements, caches ou données intermédiaires. Les
pièces utiles en sont extraites dans `pieces-extraites/`, sans modifier leurs
octets. Le PDF et le HTML autonome des schémas dupliquent les visuels : les PNG,
SVG et spécifications sont publiés avec un index Markdown.

Le [manifeste de publication](MANIFESTE-PUBLICATION.json) énumère chaque fichier
publié, son origine, son empreinte et les éléments omis avec leur motif. Les
anciens manifestes présents dans les rapports décrivent la livraison originale
complète ; leur périmètre peut donc être plus large que cette publication.
Les liens historiques vers une archive ou un dossier conservé localement
restent des références de provenance.

## Intégrité

[MANIFESTE.json](MANIFESTE.json) décrit les 63 CSV principaux : chemin d'origine,
la taille, le SHA-256, les colonnes et le nombre de lignes de chaque CSV.
Les fichiers sont copiés octet par octet. Une règle Git préserve leurs fins
de ligne et leur éventuel BOM UTF-8. Le séparateur est la virgule ; un lecteur
CSV doit respecter les champs entre guillemets et leurs retours à la ligne.

La vérification de publication contrôle la lecture des CSV, le nombre de colonnes
de chaque enregistrement et l'identité des octets avec les sources. Elle ne
constitue pas une nouvelle validation numérique ni un benchmark ROMEO.
