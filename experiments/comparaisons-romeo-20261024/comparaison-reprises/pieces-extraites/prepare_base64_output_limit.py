"""Stage a new Base64 campaign; no prior candidates, documents or search state."""
import copy
import shutil
import tarfile
import time
import uuid

from prepare import R, REPO, read, write, sha

old=R/'campaigns/base64'
item=next(p for p in read(R/'campaigns.json') if p['case_id']=='base64')
stage=R/('staging-base64-output-limit-'+uuid.uuid4().hex)
new=stage/'base64';payload=new/'payload'
shutil.copytree(old/'payload',payload,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
engine={p.relative_to(REPO).as_posix():sha(p) for p in (REPO/'src').rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
changed=[]
for name,digest in engine.items():
    target=payload/'project'/name
    if sha(target)!=digest:
        changed.append(name)
        shutil.copyfile(REPO/name,target)
assert changed==['src/hpc_forest/codex_process.py'],changed
write(R/'engine-files-output-limit.json',engine)
session=uuid.uuid4().hex
remote='/scratch_p/nimarano/forest-reference-rerun-base64-'+session
scope='reference-rerun-luna-max-v3-base64'
cfg=read(payload/'settings.json');cfg['codex'].update(session_id=session,mailbox_dir=remote+'/pending/mailbox')
assert cfg['memory']['context_characters']==64000 and cfg['budget']['wall_seconds']==7200
plan=read(old/'plan.json');prior_remote=plan['remote_root']
plan.update(scope=scope,session_id=session,remote_root=remote,created_at=time.time(),
            engine_manifest_sha256=sha(R/'engine-files-output-limit.json'),
            early_termination_output_limit_job=read(old/'job.json')['job_id'],
            output_limit_classified_as_generation_failure=True)
for name,data in [('settings.json',cfg),('plan.json',plan)]:
    write(new/name,data);write(payload/name,data)
shutil.copyfile(old/'statement.txt',new/'statement.txt')
pilot=(payload/'pilot.py').read_text(encoding='utf8')
assert 'reference-rerun-luna-max-v2' in pilot
(payload/'pilot.py').write_text(pilot.replace('reference-rerun-luna-max-v2',scope),encoding='utf8',newline='\n')
for folder,key in [('source','source_files'),('validation','protected_files')]:
    actual={p.relative_to(payload/folder).as_posix():sha(p) for p in (payload/folder).rglob('*') if p.is_file()}
    assert actual==item[key],folder
write(payload/'runtime-manifest.json',{p.relative_to(payload).as_posix():sha(p)
      for p in payload.rglob('*') if p.is_file() and p.name!='runtime-manifest.json'})
with tarfile.open(new/'payload.tar.gz','w:gz') as archive:
    for p in sorted(payload.rglob('*')):
        if p.is_file():archive.add(p,arcname=p.relative_to(payload).as_posix())
prep=read(old/'preparation.json');old_hash=prep['payload_sha256']
prep.update(remote_root=remote,remote_payload=remote+'.tar.gz',remote_results=remote+'.results.tar.gz',
            artifact=str(R/'campaigns/base64'),session_id=session,payload_sha256=sha(new/'payload.tar.gz'))
write(new/'preparation.json',prep)
(new/'command.sh').write_text((old/'command.sh').read_text().replace(prior_remote,remote).replace(old_hash,prep['payload_sha256']),encoding='utf8',newline='\n')
record=copy.deepcopy(item)
record.update(remote_root=remote,session_id=session,payload_sha256=prep['payload_sha256'],
              early_termination_output_limit_job=plan['early_termination_output_limit_job'],
              output_limit_classified_as_generation_failure=True)
write(stage/'campaign.json',record)
write(R/'staged-base64-output-limit.json',{'path':str(stage),'scope':scope,'session_id':session,
      'remote_root':remote,'changed_engine_files':changed,'source_and_validation_identical':True})
print(str(stage))
