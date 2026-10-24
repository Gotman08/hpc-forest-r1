"""Reconstruct exact trial lineage, file changes, and runtime provenance."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

from historical_audit import git_object, write

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == "scripts" else Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/comparaison-historique'
REPO=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')
OLD_WORK=REPO.parents[1]/'work'
sha=lambda b:hashlib.sha256(b).hexdigest()


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})


def read_source(store,commit):
    if not commit:return None
    try:return {name:git_object(store,commit+':'+name) for name in ('src/nbody_kernel.cu','src/launch.json')}
    except subprocess.CalledProcessError:return None


def inspect_trials():
    variants=json.loads((OUT/'data/variants.json').read_text(encoding='utf8'))
    lookup={(o['job_id'],o['commit']):v['id'] for v in variants for o in v['origins']}
    all_rows=[]
    for p in sorted((OUT/'data/campaigns').iterdir()):
        s=json.loads((p/'summary.json').read_text(encoding='utf8'))
        trials=json.loads((p/'trials.json').read_text(encoding='utf8'))
        evaluations=json.loads((p/'evaluations.json').read_text(encoding='utf8'))
        by_commit={r['payload']['commit']:r['payload'] for r in evaluations if r['phase']=='search' and r['payload'].get('commit')}
        by_trial={r['experiment_id']:r for r in evaluations if r['phase']=='search'}
        store=ROOT/'work/object-stores'/s['name']
        sources={}
        def source(commit):
            if commit not in sources:sources[commit]=read_source(store,commit)
            return sources[commit]
        best=None
        campaign_rows=[]
        for i,t in enumerate(trials,1):
            result,mission=t['result'],t['mission'];commit=result.get('commit');base=mission.get('base_commit')
            current,parent=source(commit),source(base)
            changed=[n for n in current if current[n]!=parent.get(n)] if current and parent else None
            kind='non disponible' if changed is None else 'copie exacte' if not changed else 'lancement seul' if changed==['src/launch.json'] else 'kernel seul' if changed==['src/nbody_kernel.cu'] else 'kernel et lancement'
            baseline=by_commit.get(base,{}).get('mean_seconds')
            measured=result.get('mean_seconds') if result.get('status')=='valid' else None
            prior_best=best
            if measured and t['role']!='G':best=min(best,measured) if best else measured
            patch_path=None
            if current and parent:
                diff=subprocess.check_output(['git','--git-dir='+str(store),'diff','--no-ext-diff',base,commit,'--','src/nbody_kernel.cu','src/launch.json'])
                target=OUT/'diffs'/s['job_id']/(t['id']+'.patch');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(diff)
                patch_path=target.relative_to(OUT).as_posix()
            row=dict(campaign=s['job_id'],ordinal=i,id=t['id'],role=t['role'],parent_id=mission.get('parent_id'),
                     depth=mission.get('depth'),created=t['created'],elapsed_seconds=t['created']-s['started'],
                     commit=commit,base_commit=base,variant_id=lookup.get((s['job_id'],commit)),
                     status=result.get('status'),reason=result.get('reason'),seconds=measured,
                     score=result.get('score'),base_search_seconds=baseline,
                     gain_vs_base_pct=(1-measured/baseline)*100 if measured and baseline else None,
                     best_research_before_seconds=prior_best,
                     beats_best_research=bool(measured and (prior_best is None or measured<prior_best)),
                     change_kind=kind,changed_paths=changed,patch=patch_path,
                     hypothesis=mission.get('hypothesis'),transformations=mission.get('transformations'),
                     source_ids=mission.get('sources'),source_commits=mission.get('source_commits'))
            evaluated=by_trial.get(t['id'],{}).get('created')
            row.update(evaluated_at=evaluated,measured_elapsed_seconds=evaluated-s['started'] if evaluated else None)
            if current:
                row.update(kernel_sha256=sha(current['src/nbody_kernel.cu']),launch=json.loads(current['src/launch.json']))
            campaign_rows.append(row);all_rows.append(row)
        write(p/'lineage.json',campaign_rows)
        write_csv(OUT/'tables'/('essais-'+s['job_id']+'.csv'),campaign_rows)
    write(OUT/'data/lineage.json',all_rows)
    write_csv(OUT/'tables/tous-les-essais.csv',all_rows)
    write_csv(OUT/'tables/provenance-programmes.csv',[dict(variant_id=v['id'],source_sha256=v['source_sha256'],launch=v['launch'],**o) for v in variants for o in v['origins']])
    print('Trial lineage',len(all_rows),flush=True)


def inspect_engines():
    commits=json.loads((OUT/'data/commits.json').read_text(encoding='utf8'))
    git_trees={}
    for c in commits:
        if c['source_tree'] in git_trees:continue
        data=subprocess.check_output(['git','-C',str(REPO),'archive','--format=zip',c['commit'],'src/hpc_forest'])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            git_trees[c['source_tree']]={n.removeprefix('src/hpc_forest/'):sha(z.read(n).replace(b'\r\n',b'\n')) for n in z.namelist() if n.endswith('.py')}
    payloads=[]
    for folder in sorted(OLD_WORK.glob('cuda*')):
        if not folder.is_dir():continue
        for relative in ('payload','artifact/payload'):
            root=folder/relative;src=root/'project/src/hpc_forest'
            if not src.is_dir() or not (root/'plan.json').exists():continue
            hashes={p.relative_to(src).as_posix():sha(p.read_bytes()) for p in sorted(src.rglob('*.py'))}
            exact=sha(json.dumps(hashes,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
            normalized={p.relative_to(src).as_posix():sha(p.read_bytes().replace(b'\r\n',b'\n')) for p in sorted(src.rglob('*.py'))}
            manifest=json.loads((root/'runtime-manifest.json').read_text())
            mismatches=[n for n,h in manifest.items() if not (root/n).is_file() or sha((root/n).read_bytes())!=h]
            protocol=root/'validation/protocol.py'
            if not protocol.exists():protocol=root/'trusted/protocol.py'
            matches=[c['commit'] for c in commits if git_trees[c['source_tree']]==normalized]
            distances=[]
            for tree,files in git_trees.items():
                changed=[n for n in normalized.keys()|files.keys() if normalized.get(n)!=files.get(n)]
                distances.append((len(changed),tree,changed))
            nearest=min(distances)
            payloads.append(dict(payload=str(root),engine_identity=exact,source_files=len(hashes),
                                 manifest_matches=not mismatches,manifest_mismatches=mismatches,
                                 normalized_matching_commits=matches,
                                 nearest_commit=next(c['commit'] for c in commits if c['source_tree']==nearest[1]),
                                 differences_from_nearest=nearest[2],
                                 protocol_sha256=sha(protocol.read_bytes()) if protocol.exists() else None))
    campaigns=json.loads((OUT/'data/campaigns.json').read_text(encoding='utf8'))
    mapping=[dict(campaign=c['job_id'],observed_engine_identity=c['engine_identity'],
                  payload_matches=[p for p in payloads if p['engine_identity']==c['engine_identity']]) for c in campaigns]
    write(OUT/'data/engine-provenance.json',mapping)
    write(OUT/'data/all-frozen-payloads.json',payloads)
    print(json.dumps([{'job':r['campaign'],'matches':len(r['payload_matches']),
                       'git_matches':[p['normalized_matching_commits'] for p in r['payload_matches']]} for r in mapping]),flush=True)


if __name__=='__main__':
    inspect_trials()
    inspect_engines()
