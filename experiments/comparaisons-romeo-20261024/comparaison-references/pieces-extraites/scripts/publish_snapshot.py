from pathlib import Path
import json, shutil, sys
R=Path(__file__).resolve().parent
O=Path(sys.argv[1]);O.mkdir(parents=True,exist_ok=True)
D=json.loads((R/'analysis.json').read_text(encoding='utf8'))
assert D['summary']['pending']==0 and D['summary']['measured']==57
for source,dest in [('comparison.csv','COMPARAISON.csv'),('analysis.json','RESULTATS.json')]:
    shutil.copy2(R/source,O/dest)
count=0
for attempt in D['attempts']:
    name=attempt['campaign_directory'];source=R/'campaigns'/name;dest=O/'protocol'/name
    dest.mkdir(parents=True,exist_ok=True)
    for item in ['plan.json','settings.json','preparation.json','statement.txt','adaptation.json']:
        if (source/item).is_file():shutil.copy2(source/item,dest/item);count+=1
print(json.dumps({'campaigns':len(D['attempts']),'protocol_files':count,'output':str(O)}))
