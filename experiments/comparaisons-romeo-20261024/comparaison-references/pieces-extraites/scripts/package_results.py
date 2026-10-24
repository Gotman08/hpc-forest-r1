from pathlib import Path
import json,hashlib,zipfile,shutil,re,tarfile,sys
R=Path(__file__).resolve().parent;O=Path(sys.argv[1]);O.mkdir(parents=True,exist_ok=True)
D=json.loads((R/'analysis.json').read_text(encoding='utf8'))
assert D['summary']['pending']==0 and D['summary']['measured']==57
assert len(D['engines'])==21 and len(D['attempts'])==22
audit=json.loads((O/'AUDIT-FINAL.json').read_text(encoding='utf8'))
assert audit['generated_at']==D['summary']['generated_at'] and audit['candidate_failures']==0 and audit['unexpected_reference_failures']==0
assert len(D['summary']['final_failures'])==3
files={}
def add(p,name):
 p=Path(p);assert p.is_file(),p
 assert name not in files,name
 assert not any(x in {'.ssh','broker','node_modules','worker'} for x in Path(name).parts)
 files[name]=p
add(R/'protected-suites.tar.gz','references/protected-suites.tar.gz')
for name in ['acquisition.json','ispc-assets.json','workbook.json','analysis.json','gpu-environment.json','cpu-trusted-files.json','render-trusted-files.json','utf8-audit.json','volume-domain-audit.json','diagnostics-781163.json','cpu-binaries.json','engine-file-manifests.json','engine-origin-audit.json']:
 add(R/name,'metadata/'+name)
for p in sorted(R.glob('*.json')):
 if any(s in p.name for s in ['results','environment','complete','reference-repeats','job-efficiency']) and p.name not in ['analysis.json','gpu-environment.json']:
  add(p,'mesures/'+p.name)
for p in sorted(R.glob('*.py')):
 if p.name in {'broker.py','relay.py','launch_support.py','engine_broker_client.py'}:continue
 add(p,'scripts/'+p.name)
for name in ['build_workbook.mjs','dashboard.html','gpu_driver.cu','render_driver.cpp','render_context.h']:
 add(R/name,'scripts/'+name)
for folder in ['cpu-final','gpu-final','extra-final','render-final-aobench','render-final-volume','render-final-raytracer','render-final-deferred']:
 for p in sorted((R/folder).rglob('*')):
  if p.is_file() and p.suffix in {'.py','.cu','.cpp','.json','.h'}:add(p,'candidats/'+folder+'/'+p.relative_to(R/folder).as_posix())
for e in D['attempts']:
 root=R/'campaigns'/e['campaign_directory'];dest='campagnes/'+root.name
 add(root/'results.tar.gz',dest+'/results.tar.gz')
 for name in ['plan.json','settings.json','preparation.json','statement.txt','command.sh','adaptation.json']:
  if (root/name).exists():add(root/name,dest+'/'+name)
 for name in ['runtime-manifest.json','validation/case.json','validation/protocol.py','benchmark_evaluator.py','pilot.py']:
  if (root/'payload'/name).exists():add(root/'payload'/name,dest+'/'+name)
engine=R/'campaigns/argmin/payload/project'
for p in sorted(engine.rglob('*')):
 if p.is_file() and not any(x in {'.git','__pycache__','.venv'} for x in p.relative_to(engine).parts):add(p,'moteur/'+p.relative_to(engine).as_posix())
for p in sorted((R/'upstream').rglob('*')):
 if p.is_file() and (p.name.startswith('LICENSE') or p.name.startswith('COPYING')):add(p,'licences/'+p.relative_to(R/'upstream').as_posix())
for name in ['RAPPORT.md','HISTORIQUE-FOREST.md','COMPARAISON.csv','RESULTATS.json','AUDIT-FINAL.json']:
 add(O/name,'rapport/'+name)
for name in ['DETAILS-FOREST.md','DETAILS-FOREST.csv','AUDIT-FOREST.json']:
 if (O/name).exists():add(O/name,'rapport/'+name)
add(Path('C:/Users/nicol/Downloads/Comparatif_codes_naifs_optimises.xlsx'),'entree/Comparatif_codes_naifs_optimises.xlsx')
# Only explicit research files are exported; no local relay session directory.
manifest={name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for name,p in files.items()}
readme='''# Preuves et codes — comparaison ROMEO / Forest

Voir rapport/RAPPORT.md pour les résultats et limites. Toutes les dates sont celles de la campagne du 23 octobre 2026.

L’audit complémentaire rapport/DETAILS-FOREST.md détaille les sessions neuves, la mémoire persistante interne, les interventions de préparation, le nombre d’arbres et l’architecture hybride ROMEO / relais local / inférence hébergée. AUDIT-FOREST.json fournit les constats et empreintes ; les invocations complètes restent dans les dossiers de travail locaux et ne sont pas exportées avec la configuration de connexion du relais.

- references/protected-suites.tar.gz : sources ET binaires effectivement employés sur ROMEO, journaux de construction et données de scène. Le MANIFEST.json interne contrôle 374 fichiers. Extraire sur Linux ; les binaires CPU sont x86_64 et les binaires GPU aarch64/sm_90.
- candidats/ : sources retenues et intégration G, commits et SHA256. Les sources restent inchangées après la recherche.
- campagnes/ : archives natives contenant les dépôts Git, essais, sorties, diagnostics, confirmations et mémoire ; plans et protocoles protégés de chaque campagne. Le premier deferred échoué est distinct de deferred_r2.
- moteur/ : instantané du moteur gelé, identique dans les 22 lancements ; metadata/engine-file-manifests.json vérifie chaque fichier de chaque copie.
- mesures/ : mesures brutes de référence, mesures finales et environnements.
- scripts/ : acquisition, construction, protocoles, analyses et génération des livrables. Les chemins ROMEO correspondent à la campagne et doivent être adaptés pour une nouvelle installation.
- entree/ : classeur original inchangé ; licences/ : licences des dépôts sources disponibles.

Recalcul des livrables : placer les fichiers de mesures et metadata/analysis.json dans un dossier conforme à work/reference-study, puis exécuter analyze_comparison.py, build_report.py, build_dashboard.py et build_workbook.mjs. Le dernier requiert @oai/artifact-tool. L’analyse utilise uniquement la bibliothèque standard Python. Les protocoles CPU requièrent NumPy ; les cas GPU complémentaires torch/Triton/CUDA. Les versions exactes et hashes Spack sont dans les journaux et scripts de construction.

Pour rejouer les mesures, construire les références avec cpu_build.py / render_build.py et les scripts GPU, puis exécuter les scripts *_final_compare.py dans des allocations SLURM de l’architecture correspondante, avec les compilateurs et nombres de cœurs/GPU indiqués. Conserver la même allocation entre variantes d’un cas et les mêmes fichiers d’entrée. Les candidats candidats/*/manifest.json fournissent les empreintes attendues. Les fichiers d’entrée volumineux rendus sont inclus dans l’archive protégée.

Rejouer une recherche Forest demande un accès modèle autorisé et une installation de TreeQuest 0.3.2 ; les configurations et le moteur sont fournis, les identifiants du compte et du relais ne le sont pas. Ne pas remplacer les mesures finales par les meilleurs temps de recherche. Les compteurs de tokens natifs n’ont pas été audités.

Le CSV et les colonnes de calcul utilisent des nombres bruts ; les arrondis sont uniquement une présentation. Les lignes non reproduites restent vides/NR. Le changement publié→ROMEO ne mesure pas l’effet du matériel seul.
'''
with zipfile.ZipFile(O/'PREUVES-ET-CODES.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,p in files.items():z.write(p,name,compress_type=zipfile.ZIP_STORED if p.suffix in {'.gz','.xlsx'} else zipfile.ZIP_DEFLATED)
 z.writestr('README.md',readme)
 z.writestr('MANIFEST-SHA256.json',json.dumps(manifest,indent=2,ensure_ascii=False))
with zipfile.ZipFile(O/'PREUVES-ET-CODES.zip') as z:
 assert z.testzip() is None
 assert all(hashlib.sha256(z.read(n)).hexdigest()==v['sha256'] for n,v in manifest.items())
print(json.dumps({'archive':str(O/'PREUVES-ET-CODES.zip'),'files':len(manifest),'bytes':(O/'PREUVES-ET-CODES.zip').stat().st_size,'sha256':hashlib.sha256((O/'PREUVES-ET-CODES.zip').read_bytes()).hexdigest()}))
