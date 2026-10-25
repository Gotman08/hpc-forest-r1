"""Render the measured comparison, keeping search and timing replication distinct."""
import json
from pathlib import Path
import shutil

R = Path(__file__).resolve().parent
O = R.parents[1] / 'outputs/forest-corrections-20261024'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def number(value, digits=2):
    return '—' if value is None else f'{value:.{digits}f}'


def seconds(value):
    if value is None:
        return '—'
    return f'{value*1e6:.3f} µs' if value < .001 else f'{value*1000:.3f} ms'


def main():
    d = read(O / 'RESULTATS.json')
    engines = {(e['case_id'],e['period']):e for e in d['engines']}
    rows = {r['id']:r for r in d['rows']}
    labels = {'sgemm':'SGEMM','utf8':'UTF-8','mandelbrot':'Mandelbrot'}
    lines = ['# Forest : corrections des analyses et des fermetures — ROMEO', '',
        'Toutes les recherches corrigées utilisent **GPT-6 Luna, effort max**, y compris Mother, '
        'les arbres, les analystes et l’intégration. Le moteur a été corrigé par Codex ; '
        'Luna est le modèle qui exécute les rôles pendant les expériences.', '',
        '## Comparaison des programmes livrés', '',
        'Les trois générations de programmes sont **remesurées dans une même allocation par cas**. '
        'La colonne « gain sur précédente » vaut temps de la version active précédente / temps de la version corrigée. '
        'Une valeur supérieure à 1 indique un programme corrigé plus rapide.', '',
        '| Cas | Historique avant architecture active | Active précédente | Corrigée | Gain sur précédente | Plage des rapports par bloc |',
        '|---|---:|---:|---:|---:|---:|']
    selected = [('gpu_sgemm_10','SGEMM 4096²'), ('CPU_UTF8_MEAN','UTF-8 65 536 octets, moyenne'),
                ('CPU_ISPC_MANDELBROT_1C','Mandelbrot 1 thread'),('CPU_ISPC_MANDELBROT_4C','Mandelbrot 4 threads')]
    for identity,label in selected:
        r=rows[identity]; bounds=r['corrected_vs_previous_block_range']
        lines.append('| '+ ' | '.join([label, *[seconds(r[p]['seconds']) for p in ['historical','previous','corrected']],
            number(r['corrected_vs_previous'])+'×', f'{number(bounds[0])}–{number(bounds[1])}×' if bounds else '—'])+' |')
    lines += ['', 'Les répétitions servent à observer la variabilité des mesures. Il n’y a **qu’une recherche '
        'stochastique par programme et par architecture** : elles ne démontrent pas une supériorité statistique de la stratégie.', '',
        '## Ce qui a été corrigé', '',
        '- Le JEV reçoit des extraits du dernier candidat de son arbre, de sa base et de comparateurs autorisés, '
        'avec différences, empreinte du fichier et lignes numérotées. Un rapport terminé doit citer le code exposé.',
        '- Un premier candidat correct ou un progrès mesuré déclenche une revue et une courte suite protégée, '
        'bornée à deux essais et à une enveloppe estimée de 15 % du budget de recherche disponible au démarrage. '
        'La réserve d’intégration et de confirmation reste prioritaire.',
        '- Un résultat nouveau invalide une décision d’arrêt prise sur des preuves périmées. '
        'Un progrès tardif peut réactiver un arbre suspendu.',
        '- Une fermeture se fait en deux temps : arrêt des nouvelles admissions et fin des essais déjà admis, '
        'puis bilans à jour et nouvelle décision. Les hypothèses du dernier bilan doivent être examinées.',
        '- Le contrôleur distingue fermeture revue, absence de travail admissible après revue et réserve/échéance. '
        'Une erreur d’analyste reste une analyse indisponible, sans score inventé.', '',
        'Les citations prouvent la provenance des extraits, pas la justesse de l’interprétation du modèle. '
        'La sélection AB-MCTS et les récompenses mesurées conservent leur rôle.', '',
        '## Recherche, arbres et arrêts', '',
        '| Cas / version | Job recherche | Cible | Durée moteur | Essais validés par le protocole / total | Arbres initiaux + créés | Première fermeture acceptée | Fermeture confirmée | Motif final |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for case in labels:
        for period,label in [('historical','historique'),('previous','active précédente'),('corrected','corrigée')]:
            e=engines[case,period]
            lines.append('| '+' | '.join([labels[case]+' / '+label,e['job_id'],
                number(e['target_seconds'],0)+' s', number(e['elapsed_seconds'],1)+' s',
                f"{e['correct_trials']} / {e['total_trials']}",f"{e['initial_trees']} + {e['created_trees']}",
                number(e['first_close_request_seconds'],1)+' s' if e['first_close_request_seconds'] is not None else '—',
                number(e['confirmed_close_seconds'],1)+' s' if e['confirmed_close_seconds'] is not None else '—',
                e.get('stop_reason') or 'non instrumenté dans cette version'])+' |')
    lines += ['', 'Le compte des essais validés reprend le protocole figé de campagne ; il ne garantit pas '
        'la correction sur toutes les entrées possibles. L’audit supplémentaire UTF-8 est présenté séparément. '
        'La durée moteur comprend planification, recherche et confirmation ; elle se distingue du temps '
        'd’exécution du programme livré. Les appels admis finissent même si la cible temporelle est atteinte. '
        'Les arbres créés incluent les intégrations intermédiaires, détaillées dans `trees.csv`. '
        'Dans la version active précédente, une seule décision fermait la recherche : '
        'la colonne de seconde confirmation ne s’applique pas.', '',
        '| Cas corrigé | Meilleur temps de recherche avant la première demande acceptée | Meilleur mesuré ensuite | Évaluations correctes après cette demande |',
        '|---|---:|---:|---:|']
    for case in labels:
        e=engines[case,'corrected']
        lines.append('| '+' | '.join([labels[case],seconds(e['research_best_at_first_close_seconds']),
            seconds(e['research_best_after_first_close_seconds']),
            str(e['correct_research_evaluations_after_first_close'])])+' |')
    lines += ['', '| Cas corrigé | Première proposition de fermeture, même rejetée | Fermetures rejetées | Suspensions rejetées | Revues sans arbre actif |',
        '|---|---:|---:|---:|---:|']
    for case in labels:
        e=engines[case,'corrected']
        lines.append('| '+' | '.join([labels[case],
            number(e['first_close_proposal_seconds'],1)+' s' if e['first_close_proposal_seconds'] is not None else '—',
            str(e['rejected_close_count']),str(e['rejected_suspend_count']),str(len(e['idle_review_seconds']))])+' |')
    lines += ['', 'Lorsque tous les arbres sont suspendus, le contrôleur peut aussi déclencher une revue '
        'sans demande explicite `close`. Cette revue bornée laisse une chance de réorienter la recherche '
        'avant de conclure qu’aucun travail n’est admissible. Les horaires sont dans `engines.csv`.']
    lines += ['', 'Les meilleurs temps des candidats autour de la demande acceptée proviennent de '
        'l’exploration, avant la confirmation et la remesure appariée. '
        'Ils incluent les essais déjà admis qui se terminent pendant le drainage et les intégrations intermédiaires, '
        'mais excluent G final. Ils ne suffisent pas à attribuer causalement un gain aux protections.', '',
        '## Travail des analystes', '',
        '| Cas / version active | Appels JEV | Bilans terminés | Bilans citant le code | Bilans citant le code du dernier candidat propre | Citations vérifiées | Lectures explicites de source | Analyses indisponibles |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for case in labels:
        for period,label in [('previous','précédente'),('corrected','corrigée')]:
            e=engines[case,period]
            lines.append('| '+' | '.join([labels[case]+' / '+label,*[str(e[k]) for k in [
                'analyst_calls','completed_analyses','analyses_with_code','analyses_citing_latest_own_code','verified_source_citations',
                'explicit_source_reads','unavailable_analyses']]])+' |')
    lines += ['', 'Les nouvelles requêtes contiennent déjà du code : l’absence de lecture explicite supplémentaire '
        'ne signifie donc plus l’absence de source dans le contexte. Un dernier essai interrompu avant '
        'la proposition de code peut ne fournir aucune source propre à citer ; ce cas est distingué '
        'dans les données. Le dernier code est reconnu par chemin et SHA-256, même si le JEV cite '
        'la proposition archivée qui contient exactement ce fichier ; le comptage par identifiant exact '
        'reste aussi disponible dans le CSV. `analyst_reports.csv` conserve les mécanismes, '
        'hypothèses, incertitudes et citations ; `trials.csv` conserve les identifiants des avis transmis aux essais.', '',
        '### Coût du contrôle et des analyses', '',
        '| Cas / version active | Appels natifs totaux | Tokens connus normalisés | Appels avec usage inconnu | Somme des durées JEV | Somme des durées Mother aux jalons |',
        '|---|---:|---:|---:|---:|---:|']
    for case in labels:
        for period,label in [('previous','précédente'),('corrected','corrigée')]:
            e=engines[case,period]; usage=e['native_usage_normalized']
            lines.append('| '+' | '.join([labels[case]+' / '+label,
                str(usage.get('native_invocations')),str(usage.get('known_tokens_normalized')),
                str(usage.get('unknown_invocation_usage')),number(e['analyst_call_wall_sum'],1)+' s',
                number(e['mother_call_wall_sum'],1)+' s'])+' |')
    lines += ['', 'Les durées des appels peuvent se chevaucher avec la recherche : elles ne s’additionnent '
        'pas à la durée totale. Les tokens connus sont normalisés pour éviter de recompter les compteurs '
        'cumulés de Mother ; ils ne représentent pas un coût monétaire. Les phases détaillées '
        'sont dans `durees.csv`.', '']
    lines += ['| Cas corrigé | Revues Mother indisponibles | Motifs |', '|---|---:|---|']
    for case in labels:
        e=engines[case,'corrected']
        lines.append('| '+labels[case]+' | '+str(e['unavailable_mother_jobs'])+' | '+
            '; '.join(f'{reason} ({count})' for reason,count in e['mother_errors'].items())+' |')
    lines += ['', 'Ces revues n’ont produit aucune décision admise. Une confirmation finale réussie '
        'ne transforme pas une revue invalide en fermeture confirmée.', '']
    notes=R/'case-analysis.md'
    if notes.exists(): lines += [notes.read_text(encoding='utf8'), '']
    lines += ['## Speedups publiés et remesurés', '',
        'Chaque ratio de cette table utilise le même code naïf comme dénominateur dans l’allocation de comparaison. '
        'Les valeurs publiées sont documentaires : le matériel, le compilateur et le protocole peuvent '
        'tous contribuer aux écarts. La remesure sur ROMEO ne mesure pas isolément l’effet du matériel.', '',
        '| Ligne du tableau | Publié | Référence sur ROMEO | Historique Forest | Active précédente | Corrigée |',
        '|---|---:|---:|---:|---:|---:|']
    for r in d['rows']:
        lines.append('| '+' | '.join([r['label'], number(r['published_speedup'])+'×',
            *[number(r[k+'_speedup'])+'×' for k in ['reference','historical','previous','corrected']]])+' |')
    utf=rows['CPU_UTF8_MEAN']
    lines += ['', f"Pour UTF-8, le naïf documentaire échoue sur certaines entrées mal formées. Forest part du naïf réparé. "
        f"Le speedup corrigé sur cette **base réparée** est {number(utf['corrected_vs_repaired'])}× en moyenne. "
        'La table documentaire garde son dénominateur original et ne le présente pas comme un validateur universellement correct.', '',
        '### Audit supplémentaire UTF-8', '',
        'Oracle : décodeur UTF-8 strict de Python. Énumération exhaustive des chaînes de un et deux octets, '
        'séquences spéciales près des frontières SIMD, chaînes aléatoires et mutations déterministes. '
        'Le contrôle vérifie aussi les zones sentinelles et la conservation de l’entrée.', '',
        'La variante `diagnostic_43cb_e0` est un candidat intermédiaire signalé par le JEV pour une '
        'possible inversion du test E0. Elle est auditée après la recherche et exclue des temps '
        'et des classements ; aucun résultat de cet audit n’a été transmis à Forest.', '',
        '| Variante | Cas audités | Échecs |', '|---|---:|---:|']
    for record in d['audits']['utf8']['records']:
        lines.append(f"| {record['variant']} | {record['cases']} | {record['failed']} |")
    if 'utf8_extended' in d['audits']:
        lines += ['', 'Un corpus élargi place les séquences spéciales aux offsets 0 à 132, '
            'avec des suffixes de 0, 7 ou 64 octets et toutes leurs troncatures. Il couvre notamment '
            'les traversées des frontières à 64 et 128 octets. Il a été ajouté après la découverte '
            'de variantes AVX-512 ; les entrées chronométrées et les validations de campagne restent figées.', '',
            '| Variante | Cas du corpus étendu | Échecs |', '|---|---:|---:|']
        for record in d['audits']['utf8_extended']['records']:
            lines.append(f"| {record['variant']} | {record['cases']} | {record['failed']} |")
    lines += ['', 'Ce corpus est plus large que les entrées chronométrées ; il ne constitue pas une preuve '
        'exhaustive pour toute longueur de chaîne.', '', '## Protocole et limites', '',
        '- SGEMM : matrices 4096² FP32, alpha = 0,5, beta = 3 ; GH200/Grace, CUDA 12.6.3, même pilote protégé '
        'et compilation pour SM90. Référence publiée sur RTX A6000. Neuf blocs alternant les variantes.',
        '- UTF-8 : 65 536 octets, motif 0, un thread ; AMD EPYC 9654, mêmes sources, compilateur et pilote. '
        'Référence publiée sur Intel Skylake. Sept blocs ; audit de correction séparé.',
        '- Mandelbrot : 1536 × 1024, 512 itérations ; un et quatre threads EPYC 9654. '
        'L’objectif de recherche est la moyenne géométrique des temps à un et quatre threads. '
        'Référence publiée sur iMac/Core i7 AVX. Sept blocs.',
        '- Registre, session et mémoire neufs par programme, aucune solution historique importée et aucun conseil '
        'algorithmique de l’opérateur pendant les recherches. Les caches physiques des nœuds ne sont pas purgés.',
        '- Compilation, correction et chronométrage sur les nœuds de calcul ROMEO. '
        'L’inférence passe par le service Codex via un relais local ; Luna ne tourne pas sur les GPU ROMEO.',
        '- L’identité des entrées CPU est vérifiée par les empreintes enregistrées par le pilote. '
        'Le pilote SGEMM ne fournit pas d’empreinte des matrices : la comparaison vérifie ses propres empreintes, '
        'les mêmes dimensions et la même graine dans chaque bloc, sans inventer un hash d’entrée. '
        'Les neuf blocs SGEMM utilisent neuf graines distinctes.',
        '- Les premiers jobs de diagnostic 783352, 783353 et 783354 ont été annulés après découverte du compteur '
        'de suivi non décrémenté hors enveloppe protégée. Le correctif est testé ; ces trois essais sont exclus '
        'des performances. Leurs traces et les archives vérifiées sont conservées.', '',
        'Les deux premières campagnes CPU corrigées (783358 et 783359) ont perdu la continuité de Mother '
        'pendant une coupure réseau et une interruption du poste local. La première tentative de relance '
        'Mandelbrot (783481) n’a pas reçu son worker avant le délai de démarrage : une erreur de commande du '
        'lanceur, suivie de l’interruption locale, a retardé son lancement. Elle n’a fait aucun appel modèle. '
        'Ces tentatives sont archivées et exclues. La sélection retient la première campagne achevée avec '
        'le moteur figé, sans sélectionner selon le speedup.', '',
        'Les relances CPU 783743 et 783744 ont ensuite rencontré une nouvelle panne DNS du relais local. '
        'Elles ont confirmé un candidat de secours, mais leur assemblage G est absent : elles sont exclues '
        'de la comparaison principale de la boucle complète. Leurs candidats ont été remesurés dans les '
        'jobs 783899 et 783900 et sont conservés dans l’[annexe des essais interrompus](diagnostics-interrompus/RAPPORT-INTERROMPU.md). '
        'Après confirmation par l’utilisateur du rétablissement de la connexion, les relances repartent '
        'avec une mémoire neuve. Le transport seul reçoit jusqu’à huit tentatives et une grâce maximale '
        'de 90 secondes ; il conserve les échéances plus courtes et ne rejoue aucun appel modèle. '
        'Les contrôles de reprise, d’intégrité et d’expiration de cette couche ont été vérifiés séparément.', '',
        '| Tentative exclue | Cas | État SLURM | Durée allocation |',
        '|---:|---|---|---:|']
    for attempt in d['excluded_attempts']:
        lines.append(f"| {attempt['job_id']} | {attempt['case_id']} | {attempt['scheduler_state']} | "
                     f"{number(attempt['elapsed_seconds'],0)} s |")
    lines += ['', '## Validation et pièces', '']
    validation=read(R/'software-validation.json')
    lines.append(f"Suite logicielle : **{validation['tests']} tests, {validation['failures']} échec, "
        f"{validation['errors']} erreur, {validation['skipped']} ignoré**. Ruff : {validation['ruff']}.")
    lines += ['', '- [Mesures et résultats complets](RESULTATS.json)',
        '- [Comparaison des speedups](comparaison.csv) ; [mesures par bloc](mesures.csv).',
        '- [Moteurs](engines.csv) ; [arbres](trees.csv) ; [essais](trials.csv) ; [durées](durees.csv).',
        '- [Arrêts](stops.csv) ; [décisions](decisions.csv) ; [chronologie](chronology.csv).',
        '- [Bilans JEV](analyst_reports.csv) ; [appels de contrôle](calls.csv).',
        '- [Tentatives interrompues](tentatives-interrompues.csv).',
        '', 'Empreinte du manifeste du moteur exécuté : `'+d['implementation']['engine_manifest_sha256']+'`.']
    (O/'RAPPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    for src in (R/'interrupted-diagnostics').iterdir():
        if src.is_file():
            destination=O/'diagnostics-interrompus'/src.name
            destination.parent.mkdir(exist_ok=True)
            shutil.copyfile(src,destination)
    print(O/'RAPPORT.md')


if __name__=='__main__':
    main()
