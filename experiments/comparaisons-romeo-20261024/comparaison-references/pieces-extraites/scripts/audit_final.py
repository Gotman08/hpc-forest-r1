from pathlib import Path
import json,hashlib,csv,sys,collections,math
R=Path(__file__).resolve().parent;D=json.loads((R/'analysis.json').read_text(encoding='utf8'));O=Path(sys.argv[1]) if len(sys.argv)>1 else R/'report-preview';O.mkdir(parents=True,exist_ok=True)
assert D['summary']['pending']==0 and D['summary']['measured']==57 and D['summary']['unavailable']==5
assert len(D['rows'])==len({r['id'] for r in D['rows']})==62
assert len(D['engines'])==21 and len(D['attempts'])==22
expected={'cpu':7,'clang':7,'gpu':9,'extra':9,'render':3};checked=0
for r in D['rows']:
 if not r.get('case_id'):continue
 for name in ['baseline','reference','forest','final_g']:
  assert r[name]['count']==expected[r['group']],(r['id'],name,r[name]['count'])
  assert r[name]['seconds']>0
 assert math.isclose(r['forest_speedup'],r['baseline']['seconds']/r['forest']['seconds'],rel_tol=1e-12)
 assert math.isclose(r['reference_speedup'],r['baseline']['seconds']/r['reference']['seconds'],rel_tol=1e-12)
 assert math.isclose(r['forest_vs_reference'],r['reference']['seconds']/r['forest']['seconds'],rel_tol=1e-12)
 assert r['same_input_hashes'] is not False
 checked+=1
fail=D['summary']['final_failures']
utf8fail=[r for r in fail if r['case_id']=='utf8' and r['variant']=='naive' and r['diagnostic']]
volumefail=[r for r in fail if r['case_id']=='volume' and r['variant']=='optimized' and r['diagnostic'] and r['exit_code']==-6]
assert len(fail)==3 and len(utf8fail)==1 and len(volumefail)==2
va=D['volume_domain_audit'];assert va and len(va['records'])==14
assert all(r['measurement'].get('correct') is True for r in va['records'] if r['reference_supported_domain'])
assert all(r['measurement'].get('correct') is False for r in va['records'] if not r['reference_supported_domain'])
assert all(r['correct'] is True and r['exit_code']==0 for r in D['measurements'] if r['variant'] in ['selected','final_g'])
sources=[]
for folder in ['cpu-final','gpu-final','extra-final','render-final-aobench','render-final-volume','render-final-raytracer','render-final-deferred']:
 p=R/folder/'manifest.json'
 if not p.exists():continue
 manifest=json.loads(p.read_text())
 for m in manifest:
  if m.get('missing'):raise AssertionError(m)
  source=R/folder/m['case_id']/m['variant']/('candidate'+m.get('suffix','.cu'))
  assert source.exists(),source
  assert hashlib.sha256(source.read_bytes()).hexdigest()==m['sha256'];sources.append(str(source.relative_to(R)))
assert len(sources)==42
audit={'status':'comparison_audit_passed_with_documented_reference_failures','documentary_observations':62,'remeasured_observations':checked,'unavailable':5,'engine_families':21,'engine_attempts_including_failed_import':22,'final_measurement_and_diagnostic_records':len(D['measurements']),'candidate_failures':0,'unexpected_reference_failures':0,'expected_historical_utf8_failure':utf8fail,'volume_reference_outside_precondition':volumefail,'volume_supported_domain_checks':10,'volume_guard_checks_outside_domain':4,'source_files_sha256_verified':sources,'expected_blocks_by_group':expected,'input_hashes_equal_where_available':True,'statistical_scope':'Ratios of medians; UTF8 BEST/MEAN exceptions. Observed ranges are not confidence intervals. One Forest campaign per family, technical deferred reimport excepted.','generated_at':D['summary']['generated_at']}
(O/'AUDIT-FINAL.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({k:v for k,v in audit.items() if k not in ['source_files_sha256_verified','expected_historical_utf8_failure']},ensure_ascii=False))
