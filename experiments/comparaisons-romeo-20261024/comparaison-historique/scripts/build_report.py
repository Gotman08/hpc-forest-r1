"""Build the French study report from auditable observations, never from guessed scores."""
from __future__ import annotations
import collections
import csv
import html
import json
import math
import statistics
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    PARIS=ZoneInfo('Europe/Paris')
except ZoneInfoNotFoundError:
    # This study is dated 23 October 2026; the archived commits explicitly use
    # UTC+02:00. Do not silently apply that offset to a winter rerun.
    if not '2026-10-19' <= datetime.now(timezone.utc).date().isoformat() <= '2026-10-24':
        raise RuntimeError('Install tzdata to regenerate this report outside the original study period')
    PARIS=timezone(timedelta(hours=2),'Europe/Paris')

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == "scripts" else Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/comparaison-historique'

LABELS={
 '772923':'Première campagne CUDA, recherche par vagues',
 '774157':'Arbres indépendants, assemblage par paires',
 '775521':'Mémoire persistante, réserve de budget trop conservatrice',
 '775815':'Première correction du calcul de réserve',
 '776048':'Assemblage adaptatif et budget corrigé',
 '776290':'Correction de l’admission en fin de budget',
 '780448':'Mémoire enrichie, critique du plan et interruption du relais',
}
OBSERVATIONS={
 '772923':'Le programme final est confirmé, mais le contrôleur initial échoue à l’export, car il exige Makefile et run.sh. L’export a été récupéré séparément. Les mesures restent valides ; le pipeline initial ne s’est pas terminé normalement.',
 '774157':'Le programme confirmé est rapide. La dernière intégration recopie exactement sa base dans les deux fichiers autorisés. Cette copie a été évaluée, mais ne constitue pas une nouvelle transformation du programme.',
 '775521':'La réserve de finalisation surévalue les coûts possibles. La recherche ne produit que trois essais avant assemblage. La première combinaison est plus lente que sa base ; la seconde l’améliore.',
 '775815':'Le calcul de réserve devient moins conservateur. La campagne passe à 24 essais de recherche, dont 22 valides. Le sujet de réduction parallèle des sources n’est pas présent dans le plan de cette campagne.',
 '776048':'Cette campagne explore explicitement la réduction parallèle des forces sur les sources. La première combinaison améliore la meilleure variante de cet arbre. Elle fournit le meilleur programme confirmé de l’historique archivé.',
 '776290':'La décision budgétaire de fin de campagne est corrigée, mais le programme final reste beaucoup plus lent que celui de 776048. Les deux intégrations ne changent que launch.json par rapport à leur base.',
 '780448':'Une critique du plan est bien exécutée. Une interruption du relais ferme prématurément la recherche : huit essais sont admis, dont trois sans mesure à cause de l’infrastructure. La première combinaison ralentit sa base ; la seconde ne modifie que le lancement. La fin du pipeline ne supprime pas l’incident de recherche.',
}


def load(path,default=None):
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else default


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def csv_write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})


def number(n,digits=6):
    return '—' if n is None else f'{n:.{digits}f}'.replace('.',',')


def ms(value):return number(value*1000 if value is not None else None)


def duration(value):
    return '—' if value is None else f'{int(value)//60} min {int(value)%60:02d} s'


def plain(value):return str(value).replace('|','\\|').replace('\n',' ')


def build():
    campaigns=load(OUT/'data/campaigns.json')
    commits=load(OUT/'data/commits.json')
    variants=load(OUT/'data/variants.json')
    lineage=load(OUT/'data/lineage.json')
    provenance=load(OUT/'data/engine-provenance.json')
    inventory=load(OUT/'data/inventory.json')
    replay=load(OUT/'gpu/results/summary.json',{})
    replay_analysis=load(OUT/'data/replay-analysis.json',{})
    verification=load(OUT/'protocol/replay-verification.json',{})
    mailbox_repeats=load(OUT/'regression-tests/mailbox-repeats/results.json',{})
    fresh={r['id']:r for r in replay.get('programs',[])}
    engines=[load(p) for p in (OUT/'engine-tests-isolated').glob('*/result.json')]
    engines_by={r['commit']:r for r in engines}
    regression=load(OUT/'regression-tests/results.json',[])
    variant_map={(o['job_id'],o['commit']):v['id'] for v in variants for o in v['origins']}
    summaries=[]
    for c in campaigns:
        job=c['job_id'];best=c['best_confirmed'];v=variant_map.get((job,best['commit']));new=fresh.get(v,{})
        counts=c['research_counts'];total=sum(counts.values())
        mapping=next(r for r in provenance if r['campaign']==job)['payload_matches'][0]
        summaries.append(dict(campaign=job,label=LABELS[job],trees=len(c['forest_plan']['children']),
            trials=total,valid=counts.get('valid',0),incorrect=counts.get('incorrect',0),
            unmeasured=total-counts.get('valid',0)-counts.get('incorrect',0),
            historical_seconds=best['mean_seconds'],historical_speedup=best['reference_seconds']/best['mean_seconds'],
            replay_seconds=new.get('mean_seconds'),replay_speedup=new.get('speedup'),replay_status=new.get('status','en cours'),
            duration_seconds=c['finished']-c['started'],search_seconds=c['search_closed']-c['started'],
            winner_variant=v,winner_commit=best['commit'],engine_identity=c['engine_identity'],
            exact_git_matches=mapping['normalized_matching_commits'],
            model=c['model'],effort=c['effort'],observation=OBSERVATIONS[job]))
    csv_write(OUT/'tables/campagnes.csv',summaries)
    write_json(OUT/'data/campaign-comparison.json',summaries)
    for row in lineage:
        current=fresh.get(row.get('variant_id'),{})
        base_id=variant_map.get((row['campaign'],row.get('base_commit')))
        base=fresh.get(base_id,{})
        a,b=current.get('mean_seconds'),base.get('mean_seconds')
        row.update(replay_seconds=a,replay_status=current.get('status'),base_variant_id=base_id,
                   replay_base_seconds=b,replay_gain_vs_base_pct=(1-a/b)*100 if a and b else None)
    csv_write(OUT/'tables/essais-avec-remesures.csv',lineage)
    integration=[r for r in lineage if r['role']=='G']
    csv_write(OUT/'tables/integrations.csv',integration)
    joined=[]
    for v in variants:
        r=fresh.get(v['id'],{})
        row={**v,**r};row['campaigns']=sorted({o['job_id'] for o in v['origins']})
        row['source_code']=(OUT/'sources'/v['id']/'src/nbody_kernel.cu').read_text(encoding='utf8')
        joined.append(row)
    write_json(OUT/'data/program-comparison.json',joined)
    csv_write(OUT/'tables/programmes-remesures.csv',[{k:v for k,v in r.items() if k not in {'origins','source_code'}} for r in joined])

    stamp=datetime.now(PARIS).strftime('%d/%m/%Y à %H:%M')
    text=['# Comparaison historique — HPC Forest / CUDA N-body','',f'Étude du {stamp}, heure de Paris. Dépôt observé au commit `{inventory["head"]}`.','',
          '## Résultat et périmètre','',
          f'L’étude reconstruit **{len(commits)} commits**, **7 campagnes**, **138 essais de recherche ou d’assemblage** et **124 programmes distincts octet pour octet**, retrouvés dans **152 évaluations valides**. Les programmes lents sont inclus. Les essais incorrects et les incidents restent dans l’historique. Aucune source d’une évaluation valide ne manque.','',
          '**Trois types de preuves sont séparés :** les campagnes historiques avec leurs décisions, les nouvelles exécutions GPU de leurs programmes, et les vérifications fonctionnelles des versions du moteur. Les tests du moteur ne sont pas de nouvelles recherches de 30 minutes avec Mother. Les relances GPU n’appellent aucun modèle.','']
    if fresh:
        measured=[r for r in joined if r.get('fully_measured')]
        ranked=sorted(measured,key=lambda r:r['mean_seconds'])
        best=ranked[0]
        text += [f'Les **{len(measured)}/124 programmes** ont une mesure complète sur le job ROMEO **780574**. Le plus rapide du rejeu est `{best["id"]}` : **{ms(best["mean_seconds"])} ms**, soit **{number(best["speedup"],2)}×** la référence remesurée. Son origine : campagne(s) {", ".join(best["campaigns"])}.','',
                 'Chaque programme est vérifié sur les 11 cas de recherche et les 11 cas de confirmation. Les temps proviennent de cinq répétitions fraîches ; chaque répétition agrège trois tailles. Une référence supplémentaire est mesurée au début et à la fin de chaque bloc.','']
    else:text += ['**Les nouvelles mesures GPU sont encore en cours.** Les colonnes de rejeu restent absentes jusqu’à récupération et vérification des résultats.','']
    text += ['## Comparaison des gagnants historiques','',
             'Le choix du gagnant de chaque campagne est conservé. Il n’est pas remplacé a posteriori par un candidat favorisé par les nouvelles mesures. Les valeurs ci-dessous sont des moyennes en millisecondes ; plus petit est meilleur.','',
             '| Campagne | N | Recherche : essais / valides | Durée historique | Confirmé historique (ms) | Rejeu commun (ms) | Accélération du rejeu |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        text.append(f'| {s["campaign"]} | {s["trees"]} | {s["trials"]} / {s["valid"]} | {duration(s["duration_seconds"])} | {ms(s["historical_seconds"])} | {ms(s["replay_seconds"])} | {number(s["replay_speedup"],2)}× |')
    if verification and replay_analysis:
        text += ['', '## Stabilité et détail des nouvelles mesures', '',
                 f'Les **{verification["benchmark_samples_recomputed"]} échantillons** et **{verification["size_latencies_recomputed"]} temps par taille** ont été recalculés depuis les journaux. Les **{verification["correctness_cases_recomputed"]} contrôles de cas** incluent la référence de contrôle supplémentaire ; les 124 programmes historiques représentent 2 728 contrôles. Aucun résultat incorrect ni mesure manquante dans ce rejeu.', '',
                 f'La référence de contrôle varie de **{ms(verification["baseline_min_seconds"])} à {ms(verification["baseline_max_seconds"])} ms**, soit une étendue de **{number(verification["baseline_range_pct"],3)} %** de sa moyenne. Le coefficient de variation médian des programmes est de **{number(replay_analysis["median_program_cv_pct"],3)} %** ; le maximum est de **{number(replay_analysis["max_program_cv_pct"],3)} %**. Ces valeurs décrivent la dispersion du chronométrage, pas la probabilité de réussite d’une recherche.', '',
                 'Le premier programme est premier dans quatre blocs sur cinq. Son prédécesseur gagne le quatrième bloc. Les intervalles min–max des deux meilleurs se recouvrent : leur faible écart ne mérite pas la même confiance que les grandes accélérations.', '',
                 '| Rang moyen | Programme | Moyenne (ms) | Min–max (ms) | Écart-type (ms) | Accélération |', '|---|---|---:|---:|---:|---:|']
        for rank,p in enumerate(replay_analysis['top_10'],1):
            text.append(f'| {rank} | `{p["id"]}` | {ms(p["mean_seconds"])} | {ms(p["min_seconds"])}–{ms(p["max_seconds"])} | {ms(p["stdev_seconds"])} | {number(p["speedup"],2)}× |')
        text += ['', '### Taille du problème et précision', '',
                 'Le temps agrégé masque des accélérations différentes selon la taille. Voici les moyennes des latences brutes du gagnant et de la référence :', '',
                 '| Particules | Référence (ms) | Gagnant (ms) | Accélération |', '|---|---:|---:|---:|']
        best_record=load(OUT/'gpu/results/records'/f'{best["id"]}.json')
        control_record=load(OUT/'gpu/results/records/baseline-control.json')
        for n in [4096,8192,16384]:
            base=statistics.mean(d['latency_ms'] for s in control_record['samples'] for d in s['payload']['details'] if d['n']==n)
            val=statistics.mean(d['latency_ms'] for s in best_record['samples'] for d in s['payload']['details'] if d['n']==n)
            text.append(f'| {n} | {number(base)} | {number(val)} | {number(base/val,2)}× |')
        error=max(d['max_absolute_error'] for phase in best_record['checks'].values() for d in phase['payload']['details'])
        text += ['', f'L’écart absolu maximal du gagnant sur les deux jeux de correction est **{error:.12g}**, sans aucune sortie hors de la tolérance combinée absolue et relative. Les masses restent identiques. Réussir ces cas n’implique pas une identité bit à bit de toutes les positions et vitesses.', '',
                 '[Mesures de chaque taille et chaque bloc](tables/mesures-par-taille.csv) · [Erreurs numériques de chaque cas](tables/correction-par-cas.csv) · [Vérification des agrégats](protocol/replay-verification.json)', '',
                 '## Transformations dont l’effet peut être comparé directement', '',
                 'Les observations suivantes relient une différence exacte de fichiers à la base directe, toutes deux remesurées. « Plus rapide dans 5/5 blocs » reste une description des mesures ; ce n’est pas un test de significativité ni cinq recherches indépendantes.', '',
                 '| Campagne / transition | Modification visible dans le patch | Effet frais sur le temps | Blocs plus rapides |', '|---|---|---:|---:|']
        mechanisms=[
            ('776048','bd224cee51694d00','`sqrtf` + division remplacés par `rsqrtf` et produit de trois inverses ; lancement inchangé'),
            ('776048','f1843fc5ccdb4b63','Suppression de la masse cible dans la force et de sa division à la mise à jour de vitesse'),
            ('775521','fe8207f9ecac4c0b','Racine inverse avec une correction de Newton à la place de la racine + division'),
            ('776290','1650707a621649ef','Même kernel : bloc de 256 réduit à 32, avec adaptation des sorties par bloc'),
            ('780448','154507185f9c4846','Même kernel : bloc de 256 réduit à 128'),
            ('780448','4068c0071be145e3','Deux cibles adjacentes par thread et 512 sorties par bloc au lieu d’une cible par thread'),
            ('774157','83808cc6f6df42b9','Copie strictement identique de la base ; une seule identité rejouée'),
        ]
        for campaign,trial,description in mechanisms:
            t=next(t for t in replay_analysis['transitions'] if t['campaign']==campaign and t['trial']==trial)
            text.append(f'| [{campaign} / `{trial}`](diffs/{campaign}/{trial}.patch) | {description} | {number(t["gain_pct"],2)} % de réduction | {t["faster_blocks"]}/5 |')
        text += ['', 'Une réduction négative signifie un ralentissement. Le passage à deux cibles par thread dans 780448 allonge ainsi le temps de **70,79 %**. La perte est observée ; le rejeu ne contient pas de profilage matériel permettant de l’attribuer aux registres, à l’occupation ou aux accès mémoire.', '',
                 'Le meilleur kernel répartit déjà le calcul des sources entre threads avant le remplacement de la racine. Le gain de **24,40 %** correspond à cette base précise ; ce n’est pas le gain de `rsqrtf` dans tous les kernels.', '',
                 f'À source CUDA strictement identique, **{replay_analysis["launch_group_count"]} familles** couvrent **{replay_analysis["launch_program_count"]} programmes** avec des paramètres différents. Les **{replay_analysis["launch_comparison_count"]} comparaisons** de lancement sont conservées séparément. Un changement de `launch.json` peut avoir un effet mesurable sans être une fusion de kernels.', '',
                 '[Toutes les comparaisons de lancement](tables/comparaisons-lancements.csv) · [Toutes les transitions, bloc par bloc](tables/transitions-par-bloc.csv)', '']
    text += ['', '## Ce que les observations permettent de conclure','',
       '- **Les changements n’améliorent pas tous la vitesse obtenue.** Le meilleur résultat historique vient de 776048, avant la critique du plan et plusieurs améliorations de mémoire.',
       '- **La représentation mémoire est corrigée.** Le même test avant/après reproduit l’absence du bilan factuel dans l’ancienne version, puis vérifie le meilleur programme, une alternative lente et le dernier échec dans la nouvelle.',
       '- **Les leçons facultatives ne doivent pas faire perdre le code.** Le test avant/après reproduit `CandidateRejected: Missing memory envelope`, puis passe avec conservation du code au commit `06f2b38`.',
       '- **La réserve de critique tient désormais compte de N.** Les tests avant/après montrent que les anciens calculs admettaient la critique avec 20 ou 600 arbres malgré le travail d’assemblage restant ; `106196b` corrige ces cas. Cela prouve un changement de décision budgétaire, pas un gain de vitesse du programme produit.',
       '- **Le nombre d’essais et les sujets explorés comptent.** Après la correction de réserve, les campagnes observées passent de 3 essais à 24 puis 31 ; le meilleur lancement explore aussi une réduction parallèle des forces absente de plusieurs autres plans. Ces facteurs changent ensemble : leur contribution individuelle n’est pas isolée.',
       '- **L’assemblage peut régresser ou recopier un programme.** Les différences de fichiers et les mesures sont conservées pour chaque intégration. Une déclaration de « fusion » n’est pas utilisée comme preuve de nouveauté.',
       '- **L’incident du relais reste une limite réelle.** La campagne 780448 termine l’assemblage et la confirmation après une recherche interrompue. Elle ne démontre pas une meilleure régularité.',
       '', 'Le rejeu fixe le matériel, les entrées, le vérificateur et la mesure pour comparer les programmes. Il ne mesure pas la probabilité qu’un moteur retrouve une optimisation lors d’une nouvelle recherche. Pour attribuer causalement une amélioration de recherche à une fonction du moteur, il faudrait des campagnes neuves répétées, à modèle, programme et budget identiques, avec tous les échecs conservés.','',
       '## Chronologie des commits','',
       '| Date (Paris) | Commit | Nature | Modification enregistrée |', '|---|---|---|---|']
    for c in commits:
        dt=datetime.fromisoformat(c['date']).astimezone(PARIS).strftime('%d/%m %H:%M')
        text.append(f'| {dt} | `{c["commit"][:7]}` | {"Code / tests" if c["code_or_test_change"] else "Preuves / documentation"} | {plain(c["subject"])} |')
    text += ['', 'Le dépôt contient **10 états distincts de `src/`** pour 12 commits touchant code, lanceurs ou tests. Les commits documentaires ne constituent pas de nouveaux moteurs.','',
             '## Versions réellement embarquées','',
             'Les empreintes de tous les payloads retrouvés correspondent à leurs manifestes, et leur identité de moteur correspond au registre de campagne. La correspondance Git ci-dessous compare les sources Python après normalisation CRLF/LF ; les empreintes exactes d’origine restent dans les données.','',
             '| Campagne | Sources retrouvées | Correspondance Git du moteur |', '|---|---|---|']
    for p in provenance:
        match=p['payload_matches'][0];exact=match['normalized_matching_commits']
        label=', '.join('`'+x[:7]+'`' for x in exact) if exact else 'État intermédiaire : '+str(len(match['differences_from_nearest']))+' fichiers différents du commit le plus proche `'+match['nearest_commit'][:7]+'`'
        text.append(f'| {p["campaign"]} | Oui, manifeste vérifié | {label} |')
    text += ['', '**Quatre campagnes utilisent des états intermédiaires sans commit identique.** Les rattacher directement à un commit voisin fausserait l’historique. Les payloads figés permettent de les identifier exactement.','',
             '## Vérifications fonctionnelles des versions','',
             'Chaque révision utilise ses propres tests non modifiés, un import depuis sa source Git, un dossier de travail et un répertoire temporaire distincts. Python 3.13 sous Windows est commun à cette matrice. Les nombres de tests changent avec les versions et ne sont pas des scores de performance.','',
             '| Commit | Tests collectés | Réussis | Échecs / erreurs | Ignorés | Ruff |', '|---|---:|---:|---:|---:|---|']
    for c in commits:
        if not c['code_or_test_change']:continue
        e=engines_by.get(c['commit'])
        if not e:text.append(f'| `{c["commit"][:7]}` | En cours | — | — | — | — |');continue
        suites=e.get('test_suites',[]);total=sum(int(x['tests']) for x in suites);bad=sum(int(x['failures'])+int(x['errors']) for x in suites);skip=sum(int(x['skipped']) for x in suites)
        ruff=next((x['exit_code'] for x in e['commands'] if x['check']=='ruff'),None)
        text.append(f'| `{c["commit"][:7]}` | {total} | {total-bad-skip} | {bad} | {skip} | {"OK" if ruff==0 else ruff} |')
    text += ['', 'La première révision présente trois échecs de préparation du binaire de référence sous Windows : elle cherche `solution` alors que le compilateur produit `solution.exe`. Le diagnostic vient de `contracts.py`, et la version suivante passe ces tests.', '',
             'Les trois dernières suites ont dépassé 30 minutes : seule leur supervision a été prolongée, avant expiration, en conservant les processus pytest et leurs tests inchangés. Les codes de sortie ont été observés directement par Windows. Ce temps total dépend des scénarios et de leur exécution simultanée ; il ne classe pas la vitesse des moteurs. [Trace de prolongation](protocol/test-supervision-extension.json).', '',
             'De `d2f79e7` à `6ee21f4`, le test CLI attend encore un dictionnaire sans `plan_review_calls`, alors que la nouvelle valeur par défaut est 2. Cet échec signale une attente de test obsolète, corrigée dans `2ea3236` ; il ne suffit pas à conclure que la critique du plan ne fonctionne pas.', '',
             'La suite de `6ee21f4` présente aussi une `PermissionError` Windows lors de la lecture d’une réponse locale publiée par un thread. Les dix répétitions séquentielles prévues de ce test passent toutes. Le module de messagerie est identique entre `6ee21f4` et `2ee6125`. L’échec initial est conservé : il n’est ni effacé par les répétitions, ni déclaré corrigé. Le lien éventuel avec la charge simultanée n’est pas établi. [Les dix répétitions et leurs journaux](regression-tests/mailbox-repeats/results.json).','',
             'Les premières tentatives du banc utilisaient un répertoire temporaire partagé et pouvaient se bloquer mutuellement ; elles sont exclues des résultats retenus. Le banc a ensuite isolé TEMP/TMP. Des chemins d’archives de diagnostics trop longs pour Windows ont été exclus de l’extraction des snapshots de test ; la référence CUDA utilisée par les tests est extraite inchangée de chaque commit. Les archives originales sont conservées. [Journaux des tentatives de préparation exclues](protocol/excluded-setup-attempts.zip).','',
             '### Régressions ciblées avant/après','',
             '| Cas | Parent, résultat | Correctif, résultat | Portée |', '|---|---|---|---|']
    for name,label,scope in [('memory-overview','Bilan mémoire','Absence de résultats factuels avant, conservation de la variante lente après'),('memory-decisions','Consultations et décisions','Module absent avant : comparaison de capacité, pas reproduction d’une décision identique'),('omitted-lessons','Leçons omises','Rejet du code avant ; code conservé après'),('provisional-budget','Réserve selon N','Critique admise à tort pour N=20 et N=600 avant')]:
        b=next((r for r in regression if r['case']==name and r['phase']=='before'),None);a=next((r for r in regression if r['case']==name and r['phase']=='after'),None)
        if b and a:text.append(f'| {label} | `{b["engine_commit"][:7]}`, sortie {b["exit_code"]} | `{a["engine_commit"][:7]}`, sortie {a["exit_code"]} | {scope} |')
    text += ['', '## Les 15 intégrations, une par une','',
             'Le gain est calculé par rapport à la base directe : positif = plus rapide ; négatif = plus lent. Une base non mesurée n’est pas remplacée par une valeur supposée. Une modification de source ne prouve pas une nouveauté sémantique.','',
             '| Campagne / essai | Changement vérifié | Temps historique (ms) | Gain historique / base | Gain du rejeu / base | Diff |', '|---|---|---:|---:|---:|---|']
    for r in integration:
        text.append(f'| {r["campaign"]} / `{r["id"]}` | {r["change_kind"]} | {ms(r["seconds"])} | {number(r["gain_vs_base_pct"],2)} % | {number(r["replay_gain_vs_base_pct"],2)} % | [patch]({r["patch"]}) |')
    text += ['', '## Historique détaillé par campagne','']
    for s in summaries:
        job=s['campaign'];c=next(x for x in campaigns if x['job_id']==job)
        events=load(OUT/'data/campaigns'/job/'events.json')
        csv_write(OUT/'tables'/f'evenements-{job}.csv',[
            dict(campaign=job,seconds_from_campaign_start=e['created']-c['started'],
                 paris_datetime=datetime.fromtimestamp(e['created'],PARIS).isoformat(),**e) for e in events])
        text += [f'### {job} — {s["label"]}','',s['observation'],'',
            f'Moteur observé : `{s["engine_identity"]}`. Modèle : `{s["model"]}`, effort `{s["effort"]}`. Cible : 30 minutes. Temps avant fermeture de recherche : {duration(s["search_seconds"])} ; pipeline : {duration(s["duration_seconds"])}.','',
            '| Horodatage Paris | Étape enregistrée | Diagnostic de décision |','|---|---|---|']
        stage_names={'workspace_created':'Espace préparé','mother_usage':'Proposition initiale de Mother terminée',
                     'mother_review_admission':'Décision d’admettre la critique','mother_review_usage':'Critique du plan terminée',
                     'mother_forest_selected':'Plan des arbres fixé','budget_stop':'Arrêt des nouvelles recherches',
                     'memory_assembly_budget_stop':'Arrêt budgétaire de l’assemblage',
                     'postprocess_finished':'Assemblage terminé','packaged':'Export préparé'}
        for event in events:
            if event['kind'] not in stage_names:continue
            stamp_event=datetime.fromtimestamp(event['created'],PARIS).strftime('%d/%m %H:%M:%S')
            p=event['payload'];reason=p.get('reason') or p.get('status') or '—'
            if event['kind']=='mother_review_admission':
                reason=f'can_review={p.get("can_review")}, requis={number(p.get("required_seconds"),2)} s, restant={number(p.get("remaining_seconds"),2)} s'
            text.append(f'| {stamp_event} | {stage_names[event["kind"]]} | {plain(reason)} |')
        text += ['',f'[Chronologie complète des {len(events)} événements, avec données brutes](tables/evenements-{job}.csv). Les étapes absentes du registre ne sont pas reconstituées par supposition.','',
            '| Arbre | Sujet déclaré par Mother | Essais | Valides | Meilleur de recherche (ms) |','|---|---|---:|---:|---:|']
        for child in c['forest_plan']['children']:
            rows=[r for r in lineage if r['campaign']==job and r['role']==child['role']]
            vals=[r['seconds'] for r in rows if r['seconds'] is not None]
            text.append(f'| {child["role"]} | {plain(child["subject"])} | {len(rows)} | {len(vals)} | {ms(min(vals) if vals else None)} |')
        text += ['',f'[Tous les essais et diagnostics](tables/essais-{job}.csv) · [Événements horodatés](data/campaigns/{job}/events.json) · [Décisions conservées](data/campaigns/{job}/decisions.json)','',
                 '| t depuis début | Essai / parent | Arbre, profondeur | Statut | Historique (ms) | Rejeu (ms) | Changement vérifié |','|---|---|---|---|---:|---:|---|']
        for r in lineage:
            if r['campaign']!=job:continue
            text.append(f'| {duration(r["elapsed_seconds"])} | `{r["id"]}` / `{r["parent_id"] or "origine"}` | {r["role"]}, {r["depth"]} | {r["status"]} | {ms(r["seconds"])} | {ms(r["replay_seconds"])} | {r["change_kind"]} |')
        text.append('')
    text += ['## Protocole du rejeu et limites','',
        '- Un GH200 ARM, quatre CPU, 16 Go, CUDA/NVRTC 12.6.3 et CMake fixés par empreinte Spack. GPU réservé via SLURM ; aucune mesure GPU concurrente dans l’étude.',
        '- Le protocole archivé est repris sans changement : 11 cas, graines 20261021 et 20261022, masses conservées exactement, tolérances GPU `atol=5e-5`, `rtol=2e-4`. La référence est contrôlée par un oracle CPU FP64 ; pour les grands tableaux, celui-ci porte sur 32 lignes réparties, tandis que la comparaison GPU porte sur toutes les sorties.',
        '- Tous les chronométrages frais utilisent le jeu de confirmation, commun aux 124 programmes. Tailles de performance : 4096, 8192, 16384. Dix échauffements, 100 lancements chronométrés par taille. Moyenne géométrique des trois temps, puis moyenne arithmétique des cinq répétitions.',
        '- Ordre des programmes mélangé de manière reproductible dans chacun des cinq blocs, graine 20261023. La référence de contrôle encadre chaque bloc ; ces mesures sont des répétitions de benchmark, pas des campagnes de recherche indépendantes.',
        '- Les programmes sont distincts selon leurs octets et leurs paramètres. Un changement de commentaire ou d’espacement peut créer une nouvelle identité sans changer l’algorithme. Les fichiers d’origine et les hashes restent disponibles.',
        '- Les hypothèses et leçons du modèle restent des déclarations. Les statuts, temps, erreurs, modifications et sorties de tests proviennent des registres ou des nouvelles exécutions.',
        '- Les études historiques concernent un seul problème. Elles ne suffisent pas à établir une régularité sur d’autres programmes.','',
        '## Fichiers pour vérifier ou poursuivre','',
        '- [Tableau de bord interactif](TABLEAU-DE-BORD.html) : campagnes, essais, code, diagnostics et commits.',
        '- [Campagnes](tables/campagnes.csv), [124 programmes](tables/programmes-remesures.csv), [138 essais remesurés quand valides](tables/essais-avec-remesures.csv), [15 intégrations](tables/integrations.csv).',
        '- `sources/` : deux fichiers exacts par programme ; `diffs/` : différences avec chaque base.',
        '- `gpu/` : mesures fraîches, contrôles par cas, ordre des benchmarks, environnement et journaux.',
        '- `engine-tests-isolated/` et `regression-tests/` : commandes, logs, résultats JUnit et diagnostics.',
        '- `data/` et `protocol/` : historique, provenance, empreintes, décisions, reçus et plan SLURM.',
        '- `scripts/` et `reproduction-gpu.tar.gz` : collecte, analyse, matrice et payload exact du rejeu.',
        '- `engines/` : archives des 12 révisions testées et sources Python exactes des 7 moteurs réellement embarqués, y compris les états intermédiaires.',
        '', 'Le dépôt d’origine et ses campagnes n’ont pas été modifiés. Aucun push ni nouvelle optimisation manuelle.','']
    (OUT/'RAPPORT.md').write_text('\n'.join(text),encoding='utf8')
    dashboard=dict(campaigns=summaries,programs=joined,trials=lineage,commits=commits,engines=engines,
                   regressions=regression,provenance=provenance,complete=len(fresh)==125,stamp=stamp,
                   replay_analysis=replay_analysis,verification=verification,mailbox_repeats=mailbox_repeats)
    write_json(OUT/'data/dashboard.json',dashboard)
    from dashboard_template import render
    (OUT/'TABLEAU-DE-BORD.html').write_text(render(dashboard),encoding='utf8')
    print(json.dumps({'gpu_programs':len(fresh),'engine_revisions':len(engines),'trials':len(lineage),'report':str(OUT/'RAPPORT.md')}))


if __name__=='__main__':build()
