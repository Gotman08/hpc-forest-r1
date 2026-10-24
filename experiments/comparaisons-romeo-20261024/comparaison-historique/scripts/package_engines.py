"""Preserve tested Git revisions and exact Python sources of deployed engines."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] if Path(__file__).parent.name == 'scripts' else Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/comparaison-historique'
REPO=Path(r'C:\Users\nicol\Documents\Codex\2026-10-20\new-chat\outputs\hpc-forest-r1')


def main():
    commits=json.loads((OUT/'data/commits.json').read_text(encoding='utf8'))
    mapping=json.loads((OUT/'data/engine-provenance.json').read_text(encoding='utf8'))
    target=OUT/'engines'; (target/'commits').mkdir(parents=True,exist_ok=True);(target/'deployed').mkdir(exist_ok=True)
    entries=[]
    for c in commits:
        if not c['code_or_test_change']:
            continue
        paths=subprocess.check_output(['git','-C',str(REPO),'ls-tree','--name-only',c['commit']],text=True).splitlines()
        selected=[p for p in paths if p!='experiments']
        fixture='experiments/cuda-nbody-20261021/input/reference.cu'
        if subprocess.check_output(['git','-C',str(REPO),'ls-tree','--name-only',c['commit'],'--',fixture],text=True).strip():
            selected.append(fixture)
        zip_path=target/'commits'/(c['commit'][:7]+'.zip')
        subprocess.run(['git','-C',str(REPO),'archive','--format=zip','--output='+str(zip_path),c['commit'],*selected],check=True)
        entries.append(dict(kind='tested_git_revision',commit=c['commit'],path=zip_path.relative_to(OUT).as_posix(),
                            sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest(),included_roots=selected))
    for m in mapping:
        p=m['payload_matches'][0];root=Path(p['payload']);src=root/'project/src/hpc_forest'
        files=sorted(src.rglob('*.py'))
        hashes={f.relative_to(src).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
        identity=hashlib.sha256(json.dumps(hashes,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        assert identity==m['observed_engine_identity']
        pyproject=root/'project/pyproject.toml'
        if pyproject.is_file():files.append(pyproject)
        manifest={f.relative_to(root/'project').as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
        zip_path=target/'deployed'/(m['campaign']+'.zip')
        with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for f in files:archive.write(f,f.relative_to(root/'project').as_posix())
            archive.writestr('source-manifest.json',json.dumps(manifest,indent=2)+'\n')
        entries.append(dict(kind='deployed_engine_python_sources',campaign=m['campaign'],engine_identity=identity,
                            path=zip_path.relative_to(OUT).as_posix(),sha256=hashlib.sha256(zip_path.read_bytes()).hexdigest(),
                            source_files=len(hashes),scope='Python engine sources and pyproject only; not the entire historical deployment payload'))
    (target/'manifest.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (target/'LIRE-MOI.md').write_text('# Sources des moteurs conservées\n\n'
        '`commits/` contient les fichiers Git des 12 révisions testées, extraits sans modification : sources, tests, lanceurs, configurations, documentation et fichiers de dépendances. '
        'Les campagnes volumineuses du dépôt sont exclues, sauf la référence CUDA utilisée comme fixture de test ; leurs données sont dans le dossier principal.\n\n'
        '`deployed/` contient les sources Python exactes des sept moteurs réellement embarqués. Quatre diffèrent de tous les commits. '
        'Ces archives conservent le moteur, pas la totalité du payload de déploiement ni une nouvelle exécution de Mother. '
        'Chaque archive possède un manifeste de fichiers. Le manifeste extérieur conserve aussi l’identité de moteur vérifiée.\n',encoding='utf8')
    print(json.dumps({'git_archives':12,'deployed_archives':len(mapping),'bytes':sum((OUT/e['path']).stat().st_size for e in entries)}))


if __name__=='__main__':main()
