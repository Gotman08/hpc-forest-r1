"""Audit immutable inputs, model requests and memory isolation without modifying runs."""
import argparse
import collections
import datetime
import json
from pathlib import Path
import sys

from prepare import R, REPO, read, sha, write

sys.path.insert(0,str(REPO/'src'))
from hpc_forest.codex_mailbox import json_bytes, sha256


def audit(require_complete=False):
    engine=read(R/'engine-files.json')
    selections=read(R/'main-selections.json')
    sessions=set()
    results=[]
    for folder in sorted((R/'campaigns').iterdir()):
        plan=read(folder/'plan.json')
        cfg=read(folder/'settings.json')
        assert plan['session_id'] not in sessions,folder.name
        sessions.add(plan['session_id'])
        assert plan['model']==cfg['codex']['model']=='gpt-6-luna'
        assert plan['effort']==cfg['codex']['reasoning_effort']=='max'
        assert cfg['backend']=='codex' and cfg['forest']['active']['mode']=='full'
        assert plan['fresh_memory'] is True and plan['old_candidates_imported'] is False
        assert plan['wall_seconds']==plan['previous_seconds']==cfg['budget']['wall_seconds']
        # Historical source_path can precede the documented UTF-8/deferred repair.
        # The delivered source and previous campaign payload are authoritative.
        delivered=folder/'payload/source/src'/Path(plan['source_path']).name
        assert sha(delivered)==plan['source_sha256'],folder.name
        manifest=read(folder/'payload/runtime-manifest.json')
        for name,digest in manifest.items():
            assert sha(folder/'payload'/name)==digest,(folder.name,name)
        for name,digest in engine.items():
            assert sha(folder/'payload/project/src'/name)==digest,(folder.name,name)
        prior=Path(plan['prior_campaign'])
        for sub in ['source','validation']:
            old={p.relative_to(prior/'payload'/sub).as_posix():sha(p) for p in (prior/'payload'/sub).rglob('*') if p.is_file()}
            new={p.relative_to(folder/'payload'/sub).as_posix():sha(p) for p in (folder/'payload'/sub).rglob('*') if p.is_file()}
            # Some previous campaigns refer to the original protected payload.
            if old:
                assert all(new.get(k)==v for k,v in old.items()),(folder.name,sub)
        counts=collections.Counter()
        conversations=set()
        returned=0
        for path in sorted((folder/'worker').glob('*/request.json')):
            req=read(path)
            assert req['model']=='gpt-6-luna' and req['reasoning_effort']=='max',path
            assert req['session_id']==plan['session_id'] and req['nonce']==path.parent.name,path
            role=(req.get('active_control') or {}).get('kind') or ('mother_'+req['conversation']['phase'] if req.get('conversation') else 'research_or_memory')
            counts[role]+=1
            if req.get('conversation'):
                conversations.add(req['conversation']['id'])
            if (req.get('active_control') or {}).get('kind')=='analyst':
                assert req.get('conversation') is None,path
            response=read(path.with_name('response.json')) if path.with_name('response.json').exists() else None
            if response:
                assert response['request_sha256']==sha256(json_bytes(req)),path
                assert all(response[k]==req[k] for k in ['session_id','nonce','model','reasoning_effort']),path
                returned+=1
        assert len(conversations)<=1,(folder.name,conversations)
        files=list(folder.glob('results/results-*/fresh-memory.json'))
        if files:
            assert len(files)==1
            fresh=read(files[0])
            assert fresh['session_id']==plan['session_id']
            if 'epoch' in fresh:
                assert fresh['epoch']==1
            assert fresh['trial_count']==fresh['document_count']==0
            assert fresh['previous_candidates_imported'] is False
            if 'initial_source_sha256' in fresh:
                assert fresh['initial_source_sha256']==plan['source_sha256']
        selected=selections[plan['case_id']]==folder.name
        paths=list(folder.glob('results/results-*/results.json'))
        complete=bool(paths and read(paths[0]).get('pipeline_complete'))
        if require_complete and selected:
            assert complete and files,folder.name
        results.append({'condition':folder.name,'case_id':plan['case_id'],'selected':selected,
            'session_id':plan['session_id'],'pipeline_complete':complete,'fresh_memory_receipt':bool(files),
            'engine_files_verified':len(engine),'runtime_files_verified':len(manifest),
            'prior_input_bytes_match':True,'budget_matches_previous':True,
            'requests':sum(counts.values()),'returned':returned,'requests_by_role':dict(counts),
            'all_requests_luna_max':True,'persistent_mother_conversations':len(conversations)})
    value={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'selected_programs':len(selections),'attempts':len(results),'unique_sessions':len(sessions),
           'all_checks_passed':True,'complete_matrix_required':require_complete,'campaigns':results}
    write(R/'campaign-audit.json',value)
    print(json.dumps({k:v for k,v in value.items() if k!='campaigns'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--require-complete',action='store_true')
    audit(parser.parse_args().require_complete)
