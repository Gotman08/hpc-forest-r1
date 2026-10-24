"""Replay the recorded terminal status locally, without a new model invocation."""
import json
import sys
from unittest.mock import patch

from prepare import R, REPO, read, write, sha

sys.path.insert(0,str(REPO/'src'))
from hpc_forest import codex_process  # noqa: E402
from hpc_forest.core import ProcessResult  # noqa: E402

source=R/'campaigns/base64/worker/7163005badca4b1ba7a89754d1e72515'
old=read(source/'response.json');request=read(source/'request.json')
assert old['infrastructure_error'] is True
dest=R/'output-limit-replay';dest.mkdir(exist_ok=False)

def command(*args,**kwargs):
    (dest/'instructions.txt').write_text(request['messages'][0]['content'],encoding='utf8')
    return ['recorded-status-only']

class Documentation:
    def receipt(self):return {'offline_replay':True}

with patch.object(codex_process,'command_for',command),patch.object(codex_process,'run_process',
        return_value=ProcessResult(['recorded-status-only'],1,0,False,str(source/'codex.jsonl'))):
    result=codex_process._invoke(request,old['request_sha256'],dest,'unused',None,True,
                                documentation_mcp=Documentation())
assert result['infrastructure_error'] is False and result['data'] is None
assert 'model output limit' in result['error']
assert result['usage']['token_accounting']=='unknown' and result['usage']['tokens'] is None
report={'job':'781305','recorded_nonce':request['nonce'],'native_log_sha256':sha(source/'codex.jsonl'),
        'historical_response_sha256':sha(source/'response.json'),'historical_outcome_unchanged':True,
        'offline_replay':True,'new_model_call':False,'corrected_classification':'generation_failure',
        'partial_source_accepted':False,'token_accounting':'unknown',
        'diagnostic':result['error'],'terminal_messages':result['usage']['turn_failure_messages']}
write(R/'output-limit-regression.json',report)
write(R.parents[1]/'outputs/comparaison-reprises/VALIDATION-LIMITE-SORTIE.json',report)
print(json.dumps(report))
