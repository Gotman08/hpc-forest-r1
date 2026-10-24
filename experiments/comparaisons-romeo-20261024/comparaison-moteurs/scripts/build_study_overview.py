"""Join both replay studies by exact source bytes and write the final reading guide."""
from collections import Counter
import hashlib
import json
from engine_study import ROOT,read,write,sha
from engine_extract import table
from build_engine_comparison import ms,number,LABELS

BASE=ROOT/'outputs';OLD=BASE/'comparaison-historique';NEW=BASE/'comparaison-moteurs'

def main():
    old_variants=read(OLD/'data/variants.json')
    new_variants=read(NEW/'gpu-comparaison/variants.json')
    old_replay=read(OLD/'gpu/results/summary.json')
    new_replay=read(NEW/'gpu-comparaison/results/summary.json')
    catalog={}
    for batch,variants,replay,folder in [
        ('historical',old_variants,old_replay,OLD/'sources'),
        ('new',new_variants,new_replay,NEW/'gpu-comparaison/sources')]:
        measured={p['id']:p for p in replay['programs']}
        for v in variants:
            if v['id']=='baseline-control':continue
            source=folder/v['id']/'src/nbody_kernel.cu';launch=source.with_name('launch.json')
            assert sha(source)==v['source_sha256'] and sha(launch)==v['launch_sha256']
            fingerprint=hashlib.sha256(source.read_bytes()+b'\0'+launch.read_bytes()).hexdigest()
            key=(v['source_sha256'],v['launch_sha256'])
            row=catalog.setdefault(key,{'sha256':fingerprint,'source_sha256':key[0],'launch_sha256':key[1],
                'launch':v['launch'],'origins':[],'source_files':[]})
            assert row['sha256']==fingerprint
            p=measured[v['id']]
            row.update({batch+'_id':v['id'],batch+'_replay_seconds':p['mean_seconds'],
                batch+'_replay_speedup':p['speedup'],batch+'_correct':p['correct'],
                batch+'_fully_measured':p['fully_measured'],batch+'_status':p['status']})
            row['origins'].extend({'batch':batch,**o} for o in v['origins'])
            row['source_files'].append(source.relative_to(BASE).as_posix())
    rows=list(catalog.values())
    for r in rows:
        checks=[r[k] for k in ['historical_correct','new_correct'] if k in r]
        r['all_replays_correct']=all(checks)
        r['latest_replay_correct']=r.get('new_correct',r.get('historical_correct'))
    rows.sort(key=lambda r:r['sha256'])
    assert len(rows)==291
    write(NEW/'data/catalogue-unifie.json',rows)
    table(NEW/'tables/catalogue-unifie.csv',rows)
    overlap=[r for r in rows if 'historical_id' in r and 'new_id' in r]
    assert len(overlap)==8
    anchor_rows=[{'sha256':r['sha256'],'historical_id':r['historical_id'],'new_id':r['new_id'],
        'first_replay_seconds':r['historical_replay_seconds'],'second_replay_seconds':r['new_replay_seconds'],
        'latency_change_pct':100*(r['new_replay_seconds']/r['historical_replay_seconds']-1),
        'source_files':r['source_files']} for r in overlap]
    table(NEW/'tables/reperes-entre-rejeux.csv',anchor_rows)
    primary=[r for r in read(NEW/'data/comparison.json') if r['series']=='atomic']
    winner=min([r for r in primary if r['selected_common_gpu_seconds'] is not None],key=lambda r:r['selected_common_gpu_seconds'])
    latest=next(r for r in primary if r['condition']=='780448')
    verification=read(NEW/'protocol/new-replay-verification.json')
    old_verification=read(OLD/'protocol/replay-verification.json')
    suites=[s for e in read(OLD/'data/dashboard.json')['engines'] for s in e['test_suites']]
    test_counts={key:sum(int(s.get(key,0)) for s in suites) for key in ['tests','failures','errors','skipped']}
    test_passed=test_counts['tests']-test_counts['failures']-test_counts['errors']-test_counts['skipped']
    trials=read(NEW/'data/comparison-trials.json')
    rsqrt=next(t for t in trials if t['series']=='atomic' and t['condition']=='772923' and t['id']=='63513b28c5484e1e')
    raw_new={ (v['source_sha256'],v['launch_sha256']) for v in new_variants
        if any(o.get('series') in {'interrupted','shared-scp','atomic'} for o in v['origins']) }
    counts={'historical_programs':len(old_variants),'new_campaign_programs':len(raw_new),
        'unique_programs':len(rows),'correct_in_all_replays':sum(r['all_replays_correct'] for r in rows),
        'common_programs_between_replays':len(overlap),
        'new_replay_programs_with_control':len(new_replay['programs']),
        'timing_samples_total':old_verification['benchmark_samples_recomputed']+verification['timing_samples_recomputed'],
        'per_size_latencies_total':old_verification['size_latencies_recomputed']+verification['per_size_latencies_recomputed'],
        'correctness_cases_total':old_verification['correctness_cases_recomputed']+verification['correctness_case_results']}
    counts['historical_unit_tests']={**test_counts,'passed':test_passed}
    # The historical variants file excludes its extra timing control.
    assert counts['historical_programs']==124 and counts['new_campaign_programs']==168
    write(NEW/'protocol/study-coverage.json',counts)
    out=['# Historique complet des moteurs et des programmes CUDA','',
        'L’étude est terminée : les versions du moteur, les codes produits, leurs diagnostics et leurs mesures sont conservés avec les sources exactes. Le dépôt de travail n’a pas été modifié.',
        '',f"**{counts['unique_programs']} programmes distincts** ont été rejoués : les 124 retrouvés dans les campagnes historiques et les 168 produits par les nouvelles campagnes, avec une référence initiale commune. **{counts['correct_in_all_replays']}** réussissent les contrôles de tous leurs rejeux. Les programmes identiques ne sont comptés qu’une fois, même s’ils apparaissent dans plusieurs campagnes.",
        '', 'Le programme exclu avait réussi le jeu de confirmation de S2 / 775521, mais échoué sur le jeu de recherche. Le rejeu reproduit cette différence : une composante hors tolérance à N=16384. Il reste documenté avec ses sources et ses diagnostics, sans mesure de vitesse classée.',
        '', '## Où lire les résultats', '',
        '- [Tableau de bord des nouvelles campagnes](comparaison-moteurs/TABLEAU-DE-BORD.html) : filtres par moteur et série, progression, sources, différences de code, appels et événements.',
        '- [Rapport des comparaisons](comparaison-moteurs/RAPPORT.md) : classement, répétitions, gagnants historiques et nouveaux, effets de chaque assemblage.',
        '- [Comportements et diagnostics expliqués](comparaison-moteurs/COMPORTEMENTS.md) : réserves de temps, plans, réparations, erreurs numériques, mémoire et transport.',
        '- [Historique des 19 commits et tests des 12 révisions](comparaison-historique/RAPPORT.md), avec le [tableau de bord des 124 programmes historiques](comparaison-historique/TABLEAU-DE-BORD.html).',
        '- [Catalogue unifié des 291 programmes](comparaison-moteurs/tables/catalogue-unifie.csv) : correspondance entre les deux études, empreintes et toutes les origines.',
        '', '## Ce qui a été exécuté', '',
        'Les sept états du moteur réellement déployés ont chacun été relancés trois fois depuis le même programme initial, soit **21 nouvelles campagnes, 225 essais enregistrés et 389 appels natifs**. Les deux premières séries ont révélé des incidents de transport. La troisième constitue la comparaison principale : 134 essais de recherche, dont 121 valides, et 15 assemblages valides. Les sept programmes finaux sont confirmés ; six exports aboutissent. L’ancien exporteur du septième attend des fichiers absents du paquet CUDA, mais ses sources et ses résultats ont été récupérés.',
        '', f"Les sept campagnes historiques ajoutent 138 essais. Les suites de tests de 12 révisions représentent **{test_counts['tests']} tests collectés** : **{test_passed} réussites** et **{test_counts['failures']+test_counts['errors']} échecs ou erreurs**, dont les causes et les éventuelles répétitions sont conservées. Les commits documentaires ne sont pas assimilés à de nouveaux moteurs ; quatre états déployés intermédiaires sont identifiés par leur archive exacte, faute de commit identique.",
        '',f"Les deux rejeux GPU totalisent **{counts['timing_samples_total']} échantillons de temps**, **{counts['per_size_latencies_total']} mesures par taille** et **{counts['correctness_cases_total']} contrôles de cas**, références et programmes remesurés compris. Chaque programme classé dispose de cinq répétitions et réussit les deux jeux de correction. Les comparaisons directes utilisent des mesures du même rejeu.",
        '', '## Résultat de la nouvelle comparaison commune', '',
        f"Le programme sélectionné le plus rapide vient de **{winner['condition']} — {winner['label']}** : **{ms(winner['selected_common_gpu_seconds'])} ms**, soit **{number(winner['selected_common_gpu_speedup'],2)}×** la référence. L’état le plus récent, 780448, obtient **{ms(latest['selected_common_gpu_seconds'])} ms** dans cette campagne.",
        '', '| État | Gagnant historique remesuré | Nouveau gagnant remesuré | Accélération du nouveau |',
        '|---|---:|---:|---:|']
    for r in primary:
        out.append(f"| {r['condition']} — {LABELS[r['condition']]} | {ms(r['historical_common_gpu_seconds'])} ms | {ms(r['selected_common_gpu_seconds'])} ms | {number(r['selected_common_gpu_speedup'],2)}× |")
    out+=['', 'Ces valeurs décrivent les codes effectivement trouvés. Il n’y a qu’une nouvelle campagne sans incident de transport par état : elles ne démontrent pas qu’un moteur retrouve systématiquement un meilleur code. Les plans, le nombre d’arbres et les fonctionnalités historiques diffèrent aussi.',
        '', '## Améliorations et limites établies', '',
        f"- **Arithmétique CUDA :** dans le nouvel assemblage de 772923, le passage à `rsqrtf` réduit la latence de **{number(rsqrt['common_gain_vs_base_pct'],2)} %** par rapport à son parent, avec **{rsqrt['winning_blocks_vs_base']}/5 blocs** plus rapides. Le patch et les deux codes sont conservés. Le premier rejeu avait mesuré 24,40 % sur une autre base historique ; ces pourcentages concernent leurs bases respectives.",
        '- **Certaines transformations ralentissent :** dans le premier rejeu, le passage à deux cibles par thread du candidat historique 780448 allonge le temps de 70,79 %. Une transformation présentée comme une optimisation n’est pas considérée comme un gain sans mesure.',
        '- **La correction de réserve engage davantage de travail :** 775521 réserve environ 52 minutes alors qu’il en reste 28 et ne lance que trois essais de recherche. Les versions suivantes explorent davantage. Cela améliore le comportement d’admission observé, sans garantir le meilleur noyau.',
        '- **La mémoire et la critique ont des effets fonctionnels vérifiés :** les tests avant/après montrent la présence des résultats mesurés dans les résumés, la conservation du code sans leçons facultatives et la correction de la réserve pour une grande forêt provisoire. Leur effet causal sur la vitesse du meilleur CUDA n’est pas isolé.',
        '- **Les erreurs restent visibles :** sept missions de la série principale réussissent après un contrôle local échoué. Les refus de génération, les sorties numériques incorrectes, les copies exactes et les erreurs d’export sont distingués dans les tables.',
        '- **Le comptage des jetons est défectueux dans les sept moteurs figés :** ils additionnent à nouveau des compteurs cumulatifs lors des reprises. Le contre-exemple est exécuté sur leurs sources. Les tableaux corrigent ce comptage ; les moteurs eux-mêmes restent inchangés.',
        '',f"La stabilité du dernier rejeu est documentée : étendue des contrôles de référence **{number(verification['baseline_range_pct'],3)} %**, coefficient de variation médian **{number(verification['median_program_cv_pct'],3)} %**. Les petits écarts doivent être lus avec cette dispersion. Aucun profilage matériel n’a été effectué pour attribuer les écarts aux registres, à l’occupation ou à la mémoire.",
        '', '## Vérification et reproduction', '',
        '[Méthode, conditions et limites](comparaison-moteurs/METHODE.md) · [Instructions de reproduction](comparaison-moteurs/REPRODUCTION.md) · [Couverture vérifiée des deux études](comparaison-moteurs/protocol/study-coverage.json) · [Les huit mêmes programmes remesurés dans les deux rejeux](comparaison-moteurs/tables/reperes-entre-rejeux.csv).',
        '', 'L’archive de livraison `historique-moteurs-et-cuda.zip` regroupe les deux études, les sources, les diagnostics, les capsules des moteurs et les scripts d’analyse. Son index précise les archives brutes volumineuses exclues du ZIP, conservées séparément dans les dossiers locaux. Les fichiers livrés et l’archive ont des empreintes SHA-256.', '']
    (BASE/'BILAN-COMPLET.md').write_text('\n'.join(out),encoding='utf8')
    print(json.dumps(counts))

if __name__=='__main__':main()
