# Comparaison publiée → ROMEO → Forest

Mesures du 23 octobre 2026 · synthèse générée 2026-10-23T19:28:02.796533+00:00.

**57 des 62 observations du classeur ont été mesurées**, à partir de 21 familles de programmes. Cinq observations ne sont pas reproduites faute de source complète ou d’entrées exactes. La campagne finale est terminée.

Forest obtient des gains sur certaines familles et reste derrière les références sur d’autres. On ne peut donc pas conclure que le système atteint globalement les résultats du tableau. Les comparaisons de chaque variante sur ROMEO sont directes ; le passage d’un résultat publié à ROMEO combine les effets du matériel, du compilateur, des versions de sources et parfois des données et du protocole.

[Tableau de bord interactif](TABLEAU-DE-BORD.html) · [Classeur](COMPARAISON.xlsx) · [CSV](COMPARAISON.csv) · [Historique des essais](HISTORIQUE-FOREST.md) · [Audit du contexte, de la mémoire et des arbres](DETAILS-FOREST.md) · [Preuves et codes](PREUVES-ET-CODES.zip).

## Résultats représentatifs

| Programme / variante | Publié | Référence sur ROMEO | Forest sur ROMEO | Forest / référence |
|---|---:|---:|---:|---:|
| Argmin bloqué — entrée aléatoire | 14,44× | 2,65× | 9,84× | 3,71× |
| Binomial options — ISPC 1 cœur(s) | 7,94× | 4,71× | 6,95× | 1,47× |
| Black–Scholes options — ISPC 4 cœur(s) | 32,48× | 29,86× | 3,90× | 0,13× |
| Mandelbrot — ISPC 4 cœur(s) | 20,28× | 36,90× | 3,99× | 0,11× |
| Boehm GEMM — O3_FINAL | 101,31× | 62,08× | 744,15× | 11,99× |
| Double tampon | 55,92× | 75,63× | 48,64× | 0,64× |
| SGEMM CUDA naïf → référence cuBLAS | 75,24× | 100,50× | 48,64× | 0,48× |
| Réduction naïve → plusieurs éléments par thread | 30,04× | 3,32× | 6,58× | 1,98× |
| Softmax naïf PyTorch → Triton fusionné | 4,15× | 4,69× | 5,07× | 1,08× |
| sum(abs(x)) : deux kernels → un kernel fusionné | 3,00× | 2,75× | 4,19× | 1,52× |
| S4ConvD : somme des temps des kernels de convolution | 3,26× | 6,28× | 2,31× | 0,37× |

Chaque speedup ROMEO est calculé par **temps du même naïf / temps de la variante**. La dernière colonne vaut temps de la référence / temps de Forest : au-dessus de 1, Forest est plus rapide. Les références publiées ne sont pas réutilisées comme dénominateur ROMEO.

Sur les lignes documentaires mesurées, Forest est plus rapide à chaque bloc dans 22 cas, la référence dans 30, et le classement varie dans 5. **Ces comptes ne sont pas un taux de réussite sur des problèmes indépendants** : plusieurs lignes partagent le même naïf et le même candidat Forest, notamment les étapes SGEMM, la réduction et les matériels historiques de transpose. Les étendues observées ne sont pas des intervalles de confiance ; aucune significativité statistique n’est affirmée.

## Matériel et comparabilité

| Élément | CPU ROMEO | GPU ROMEO |
|---|---|---|
| Processeur | AMD EPYC 9654, 2 × 96 cœurs ; SMT désactivé | CPU Grace ARM + NVIDIA GH200 120 Go |
| Allocation | Sous-ensemble de 1, 4, 8 ou 40 cœurs physiques | 1 GPU alloué ; 4 CPU pour les outils/hôtes |
| Logiciels | GCC 14.2 ; Clang 17.0.6 pour la ligne popcount Clang ; ISPC 1.32.0, LLVM 23.1.2 | CUDA 12.6.3 ; pilote 590.48.01 ; torch 2.9.1+cu126 ; Triton 3.5.1 |
| Compilation | C++17, -O3 -march=native ; ISPC -O2 --target=avx512skx-x16 | -O3 -arch=sm_90 ; précision FP32, pas de remplacement par TF32 |

Les nœuds CPU sont partagés ; les cœurs attribués et l’affinité sont consignés. Il ne s’agit pas de nœuds entiers réservés. Les variantes d’un même cas final sont exécutées en série dans la même allocation, avec un ordre pseudo-aléatoire par bloc. Les familles indépendantes peuvent utiliser des allocations distinctes. Fréquence, caches, NUMA et charge extérieure restent des sources de variabilité ; aucun compteur matériel ne permet ici d’en attribuer précisément l’effet. Le tableau fournit les temps absolus, la dispersion et les compilateurs au lieu d’une correction fondée sur les FLOPS théoriques.

Les lignes à 1/4/40 cœurs ne sont pas toutes une étude à taille constante : AO passe de 512² à 2048², et les options de 131 072 à 2 097 152 éléments pour les lignes à 40 cœurs. Chaque speedup utilise son propre naïf de même taille. On ne peut pas déduire directement de ces lignes une efficacité de montée en nombre de cœurs à problème constant.

Le speedup publié et le speedup ROMEO répondent à une question différente du ratio Forest/référence sur ROMEO. Un gain publié de 30× qui devient 3× sur GH200 ne prouve pas que l’optimisation est mauvaise : le naïf et l’optimisé peuvent bénéficier différemment du nouveau matériel et du nouveau compilateur. L’effet *strictement matériel* nécessiterait également le même code, les mêmes entrées et un protocole identique sur les deux anciennes et nouvelles machines, ce qui n’a pas été réalisé.

Le code du moteur est identique dans les 22 lancements, vérification SHA256 fichier par fichier à l’appui. Les 58 fichiers Python correspondent au dépôt propre pour ces sources au commit `934627c1399b48e4aa0f25630e9c4223680a3511`. L’empreinte agrégée du manifeste trié vaut `047ebea64b2e1d39249d1b6303e0bcbcf1ff92ffb548658a5c91cb2d5ab7fb4e`. Les adaptateurs changent selon la famille ; la politique du moteur reste gelée.

## Protocole suivi

1. Lire les 62 lignes et leurs conditions dans le classeur, retrouver les sources primaires, figer les commits et empreintes des fichiers.
2. Construire et tester d’abord les références naïves et optimisées sur ROMEO : jobs 781111 (GPU initial, puis répétitions supplémentaires 781153), 781157/781163 (CPU et diagnostics), 781161 (GPU complémentaire), 781186 (rendus). Le test Clang 781195 commence également par les références avant de compiler les sources Forest déjà retenues sous GCC.
3. Démarrer Forest du naïf avec le moteur gelé, sans lui fournir le code optimisé de référence. Les contrôles, tailles, drapeaux de compilation et fichiers de données sont protégés. Le seul naïf réparé avant la recherche est UTF-8, dont la version historique est objectivement incorrecte sur des séquences malformées.
4. Conserver essais corrects, incorrects, erreurs d’infrastructure et intégrations. Confirmer le meilleur candidat et G séparément. Aucune optimisation manuelle n’est ajoutée aux candidats générés.
5. Recompiler les sources sélectionnées inchangées puis remesurer naïf, référence, meilleur confirmé et G sur les mêmes entrées, après échauffement. Les valeurs du tableau viennent de cette phase indépendante, pas du meilleur temps de recherche.

### Mesures et contrôles

| Groupe | Blocs finaux | Chronométrage | Contrôles supplémentaires |
|---|---:|---|---|
| CPU | 7 | Boucle native adaptative ≥0,1 s ; 3 échauffements ; temps mural | Graines 1907 + 53×bloc, variantes de données, gardes et immutabilité ; oracles adaptés au problème |
| GPU initial | 9 | Événements CUDA ; SGEMM 20 répétitions/5 échauffements, transpose et stencil 100/10 | Sorties complètes, tailles supplémentaires, erreurs CUDA, gardes mémoire |
| GPU complémentaire | 9 | Même chronomètre pour toutes les variantes d’un cas ; kernels/wrappers complets | 79 enregistrements diagnostiques, références FP64 selon les cas |
| Rendus | 3 | C++ steady_clock ; 2 échauffements ; boucle adaptative ≥0,05 s | Autres résolutions, caméra/densités/lumières modifiées, images complètes et IDs exacts pour ray tracing |

Le rapport des médianes est retenu, avec deux exceptions documentaires : UTF-8 « BEST » utilise le minimum des temps de lots, « MEAN » leur moyenne. L’ordre varie entre blocs. Les données et graines sont identiques entre variantes d’un bloc ; sur CPU, les SHA256 d’entrée ont été comparés automatiquement. Un seul tirage Forest par famille ne permet pas d’évaluer sa variabilité entre campagnes ou modèles.

AO reste un rendu stochastique : le générateur aléatoire peut différer pour permettre le parallélisme, mais la scène, les échantillons primaires et les 8×8 rayons d’occlusion par impact sont conservés. Le contrôle combine RMSE ≤0,06, biais moyen absolu ≤0,015 et revue du code. Une tolérance image seule ne suffirait pas à justifier une baisse de qualité.

## Résultats du moteur, diagnostics et régressions

18/21 campagnes retenues ont achevé le pipeline complet. L’historique contient 173 essais enregistrés : 2 generation_failed, 2 incorrect, 7 infrastructure_error, 162 valid. Les 1243 enregistrements finaux incluent les diagnostics, pas seulement les temps. Échecs finaux de candidats Forest/G : **0**. Échecs finaux de références : 3 (1 naïf UTF-8 sur texte malformé et 2 tests du volume ISPC hors de sa précondition de dimensions).

- **UTF-8** : l’audit indépendant teste 79 729 chaînes par version, dont toutes les séquences de 1 et 2 octets, des frontières SIMD et des mutations déterministes. Le naïf historique échoue 5 773 fois ; le naïf réparé, la référence AVX, Forest et G n’échouent pas sur cet audit. Les speedups du tableau restent limités au texte valide chronométré. Le gain de validation correcte est distingué du gain de vitesse.
- **Accès aux outils** : deux essais de recherche Base64 échouent après une tentative d’accès à un outil non autorisé par le worker. Le meilleur confirmé reste le naïf scalaire. Le même diagnostic touche certaines branches des rendus (AO, ray tracing et deferred). Les journaux indiquent exactement les essais affectés. Cela montre une limite de cette exécution du moteur, pas l’impossibilité d’optimiser ces algorithmes. G Base64 existe mais est plus lent.
- **GPU initial** : recherche, sélection et confirmation ont produit des sources valides pour SGEMM, stencil et transpose ; la fin du pipeline échoue sur l’empaquetage, car l’adaptateur initial ne fournissait pas Makefile/run.sh. Le défaut est conservé dans les résultats. Les sources ont ensuite été revalidées et chronométrées indépendamment.
- **Deferred** : le premier import dépasse la limite de lecture de source de Mother (32 000 caractères) avant tout appel au modèle. Un nouveau lancement enlève uniquement l’indentation en début de ligne ; le flux de tokens C++ est identique, commentaires de licence conservés. Le premier échec reste archivé. Les sources et protocoles expérimentaux ne sont pas optimisés à cette occasion.
- **Volume ISPC** : le noyau documente une précondition de dimensions multiples de 4. Les contrôles additionnels en 96×126 et 128×169 sortent de ce domaine et provoquent deux plantages. Un audit distinct avec une zone de garde agrandie confirme 192 et 384 écritures hors de l’image, pour les versions ISPC simple et tasks. Sur les tailles admissibles 224×296 et 336×444, les 10 contrôles des cinq variantes passent. Forest et le naïf passent aussi les deux petites tailles hors domaine ISPC. Le benchmark 896×1184 satisfait la précondition ; ses temps ne sont pas rejetés. Aucun masque ou changement du code de référence n’a été ajouté aux mesures.
- **Clang** : le premier job final ne charge pas libomp et produit des erreurs d’infrastructure, malgré un code de sortie SLURM zéro. Il est exclu des temps. Le job 781195 charge le runtime et fournit les mesures valides.
- **Intégration G** : le tableau principal utilise le meilleur confirmé par le moteur. Les colonnes détaillées conservent G même s’il régresse, en particulier sur SGEMM, GEMM CPU, Base64 et ray tracing à 40 cœurs (13,38× pour le meilleur confirmé contre 10,10× pour G). Aucun remplacement manuel après coup n’est effectué.

### Changements qui expliquent les gains observés

La revue du code relie les candidats aux transformations réelles ; elle ne remplace pas une étude d’ablation.

| Famille | Transformation observée dans le candidat retenu | Limite d’interprétation |
|---|---|---|
| Argmin | Réduction SIMD par blocs, puis récupération stable du premier indice | Deux distributions et tailles de contrôle, pas tous les usages possibles |
| GEMM CPU | Micro-noyau AVX2/FMA 4×16 et parallélisme OpenMP | Comparaison à une adaptation de l’article ; le facteur face au naïf est très dépendant du compilateur |
| Binomial | Espérance binomiale équivalente aux 63 transitions historiques, récurrence des puissances, OpenMP | Le gain à 1/4 cœurs ne garantit pas le même classement à 40 |
| Réduction GPU | Plusieurs éléments par thread, réduction par warp et deux passes | Référence moderne portée, pas exécution inchangée du code G80 |
| sum(abs) | Fusion et réduction par blocs CUB, plusieurs accumulateurs | Volume exact fixé à 1 GiB, celui du billet historique reste ambigu |
| Softmax | Noyau Triton fusionné avec regroupement de lignes | Le gain face au Triton de référence est plus petit que celui face au naïf |
| Occlusion ambiante | Calculs invariants d’intersection réutilisés et accumulation RGB commune | Nombre de rayons conservé ; le candidat reste séquentiel après l’échec de la branche de parallélisme |
| Volume | OpenMP, réutilisation des indices et pointeurs d’interpolation, intersection des ombres adaptée aux origines intérieures | Pas d’échantillonnage et rayons conservés ; domaine de la référence ISPC limité aux dimensions multiples de 4 |
| S4ConvD | Fusion du forward et d’une partie du backward, réduction du gradient poids | Ici la référence complète reste plus rapide ; pas d’extrapolation à une epoch |
| Black-Scholes / Mandelbrot | Parallélisme CPU, vectorisation restant limitée face à ISPC | La montée en nombre de cœurs ne suffit pas à combler le déficit SIMD |

Les hypothèses détaillées, les commits parents, les essais invalides et les essais d’intégration figurent dans [HISTORIQUE-FOREST.md](HISTORIQUE-FOREST.md). Les compteurs de tokens natifs peuvent additionner plusieurs fois des compteurs cumulés de conversations reprises ; aucun coût total n’est présenté comme audité.

La cible de 30 minutes est une cible d’admission, avec la politique `finish-started` : les confirmations commencées peuvent la dépasser. La feuille Moteur et l’historique donnent les durées observées et dépassements. Dans les rendus, chaque évaluation reconstruit aussi l’image oracle hors chronométrage : cette validation répétée peut dominer le temps mural de la campagne, sans faire partie du temps du noyau affiché. Les statistiques d’efficacité SLURM décrivent l’allocation entière, attentes modèle comprises ; elles ne mesurent pas l’efficacité du noyau optimisé seul.

## Observations non reproduites

- **Parcours BVH récursif → parcours itératif ordonné et sans doublons** : Scène APEX Destruction exacte (12486 objets, 73704 paires) non fournie ; article contenant des extraits, pas un programme complet prêt à rejouer. Aucun speedup inventé sur une scène substituée. [Source](https://developer.nvidia.com/blog/thinking-parallel-part-ii-tree-traversal-gpu/).
- **Génération de hiérarchie BVH descendante → entièrement parallèle** : Codes Morton triés de la scène publiée et programme complet manquants. Une autre scène ne reproduirait pas ce point de mesure. [Source](https://developer.nvidia.com/blog/thinking-parallel-part-iii-tree-construction-gpu/).
- **S4ConvD : temps d'une epoch d'entraînement** : Données CSV et état complet du modèle/entraînement non disponibles dans les éléments fournis ; les kernels ont été testés séparément, sans extrapoler leur gain à l’epoch. [Source](https://arxiv.org/html/2604.25422v1).
- **MIT GEMM : Python naïf vers C/AVX parallèle** : Version optimisée complète et entrées exactes de la démonstration MIT non fournies. Les slides et une reproduction tierce ne suffisent pas à rejouer exactement le programme annoncé. Aucun temps extrapolé. [Source](https://ocw.mit.edu/courses/6-172-performance-engineering-of-software-systems-fall-2018/d0c73dd51c79b95196a2e6faa824e1b4_MIT6_172F18_lec1.pdf).
- **MIT GEMM : C initial vers C/AVX parallèle** : Version AVX complète de la démonstration MIT et entrées exactes non fournies. Le GEMM FP32 1024² mesuré ailleurs ne remplace pas ce GEMM FP64 4096². [Source](https://ocw.mit.edu/courses/6-172-performance-engineering-of-software-systems-fall-2018/d0c73dd51c79b95196a2e6faa824e1b4_MIT6_172F18_lec1.pdf).

## Adaptations et sources, par famille

Les lignes « remesurées » incluent des ports ou reconstructions explicités ci-dessous. Ce sont des comparaisons reproductibles sur ROMEO, pas des reproductions exactes de toutes les conditions historiques.

- **aobench** — ISPC 1.32.0 courant, pas la version historique. Scène et nombre de rayons conservés ; générateurs aléatoires natifs différents. Contrôle image RMSE ≤0,06 et biais moyen ≤0,015 ; revue du candidat confirmant la conservation du nombre de rayons. [Source 1](https://ispc.github.io/perf.html)
- **argmin** — 8192 int32 ; premier indice en cas d’égalité. Référence du dépôt courant : bloc 2048, contre 256 dans l’article. Compilation GCC 14.2 -O3 -march=native. [Source 1](https://en.algorithmica.org/hpc/algorithms/argmin/)
- **base64** — Image Lena fournie : 141020 octets encodés, 105764 décodés ; résultat exact. Deux erreurs d’accès aux outils pendant la recherche ; Forest a conservé le naïf scalaire. [Source 1](https://github.com/lemire/fastbase64)
- **binomial** — ISPC 1.32.0 courant. 128k=131072 et 2M=2097152 ; constantes originales pour le chronométrage, options variées pour la correction. GCC 14.2 contre ISPC LLVM 23.1.2/AVX-512. Le code conserve la convention historique de 63 transitions. [Source 1](https://ispc.github.io/perf.html)
- **blackscholes** — ISPC 1.32.0 courant. 128k=131072 et 2M=2097152 ; constantes originales au chronométrage et entrées variées aux contrôles. GCC 14.2 contre ISPC LLVM 23.1.2/AVX-512. [Source 1](https://ispc.github.io/perf.html)
- **deferred** — ISPC 1.32.0 ; fichier fourni pp1280x720.bin. Frame entière, RGB contrôlé à ±1 niveau. La hiérarchie de profondeur dynamique est recalculée à chaque rendu. [Source 1](https://ispc.github.io/perf.html)
- **gemm_cpu** — Reconstitution des extraits de l’article ; tuile intérieure fixée à 16, non précisée dans la source. FP32, 1024², 8 cœurs physiques ROMEO contre 8 threads logiques historiques. GCC 14.2 strict contre Clang 14 fast-math historique ; pas une reproduction exacte. [Source 1](https://siboehm.com/articles/22/Fast-MMM-on-CPU)
- **mandelbrot** — Exemple ISPC courant : 1536×1024 pixels, 512 itérations maximum. La publication ne précise pas la taille. Même compte entier par pixel. [Source 1](https://ispc.github.io/perf.html)
- **noise** — Exemple ISPC courant : 768×768, bornes [-10,10], 8 octaves. La publication ne précise pas la taille. Tolérance absolue et relative 5e-5. [Source 1](https://ispc.github.io/perf.html)
- **popcount** — Boucle dépendante uint32 avec débordement modulaire, 1000 valeurs×100 passages. Le temps est celui du lot complet. Même code source pour les compilateurs ; version historique non précisée. Forest a recherché sous GCC ; ses sources retenues sont ici recompilées inchangées avec Clang 17.0.6. [Source 1](https://github.com/BartMassey/popcount)
- **raytracer** — Exemple ISPC courant : Sponza 900×900 ; scène et BVH fournis. Identifiants des triangles exacts, profondeur avec tolérance 5e-4 absolue et relative. [Source 1](https://ispc.github.io/perf.html)
- **reduction** — Port actuel du sample NVIDIA ; variantes 5–7 utilisent des shuffles synchronisés, pas le code G80 inchangé. 2^22 int32, 128 threads de référence, réduction complète multi-passes ; entiers bornés [-5,5]. [Source 1](https://developer.download.nvidia.com/assets/cuda/files/reduction.pdf)
- **s4convd** — Kernels CUDA des notebooks, B=16384 H=128 L=48 K=47. Entrées aléatoires communes, distinctes des projections du modèle publié. Forward, gradient entrée, gradient poids et remise à zéro chronométrés ensemble. Pas de mesure d’epoch. [Source 1](https://arxiv.org/html/2604.25422v1)
- **sgemm** — Sources SGEMM_CUDA figées ; M=N=K=4096 FP32, alpha=0,5 beta=3. CUDA 12.6.3, -O3 -arch=sm_90 ; oracle cuBLAS sans TF32. Même calcul sur GH200 pour tous les candidats. [Source 1](https://github.com/siboehm/SGEMM_CUDA)
- **softmax** — Tutoriel Triton courant, torch 2.9.1+cu126 et Triton 3.5.1. FP32 4096². Même triton.testing.do_bench pour tous, allocations/lancements inclus, compilation JIT préchauffée. [Source 1](https://triton-lang.org/main/getting-started/tutorials/02-fused-softmax.html)
- **stencil3d** — Exemple ISPC courant : 256³, 6 étapes, deux grilles contrôlées. Entrées aléatoires communes ; remise à zéro/copier la grille incluse dans tous les temps. Taille historique non précisée. [Source 1](https://ispc.github.io/perf.html)
- **stencil_y** — Sources NVIDIA : grille 64³, halo périodique de période 63, coefficients 63×[4/5,-1/5,4/105,-1/280]. Même calcul et oracle sur GH200. [Source 1](https://developer.nvidia.com/blog/finite-difference-methods-cuda-c-part-2/)
- **sumabs** — Reconstitution de l’extrait NVIDIA ; 1 GiB exactement (268435456 float), 256 threads et 1024 blocs de référence. Nombre historique exact non établi. Remise à zéro de la sortie incluse ; oracle FP64, rtol 2e-4. [Source 1](https://developer.nvidia.com/blog/kernel-fusion-in-nvidia-cuda-optimizing-memory-traffic-and-launch-overhead/)
- **transpose** — Sources NVIDIA : 1024² FP32. Même mesure ROMEO réutilisée pour les deux matériels publiés ; il ne s’agit pas de deux réplications indépendantes. [Source 1](https://developer.nvidia.com/blog/efficient-matrix-transpose-cuda-cc)
- **utf8** — Générateur déterministe de même distribution de longueurs, pas la même séquence libc historique. Le naïf original est incorrect sur certaines chaînes malformées ; ses temps concernent uniquement du texte valide. Forest part de sa version corrigée. Contrôles supplémentaires exhaustifs et aléatoires séparés. [Source 1](https://github.com/lemire/fastvalidate-utf-8)
- **volume** — Exemple ISPC courant : caméra 896×1184 et density_lowres.vol. Taille historique non précisée. Même ray marching ; tolérance 5e-4 absolue et relative. Référence ISPC limitée aux dimensions multiples de 4 : les contrôles 96×126 et 128×169, hors précondition, plantent. Forest et le naïf y passent. Audit séparé sur tailles admissibles 224×296 et 336×444. [Source 1](https://ispc.github.io/perf.html)

## Tableau complet des 62 observations

| Programme / variante | Publié | Référence sur ROMEO | Forest sur ROMEO | Forest / référence |
|---|---:|---:|---:|---:|
| AOBench — ISPC 1 cœur(s) | 6,19× | 7,24× | 1,07× | 0,15× |
| AOBench — ISPC 4 cœur(s) | 28,06× | 14,24× | 1,07× | 0,07× |
| Binomial options — ISPC 1 cœur(s) | 7,94× | 4,71× | 6,95× | 1,47× |
| Binomial options — ISPC 4 cœur(s) | 33,43× | 18,74× | 27,68× | 1,48× |
| Black–Scholes options — ISPC 1 cœur(s) | 8,45× | 9,56× | 1,00× | 0,10× |
| Black–Scholes options — ISPC 4 cœur(s) | 32,48× | 29,86× | 3,90× | 0,13× |
| Deferred shading — ISPC 1 cœur(s) | 5,02× | 7,19× | 1,00× | 0,14× |
| Deferred shading — ISPC 4 cœur(s) | 23,06× | 26,52× | 3,45× | 0,13× |
| Mandelbrot — ISPC 1 cœur(s) | 6,21× | 9,26× | 1,00× | 0,11× |
| Mandelbrot — ISPC 4 cœur(s) | 20,28× | 36,90× | 3,99× | 0,11× |
| Perlin noise — ISPC 1 cœur(s) | 5,37× | 9,89× | 1,19× | 0,12× |
| Ray tracer — ISPC 1 cœur(s) | 4,31× | 6,05× | 1,03× | 0,17× |
| Ray tracer — ISPC 4 cœur(s) | 20,29× | 23,12× | 3,96× | 0,17× |
| 3D stencil — ISPC 1 cœur(s) | 4,05× | 4,78× | 5,85× | 1,23× |
| 3D stencil — ISPC 4 cœur(s) | 15,53× | 13,45× | 13,39× | 1,00× |
| Volume rendering — ISPC 1 cœur(s) | 3,60× | 2,86× | 1,14× | 0,40× |
| Volume rendering — ISPC 4 cœur(s) | 17,53× | 11,48× | 3,54× | 0,31× |
| AOBench — ISPC 40 cœurs | 182,36× | 136,75× | 1,07× | 0,01× |
| Binomial options — ISPC 40 cœurs | 63,85× | 143,48× | 77,65× | 0,54× |
| Black–Scholes options — ISPC 40 cœurs | 83,97× | 120,00× | 3,55× | 0,03× |
| Ray tracer — ISPC 40 cœurs | 195,67× | 42,40× | 13,38× | 0,32× |
| Volume rendering — ISPC 40 cœurs | 243,18× | 106,06× | 32,92× | 0,31× |
| Popcount uint32 — CLANG | 21,42× | 16,40× | 16,40× | 1,00× |
| Popcount uint32 — GCC | 16,27× | 12,81× | 12,81× | 1,00× |
| Base64 lena — baseline scalar_base64_decode | 9,86× | 9,56× | 1,00× | 0,10× |
| Base64 lena — baseline chromium_base64_decode | 8,76× | 6,96× | 0,73× | 0,10× |
| Validation UTF-8 aléatoire — minimum | 24,48× | 4,85× | 2,16× | 0,45× |
| Validation UTF-8 aléatoire — moyenne | 22,69× | 4,88× | 2,17× | 0,44× |
| Argmin bloqué — entrée aléatoire | 14,44× | 2,65× | 9,84× | 3,71× |
| Argmin bloqué — entrée décroissante | 10,21× | 2,40× | 8,97× | 3,74× |
| Boehm GEMM — DEFAULT_FINAL | 280,06× | 39,65× | 475,24× | 11,99× |
| Boehm GEMM — O3_FINAL | 101,31× | 62,08× | 744,15× | 11,99× |
| Boehm GEMM — O3_REORDER | 18,21× | 76,26× | 744,15× | 9,76× |
| Boehm GEMM — O3_TILING | 23,16× | 74,95× | 744,15× | 9,93× |
| Coalescence des accès mémoire globaux | 6,43× | 12,76× | 48,64× | 3,81× |
| Cache en mémoire partagée | 9,64× | 18,38× | 48,64× | 2,65× |
| Tuilage 1D | 27,43× | 33,99× | 48,64× | 1,43× |
| Tuilage 2D | 51,69× | 51,79× | 48,64× | 0,94× |
| Évitement des conflits de banques par linéarisation | 52,47× | 56,25× | 48,64× | 0,86× |
| Évitement des conflits de banques par décalage | 53,27× | 46,51× | 48,64× | 1,05× |
| Double tampon | 55,92× | 75,63× | 48,64× | 0,64× |
| Accès mémoire vectorisés | 59,02× | 62,69× | 48,64× | 0,78× |
| Autotuning | 63,82× | 62,38× | 48,64× | 0,78× |
| SGEMM CUDA naïf → meilleur kernel maison publié | 70,48× | 71,62× | 48,64× | 0,68× |
| SGEMM CUDA naïf → référence cuBLAS | 75,24× | 100,50× | 48,64× | 0,48× |
| Réduction : suppression des branchements divergents | 2,33× | 1,41× | 6,58× | 4,68× |
| Réduction : adressage séquentiel | 4,68× | 1,51× | 6,58× | 4,37× |
| Réduction : premier ajout pendant le chargement global | 8,34× | 2,50× | 6,58× | 2,63× |
| Réduction : déroulage du dernier warp | 15,01× | 2,53× | 6,58× | 2,60× |
| Réduction : déroulage complet | 21,16× | 2,51× | 6,58× | 2,62× |
| Réduction naïve → plusieurs éléments par thread | 30,04× | 3,32× | 6,58× | 1,98× |
| Transposition naïve → optimisée, Tesla M2050 | 5,29× | 5,02× | 5,06× | 1,01× |
| Transposition naïve → optimisée, Tesla K20c | 2,61× | 5,02× | 5,06× | 1,01× |
| Dérivée Y : tuiles 4×64 → 32×64 | 1,67× | 0,86× | 1,03× | 1,21× |
| Softmax naïf PyTorch → Triton fusionné | 4,15× | 4,69× | 5,07× | 1,08× |
| Parcours BVH récursif → parcours itératif ordonné et sans doublons | 15,00× | NR | NR | NR |
| Génération de hiérarchie BVH descendante → entièrement parallèle | 50,00× | NR | NR | NR |
| sum(abs(x)) : deux kernels → un kernel fusionné | 3,00× | 2,75× | 4,19× | 1,52× |
| S4ConvD : somme des temps des kernels de convolution | 3,26× | 6,28× | 2,31× | 0,37× |
| S4ConvD : temps d'une epoch d'entraînement | 1,29× | NR | NR | NR |
| MIT GEMM : Python naïf vers C/AVX parallèle | 53292,00× | NR | NR | NR |
| MIT GEMM : C initial vers C/AVX parallèle | 2963,51× | NR | NR | NR |

## Fichiers et traçabilité

Le classeur source est conservé intact dans les preuves. Les feuilles du nouveau classeur distinguent les ratios calculés, les conditions, les mesures brutes, les essais et l’état du moteur. Le dashboard expose les temps, étendues par paire, diagnostics et commits au clic sur une ligne.

L’archive contient les résultats bruts, les captures d’environnement, les scripts, les sources des références et les archives natives des campagnes. MANIFEST-SHA256.json permet de contrôler les fichiers inclus. Les détails d’authentification du relais ne sont pas exportés. Les calculs ont été exécutés dans des jobs SLURM, pas sur le nœud de login.

L’étude historique antérieure est conservée séparément : [comparaison des anciens codes](../comparaison-historique/TABLEAU-DE-BORD.html) et [bilan historique](../BILAN-COMPLET.md). Cette nouvelle campagne compare le moteur gelé courant aux programmes du classeur ; elle ne rejoue pas une nouvelle fois toutes les anciennes versions du moteur sur chaque nouvelle famille.
