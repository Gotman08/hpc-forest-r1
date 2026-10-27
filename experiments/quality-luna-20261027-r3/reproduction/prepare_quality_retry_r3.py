"""Fresh paired pilot after fixing continuation of exhausted integrations."""
import json
import shutil

import prepare_quality_luna as preparation

preparation.STUDY = preparation.REPO / 'experiments/quality-luna-20261027-r3'
preparation.WORK = preparation.TASK / 'work/quality-luna-20261027-r3'
preparation.main()

for directory in (preparation.STUDY / 'reproduction', preparation.WORK / 'common'):
    preparation.change(directory / 'audit_control.py',
        'result = read(root / "arm-result.json")',
        'result = read(root / "arm-result.json", {}) or {}')

import finalize_quality_luna as finalization

finalization.main()
path = preparation.STUDY / 'pipeline-arguments.json'
arguments = preparation.read(path)
arguments['name'] = preparation.STUDY.name
preparation.atomic_json(path, arguments)
shutil.copyfile(__file__, preparation.STUDY / 'reproduction/prepare_quality_retry_r3.py')
print(json.dumps({'pipeline': str(path), 'supplements': 'quality-luna-20261027-r2',
                  'fresh_campaigns': True, 'no_candidate_or_model_guidance_imported': True}))
