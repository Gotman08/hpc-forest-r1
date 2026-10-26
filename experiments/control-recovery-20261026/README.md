# Reprise de Mother et clôture — comparaison sur ROMEO

**Campagne terminée : [rapport et comparaison finale](RAPPORT.md).** Huit livraisons
sur huit, remesurées avec les anciens codes dans le job 784760. Le protocole
ci-dessous est conservé ; les CSV de fin se lisent selon [cet index](results/README.md).

Campagne distincte du comparatif du 25 octobre. Les anciennes recherches restent
intactes. Un seul Forest, tous les rôles LLM en GPT-6 Luna, effort max ; TabPFN est
le seul réglage qui diffère entre les deux conditions.

Le [protocole figé](protocol.json) prévoit UTF-8 et Mandelbrot, deux graines par
programme, conditions inversées entre graines, 90 minutes de recherche et
120 minutes au total par condition. Mémoire et conversations neuves ; mêmes
entrées, oracle, compilateur, ressources et budgets autorisés. Les durées et les
tokens effectivement utilisés peuvent différer. Une clôture valide reste possible
avant la limite ; un blocage de la revue ne vaut plus clôture.

Les changements de contrôle sont communs aux deux conditions :

- reconnaître uniquement l'événement natif de `wait` sans destinataire, état
  d'agent, prompt ni autre effet ; toute véritable action non autorisée est refusée ;
- reprendre une réponse de pilotage tronquée seulement après preuve de sa fin
  et de son UUID natif, dans le même fil, avec un nouveau tour compté et borné ;
- limiter les citations de revue aux preuves visibles et préciser les refus ;
- rouvrir les arbres admissibles après une revue de clôture sans décision valide,
  en conservant leurs objectifs, mesures, politiques TreeQuest et réserves finales.

Les scénarios déterministes simulent les pannes : ils ne prouvent pas un gain
de performance du modèle. Les campagnes réelles ne recevront aucune intervention
algorithmique manuelle.

Les scripts de `reproduction/` préparent les campagnes et exportent les essais,
les avis TabPFN, les reprises de Mother et les décisions de clôture. Les codes
livrés seront remesurés ensemble après toutes les recherches, dans une allocation
distincte. Les cas sans livraison ne recevront aucun speedup final inventé.
