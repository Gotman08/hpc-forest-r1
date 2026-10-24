from pathlib import Path
import json,shutil,uuid,time,hashlib,tarfile,re
R=Path(__file__).resolve().parent;old=R/'campaigns/deferred';a=R/'campaigns/deferred_r2';p=a/'payload'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False),encoding='utf8')
assert not (a/'adaptation.json').exists();shutil.copytree(old/'payload',p,dirs_exist_ok=True)
src=p/'source/src/candidate.cpp';original=src.read_text();short='\n'.join(line.lstrip(' \t') for line in original.split('\n'))
token=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\w+|[^\s]')
def tokens(s):return [x for x in token.findall(s) if not x.startswith(('//','/*'))]
assert tokens(original)==tokens(short)
assert len(short)<32000
src.write_text(short);session=uuid.uuid4().hex;remote='/scratch_p/nimarano/forest-reference-run-deferred_r2-'+session
plan=json.loads((p/'plan.json').read_text());oldroot=plan['remote_root'];plan.update(session_id=session,remote_root=remote,source_sha256=sha(src),created_at=time.time(),source_adaptation='Leading indentation removed only; full C++ token sequence unchanged. Prior attempt 781194 exceeded the unchanged 32000-character Mother source limit.')
cfg=json.loads((p/'settings.json').read_text());cfg['codex'].update(session_id=session,mailbox_dir=remote+'/pending/mailbox')
for name,data in [('plan.json',plan),('settings.json',cfg)]:write(p/name,data);write(a/name,data)
shutil.copyfile(p/'statement.txt',a/'statement.txt')
write(p/'runtime-manifest.json',{f.relative_to(p).as_posix():sha(f) for f in p.rglob('*') if f.is_file() and f.name!='runtime-manifest.json'})
with tarfile.open(a/'payload.tar.gz','w:gz') as t:
    for f in p.iterdir():t.add(f,arcname=f.name)
prep=json.loads((old/'preparation.json').read_text());oldsha=prep['payload_sha256'];prep.update(condition='deferred_r2',remote_root=remote,remote_payload=remote+'.tar.gz',remote_results=remote+'.results.tar.gz',artifact=str(a),session_id=session,payload_sha256=sha(a/'payload.tar.gz'));write(a/'preparation.json',prep)
(a/'command.sh').write_text((old/'command.sh').read_text().replace(oldroot,remote).replace(oldsha,prep['payload_sha256']))
write(a/'adaptation.json',{'original_characters':len(original),'new_characters':len(short),'tokens_unchanged':True,'previous_job':'781194','original_sha256':hashlib.sha256(original.encode()).hexdigest(),'new_sha256':sha(src)})
print(json.dumps(prep));print('characters',len(original),'to',len(short))
