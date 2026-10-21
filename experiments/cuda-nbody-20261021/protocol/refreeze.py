"""Refreeze owned preparation before any upload, model call or GPU submission."""
import hashlib
import json
import shlex
import shutil
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
state = json.loads((HERE/'state.json').read_text())
artifact = Path(state['artifact'])
payload = artifact/'payload'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for src,dest in [('protocol.py','validation/protocol.py'),('pilot.py','pilot.py'),
                 ('cuda_evaluator.py','cuda_evaluator.py')]:
    shutil.copyfile(HERE/src,payload/dest)
manifest = {p.relative_to(payload).as_posix():sha(p) for p in sorted(payload.rglob('*'))
    if p.is_file() and p.name != 'runtime-manifest.json' and '__pycache__' not in p.parts}
data = json.dumps(manifest,indent=2)+'\n'
(payload/'runtime-manifest.json').write_text(data,encoding='utf8')
(artifact/'runtime-manifest.json').write_text(data,encoding='utf8')
archive = artifact/'payload.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for p in sorted(payload.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            tar.add(p,arcname=p.relative_to(payload).as_posix(),recursive=False)
oldsha = state['payload_sha256']
state['payload_sha256'] = sha(archive)
state['runtime_manifest_sha256'] = sha(payload/'runtime-manifest.json')
state['job_command'] = state['job_command'].replace(oldsha,state['payload_sha256'])
state['batch_command'] = 'bash -lc '+shlex.quote(state['job_command'])
(HERE/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'files':len(manifest),'sha256':state['payload_sha256'],'bytes':archive.stat().st_size}))
