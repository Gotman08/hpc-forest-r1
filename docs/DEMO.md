# Démonstration visuelle de Forest

Le [GIF du README](media/forest-demo.gif) présente la véritable interface de
Forest 0.2, dans son thème sombre. Le scénario et tous ses chiffres sont
**synthétiques** : ils illustrent le parcours et ne constituent ni un benchmark
ni une preuve de performance. Chaque scène conserve cette mention à l’écran.

## Parcours présenté

| Étape | Ce que montre l’interface |
|---|---|
| Explorer | Trois arbres, leurs variantes, les temps et les états de vérification |
| Vérifier | Sélection d’un nœud, tests de correction et échantillons de mesure |
| Comprendre | Diff de la variante par rapport à son code de référence |
| Livrer | Comparaison confirmée, bilan des essais, conditions et liens de téléchargement |

Le code, les tests et les mesures affichés sont des exemples de présentation.
Aucune commande de compilation, de test ou de mesure n’est exécutée par la
capture. La recherche TreeQuest n’est pas simulée par un autre algorithme :
seule une vue de données préconstruite est présentée. Les tests de campagne et
les archives de résultats restent inchangés.

## Images et provenance

- [Animation](media/forest-demo.gif) : boucle silencieuse avec transitions douces.
- [Image fixe](media/forest-overview.png) : première scène, consultable sans animation.
- [Reçu de génération](media/forest-demo.json) : dimensions, durée, versions,
  empreintes des sources et des médias, absence d’appel au modèle ou de job HPC.
- [Scénario synthétique](../tools/demo_fixture.py) et
  [outil de capture](../tools/render_demo.py).

Les médias sont versionnés dans le dépôt et fonctionnent sans hébergeur
d’images. L’animation est accompagnée d’un texte alternatif dans le README.
Les captures utilisent les fichiers HTML, CSS et JavaScript du produit,
sans modifier leur présentation.
Les empreintes des sources utilisent des fins de ligne LF pour rester
comparables entre les checkouts Windows et Unix ; les médias sont hashés
sur leurs octets exacts.

## Régénérer depuis un checkout complet

La capture utilise un environnement séparé du runtime produit. Depuis la
racine du dépôt, créer un environnement de présentation puis installer les
dépendances facultatives :

```powershell
python -m venv artifacts/demo-runtime
artifacts/demo-runtime/Scripts/python -m pip install "playwright==1.64.1" "Pillow==12.3.0"
artifacts/demo-runtime/Scripts/python -m playwright install chromium
artifacts/demo-runtime/Scripts/python tools/render_demo.py
```

Sous Linux ou macOS, utiliser `bin/python` à la place de `Scripts/python`.
Chromium doit disposer des bibliothèques système requises sur la machine.
Le rendu des polices peut varier selon le système ; les empreintes du reçu
identifient les fichiers produits, sans promettre un rendu identique partout.

L’outil démarre uniquement un serveur de fichiers statiques sur une adresse
locale et un port éphémère. Les lectures API sont remplacées dans le navigateur
par le scénario synthétique. Les écritures et les requêtes externes sont
refusées. Il ne charge pas le backend Forest, les stockages personnels, les
registres de campagne ou la configuration ROMEO.

Pour utiliser un Chromium déjà installé et conserver les scènes séparées :

```powershell
artifacts/demo-runtime/Scripts/python tools/render_demo.py --browser CHEMIN_CHROMIUM --frames artifacts/demo-scenes
```

Par défaut, seuls le GIF, l’image fixe et le reçu sont écrits dans `docs/media/`.
`--output AUTRE_DOSSIER` permet de préparer un nouveau rendu avant de remplacer
les médias versionnés. Une capture échoue en présence d’erreurs JavaScript ou
de requêtes non prévues ; l’encodage vérifie le nombre d’images et la durée.
