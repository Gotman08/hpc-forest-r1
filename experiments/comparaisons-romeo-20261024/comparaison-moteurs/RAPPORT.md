# Historique et nouvelles comparaisons : moteurs et CUDA

Les sept états du moteur ont été relancés depuis le même programme initial. Trois séries sont conservées : deux séries de diagnostic du transport, puis une série commune avec messages atomiques. Le rejeu final compare **175 programmes distincts et points de comparaison**, plus une référence de contrôle, sur un seul GPU.

Dans la troisième série, le meilleur programme sélectionné vient de l’état **772923** : **0,083213 ms**, soit **22,22×** la référence dans le rejeu commun. Ce classement est celui d’une nouvelle campagne par état ; il ne mesure pas la probabilité qu’un moteur retrouve ce résultat.

[Tableau de bord interactif](TABLEAU-DE-BORD.html) · [Comportements et diagnostics expliqués](COMPORTEMENTS.md) · [Méthode et limites](METHODE.md) · [Historique initial : 19 commits, 12 révisions testées, 124 programmes rejoués](../comparaison-historique/RAPPORT.md)

## Comparaison principale : troisième série

| État du moteur | Arbres | Essais recherche / valides | G valides / essais | G confirmé | Pipeline | Programme sélectionné, rejeu commun | Accélération | Durée observée |
|---|---:|---:|---:|---|---|---:|---:|---:|
| 772923 — Vagues / paires | 3 | 6 / 6 | 2 / 2 | confirmed | incomplet | 0,083213 ms | 22,22× | 17 min 22 s |
| 774157 — Arbres indépendants / paires | 4 | 33 / 30 | 3 / 3 | confirmed | complet | 0,093721 ms | 19,73× | 23 min 23 s |
| 775521 — Mémoire / réserve initiale | 3 | 3 / 2 | 2 / 2 | confirmed | complet | 0,137762 ms | 13,42× | 12 min 44 s |
| 775815 — Première correction de réserve | 3 | 16 / 12 | 2 / 2 | confirmed | complet | 0,592769 ms | 3,12× | 27 min 38 s |
| 776048 — Réserve et assemblage adaptatifs | 4 | 22 / 19 | 2 / 2 | confirmed | complet | 0,639299 ms | 2,89× | 25 min 42 s |
| 776290 — Correction d’admission | 3 | 23 / 21 | 3 / 3 | confirmed | complet | 0,328067 ms | 5,64× | 28 min 52 s |
| 780448 — Fiabilité et critique du plan | 3 | 31 / 31 | 1 / 1 | confirmed | complet | 0,592180 ms | 3,12× | 25 min 06 s |

Les durées comprennent les phases observées jusqu’à la fin de confirmation ou de préparation de l’archive. Une terminaison anticipée, une erreur d’export et un arrêt normal de recherche ne sont pas assimilés. Le budget de 30 minutes est un budget d’admission avec achèvement du travail déjà engagé.

## Historique et nouvelle recherche : même GPU pour les gagnants

| État | Gagnant historique remesuré | Gagnant de S3 remesuré | Variation de latence |
|---|---:|---:|---:|
| 772923 | 0,113190 ms | 0,083213 ms | -26,48 % |
| 774157 | 0,118552 ms | 0,093721 ms | -20,95 % |
| 775521 | 0,697122 ms | 0,137762 ms | -80,24 % |
| 775815 | 0,525592 ms | 0,592769 ms | 12,78 % |
| 776048 | 0,099665 ms | 0,639299 ms | 541,45 % |
| 776290 | 0,852576 ms | 0,328067 ms | -61,52 % |
| 780448 | 1,007912 ms | 0,592180 ms | -41,25 % |

Une variation négative indique une latence plus faible. Cette comparaison porte sur les programmes effectivement trouvés ; une modification du moteur n’est pas à elle seule une explication causale de cet écart.

## Contrôles et dispersion du rejeu commun

Le rejeu examine **176 programmes**, référence comprise : **175** réussissent les contrôles de correction et **175** ont une mesure complète. Les **880 échantillons** et **2640 temps par taille** sont recalculés depuis les journaux.

La référence varie sur une étendue de **0,609 %** de sa moyenne. Le coefficient de variation médian des programmes est **0,374 %**, et le maximum **3,549 %**. Ce sont des dispersions de chronométrage ; elles ne mesurent pas la variabilité d’une recherche avec le modèle.

[Vérification indépendante](protocol/new-replay-verification.json) · [Mesures par taille](tables/rejeu-temps-par-taille.csv) · [Cas numériques du rejeu](tables/rejeu-correction-par-cas.csv)

### Programmes exclus du classement

- `167f745188249e0e` : `incorrect`. search, N=16384 (quadruple_size), 1 composante(s) hors tolérance [Enregistrement](gpu-comparaison/results/records/167f745188249e0e.json).

L’admission au rejeu exigeait une évaluation valide dans au moins une phase historique. Le classement final exige les deux jeux de correction et toutes les mesures. Un échec déjà présent dans une campagne n’est pas présenté comme une nouvelle régression due au rejeu.

## Programmes les plus rapides, toutes origines confondues

| Rang | Programme | Origines | Moyenne | Min–max | Accélération |
|---:|---|---|---:|---:|---:|
| 1 | [2eaa36901ee31a47](gpu-comparaison/sources/2eaa36901ee31a47/src/nbody_kernel.cu) | atomic / 772923 | 0,083213 ms | 0,082124–0,084390 ms | 22,22× |
| 2 | [98f2c0e0972dee6f](gpu-comparaison/sources/98f2c0e0972dee6f/src/nbody_kernel.cu) | atomic / 774157 | 0,093721 ms | 0,092466–0,094124 ms | 19,73× |
| 3 | [b461f361f44a6fa4](gpu-comparaison/sources/b461f361f44a6fa4/src/nbody_kernel.cu) | historical-winner / 776048 | 0,099665 ms | 0,099067–0,100065 ms | 18,55× |
| 4 | [ef8d1d746c34d514](gpu-comparaison/sources/ef8d1d746c34d514/src/nbody_kernel.cu) | historical-winner / 772923 | 0,113190 ms | 0,111739–0,114010 ms | 16,34× |
| 5 | [5f93651000397a95](gpu-comparaison/sources/5f93651000397a95/src/nbody_kernel.cu) | atomic / 774157 | 0,116255 ms | 0,115008–0,116981 ms | 15,91× |
| 6 | [ee87da1669bdad9a](gpu-comparaison/sources/ee87da1669bdad9a/src/nbody_kernel.cu) | atomic / 774157 | 0,116697 ms | 0,115891–0,117490 ms | 15,84× |
| 7 | [fd8133554233564b](gpu-comparaison/sources/fd8133554233564b/src/nbody_kernel.cu) | historical-winner / 774157 | 0,118552 ms | 0,117492–0,119345 ms | 15,60× |
| 8 | [a02df0e35576ad85](gpu-comparaison/sources/a02df0e35576ad85/src/nbody_kernel.cu) | atomic / 772923 | 0,125561 ms | 0,123809–0,126197 ms | 14,73× |
| 9 | [802f51d7cdbe45f1](gpu-comparaison/sources/802f51d7cdbe45f1/src/nbody_kernel.cu) | interrupted / 775521 | 0,128149 ms | 0,126634–0,129393 ms | 14,43× |
| 10 | [a7b36d22b351328f](gpu-comparaison/sources/a7b36d22b351328f/src/nbody_kernel.cu) | atomic / 775521 | 0,137762 ms | 0,135922–0,139813 ms | 13,42× |
| 11 | [190b449a6ee65665](gpu-comparaison/sources/190b449a6ee65665/src/nbody_kernel.cu) | atomic / 775521 | 0,148015 ms | 0,146982–0,148754 ms | 12,49× |
| 12 | [d59fa7ad290a0542](gpu-comparaison/sources/d59fa7ad290a0542/src/nbody_kernel.cu) | atomic / 774157 | 0,152354 ms | 0,151784–0,153099 ms | 12,14× |
| 13 | [155180304d67b300](gpu-comparaison/sources/155180304d67b300/src/nbody_kernel.cu) | atomic / 774157 | 0,152676 ms | 0,150995–0,154036 ms | 12,11× |
| 14 | [ef2d411c290d9f1f](gpu-comparaison/sources/ef2d411c290d9f1f/src/nbody_kernel.cu) | atomic / 774157 | 0,153453 ms | 0,152012–0,154646 ms | 12,05× |
| 15 | [9cf001565cfb9a8d](gpu-comparaison/sources/9cf001565cfb9a8d/src/nbody_kernel.cu) | atomic / 774157 | 0,154346 ms | 0,151606–0,155566 ms | 11,98× |

Ce classement rétrospectif inclut les programmes intermédiaires. Il ne remplace pas le gagnant choisi et confirmé par chaque moteur. Les sources identiques sont dédupliquées et leurs origines restent toutes conservées.

## Réglages de lancement avec un noyau inchangé

Les 175 programmes hors contrôle utilisent 148 sources CUDA distinctes octet pour octet. 15 groupes permettent de comparer plusieurs lancements avec une même source ; leurs 94 comparaisons sont conservées. Les configurations identiques après lecture du JSON sont signalées, même si les octets du fichier diffèrent.

| Source commune | Programmes mesurés | Lancement le plus rapide | Temps | Lancement le plus lent | Temps |
|---|---:|---|---:|---|---:|
| `ab22e9f1e077` | 13 | [12/12/0](gpu-comparaison/sources/4d85abd7289e1eb9/src/launch.json) | 1,802841 ms | [1/1/0](gpu-comparaison/sources/3cc253c2323f5f98/src/launch.json) | 3,829372 ms |
| `7dae332eea61` | 2 | [512/16/0](gpu-comparaison/sources/6d645e9fd375e69c/src/launch.json) | 0,160910 ms | [256/8/0](gpu-comparaison/sources/660aaa31c3cf02d1/src/launch.json) | 0,166699 ms |
| `3819309d33a6` | 3 | [256/8/0](gpu-comparaison/sources/155180304d67b300/src/launch.json) | 0,152676 ms | [1024/32/0](gpu-comparaison/sources/ab9387420098a7cd/src/launch.json) | 0,159588 ms |
| `2cf9a0ae4fc0` | 2 | [256/8/0](gpu-comparaison/sources/5f93651000397a95/src/launch.json) | 0,116255 ms | [512/16/0](gpu-comparaison/sources/ee87da1669bdad9a/src/launch.json) | 0,116697 ms |
| `8a8c001832ae` | 2 | [256/8/0](gpu-comparaison/sources/d59fa7ad290a0542/src/launch.json) | 0,152354 ms | [768/24/0](gpu-comparaison/sources/9cf001565cfb9a8d/src/launch.json) | 0,154346 ms |
| `bc1f20055742` | 2 | [16/16/0](gpu-comparaison/sources/3efc5108ecb2298c/src/launch.json) | 0,814117 ms | [256/256/0](gpu-comparaison/sources/1e3e33e7d33fffb9/src/launch.json) | 0,984193 ms |
| `184ec80be3c8` | 2 | [192/192/3072](gpu-comparaison/sources/1a4095d626f968cf/src/launch.json) | 1,005499 ms | [512/512/8192](gpu-comparaison/sources/6e6860b9d67485ff/src/launch.json) | 1,099629 ms |
| `5f38bea26df5` | 2 | [64/128/0](gpu-comparaison/sources/82065d579bb2e7d7/src/launch.json) | 2,585988 ms | [128/256/0](gpu-comparaison/sources/9c92c8ced6b18803/src/launch.json) | 2,600913 ms |
| `0afd138b9b83` | 2 | [64/192/0](gpu-comparaison/sources/a4addbd0b2f0e7c5/src/launch.json) | 3,399744 ms | [256/768/0](gpu-comparaison/sources/d8ae9324bc8f37a9/src/launch.json) | 3,473741 ms |
| `ca3e94cef975` | 2 | [64/128/0](gpu-comparaison/sources/a6b03b3418f89b52/src/launch.json) | 2,610101 ms | [256/512/0](gpu-comparaison/sources/2678dae26c970239/src/launch.json) | 2,723619 ms |
| `5824ddce23c8` | 2 | [128/128/2048](gpu-comparaison/sources/806ffcf6f61eec16/src/launch.json) | 0,897160 ms | [64/64/1024](gpu-comparaison/sources/9907ce72b24d6caf/src/launch.json) | 0,913664 ms |
| `aa9772cc46f7` | 2 | [32/64/0](gpu-comparaison/sources/6acc2f24fa974ed3/src/launch.json) | 2,605901 ms | [128/256/0](gpu-comparaison/sources/4b5f943f0fe60620/src/launch.json) | 2,616711 ms |
| `f8d3d81c330f` | 2 | [160/320/0](gpu-comparaison/sources/6e44bcfa9d2bbacf/src/launch.json) | 2,570950 ms | [128/256/0](gpu-comparaison/sources/052fb0732c47580f/src/launch.json) | 2,598807 ms |
| `786e03053bc9` | 2 | [192/384/0](gpu-comparaison/sources/fda4159a6ed9ff7a/src/launch.json) | 2,628244 ms | [256/512/0](gpu-comparaison/sources/5a28f8ec5705cede/src/launch.json) | 2,759140 ms |
| `a3c1738bd2c7` | 2 | [96/96/2688](gpu-comparaison/sources/a20cdd34905b4854/src/launch.json) | 0,987584 ms | [192/192/5376](gpu-comparaison/sources/7000ec4138d96bd6/src/launch.json) | 0,998404 ms |

Les triplets indiquent threads par bloc / cibles par bloc / octets de mémoire partagée dynamique. Le choix rétrospectif du plus rapide ne remplace pas le choix fait pendant la campagne. Les paires ne sont pas ordonnées comme des transitions chronologiques et les petits écarts restent à lire avec la dispersion des blocs.

[Toutes les paires de lancements](tables/comparaisons-lancements.csv) · [Résumé par source identique](tables/familles-lancements.csv)

## Planification, critique et volume de recherche

| État | Plan initial : temps natif | Critique : temps natif | Appels natifs | Essais incorrects | Erreurs d’infrastructure | Autres échecs de recherche |
|---|---:|---:|---:|---:|---:|---:|
| 772923 | 1 min 46 s | 0 min 00 s | 10 | 0 | 0 | 0 |
| 774157 | 3 min 12 s | 0 min 00 s | 46 | 2 | 0 | 1 |
| 775521 | 1 min 53 s | 0 min 00 s | 12 | 1 | 0 | 0 |
| 775815 | 2 min 04 s | 0 min 00 s | 42 | 1 | 0 | 3 |
| 776048 | 2 min 06 s | 0 min 00 s | 45 | 3 | 0 | 0 |
| 776290 | 1 min 21 s | 0 min 00 s | 48 | 2 | 0 | 0 |
| 780448 | 1 min 01 s | 1 min 05 s | 42 | 0 | 0 | 0 |

Les appels natifs ne sont pas les essais : une réparation du candidat peut consommer plusieurs appels. Les temps natifs parallèles ne doivent pas être additionnés pour obtenir la durée murale. [Détail des appels et des jetons](tables/comparaison-appels.csv).

## Réserve de temps et décisions de sélection

| État | Réserve initiale estimée | Temps restant au même instant | Fin de recherche observée | Sélections mémoire / rejetées |
|---|---:|---:|---:|---:|
| 772923 | 10 min 36 s | 27 min 41 s | 12 min 59 s | 0 / 0 |
| 774157 | 13 min 39 s | 26 min 13 s | 19 min 19 s | 0 / 0 |
| 775521 | 52 min 21 s | 27 min 51 s | 5 min 43 s | 4 / 2 |
| 775815 | 11 min 59 s | 27 min 26 s | 20 min 09 s | 5 / 0 |
| 776048 | 12 min 00 s | 27 min 24 s | 19 min 08 s | 4 / 0 |
| 776290 | 10 min 31 s | 28 min 20 s | 18 min 53 s | 8 / 3 |
| 780448 | 10 min 28 s | 27 min 29 s | 20 min 50 s | 4 / 0 |

La réserve est l’estimation du moteur pour les étapes restantes, pas une durée réellement consommée. Une réserve initiale supérieure au temps disponible explique un arrêt anticipé d’admission après la première vague. Les sélections rejetées désignent les décisions refusées par le protocole mémoire ; elles ne sont pas des échecs numériques CUDA.

## Les séries précédentes restent visibles

| Série | État | Job | Recherche valide / totale | Recherche : arrêt | G confirmé | Pipeline | Meilleur candidat confirmé pendant la campagne |
|---|---|---|---:|---|---|---|---:|
| S1 — relais historiques | 772923 | 780639 | 3 / 6 | infrastructure_error | unavailable | incomplet | 0,153838 ms |
| S1 — relais historiques | 774157 | 780640 | 2 / 5 | infrastructure_error | unavailable | incomplet | 0,888508 ms |
| S1 — relais historiques | 775521 | 780641 | 2 / 3 | infrastructure_error | unavailable | incomplet | 0,126438 ms |
| S1 — relais historiques | 775815 | 780642 | 2 / 5 | infrastructure_error | unavailable | incomplet | 0,158585 ms |
| S1 — relais historiques | 776048 | 780643 | 3 / 6 | infrastructure_error | unavailable | incomplet | 1,025653 ms |
| S1 — relais historiques | 776290 | 780644 | 4 / 7 | infrastructure_error | unavailable | incomplet | 1,004232 ms |
| S1 — relais historiques | 780448 | 780645 | 1 / 4 | infrastructure_error | unavailable | incomplet | 1,854120 ms |
| S2 — connexion partagée | 772923 | 780672 | 0 / 3 | infrastructure_error | unavailable | incomplet | 1,855329 ms |
| S2 — connexion partagée | 774157 | 780673 | 0 / 3 | infrastructure_error | confirmed | complet | 1,003387 ms |
| S2 — connexion partagée | 775521 | 780674 | 0 / 3 | infrastructure_error | rejected | incomplet | 1,006104 ms |
| S2 — connexion partagée | 775815 | 780675 | 3 / 4 | budget_exhausted | confirmed | complet | 1,131187 ms |
| S2 — connexion partagée | 776048 | 780676 | 0 / 4 | infrastructure_error | confirmed | complet | 1,020451 ms |
| S2 — connexion partagée | 776290 | 780677 | 0 / 3 | infrastructure_error | confirmed | incomplet | 1,851522 ms |
| S2 — connexion partagée | 780448 | 780678 | 0 / 4 | infrastructure_error | confirmed | complet | 1,283503 ms |
| S3 — messages atomiques | 772923 | 780687 | 6 / 6 | budget_exhausted | confirmed | incomplet | 0,082183 ms |
| S3 — messages atomiques | 774157 | 780688 | 30 / 33 | budget_exhausted | confirmed | complet | 0,094781 ms |
| S3 — messages atomiques | 775521 | 780689 | 2 / 3 | budget_exhausted | confirmed | complet | 0,136935 ms |
| S3 — messages atomiques | 775815 | 780690 | 12 / 16 | budget_exhausted | confirmed | complet | 0,596515 ms |
| S3 — messages atomiques | 776048 | 780691 | 19 / 22 | budget_exhausted | confirmed | complet | 0,638093 ms |
| S3 — messages atomiques | 776290 | 780692 | 21 / 23 | budget_exhausted | confirmed | complet | 0,328576 ms |
| S3 — messages atomiques | 780448 | 780693 | 31 / 31 | budget_exhausted | confirmed | complet | 0,588652 ms |

S1 et S2 documentent les incidents et les attentes de transfert. Elles ne sont pas fusionnées avec S3 pour calculer une moyenne de performance des moteurs. Les programmes validés de ces séries restent inclus dans le rejeu commun.

## Ce que l’assemblage a réellement changé

| Série / état / essai G | Modification | Gain contre son parent, même GPU | Blocs gagnés |
|---|---|---:|---:|
| interrupted / 772923 / 0e6aa24de9754cf3 | indisponible ; infrastructure_error | — % | — |
| interrupted / 774157 / 06f369a32a2140c2 | indisponible ; infrastructure_error | — % | — |
| shared-scp / 772923 / eb91637b38b6458a | indisponible ; infrastructure_error | — % | — |
| shared-scp / 774157 / [096bd0a3fa2549b5](relance-controlee/diffs/774157/096bd0a3fa2549b5.patch) | noyau et lancement ; valid | 46,18 % | 5/5 |
| shared-scp / 775521 / [3986de7ae7794f6e](relance-controlee/diffs/775521/3986de7ae7794f6e.patch) | noyau seul ; valid | 45,84 % | 5/5 |
| shared-scp / 775521 / [cd4de6eb19c045a3](relance-controlee/diffs/775521/cd4de6eb19c045a3.patch) | noyau seul ; incorrect | — % | — |
| shared-scp / 775815 / [a8472c694eaa4bfe](relance-controlee/diffs/775815/a8472c694eaa4bfe.patch) | noyau seul ; valid | 0,43 % | 5/5 |
| shared-scp / 775815 / [e03a3d880aa74e0e](relance-controlee/diffs/775815/e03a3d880aa74e0e.patch) | noyau et lancement ; valid | -76,53 % | 0/5 |
| shared-scp / 776048 / [8279af122c664ef9](relance-controlee/diffs/776048/8279af122c664ef9.patch) | noyau seul ; valid | 45,05 % | 5/5 |
| shared-scp / 776290 / [9b2da819634b40dd](relance-controlee/diffs/776290/9b2da819634b40dd.patch) | noyau seul ; valid | 0,12 % | 3/5 |
| shared-scp / 776290 / [5e853b44a8bc44c4](relance-controlee/diffs/776290/5e853b44a8bc44c4.patch) | noyau seul ; valid | 1,48 % | 5/5 |
| shared-scp / 776290 / [52d1defc653743d0](relance-controlee/diffs/776290/52d1defc653743d0.patch) | noyau seul ; valid | 0,82 % | 5/5 |
| shared-scp / 776290 / [3f23558b5b9e4387](relance-controlee/diffs/776290/3f23558b5b9e4387.patch) | noyau seul ; valid | 0,27 % | 4/5 |
| shared-scp / 776290 / [f4f3935e70954c99](relance-controlee/diffs/776290/f4f3935e70954c99.patch) | noyau seul ; valid | 0,02 % | 3/5 |
| shared-scp / 776290 / [bdae446f3570488f](relance-controlee/diffs/776290/bdae446f3570488f.patch) | noyau seul ; valid | 0,12 % | 5/5 |
| shared-scp / 780448 / [2d9d46a27e344d6a](relance-controlee/diffs/780448/2d9d46a27e344d6a.patch) | noyau seul ; valid | 30,81 % | 5/5 |
| atomic / 772923 / [ec2a1c1b82fc4991](serie-atomique/diffs/772923/ec2a1c1b82fc4991.patch) | noyau seul ; valid | 21,97 % | 5/5 |
| atomic / 772923 / [63513b28c5484e1e](serie-atomique/diffs/772923/63513b28c5484e1e.patch) | noyau seul ; valid | 33,73 % | 5/5 |
| atomic / 774157 / [bdce72cb10924576](serie-atomique/diffs/774157/bdce72cb10924576.patch) | noyau et lancement ; valid | 19,38 % | 5/5 |
| atomic / 774157 / [1d122d9ba23047ef](serie-atomique/diffs/774157/1d122d9ba23047ef.patch) | lancement seul ; valid | 17,28 % | 5/5 |
| atomic / 774157 / [e4677d85c17f4c0d](serie-atomique/diffs/774157/e4677d85c17f4c0d.patch) | copie exacte ; valid | 0,00 % | 0/5 |
| atomic / 775521 / [00f539728bdf4a2c](serie-atomique/diffs/775521/00f539728bdf4a2c.patch) | noyau seul ; valid | -11,67 % | 0/5 |
| atomic / 775521 / [44e22fac251348d2](serie-atomique/diffs/775521/44e22fac251348d2.patch) | noyau et lancement ; valid | 6,93 % | 5/5 |
| atomic / 775815 / [34ca1c417cff4cb6](serie-atomique/diffs/775815/34ca1c417cff4cb6.patch) | noyau et lancement ; valid | -76,19 % | 0/5 |
| atomic / 775815 / [4af3cb0c24824e8b](serie-atomique/diffs/775815/4af3cb0c24824e8b.patch) | noyau seul ; valid | 33,49 % | 5/5 |
| atomic / 776048 / [fd41c25e396b42c2](serie-atomique/diffs/776048/fd41c25e396b42c2.patch) | noyau seul ; valid | 22,53 % | 5/5 |
| atomic / 776048 / [873f902b4e9c4cd7](serie-atomique/diffs/776048/873f902b4e9c4cd7.patch) | noyau seul ; valid | 7,51 % | 5/5 |
| atomic / 776290 / [39c6be41cc524cf0](serie-atomique/diffs/776290/39c6be41cc524cf0.patch) | noyau seul ; valid | 27,06 % | 5/5 |
| atomic / 776290 / [038c7d345d454f80](serie-atomique/diffs/776290/038c7d345d454f80.patch) | noyau seul ; valid | 49,43 % | 5/5 |
| atomic / 776290 / [19e8c47b42b743d2](serie-atomique/diffs/776290/19e8c47b42b743d2.patch) | copie exacte ; valid | 0,00 % | 0/5 |
| atomic / 780448 / [3c15673a5456404b](serie-atomique/diffs/780448/3c15673a5456404b.patch) | noyau seul ; valid | 34,02 % | 5/5 |

Le parent est le `base_commit` enregistré pour l’essai. Une intégration peut mobiliser plusieurs sources ; le tableau ne prétend pas attribuer un effet individuel à chacune. Les variations petites devant la dispersion des cinq blocs restent incertaines.

## Reconstitution par moteur

### 772923 — Vagues / paires

Job **780687**. Recherche : `budget_exhausted`. G : `confirmed`. Pipeline complet : **non**.

Diagnostic final : `ForestError: Submission requires a Makefile and run.sh in the imported repository`.

- **T1 — Shared-memory source tiling and reuse** : In src/nbody_kernel.cu, test a thread-per-output implementation that cooperatively stages source-particle data in shared-memory tiles and reuses each tile across destination threads. Explore compatible block and items_per_block settings in src/launch.json. Handle source and output tails and self-interaction correctly; add no launches or host work. Measure all official sizes and retain only versions passing the full correctness suite.
- **T2 — Warp-parallel source traversal and reduction** : In src/nbody_kernel.cu, investigate a warp-cooperative source reduction, such as assigning a warp to an output particle and having lanes accumulate different source indices before reducing the force components. Tune the block and items_per_block mapping in src/launch.json. Handle arbitrary N, self-interactions, tails, output ownership, and changed floating-point summation order; preserve exact masses and pass all correctness checks before comparing timings.
- **T3 — Per-interaction math and instruction reduction** : In src/nbody_kernel.cu, optimize the direct thread-per-output arithmetic path by evaluating explicit rsqrtf-based inverse-distance arithmetic and, only if accuracy permits, cancellation of target-mass multiply/divide operations. Do not enable global fast math or assume algebraic equivalence guarantees acceptable float32 results. Preserve behavior for coincident positions, varying positive and extreme masses, and all dt values; keep exact output masses and require full correctness before measuring the official sizes.

[Métadonnées et décisions](serie-atomique/data/772923/metadata.json) · [Événements](serie-atomique/tables/772923-events.csv) · [Appels du modèle](serie-atomique/data/772923/native-calls.json)

| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |
|---:|---|---|---|---:|---:|---:|
| 1 | T1 / [79f075cbacca441f](serie-atomique/diffs/772923/79f075cbacca441f.patch) | valid | noyau seul | 1,001336 ms | 1,000481 ms | 45,99 % |
| 2 | T2 / [71228eb5314942d5](serie-atomique/diffs/772923/71228eb5314942d5.patch) | valid | noyau et lancement | 0,165582 ms | 0,166699 ms | 91,00 % |
| 3 | T3 / [6c186c00ce3d49e5](serie-atomique/diffs/772923/6c186c00ce3d49e5.patch) | valid | noyau seul | 1,009020 ms | 1,012643 ms | 45,34 % |
| 4 | T1 / [d653312aaffb40d9](serie-atomique/diffs/772923/d653312aaffb40d9.patch) | valid | noyau et lancement | 1,088071 ms | 1,094809 ms | 40,90 % |
| 5 | T2 / [cd568c71cce6434b](serie-atomique/diffs/772923/cd568c71cce6434b.patch) | valid | lancement seul | 0,159845 ms | 0,160910 ms | 3,47 % |
| 6 | T3 / [b9ffa352d1be4325](serie-atomique/diffs/772923/b9ffa352d1be4325.patch) | valid | noyau seul | 1,091602 ms | 1,091693 ms | 41,07 % |
| 7 | G / [ec2a1c1b82fc4991](serie-atomique/diffs/772923/ec2a1c1b82fc4991.patch) | valid | noyau seul | 0,124380 ms | 0,125561 ms | 21,97 % |
| 8 | G / [63513b28c5484e1e](serie-atomique/diffs/772923/63513b28c5484e1e.patch) | valid | noyau seul | 0,082153 ms | 0,083213 ms | 33,73 % |

### 774157 — Arbres indépendants / paires

Job **780688**. Recherche : `budget_exhausted`. G : `confirmed`. Pipeline complet : **oui**.

- **T1 — CTA-level shared-memory reuse of source-particle fields** : In src/nbody_kernel.cu, retain one thread per target and the existing force arithmetic while cooperatively staging source x, y, z, and mass tiles in shared memory for reuse across the CTA’s targets. Handle partial source tiles and target tails safely, retain self-interaction exclusion, and keep shared memory within the 49,152-byte limit. Sweep feasible tile sizes and matching block/items_per_block settings; use only the permitted source and launch files. Judge candidates by full correctness and the official per-size geometric-mean timing protocol.
- **T2 — Warp-parallel inner-loop reduction per target** : Explore a warp-cooperative traversal in which each warp owns one target and its lanes accumulate disjoint source-particle subsets, then reduce the three force components within the warp; one lane writes the complete output state. For this mapping, make items_per_block equal the number of target warps per CTA (block/32), and handle N tails, self pairs, coincident positions, and all output fields correctly. Keep this path distinct from shared-memory tiling and measure only candidates passing all correctness checks.
- **T3 — Launch-geometry tuning for the baseline ownership mapping** : Keep the one-thread-per-target traversal, force equations, and memory strategy unchanged; isolate launch-geometry effects by comparing legal block sizes with items_per_block equal to block and shared_memory_bytes zero. In particular, test whether smaller CTAs improve the measured workload without assuming that more CTAs guarantee a gain. Preserve the exact JSON key set and validate every supported size before comparing official timings.
- **T4 — Per-interaction arithmetic throughput with correctness-bounded transforms** : Keep the one-thread-per-target and source traversal structure while exploring algebraically equivalent interaction arithmetic, such as explicit rsqrtf-based inverse-distance-cubed scaling and cancellation of the target-mass multiply/divide. Preserve float32 softening, self-pair handling, velocity-then-position update order, and exact mass copying. Do not enable global fast math; validate numerical tolerances, nonfinite-output checks, and the extreme-mass case before judging timing.

[Métadonnées et décisions](serie-atomique/data/774157/metadata.json) · [Événements](serie-atomique/tables/774157-events.csv) · [Appels du modèle](serie-atomique/data/774157/native-calls.json)

| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |
|---:|---|---|---|---:|---:|---:|
| 1 | T1 / [9e2b831b4a2b4465](serie-atomique/diffs/774157/9e2b831b4a2b4465.patch) | valid | noyau et lancement | 1,058278 ms | 1,057974 ms | 42,89 % |
| 2 | T2 / [9218a96750bb4359](serie-atomique/diffs/774157/9218a96750bb4359.patch) | valid | noyau et lancement | 0,153002 ms | 0,152676 ms | 91,76 % |
| 3 | T3 / [069b25d4d1b24143](serie-atomique/diffs/774157/069b25d4d1b24143.patch) | valid | lancement seul | 1,828811 ms | 1,826139 ms | 1,43 % |
| 4 | T4 / [df913111dbad4ccd](serie-atomique/diffs/774157/df913111dbad4ccd.patch) | incorrect | noyau seul | — ms | — ms | — % |
| 5 | T3 / [da99ff86be8345aa](serie-atomique/diffs/774157/da99ff86be8345aa.patch) | valid | lancement seul | 1,811843 ms | 1,813501 ms | 2,11 % |
| 6 | T1 / [4638b22c70eb4dbc](serie-atomique/diffs/774157/4638b22c70eb4dbc.patch) | valid | noyau et lancement | 1,017024 ms | 1,017880 ms | 45,06 % |
| 7 | T3 / [98be2c0cb588455c](serie-atomique/diffs/774157/98be2c0cb588455c.patch) | valid | lancement seul | 1,805407 ms | 1,807412 ms | 1,03 % |
| 8 | T2 / [3001b0f6ac854db4](serie-atomique/diffs/774157/3001b0f6ac854db4.patch) | valid | noyau seul | 0,116688 ms | 0,116255 ms | 23,85 % |
| 9 | T3 / [78d4bf6a2d734d9e](serie-atomique/diffs/774157/78d4bf6a2d734d9e.patch) | valid | lancement seul | 1,797776 ms | 1,804639 ms | 2,59 % |
| 10 | T1 / [7b5c1c591c5b49c1](serie-atomique/diffs/774157/7b5c1c591c5b49c1.patch) | valid | noyau et lancement | 1,011250 ms | 1,005732 ms | 45,71 % |
| 11 | T4 / [cf8a5454cbb24932](serie-atomique/diffs/774157/cf8a5454cbb24932.patch) | incorrect | noyau seul | — ms | — ms | — % |
| 12 | T3 / [5dd425f05fed4fc6](serie-atomique/diffs/774157/5dd425f05fed4fc6.patch) | valid | lancement seul | 1,824487 ms | 1,815772 ms | 1,99 % |
| 13 | T2 / [13f04c1bfb924053](serie-atomique/diffs/774157/13f04c1bfb924053.patch) | valid | noyau et lancement | 0,152791 ms | 0,152354 ms | 91,78 % |
| 14 | T3 / [2eacce1387154875](serie-atomique/diffs/774157/2eacce1387154875.patch) | valid | lancement seul | 1,874114 ms | 1,866074 ms | -0,73 % |
| 15 | T1 / [b5e5fa1eb4f5434d](serie-atomique/diffs/774157/b5e5fa1eb4f5434d.patch) | valid | noyau et lancement | 1,123310 ms | 1,126161 ms | 39,21 % |
| 16 | T3 / [a9430a885f884064](serie-atomique/diffs/774157/a9430a885f884064.patch) | valid | lancement seul | 2,426411 ms | 2,417661 ms | -30,50 % |
| 17 | T1 / [2af36caca1a146f4](serie-atomique/diffs/774157/2af36caca1a146f4.patch) | valid | noyau et lancement | 1,091577 ms | 1,088160 ms | 3,37 % |
| 18 | T3 / [add2906a7ca04e04](serie-atomique/diffs/774157/add2906a7ca04e04.patch) | valid | lancement seul | 3,835059 ms | 3,829372 ms | -106,71 % |
| 19 | T2 / [83c097845ed94ccb](serie-atomique/diffs/774157/83c097845ed94ccb.patch) | valid | lancement seul | 0,117389 ms | 0,116697 ms | -0,38 % |
| 20 | T4 / [b53069b033954bb1](serie-atomique/diffs/774157/b53069b033954bb1.patch) | valid | noyau seul | 0,981678 ms | 0,984193 ms | 46,87 % |
| 21 | T1 / [193cb62dae284e4d](serie-atomique/diffs/774157/193cb62dae284e4d.patch) | valid | noyau seul | 1,020027 ms | 1,018289 ms | -0,04 % |
| 22 | T3 / [11c2b88cee8748c1](serie-atomique/diffs/774157/11c2b88cee8748c1.patch) | valid | lancement seul | 1,804458 ms | 1,803494 ms | 2,65 % |
| 23 | T1 / [62559e021f254a31](serie-atomique/diffs/774157/62559e021f254a31.patch) | valid | noyau et lancement | 1,255722 ms | 1,260563 ms | -11,93 % |
| 24 | T2 / [15fec9f090dd47ae](serie-atomique/diffs/774157/15fec9f090dd47ae.patch) | valid | lancement seul | 0,160125 ms | 0,159588 ms | -4,53 % |
| 25 | T3 / [ac957ac5f5a74191](serie-atomique/diffs/774157/ac957ac5f5a74191.patch) | valid | lancement seul | 1,797794 ms | 1,802841 ms | 52,92 % |
| 26 | T1 / [f5d3592b1dee4019](serie-atomique/diffs/774157/f5d3592b1dee4019.patch) | valid | noyau seul | 0,999045 ms | 1,002975 ms | 45,86 % |
| 27 | T2 / [36092e384a9044d4](serie-atomique/diffs/774157/36092e384a9044d4.patch) | valid | lancement seul | 0,154385 ms | 0,153453 ms | -0,51 % |
| 28 | T3 / [14302a456c844642](serie-atomique/diffs/774157/14302a456c844642.patch) | valid | lancement seul | 1,821566 ms | 1,814060 ms | 2,08 % |
| 29 | T1 / [7d8bd38d3e9c4dbd](serie-atomique/diffs/774157/7d8bd38d3e9c4dbd.patch) | valid | noyau seul | 1,090439 ms | 1,086857 ms | -2,73 % |
| 30 | T2 / [89626ec0fb3c40cb](serie-atomique/diffs/774157/89626ec0fb3c40cb.patch) | valid | lancement seul | 0,153045 ms | 0,154346 ms | -1,31 % |
| 31 | T3 / [148122a8ca014b75](serie-atomique/diffs/774157/148122a8ca014b75.patch) | valid | lancement seul | 1,826901 ms | 1,814405 ms | 2,06 % |
| 32 | T1 / [5d078c6a6edd41aa](serie-atomique/diffs/774157/5d078c6a6edd41aa.patch) | valid | noyau et lancement | 0,994716 ms | 0,999527 ms | 46,05 % |
| 33 | T3 / [208780a286264327](serie-atomique/diffs/774157/208780a286264327.patch) | duplicate | lancement seul | — ms | 1,803494 ms | 2,65 % |
| 34 | G / [bdce72cb10924576](serie-atomique/diffs/774157/bdce72cb10924576.patch) | valid | noyau et lancement | 0,094466 ms | 0,093721 ms | 19,38 % |
| 35 | G / [1d122d9ba23047ef](serie-atomique/diffs/774157/1d122d9ba23047ef.patch) | valid | lancement seul | 0,817237 ms | 0,814117 ms | 17,28 % |
| 36 | G / [e4677d85c17f4c0d](serie-atomique/diffs/774157/e4677d85c17f4c0d.patch) | valid | copie exacte | 0,094493 ms | 0,093721 ms | 0,00 % |

### 775521 — Mémoire / réserve initiale

Job **780689**. Recherche : `budget_exhausted`. G : `confirmed`. Pipeline complet : **oui**.

- **T1 — Réutilisation des sources par tuilage en mémoire partagée** : Explorer une décomposition par tuiles de particules sources en mémoire partagée : chaque CTA coopère pour charger des tuiles et les réutilise pour ses particules cibles, en balayant toutes les sources. Optimiser la taille des tuiles, la configuration block/items_per_block et les synchronisations dans la limite de shared_memory_bytes autorisée. Couvrir les tailles non multiples et tous les cas de bord; n’ajouter ni lancement ni prétraitement. Comparer les mesures officielles sur les trois tailles et ne retenir que les versions validées.
- **T2 — Parallélisme warp sur l’axe des sources et réduction des contributions** : Étudier une décomposition distincte où les lanes d’un warp parcourent des indices source différents pour une cible, accumulent des contributions partielles puis réduisent les trois composantes par warp. Adapter items_per_block au nombre de cibles réellement traitées par CTA et vérifier le calcul des indices, les queues et le masque de réduction. Conserver chaque interaction, traiter l’auto-interaction sans contribution, et valider avec l’oracle indépendant, car l’ordre de réduction change. Mesurer le temps officiel sur les trois tailles.
- **T3 — Réduction du coût mathématique par interaction avec validation de précision** : Explorer les simplifications arithmétiques par interaction : notamment calculer directement l’accélération après annulation algébrique de la masse cible, remplacer sqrt/division par une formulation avec rsqrtf et multiplications, et évaluer prudemment les regroupements/FMA. Ce sont des hypothèses à mesurer : garder G=1, softening=0.001f, toutes les interactions, l’ordre d’intégration requis et la masse copiée exactement; rejeter toute variante échouant aux tolérances ou produisant une sortie non finie. Tester toutes les tailles et cas limites, y compris masse extrême isolée, puis comparer le temps officiel.

[Métadonnées et décisions](serie-atomique/data/775521/metadata.json) · [Événements](serie-atomique/tables/775521-events.csv) · [Appels du modèle](serie-atomique/data/775521/native-calls.json)

| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |
|---:|---|---|---|---:|---:|---:|
| 1 | T1 / [f2ddc9b63af245be](serie-atomique/diffs/775521/f2ddc9b63af245be.patch) | valid | noyau et lancement | 0,920534 ms | 0,922570 ms | 50,20 % |
| 2 | T2 / [703832c7f4d84646](serie-atomique/diffs/775521/703832c7f4d84646.patch) | valid | noyau et lancement | 0,148049 ms | 0,148015 ms | 92,01 % |
| 3 | T3 / [afd29401fa204b75](serie-atomique/diffs/775521/afd29401fa204b75.patch) | incorrect | noyau seul | — ms | — ms | — % |
| 4 | G / [00f539728bdf4a2c](serie-atomique/diffs/775521/00f539728bdf4a2c.patch) | valid | noyau seul | 0,164892 ms | 0,165283 ms | -11,67 % |
| 5 | G / [44e22fac251348d2](serie-atomique/diffs/775521/44e22fac251348d2.patch) | valid | noyau et lancement | 0,136294 ms | 0,137762 ms | 6,93 % |

### 775815 — Première correction de réserve

Job **780690**. Recherche : `budget_exhausted`. G : `confirmed`. Pipeline complet : **oui**.

- **T1 — Réutilisation des particules sources par tuilage en mémoire partagée avec une cible par thread** : Explorer un noyau d’interactions par tuiles qui garde une cible par thread et charge coopérativement les positions et masses des particules sources en mémoire partagée. Gérer les tuiles finales, les barrières et l’exclusion de j==i pour toutes les tailles. Pour isoler cette piste, conserver autant que possible l’ordre et la formule arithmétiques de référence ; tester des tailles de bloc et configurations légales adaptées au noyau. Éditer seulement les deux fichiers autorisés. Rapporter la correction, les configurations exactes et les trois mesures de recherche, y compris tout ralentissement.
- **T2 — Tuilage des cibles et accumulateurs multiples par thread en registres** : Explorer une autre cartographie des interactions où chaque thread accumule en registres plusieurs cibles, afin de réutiliser les données sources et le travail de boucle tout en réduisant le coût de distribution ou de synchronisation. Lier explicitement toute constante de tuilage à la configuration de lancement correspondante, gérer les queues pour tout N, et préserver sortie complète, masses exactes et exclusion de l’auto-interaction. Distinguer cette approche du tuilage simple à une cible par thread ; ne pas spécialiser les tailles de benchmark. Valider puis mesurer les trois tailles et rapporter les configurations et régressions.
- **T3 — Réduction du coût arithmétique par paire avec validation numérique stricte** : Isoler les transformations arithmétiques par paire : étudier rsqrtf et la simplification/factorisation de la formule d’accélération pour éviter des opérations redondantes. Ne pas activer fast-math ni modifier le protocole. Comparer les variantes en respectant les tolérances GPU et l’oracle FP64, les positions coïncidentes, les dt nuls ou négatifs, les vitesses et masses variées et le cas isolé de masse extrême. Éditer seulement les fichiers autorisés ; mesurer les trois tailles et fournir résultats de correction, temps et changements retenus.

[Métadonnées et décisions](serie-atomique/data/775815/metadata.json) · [Événements](serie-atomique/tables/775815-events.csv) · [Appels du modèle](serie-atomique/data/775815/native-calls.json)

| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |
|---:|---|---|---|---:|---:|---:|
| 1 | T1 / [a0ecc881ed964bda](serie-atomique/diffs/775815/a0ecc881ed964bda.patch) | valid | noyau et lancement | 0,926477 ms | 0,923673 ms | 50,14 % |
| 2 | T2 / [bdca09b7758b4bc8](serie-atomique/diffs/775815/bdca09b7758b4bc8.patch) | valid | noyau et lancement | 2,601002 ms | 2,595245 ms | -40,09 % |
| 3 | T3 / [2437d99c0c3b4b21](serie-atomique/diffs/775815/2437d99c0c3b4b21.patch) | incorrect | noyau seul | — ms | — ms | — % |
| 4 | T1 / [4d46c44fb7074759](serie-atomique/diffs/775815/4d46c44fb7074759.patch) | valid | noyau et lancement | 0,897521 ms | 0,892888 ms | 51,80 % |
| 5 | T2 / [60d4032491464ad3](serie-atomique/diffs/775815/60d4032491464ad3.patch) | valid | noyau et lancement | 4,238943 ms | 4,224858 ms | -62,79 % |
| 6 | T1 / [005966a372d94d9e](serie-atomique/diffs/775815/005966a372d94d9e.patch) | valid | noyau et lancement | 1,000413 ms | 0,998804 ms | 46,08 % |
| 7 | T2 / [74a2d6c63a1b4bd6](serie-atomique/diffs/775815/74a2d6c63a1b4bd6.patch) | valid | noyau et lancement | 2,615073 ms | 2,609915 ms | -40,88 % |
| 8 | T1 / [5d4e46ca68854f49](serie-atomique/diffs/775815/5d4e46ca68854f49.patch) | valid | noyau et lancement | 1,103226 ms | 1,099629 ms | 40,64 % |
| 9 | T3 / [7e1c37e44c544dcb](serie-atomique/diffs/775815/7e1c37e44c544dcb.patch) | valid | noyau seul | 1,648741 ms | 1,650932 ms | 10,88 % |
| 10 | T2 / d6919defe40a4202 | generation_failed | indisponible | — ms | — ms | — % |
| 11 | T1 / [19d5e293f1004268](serie-atomique/diffs/775815/19d5e293f1004268.patch) | valid | lancement seul | 1,008016 ms | 1,005499 ms | 8,56 % |
| 12 | T3 / [28791c54d89a4620](serie-atomique/diffs/775815/28791c54d89a4620.patch) | valid | noyau seul | 1,009913 ms | 1,014219 ms | — % |
| 13 | T1 / [b20762207d5e44f9](serie-atomique/diffs/775815/b20762207d5e44f9.patch) | valid | noyau et lancement | 0,888172 ms | 0,891250 ms | 0,18 % |
| 14 | T3 / 10db1d3dac854073 | generation_failed | indisponible | — ms | — ms | — % |
| 15 | T2 / [93ae94694c134058](serie-atomique/diffs/775815/93ae94694c134058.patch) | valid | noyau et lancement | 1,653253 ms | 1,654674 ms | 36,24 % |
| 16 | T1 / 6a04d28e525a4607 | generation_failed | indisponible | — ms | — ms | — % |
| 17 | G / [34ca1c417cff4cb6](serie-atomique/diffs/775815/34ca1c417cff4cb6.patch) | valid | noyau et lancement | 1,566483 ms | 1,570321 ms | -76,19 % |
| 18 | G / [4af3cb0c24824e8b](serie-atomique/diffs/775815/4af3cb0c24824e8b.patch) | valid | noyau seul | 0,596312 ms | 0,592769 ms | 33,49 % |

### 776048 — Réserve et assemblage adaptatifs

Job **780691**. Recherche : `budget_exhausted`. G : `confirmed`. Pipeline complet : **oui**.

- **T1 — Tuilage des sources en mémoire partagée par bloc** : Explorer un kernel où chaque thread traite une cible et où chaque bloc charge coopérativement des tuiles de particules sources en mémoire partagée. Comparer des tailles de bloc/tuiles compatibles avec la limite de mémoire partagée et mesurer les trois tailles officielles. Gérer les tuiles de fin, les synchronisations et les particules coincidentes; préserver la structure Particle et l’interface.
- **T2 — Réutilisation des sources par shuffle au niveau warp** : Explorer une variante distincte sans diffusion de sources par mémoire partagée : faire charger un segment de sources par les lanes d’un warp puis diffuser ses champs aux lanes cibles avec les primitives shuffle CUDA. Assurer la participation correcte des lanes de fin et ne pas retourner avant les échanges warp. Mesurer les trois tailles officielles et valider toutes les tailles et cas limites.
- **T3 — Simplification du calcul de force et de la distance** : Explorer l’optimisation arithmétique de la boucle d’interaction : simplifier algébriquement l’accélération en annulant la masse cible, et évaluer rsqrtf pour le facteur inverse de distance au cube. Préserver l’exclusion de soi pour éviter les cas infini×zéro; maintenir une sortie correcte et des masses exactes. Vérifier soigneusement la tolérance numérique et les cas extrêmes avant de comparer les temps.
- **T4 — Blocage de plusieurs cibles par thread et réglage du lancement** : Explorer le traitement de plusieurs particules cibles par thread, en réutilisant dans les registres les champs de chaque source entre ces cibles. Adapter le mappage des cibles à block et items_per_block (grid calculée par le contrôleur), puis mesurer des configurations légales sur les trois tailles officielles. Évaluer les compromis entre réutilisation, registres et parallélisme, sans laisser de cible sans sortie.

[Métadonnées et décisions](serie-atomique/data/776048/metadata.json) · [Événements](serie-atomique/tables/776048-events.csv) · [Appels du modèle](serie-atomique/data/776048/native-calls.json)

| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |
|---:|---|---|---|---:|---:|---:|
| 1 | T1 / [ee59d2d9f6dc422b](serie-atomique/diffs/776048/ee59d2d9f6dc422b.patch) | valid | noyau et lancement | 1,010592 ms | 1,008669 ms | 45,55 % |
| 2 | T2 / [7f202149e3894459](serie-atomique/diffs/776048/7f202149e3894459.patch) | valid | noyau seul | 1,113113 ms | 1,109401 ms | 40,11 % |
| 3 | T3 / [527046c0d5534746](serie-atomique/diffs/776048/527046c0d5534746.patch) | incorrect | noyau seul | — ms | — ms | — % |
| 4 | T4 / [0f2dfb784d8d42b0](serie-atomique/diffs/776048/0f2dfb784d8d42b0.patch) | valid | noyau et lancement | 4,220542 ms | 4,188216 ms | -126,08 % |
| 5 | T1 / [b3f7172206a040f1](serie-atomique/diffs/776048/b3f7172206a040f1.patch) | valid | noyau et lancement | 0,994833 ms | 0,990679 ms | 46,52 % |
| 6 | T4 / [48a9dbbe207f464c](serie-atomique/diffs/776048/48a9dbbe207f464c.patch) | valid | noyau et lancement | 2,582948 ms | 2,600913 ms | 37,90 % |
| 7 | T2 / [7cb6054219d04953](serie-atomique/diffs/776048/7cb6054219d04953.patch) | valid | noyau et lancement | 1,883793 ms | 1,886990 ms | -70,09 % |
| 8 | T1 / [891743f03e11463b](serie-atomique/diffs/776048/891743f03e11463b.patch) | valid | noyau et lancement | 0,963617 ms | 0,965941 ms | 47,86 % |
| 9 | T4 / [1fe548aa76994ea1](serie-atomique/diffs/776048/1fe548aa76994ea1.patch) | valid | noyau et lancement | 2,703061 ms | 2,679457 ms | -44,64 % |
| 10 | T1 / [87f49c37da994ca1](serie-atomique/diffs/776048/87f49c37da994ca1.patch) | incorrect | noyau et lancement | — ms | — ms | — % |
| 11 | T2 / [c15bc6e5094d48bf](serie-atomique/diffs/776048/c15bc6e5094d48bf.patch) | valid | noyau seul | 0,891600 ms | 0,892157 ms | 51,84 % |
| 12 | T3 / [d02c3bc452244f32](serie-atomique/diffs/776048/d02c3bc452244f32.patch) | valid | noyau seul | 1,273197 ms | 1,307178 ms | 29,44 % |
| 13 | T4 / [e70620425ba048e1](serie-atomique/diffs/776048/e70620425ba048e1.patch) | valid | noyau et lancement | 3,365159 ms | 3,360110 ms | -29,19 % |
| 14 | T4 / [b599b3b7be404951](serie-atomique/diffs/776048/b599b3b7be404951.patch) | valid | noyau et lancement | 3,534793 ms | 3,473741 ms | -29,64 % |
| 15 | T2 / [e572c8a8f7b64df3](serie-atomique/diffs/776048/e572c8a8f7b64df3.patch) | valid | noyau seul | 1,658448 ms | 1,659749 ms | 12,04 % |
| 16 | T4 / [05508f91618c404d](serie-atomique/diffs/776048/05508f91618c404d.patch) | valid | lancement seul | 2,570730 ms | 2,585988 ms | 0,57 % |
| 17 | T1 / [5c553d6c3b404918](serie-atomique/diffs/776048/5c553d6c3b404918.patch) | valid | noyau et lancement | 0,993309 ms | 0,995731 ms | — % |
| 18 | T4 / [c8c91898aaea4e7c](serie-atomique/diffs/776048/c8c91898aaea4e7c.patch) | valid | lancement seul | 3,389549 ms | 3,399744 ms | 2,13 % |
| 19 | T2 / [9de5dc1f8b9a4eb0](serie-atomique/diffs/776048/9de5dc1f8b9a4eb0.patch) | valid | noyau seul | 0,977335 ms | 0,985118 ms | 11,20 % |
| 20 | T1 / [645de581d96d4755](serie-atomique/diffs/776048/645de581d96d4755.patch) | incorrect | noyau et lancement | — ms | — ms | — % |
| 21 | T4 / [254ee8e4c27d450e](serie-atomique/diffs/776048/254ee8e4c27d450e.patch) | valid | noyau et lancement | 2,570502 ms | 2,591756 ms | -39,90 % |
| 22 | T1 / [38d2651539844d5b](serie-atomique/diffs/776048/38d2651539844d5b.patch) | valid | noyau et lancement | 0,961671 ms | 0,965350 ms | 0,06 % |
| 23 | G / [fd41c25e396b42c2](serie-atomique/diffs/776048/fd41c25e396b42c2.patch) | valid | noyau seul | 0,687351 ms | 0,691174 ms | 22,53 % |
| 24 | G / [873f902b4e9c4cd7](serie-atomique/diffs/776048/873f902b4e9c4cd7.patch) | valid | noyau seul | 0,637818 ms | 0,639299 ms | 7,51 % |

### 776290 — Correction d’admission

Job **780692**. Recherche : `budget_exhausted`. G : `confirmed`. Pipeline complet : **oui**.

- **T1 — CTA shared-memory source tiling** : Investigate conventional shared-memory source tiling: cooperatively stage source particle data in chunks, synchronize correctly, and have CTA targets reuse each chunk while accumulating one output per thread. Explore tile and compatible launch configurations; handle partial tiles, self-interaction exclusion, and complete output coverage for all supported N. Do not make multi-target-per-thread coarsening the focus. Preserve the fixed interface, exact masses, and numerical tolerance; evaluate with the full correctness suite and official timing metric.
- **T2 — Per-thread multi-target coarsening** : Investigate target-axis register reuse by having each thread accumulate forces for multiple output particles, reusing each streamed source particle across those targets. Explore coarsening factors and compatible launch settings while monitoring register pressure and occupancy. Keep this path distinct from shared-memory source staging; ensure all outputs are covered for arbitrary N. Preserve the fixed interface, exact masses, and numerical tolerance; evaluate with the full correctness suite and official timing metric.
- **T3 — Pairwise arithmetic reduction** : Investigate arithmetic and instruction-count reductions in a one-output-per-thread kernel without introducing shared-memory source tiling or multi-target coarsening. Evaluate algebraically equivalent force/acceleration factoring and reciprocal-distance formulations using available CUDA math operations, retaining adequate float32 accuracy without relying on a global fast-math option. Reject any variant that fails edge cases, the independent oracle, or tolerance. Measure against the official geometric-mean objective.

[Métadonnées et décisions](serie-atomique/data/776290/metadata.json) · [Événements](serie-atomique/tables/776290-events.csv) · [Appels du modèle](serie-atomique/data/776290/native-calls.json)

| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |
|---:|---|---|---|---:|---:|---:|
| 1 | T1 / [b7d0784bb0e34f1a](serie-atomique/diffs/776290/b7d0784bb0e34f1a.patch) | valid | noyau et lancement | 1,003741 ms | 1,000133 ms | 46,01 % |
| 2 | T2 / [975a274350a84bec](serie-atomique/diffs/776290/975a274350a84bec.patch) | valid | noyau et lancement | 4,442421 ms | 4,429260 ms | -139,09 % |
| 3 | T3 / [7151826c81c94a83](serie-atomique/diffs/776290/7151826c81c94a83.patch) | incorrect | noyau seul | — ms | — ms | — % |
| 4 | T1 / [1ee0d3b3e82e43a5](serie-atomique/diffs/776290/1ee0d3b3e82e43a5.patch) | valid | noyau et lancement | 0,899768 ms | 0,897160 ms | 51,57 % |
| 5 | T2 / [5741d32b57d24721](serie-atomique/diffs/776290/5741d32b57d24721.patch) | valid | noyau et lancement | 2,727177 ms | 2,723619 ms | 38,51 % |
| 6 | T2 / [c3dc749ff6434229](serie-atomique/diffs/776290/c3dc749ff6434229.patch) | valid | noyau et lancement | 2,616992 ms | 2,616711 ms | -41,25 % |
| 7 | T1 / [97545ce3b70948ef](serie-atomique/diffs/776290/97545ce3b70948ef.patch) | valid | noyau et lancement | 1,011208 ms | 1,007599 ms | 45,61 % |
| 8 | T1 / [a47fd303c1344204](serie-atomique/diffs/776290/a47fd303c1344204.patch) | valid | noyau et lancement | 1,102419 ms | 1,098380 ms | 40,71 % |
| 9 | T2 / [337076d60da0486a](serie-atomique/diffs/776290/337076d60da0486a.patch) | valid | lancement seul | 2,617341 ms | 2,610101 ms | 4,17 % |
| 10 | T1 / [5d603cb5579a4c56](serie-atomique/diffs/776290/5d603cb5579a4c56.patch) | valid | noyau et lancement | 1,107780 ms | 1,103498 ms | -0,47 % |
| 11 | T3 / [30ef56a858b64784](serie-atomique/diffs/776290/30ef56a858b64784.patch) | valid | noyau seul | 1,186732 ms | 1,200732 ms | 35,18 % |
| 12 | T2 / [5bc8d09cf22c4203](serie-atomique/diffs/776290/5bc8d09cf22c4203.patch) | valid | noyau et lancement | 3,500416 ms | 3,465529 ms | 21,76 % |
| 13 | T1 / [250439278b004b71](serie-atomique/diffs/776290/250439278b004b71.patch) | valid | lancement seul | 0,918184 ms | 0,913664 ms | -1,84 % |
| 14 | T3 / [b5b00ebed9254b9d](serie-atomique/diffs/776290/b5b00ebed9254b9d.patch) | valid | noyau seul | 1,247915 ms | 1,263650 ms | — % |
| 15 | T2 / [5f925a566ea04b8b](serie-atomique/diffs/776290/5f925a566ea04b8b.patch) | valid | noyau et lancement | 2,726799 ms | 2,717132 ms | 38,65 % |
| 16 | T1 / [87e259578e29474c](serie-atomique/diffs/776290/87e259578e29474c.patch) | valid | noyau et lancement | 1,134238 ms | 1,132305 ms | -3,09 % |
| 17 | T1 / [c4f96bec12ba47ff](serie-atomique/diffs/776290/c4f96bec12ba47ff.patch) | valid | noyau et lancement | 0,926238 ms | 0,923505 ms | 50,15 % |
| 18 | T2 / [5a251fdb531243a9](serie-atomique/diffs/776290/5a251fdb531243a9.patch) | valid | lancement seul | 2,614079 ms | 2,605901 ms | 0,41 % |
| 19 | T3 / [47f44be9cc364759](serie-atomique/diffs/776290/47f44be9cc364759.patch) | valid | noyau seul | 1,295456 ms | 1,310073 ms | -9,11 % |
| 20 | T1 / [22a44126bf104383](serie-atomique/diffs/776290/22a44126bf104383.patch) | valid | noyau et lancement | 0,892033 ms | 0,889472 ms | 11,06 % |
| 21 | T2 / [09131d10999c43c6](serie-atomique/diffs/776290/09131d10999c43c6.patch) | valid | noyau et lancement | 2,568578 ms | 2,536184 ms | -36,90 % |
| 22 | T1 / [dbbc5eebcbc94010](serie-atomique/diffs/776290/dbbc5eebcbc94010.patch) | incorrect | noyau et lancement | — ms | — ms | — % |
| 23 | T2 / [c8b2280c09214ba7](serie-atomique/diffs/776290/c8b2280c09214ba7.patch) | valid | noyau et lancement | 3,409148 ms | 3,367529 ms | -32,78 % |
| 24 | G / [39c6be41cc524cf0](serie-atomique/diffs/776290/39c6be41cc524cf0.patch) | valid | noyau seul | 0,650019 ms | 0,648763 ms | 27,06 % |
| 25 | G / [038c7d345d454f80](serie-atomique/diffs/776290/038c7d345d454f80.patch) | valid | noyau seul | 0,327489 ms | 0,328067 ms | 49,43 % |
| 26 | G / [19e8c47b42b743d2](serie-atomique/diffs/776290/19e8c47b42b743d2.patch) | valid | copie exacte | 0,328743 ms | 0,328067 ms | 0,00 % |

### 780448 — Fiabilité et critique du plan

Job **780693**. Recherche : `budget_exhausted`. G : `confirmed`. Pipeline complet : **oui**.

- **T1 — Shared-memory source tiling with one target per thread** : Explore CTA-level shared-memory tiling of source particles, with exactly one target per thread and no multi-target coarsening. Use a consistent mapping such as items_per_block=block, stage source tiles, and handle partial tiles and output bounds. Keep shared-memory use within the allowed limit. Compare staging costs and benefits under the official protocol; pass all correctness checks before timing. Work only in src/nbody_kernel.cu and src/launch.json.
- **T2 — Per-thread target coarsening without shared memory** : Explore per-thread register coarsening only: each thread computes multiple distinct target particles while reusing source values in registers. Do not use shared-memory source tiling or block-level multi-output assignment, so this contrasts with T1. Set block and items_per_block to implement an explicit, unique target mapping (for example, items_per_block as a multiple of block); handle partial groups and write each output exactly once. Measure the reuse, register-pressure, and parallelism tradeoffs across all scored sizes under the official protocol, after full correctness checks.
- **T3 — Direct-loop control and arithmetic** : Explore direct-loop control and arithmetic changes with one target per thread, no shared-memory tiling, and no multi-target coarsening. Contrast the original self-exclusion check with split source ranges that exclude j=i without evaluating that interaction; do not simply include the self term, since intermediate overflow could make a zero-displacement term non-finite for extreme mass. Separately test arithmetic variants such as target-mass cancellation or reciprocal-square-root-based factors, first in isolation and then in useful combinations. Validate against the GPU tolerance and FP64 checks, including coincident positions and extreme mass, before timing all scored sizes under the official protocol.

[Métadonnées et décisions](serie-atomique/data/780448/metadata.json) · [Événements](serie-atomique/tables/780448-events.csv) · [Appels du modèle](serie-atomique/data/780448/native-calls.json)

| Ordre | Rôle / essai | État | Modification | Temps de recherche | Temps du rejeu commun | Gain contre parent, même GPU |
|---:|---|---|---|---:|---:|---:|
| 1 | T1 / [ba94d65d60514bb0](serie-atomique/diffs/780448/ba94d65d60514bb0.patch) | valid | noyau et lancement | 0,996163 ms | 1,001470 ms | 45,94 % |
| 2 | T2 / [8770c36638ae41c1](serie-atomique/diffs/780448/8770c36638ae41c1.patch) | valid | noyau et lancement | 2,585106 ms | 2,598807 ms | -40,28 % |
| 3 | T3 / [896161c511ca4f2b](serie-atomique/diffs/780448/896161c511ca4f2b.patch) | valid | noyau seul | 1,842930 ms | 1,848199 ms | 0,23 % |
| 4 | T3 / [2495c63d565b4f3e](serie-atomique/diffs/780448/2495c63d565b4f3e.patch) | valid | noyau seul | 1,009684 ms | 1,010576 ms | 45,45 % |
| 5 | T1 / [31ec0039ab264db0](serie-atomique/diffs/780448/31ec0039ab264db0.patch) | valid | noyau et lancement | 0,963178 ms | 0,967148 ms | 47,79 % |
| 6 | T2 / [962a42ac12d84de9](serie-atomique/diffs/780448/962a42ac12d84de9.patch) | valid | noyau et lancement | 4,165440 ms | 4,188225 ms | -61,16 % |
| 7 | T1 / [b076438362074b85](serie-atomique/diffs/780448/b076438362074b85.patch) | valid | noyau et lancement | 1,087966 ms | 1,091129 ms | 41,10 % |
| 8 | T2 / [cce1cc04e87e4405](serie-atomique/diffs/780448/cce1cc04e87e4405.patch) | valid | noyau et lancement | 2,744740 ms | 2,759140 ms | -48,94 % |
| 9 | T3 / [f7b049e78ea14fc7](serie-atomique/diffs/780448/f7b049e78ea14fc7.patch) | valid | noyau seul | 1,025174 ms | 1,030994 ms | 44,22 % |
| 10 | T1 / [1d5d63a7720744f1](serie-atomique/diffs/780448/1d5d63a7720744f1.patch) | valid | noyau et lancement | 0,993696 ms | 0,998404 ms | 46,11 % |
| 11 | T2 / [a035fbf236b64245](serie-atomique/diffs/780448/a035fbf236b64245.patch) | valid | noyau et lancement | 3,349115 ms | 3,366231 ms | 19,63 % |
| 12 | T3 / [7f81c093820b4441](serie-atomique/diffs/780448/7f81c093820b4441.patch) | valid | noyau seul | 1,009364 ms | 1,012388 ms | 45,35 % |
| 13 | T1 / [7dadbb46db0442ad](serie-atomique/diffs/780448/7dadbb46db0442ad.patch) | valid | lancement seul | 0,980549 ms | 0,987584 ms | 1,08 % |
| 14 | T1 / [bd91ae4cb4c84315](serie-atomique/diffs/780448/bd91ae4cb4c84315.patch) | valid | noyau et lancement | 0,890080 ms | 0,897459 ms | 7,21 % |
| 15 | T3 / [9562195e979e488d](serie-atomique/diffs/780448/9562195e979e488d.patch) | valid | noyau seul | 1,846100 ms | 1,851951 ms | 0,03 % |
| 16 | T1 / [1a6623f1af9b4c14](serie-atomique/diffs/780448/1a6623f1af9b4c14.patch) | valid | noyau et lancement | 0,922626 ms | 0,945618 ms | 5,29 % |
| 17 | T2 / [afc9f522ff1c4546](serie-atomique/diffs/780448/afc9f522ff1c4546.patch) | valid | noyau et lancement | 2,554343 ms | 2,558797 ms | 1,54 % |
| 18 | T3 / [fd180002914c485c](serie-atomique/diffs/780448/fd180002914c485c.patch) | valid | noyau seul | 0,899482 ms | 0,900251 ms | 51,40 % |
| 19 | T1 / [9922721cde294fb4](serie-atomique/diffs/780448/9922721cde294fb4.patch) | valid | noyau et lancement | 0,928082 ms | 0,934274 ms | 49,57 % |
| 20 | T2 / [01cc93ac7e0c4926](serie-atomique/diffs/780448/01cc93ac7e0c4926.patch) | valid | lancement seul | 2,566632 ms | 2,570950 ms | 1,07 % |
| 21 | T3 / [878d9f9ee5d54551](serie-atomique/diffs/780448/878d9f9ee5d54551.patch) | valid | noyau seul | 1,843578 ms | 1,850772 ms | 0,10 % |
| 22 | T1 / [b9a7c292332b43ee](serie-atomique/diffs/780448/b9a7c292332b43ee.patch) | valid | noyau et lancement | 0,919968 ms | 0,923197 ms | 7,82 % |
| 23 | T3 / [fa67fd200c0b4a0e](serie-atomique/diffs/780448/fa67fd200c0b4a0e.patch) | valid | noyau seul | 1,013465 ms | 1,015151 ms | 45,20 % |
| 24 | T1 / [f7c7e6dc93fc4923](serie-atomique/diffs/780448/f7c7e6dc93fc4923.patch) | valid | noyau et lancement | 0,920466 ms | 0,925410 ms | 50,05 % |
| 25 | T2 / [5836917733a541d7](serie-atomique/diffs/780448/5836917733a541d7.patch) | valid | lancement seul | 2,614293 ms | 2,628244 ms | 4,74 % |
| 26 | T3 / [5802cef1d7414553](serie-atomique/diffs/780448/5802cef1d7414553.patch) | valid | noyau seul | 0,983105 ms | 0,985405 ms | 46,81 % |
| 27 | T2 / [0cd32458d573434e](serie-atomique/diffs/780448/0cd32458d573434e.patch) | valid | noyau et lancement | 2,578602 ms | 2,582858 ms | -39,42 % |
| 28 | T1 / [fa5bfcad425f4a2c](serie-atomique/diffs/780448/fa5bfcad425f4a2c.patch) | valid | noyau et lancement | 0,893378 ms | 0,897945 ms | 51,53 % |
| 29 | T3 / [0f420ef18f3d460a](serie-atomique/diffs/780448/0f420ef18f3d460a.patch) | valid | noyau seul | 1,230345 ms | 1,231959 ms | -21,36 % |
| 30 | T1 / [c6952450abf941d9](serie-atomique/diffs/780448/c6952450abf941d9.patch) | valid | noyau et lancement | 0,983459 ms | 0,990743 ms | 46,52 % |
| 31 | T3 / [de51b752dcb04cd9](serie-atomique/diffs/780448/de51b752dcb04cd9.patch) | valid | noyau seul | 1,825557 ms | 1,825231 ms | 1,47 % |
| 32 | G / [3c15673a5456404b](serie-atomique/diffs/780448/3c15673a5456404b.patch) | valid | noyau seul | 0,588542 ms | 0,592180 ms | 34,02 % |

## Pièces de preuve

- [Table complète des campagnes](tables/comparaison-campagnes.csv), [essais](tables/comparaison-essais.csv), [événements](tables/comparaison-evenements.csv) et [appels natifs](tables/comparaison-appels.csv).
- Les sources et leurs empreintes sont conservées dans chaque série ; les différences de code sont dans `diffs/`.
- Les bases SQLite, résultats, journaux de compilation, contrôles numériques et mesures sont dans `evidence/`.
- Les messages et réponses publics des modèles ainsi que les reçus de transfert sont dans `native/` et `protocol/`.
- [Diagnostics par cas numérique](tables/diagnostics-cas.csv), [évaluations](tables/diagnostics-evaluations.csv), [sélections mémoire](tables/diagnostics-selections.csv).
- [Étapes et réparations internes aux essais](tables/diagnostics-tentatives-locales.csv), avec les hypothèses, les refus et les journaux exacts.
- Le rejeu commun conserve son ordre aléatoire, ses cinq blocs, les dix contrôles de référence et les résultats par taille dans `gpu-comparaison/`.

Les tests de douze révisions du moteur et les comparaisons avant/après des régressions restent détaillés dans le rapport historique. Aucun fichier du dépôt étudié n’a été modifié par cette comparaison.
