# Candidat UTF-8 bloqué, classé infrastructure par le protocole historique

Job 784228, premier bras (conseiller activé), essai `ca0e81cad5ba48aa`.
La proposition originale de Luna est conservée sans correction dans
`agent-result.json`. Ce candidat n'est pas le code livré.

Avec SSE2 activé, le traitement scalaire final est situé à l'intérieur du bloc
`if (length - index >= 16)`. Pour une entrée d'un octet, ce bloc n'est jamais
exécuté et la boucle `while (index < length)` ne fait jamais avancer `index`.
Le contrôle de correction sur `n=1` a effectivement dépassé 180 secondes.

Le protocole historique `validation/protocol.py` capture `TimeoutExpired` avec
les erreurs d'infrastructure et renvoie 70. Forest conserve donc un score absent
et arrête l'exploration, au lieu de traiter ce candidat comme incorrect et de
poursuivre les autres pistes. Le journal de contrôle et la source établissent
ce chemin ; il ne s'agit pas d'un problème de relais PC ou d'OAuth.

Aucune prédiction TabPFN n'avait été appelée. Cet incident ne démontre pas une
régression causée par le modèle conseiller. Le meilleur programme livré par le
bras a passé sa confirmation indépendante. La classification du validateur n'a
pas été changée au milieu de l'expérience : une correction demande une nouvelle
version de protocole et de nouvelles campagnes comparables.
