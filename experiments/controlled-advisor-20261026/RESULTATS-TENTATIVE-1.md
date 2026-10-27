# Résultat de la tentative contrôlée du 26 octobre 2026

Vérifié le **26 octobre 2026 à 20 h 34 (Europe/Paris)**.

**Cette tentative ne fournit aucune comparaison valide de performance.**
Les six blocs ont échoué sur le stockage temporaire après 33 à 35 minutes.
Ils ne tournent plus. Sur 30 recherches prévues, 6 ont commencé, 24 n’ont
pas commencé, et aucune n’a livré de programme optimisé confirmé.

| Problème | Répétition | Première condition | Job | Durée du bloc | Essais terminés* | Appels TabPFN | Choix de parent modifiés |
|---|---:|---|---|---|---:|---:|---:|
| GEMM CPU | 1 | Sans conseiller | 784836 | 33 min 46 s | 16 | 0 | 0 |
| GEMM CPU | 2 | Données du même arbre | 784837 | 33 min 19 s | 14 | 0 | 0 |
| GEMM CPU | 3 | Validation renforcée | 784838 | 34 min 26 s | 17 | 3 | 0 |
| Black–Scholes | 1 | Données et validation modifiées | 784839 | 34 min 46 s | 8 | 0 | 0 |
| Black–Scholes | 2 | Conseiller actuel | 784840 | 35 min 17 s | 10 | 1 | 1 |
| Black–Scholes | 3 | Sans conseiller | 784841 | 34 min 27 s | 9 | 0 | 0 |

*Statut `completed` des essais dans le registre récupéré ; ce ne sont pas
des recherches terminées, ni des codes livrés avec confirmation finale.
Ces comptes comprennent les essais d’intégration.

## Cause observée

Les six journaux SLURM se terminent par :

```text
OSError: [Errno 28] No space left on device
/tmp/forest-controlled-…/forest-app-…/arm-result.json.tmp
```

Des essais échouent aussi au moment d’écrire leurs journaux de mesure.
Les six recherches utilisaient `romeo-c021` et se sont arrêtées entre
**11 h 21 et 11 h 23**, heure de Paris.

Le stockage temporaire a refusé les écritures. Les preuves conservées ne
permettent pas de distinguer avec certitude une saturation des blocs d’une
saturation des inodes, ni d’attribuer l’occupation totale à nos seuls essais.

Le lancement préparé par l’opérateur utilisait `/tmp` pour contourner le quota
de fichiers du stockage partagé rencontré pendant la préparation. Cette solution
n’a pas assuré la capacité nécessaire pendant l’exécution. Le journal final de
chaque recherche était lui-même écrit dans cet espace devenu indisponible,
ce qui a interrompu le bloc avant le lancement des quatre conditions suivantes.

Il s’agit d’un échec de l’infrastructure d’expérimentation. Ces résultats ne
démontrent ni une régression ni une amélioration due à TabPFN, aux données ou
aux décisions de Mother.

## Remesure et rapport automatique

Le job **784842** s’est exécuté sur `romeo-c022` pendant 1 min 46 s,
puis a déclaré un échec de la campagne. Les deux phases de mesure ont pu
évaluer **uniquement les programmes naïfs** : aucun candidat optimisé livré
n’était disponible. Leurs codes de sortie individuels à zéro ne constituent
donc pas une comparaison réussie.

Le rapport automatique conserve les 30 conditions attribuées et affiche
**zéro paire valide**. Il signale aussi deux défauts de traitement des sorties
manquantes : addition d’un temps absent pour les six recherches interrompues
et ouverture impossible d’une base inexistante pour les 24 non démarrées.
Ce sont des erreurs secondaires du rapport ; elles ne sont pas la cause
de l’arrêt des recherches.

Sur les essais partiels récupérés, quatre appels réels à TabPFN ont été
enregistrés et un seul a changé le choix de parent. Ce volume est insuffisant
pour évaluer son utilité. Les six recherches n’offrent ni conditions appariées
complètes, ni même budget effectivement consommé, ni confirmation finale.

## Preuves conservées

- [État et interventions récupérés](results-attempt-1/incident-evidence.json).
- [Résultat du traitement final](results-attempt-1/completion.json).
- [Tableau automatique sans paire valide](results-attempt-1/automatic-comparison/RAPPORT.md).
- Journaux d’erreur dans `results-attempt-1/scheduler-errors/`.
- Archives complètes de récupération et de mesures téléchargées ; empreintes
  SHA-256 locales comparées aux empreintes distantes.
- Les contrôles de départ restent valides : plans initiaux identiques par problème,
  six conversations distinctes et mémoire neuve. Ils n’assuraient pas la réussite
  de plusieurs heures d’exécution.

## Avant une nouvelle tentative

Vérifier l’espace et les inodes sur le stockage réellement utilisé par chaque
allocation, prévoir une marge et une surveillance en cours d’exécution, puis
rendre les journaux d’état et les sauvegardes indépendants du stockage de travail.
Corriger également le rapport pour représenter explicitement une recherche
interrompue ou non démarrée. La relance doit conserver cette tentative comme
échec d’infrastructure et garder les mêmes plans, facteurs et plafonds.

**Aucune relance de cette étude n’a été soumise pendant cette vérification.**

