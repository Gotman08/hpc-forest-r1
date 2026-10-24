"""Publish verified artifacts, excluding live sessions, secrets and executables."""
from pathlib import Path, PurePosixPath
import importlib.util
import json
import re
import subprocess
import tarfile

from prepare import R, ROOT, REPO, read

spec = importlib.util.spec_from_file_location('archive_policy', R/'publication_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
policy.DEST = REPO/'experiments/architecture-active-20261024'


def include(relative, data, origin):
    reason = policy.path_reason(relative) or policy.content_reason(data)
    if reason:
        policy.omitted(origin, reason, data)
    else:
        policy.write(relative, data, origin)


def copy_file(path, relative):
    if path.is_file():
        include(relative, path.read_bytes(), str(path))


def git(repo, *args):
    return subprocess.check_output(['git', '-c', 'core.fsmonitor=false', '-C', str(repo), *args])


def campaign(folder, prefix):
    for name in ['plan.json', 'settings.json', 'statement.txt', 'job.json', 'preparation.json',
                 'job-arguments.json', 'command.sh', 'slurm-plan.json', 'efficiency.json', 'result-transfer.json']:
        copy_file(folder/name, prefix+'/'+name)
    for sub in ['source', 'validation']:
        for path in sorted((folder/'payload'/sub).rglob('*')):
            if path.is_file():
                copy_file(path, prefix+'/input/'+sub+'/'+path.relative_to(folder/'payload'/sub).as_posix())
    copy_file(folder/'payload/runtime-manifest.json', prefix+'/runtime-manifest.json')
    # Extract only accounting and chain identities; private native sessions stay local.
    usages=[]
    for path in sorted((folder/'worker').glob('*/request.json')):
        if not path.with_name('generation-claimed.json').exists():
            continue
        request=read(path)
        response=read(path.with_name('response.json')) if path.with_name('response.json').exists() else {}
        usage=response.get('usage') or {}
        event_keys={'input_tokens','output_tokens','cached_input_tokens','reasoning_output_tokens','total_tokens'}
        counters=lambda events: [{k:v for k,v in event.items() if k in event_keys and type(v) is int}
                                 for event in events if isinstance(event,dict)]
        usages.append({'request_sha256':response.get('request_sha256'),
            'request_file_sha256':policy.digest(path.read_bytes()),
            'response_file_sha256':policy.digest(path.with_name('response.json').read_bytes()) if response else None,
            'model':request['model'],'effort':request['reasoning_effort'],
            'mission_id':request.get('mission_id'),'meta_role':request.get('meta_role'),
            'conversation':request.get('conversation'),
            'usage':{k:usage.get(k) for k in ['tokens','observed_tokens','token_accounting','accounting_scope','llm_calls','native_cumulative_tokens']},
            'events':counters(usage.get('events') or []),
            'native_cumulative_events':counters(usage.get('native_cumulative_events') or []),
            'error':response.get('error'),'response_available':bool(response)})
    include(prefix+'/usage-receipts.json',json.dumps(usages,ensure_ascii=False,indent=2).encode('utf8'),str(folder/'worker'))
    bundle = folder/'results.tar.gz'
    if not bundle.is_file():
        return
    policy.ARCHIVES.append({'source':str(bundle), 'bytes':bundle.stat().st_size,
                           'sha256':policy.digest(bundle.read_bytes()), 'extracted_to':prefix+'/evidence'})
    with tarfile.open(bundle) as archive:
        for member in archive:
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            if {'repo', 'worktrees', 'mailbox', 'deliverables'} & set(parts):
                policy.omitted(str(bundle)+'!'+member.name, 'runtime_copy_or_delivery_container', size=member.size)
                continue
            reason = policy.path_reason(member.name)
            if reason:
                policy.omitted(str(bundle)+'!'+member.name, reason, size=member.size)
                continue
            include(prefix+'/evidence/'+member.name, archive.extractfile(member).read(), str(bundle)+'!'+member.name)
    result_files = list(folder.glob('results/results-*/results.json'))
    if not result_files:
        return
    result = read(result_files[0])
    repo = result_files[0].parent/result['subject']/'repo'
    if not (repo/'.git').exists():
        return
    commits = set(git(repo, 'rev-list', '--all', '--reflog').decode().split())
    for trial in result.get('trials', []):
        outcome = json.loads(trial.get('result') or '{}')
        if outcome.get('commit'):
            commits.add(outcome['commit'])
    entries = []
    for commit in sorted(commits):
        assert re.fullmatch('[0-9a-f]{40}', commit), commit
        names = git(repo, 'ls-tree', '-r', '--name-only', commit, '--', 'src', 'Makefile', 'run.sh').decode().splitlines()
        for name in names:
            data = git(repo, 'show', commit+':'+name)
            include(prefix+'/sources/'+commit+'/'+name, data, str(repo)+'@'+commit+':'+name)
            entries.append({'commit':commit, 'path':name, 'sha256':policy.digest(data), 'bytes':len(data)})
    include(prefix+'/source-history.json', json.dumps(entries,indent=2).encode(), str(repo))


def main():
    outputs = ROOT/'outputs/architecture-active'
    summary = read(outputs/'RESULTATS.json')['summary']
    assert summary['new_finished'] == 21 and summary['measured_rows'] == 57, summary
    for path in sorted(outputs.iterdir()):
        if path.is_file():
            copy_file(path, path.name)
    for path in sorted(R.glob('*.py')):
        copy_file(path, 'reproduction/'+path.name)
    for path in sorted(R.glob('*.ps1')):
        copy_file(path, 'reproduction/'+path.name)
    # Preserve exactly the bytes executed on ROMEO, including line endings.
    engine = read(R/'engine-files.json')
    frozen = R/'campaigns/base64/payload/project/src'
    for name, digest in engine.items():
        source = frozen/name
        assert policy.digest(source.read_bytes()) == digest, name
        copy_file(source, 'moteur/src/'+name)
    for pattern in ['protocol.json', 'engine-files.json', 'campaigns.json', 'tests-*.xml',
                    'reviewed-queue*.json', 'queue-events.jsonl', 'queue-status.json', 'test-interruption.json',
                    'local-environment.json', 'main-selections.json', 'infrastructure-retries.json',
                    'campaign-audit.json', 'software-validation.json', 'dashboard-validation.json',
                    'runtime-library-fix.json', 'cuda-runtime-check-*', 'cuda-runtime-check.log',
                    'publication-preflight.json', 'workbook-validation.json', 'private-token-scan.json',
                    'volume-negative-control-validation.json', 'postprocessing-validation-notes.json',
                    'figure-validation.json', 'validation-finalization-*.log']:
        for path in R.glob(pattern):
            copy_file(path, 'validation/'+path.name)
    copy_file(R.parent/'active-architecture-v5-reprise-full-tests.log', 'validation/pytest.log')
    copy_file(R.parent/'active-architecture-20261024-v5/power-interruption.json', 'validation/power-interruption.json')
    copy_file(R.parent/'active-architecture-v5-full-tests.log', 'validation/pytest-interrompu-par-veille.log')
    copy_file(R/'broker/cleanup.json', 'validation/broker-cleanup.json')
    selections=read(R/'main-selections.json')
    for item in read(R/'campaigns.json'):
        selected=selections.get(item['case_id'])==item['condition']
        prefix=('campagnes/'+item['case_id'] if selected else 'tentatives-interrompues/'+R.name+'/'+item['condition'])
        campaign(R/'campaigns'/item['condition'], prefix)
    for version in ['active-architecture-20261024', 'active-architecture-20261024-v2', 'active-architecture-20261024-v3', 'active-architecture-20261024-v4', 'active-architecture-20261024-v5']:
        previous=R.parent/version
        for item in read(previous/'campaigns.json'):
            if (previous/'campaigns'/item['condition']/'job.json').exists():
                prefix=('pilotes/'+item['condition'] if item['smoke_only'] else 'tentatives-interrompues/'+version+'/'+item['condition'])
                campaign(previous/'campaigns'/item['condition'], prefix)
    for path in sorted(R.glob('paired-*')):
        if path.is_file():
            copy_file(path, 'mesures/'+path.name)
        elif path.is_dir():
            for entry in sorted(path.rglob('*')):
                if entry.is_file():
                    copy_file(entry, 'mesures/'+entry.relative_to(R).as_posix())
    paired_pilot = R.parent/'comparison-validation-20261024'
    for path in sorted(paired_pilot.iterdir()):
        if path.name == 'campaigns':
            continue  # Private duplicate campaign runtime; its original is archived above.
        if path.is_file():
            copy_file(path, 'validation/remesure-pilote/'+path.name)
        elif path.is_dir():
            for entry in sorted(path.rglob('*')):
                if entry.is_file():
                    copy_file(entry, 'validation/remesure-pilote/'+entry.relative_to(paired_pilot).as_posix())
    manifest = {'version':1, 'engine_commit':git(REPO, 'rev-parse', 'HEAD').decode().strip(),
                'files':sorted(policy.FILES.values(),key=lambda x:x['path']),
                'original_archives':policy.ARCHIVES, 'omitted':policy.OMITTED,
                'published_files':len(policy.FILES), 'published_bytes':sum(x['bytes'] for x in policy.FILES.values())}
    policy.DEST.mkdir(parents=True,exist_ok=True)
    (policy.DEST/'MANIFESTE-PUBLICATION.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    for item in manifest['files']:
        path=Path('\\\\?\\'+str((policy.DEST/item['path']).resolve()))
        assert policy.digest(path.read_bytes()) == item['sha256'], item['path']
    print(json.dumps({k:manifest[k] for k in ['engine_commit','published_files','published_bytes']}))


if __name__ == '__main__':
    main()
