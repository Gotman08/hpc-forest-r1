import json,tarfile
from pathlib import Path
r=Path(r'C:\Users\nicol\Documents\Codex\2026-10-23\ce-que-je-voudrais-que-tu\work\active-architecture-20261024-v5-reprise')
secrets=[]
for v in r.parent.glob('active-architecture-*'):
 p=v/'broker/connection.json'
 if p.is_file():
  t=json.loads(p.read_text(encoding='utf8')).get('token')
  if isinstance(t,str) and len(t)>15: secrets.append(t.encode())
names=['plan.json','settings.json','statement.txt','job.json','preparation.json','job-arguments.json','command.sh','slurm-plan.json','efficiency.json','result-transfer.json']
hits=[];checked=0
for c in (r/'campaigns').iterdir():
 for name in names:
  p=c/name
  if p.is_file():
   b=p.read_bytes();checked+=1
   if any(t in b for t in secrets): hits.append(str(p.relative_to(r)))
 p=c/'results.tar.gz'
 if p.exists():
  with tarfile.open(p) as archive:
   for item in archive:
    if not item.isfile() or item.size>10_000_000 or any(x in Path(item.name).parts for x in ['repo','worktrees','mailbox','worker','native']):continue
    b=archive.extractfile(item).read();checked+=1
    if any(t in b for t in secrets):hits.append(str(p.relative_to(r))+'!'+item.name)
result={'private_tokens_checked':len(secrets),'public_candidate_files_checked':checked,'matching_paths':hits}
(r/'private-token-scan.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result))
assert not hits, 'A publication candidate contains a private broker token'
