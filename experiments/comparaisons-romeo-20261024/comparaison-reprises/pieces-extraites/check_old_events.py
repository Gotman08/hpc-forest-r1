from pathlib import Path
import json
import sys

R = Path(__file__).resolve().parent
sys.path.insert(0, str(R/'campaigns/base64/payload/project/src'))
from hpc_forest.codex_process import usage_from_events

cases = {
    'aobench': ['cb95413fe3d04d64b98589101c189a77'],
    'base64': ['47d1f02866064ff0b2d3573aea40221a', '9f20779fca734deeba11255590a311de'],
    'deferred_r2': ['aea8e7f02f5d4ad2bbe8b5d76a0cd1ab', 'eb3fc0073d234e6db0408c9ea7238cb0',
                    'f44c6487849d45dd81fa0e8bcab39ac2'],
    'raytracer': ['1284c0d991664334bab70ac0f6e66569'],
}
rows = []
for key, nonces in cases.items():
    for nonce in nonces:
        log = R.parent/'reference-study/campaigns'/key/'worker'/nonce/'codex.jsonl'
        usage, forbidden = usage_from_events(log, allow_documentation=True, observe_only=True)
        assert not forbidden, (key, nonce, usage['forbidden_tool_events'])
        rows.append({'case': key, 'nonce': nonce, 'old_event_log_sha256': usage['codex_jsonl_sha256'],
                     'would_reject_after_fix': forbidden, 'mcp_calls': usage['mcp_tool_calls']})
(R/'historical-event-regression.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
print('All seven historical discovery-only failures are correctly classified; old outcomes unchanged.')
