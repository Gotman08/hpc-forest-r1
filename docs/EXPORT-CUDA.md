# Export d'un bundle CUDA confirmé

Le contrat `submission.kind = "cuda-kernel"` livre une source device NVRTC et
sa configuration de lancement. Il n'exige pas les fichiers `Makefile` et
`run.sh` du contrat `executable`, qui reste celui des imports habituels.
L'export n'ajoute aucun code d'optimisation ou lanceur après les mesures.

```json
{
  "submission": {
    "kind": "cuda-kernel",
    "source": "src/nbody_kernel.cu",
    "launch": "src/launch.json",
    "kernel": "nbody_step_naive"
  }
}
```

Pour l'import CUDA N-corps existant, le contrôleur reconnaît mécaniquement
une source `.cu` avec une seule entrée `extern "C" __global__ void` et
`src/launch.json`, en l'absence de lanceurs exécutables. Il fige ce contrat
dans la configuration protégée **avant tout appel modèle**. Pour un autre
agencement ou plusieurs entrées, fournir le contrat explicitement.

Le format de lancement contient les trois entiers `block`, `items_per_block`
et `shared_memory_bytes`. Le harnais utilise `grid.x = ceil(N/items_per_block)`
et `block.x = block`, les autres dimensions étant égales à un. Les bornes
restent celles du protocole CUDA actuel : 1–1024 threads, 1–1048576 éléments
par bloc, 0–49152 octets de mémoire partagée dynamique. Cette validation
décrit l'interface ; elle ne recommande aucun réglage aux modèles.

`package()` vérifie le reçu de confirmation du commit sélectionné et celui
de G final obligatoire, puis archive **le commit Git confirmé**. Le manifeste
contient le type de livraison, le symbole du kernel, les réglages exacts et
les SHA-256 des deux fichiers. L'archive finale et son fichier `.sha256`
sont produits sans récupération manuelle d'un `.zip.tmp`.

Ce bundle s'utilise avec le harnais hôte correspondant à l'interface déclarée
du kernel. Il n'est pas présenté comme une application autonome ou comme une
nouvelle mesure GPU. Les protections du contrat exécutable demeurent actives.

La campagne historique `experiments/cuda-nbody-20261021/` conserve ses résultats,
son échec d'export et ses empreintes. Une campagne utilisant le moteur corrigé
doit être créée dans un nouveau dossier ; les anciennes preuves ne sont pas
réécrites pour les faire passer au statut de réussite.
