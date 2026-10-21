"""Verify the exact pre-existing Git archive; never rewrite measured code or raw results."""
import hashlib
import json
import time
import zipfile
from pathlib import Path

from local_status import HERE,STATE,read

result = read(HERE/'evidence/results.json')
audit = read(HERE/'audit.json')
source = read(HERE/'G-final-source-receipt.json')
path = HERE/'evidence/confirmed-sources.zip'
original_results_sha = hashlib.sha256((HERE/'evidence/results.json').read_bytes()).hexdigest()
with zipfile.ZipFile(path) as archive:
    assert archive.testzip() is None
    manifest = json.loads(archive.read('HPC_FOREST_MANIFEST.json'))
    names = set(archive.namelist())
    assert manifest['commit'] == result['best_confirmed']['commit']
    assert manifest['final_g_confirmation'] == result['final_g_confirmation']
    assert manifest['confirmation']['commit'] == manifest['commit']
    assert manifest['confirmation']['correct'] is True
    assert len(manifest['confirmation']['times']) == 5
    assert result['final_g_confirmation']['status'] == 'confirmed'
    assert manifest['commit'] == result['final_g_confirmation']['outcome']['commit']
    assert source['all_proposed_sources_match_actual_final_g_worktree'] is True
    entries = []
    for entry in source['files']:
        name = entry['path']
        assert name in names
        actual = hashlib.sha256(archive.read(name)).hexdigest()
        assert actual == entry['actual_sha256'] == entry['proposed_sha256']
        entries.append({'path':name,'sha256':actual,'matches_native_and_measured_source':True})
assert hashlib.sha256((HERE/'evidence/results.json').read_bytes()).hexdigest() == original_results_sha
receipt = {'job_id':STATE['job_id'],'at':time.time(),
    'recovery':'verified copy of exact archive already created before runner validation failed',
    'source_remote':STATE['remote_root']+'/results-'+STATE['job_id']+'/cuda-nbody/submission.zip.tmp',
    'local_archive':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
    'raw_controller_pipeline_complete':result['pipeline_complete'],
    'raw_controller_error':result['error'],'raw_results_sha256_preserved':original_results_sha,
    'actual_g_final_confirmed':True,'five_fresh_confirmation_samples':True,
    'confirmed_commit':manifest['commit'],'source_files':entries,
    'native_proposal_measured_worktree_and_archive_match':True,
    'model_calls_added':0,'hpc_jobs_added':0,'candidate_code_changed':False,
    'makefile_and_run_sh_present':{'Makefile','run.sh'}.issubset(names),
    'standalone_application_launcher_added':False,'source_export_verified':True}
(HERE/'export-recovery.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
print(json.dumps(receipt))
