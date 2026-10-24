"""Record a fresh attempt after the first native model-run failure of Stencil Y."""
from launch_support import R, read, write, sha

key = 'stencil_y_retry2'
directory = R / 'campaigns' / key
review = read(R / 'reviewed-queue.json')
assert key not in review['campaigns']
write(R / 'reviewed-queue-retry5.json', review)
review['pending_order'].insert(0, key)
review['campaigns'][key] = {name: sha(directory / name) for name in
    ['payload.tar.gz', 'plan.json', 'slurm-plan.json', 'job-arguments.json']}
review['authorization'] = 'All CSV cases authorized by the user. Exact plans reviewed. One fresh native retry for Stencil Y after its first actual model-run failure; earlier failure occurred before any model call because of a missing CUDA runtime path. Frozen engine, inputs, checker and nominal budget; first complete attempt retained regardless of speedup.'
write(R / 'reviewed-queue.json', review)
selections = read(R / 'main-selections.json')
assert selections['stencil_y'] == 'stencil_y_retry1'
selections['stencil_y'] = key
write(R / 'main-selections.json', selections)
retries = read(R / 'infrastructure-retries.json')
assert not any(r['retry_condition'] == key for r in retries)
retries.append({'case_id': 'stencil_y', 'failed_condition': 'stencil_y_retry1',
    'failed_job': '783180', 'retry_condition': key,
    'reason': 'Native Mother returned max_output_tokens without a completed-turn receipt. The controller stopped rather than replacing or replaying her conversation. One fresh retry after the first actual model-run failure; original attempt failed before all model calls because of the missing CUDA runtime path.',
    'selection_rule': 'First complete campaign, never choose an attempt based on speedup. Failed attempt and usage remain in the report.',
    'reuse_candidates': False, 'engine_changed': False, 'protected_protocol_changed': False,
    'budget_seconds_each_attempt': 1800, 'model': 'gpt-6-luna', 'effort': 'max'})
write(R / 'infrastructure-retries.json', retries)
print('Registered Stencil Y retry with fresh memory; 29 total attempts for 21 programs.')
