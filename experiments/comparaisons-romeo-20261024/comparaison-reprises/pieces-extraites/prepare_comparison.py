"""Export confirmed commits only; keep previous sources out of search payloads."""
import json
import re
import shutil
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path

from prepare import R, OLD, read, write, sha

group = sys.argv[1]
single = sys.argv[2] if len(sys.argv) > 2 else None
groups = {'cpu': ['base64', 'blackscholes', 'gemm_cpu', 'mandelbrot', 'stencil3d', 'utf8'],
          'extra': ['reduction', 's4convd', 'softmax', 'sumabs'],
          'render': ['aobench', 'deferred', 'raytracer', 'volume']}
keys = groups[group]
if single:
    if group == 'cpu' and single == 'without-base64':
        keys = [key for key in keys if key != 'base64']
        single = None
    else:
        assert single in keys
        keys = [single]
stem = 'paired-'+group+('-'+single if single else '')
dest = R/stem
dest.mkdir(exist_ok=False)
manifest = []
for key in keys:
    for period, root in [('old', OLD/'campaigns'/('deferred_r2' if key == 'deferred' else key)),
                         ('new', R/'campaigns'/key)]:
        if not (root/'results').exists():
            with tarfile.open(root/'results.tar.gz') as archive:
                archive.extractall(root/'results', filter='data')
        result_file = next(root.glob('results/results-*/results.json'))
        result = read(result_file)
        assert result.get('best_confirmed'), (key, period, result.get('error'))
        repo = result_file.parent/('reference-'+key)/'repo'
        selected = result['best_confirmed']
        final = (result.get('final_g_confirmation') or {}).get('outcome') or {}
        suffix = '.py' if key == 'softmax' else '.cu' if group == 'extra' else '.cpp'
        for variant, ev in [('selected', selected), ('g', final)]:
            if variant == 'g' and (result.get('final_g_confirmation') or {}).get('status') != 'confirmed':
                manifest.append({'case_id': key, 'variant': period+'_g', 'missing': True,
                                 'reason': 'Final G was not independently confirmed',
                                 'engine_job': result['job_id']})
                continue
            commit = ev['commit']
            assert re.fullmatch('[0-9a-f]{40}', commit)
            target = dest/key/(period+'_'+variant)
            target.mkdir(parents=True)
            source = subprocess.check_output(['git', '-C', str(repo), 'show', commit+':src/candidate'+suffix])
            file = target/('candidate'+suffix)
            file.write_bytes(source)
            manifest.append({'case_id': key, 'variant': period+'_'+variant, 'commit': commit,
                             'sha256': sha(file), 'engine_job': result['job_id'], 'suffix': suffix,
                             'reported_seconds': ev.get('mean_seconds'),
                             'confirmed_correct': True})
    # Frozen validation manifests make changes to the shared reference suite fatal.
    shutil.copyfile(R/'campaigns'/key/'payload/validation/case.json', dest/key/'protected.json')

script = (OLD/(group+'_final_compare.py')).read_text()
suite_name = {'cpu': 'cpu-suite', 'extra': 'gpu-extra', 'render': 'render-suite'}[group]
frozen_suite = {name.removeprefix(suite_name+'/'): entry['sha256']
                for name, entry in read(OLD/'protected-suites/MANIFEST.json').items()
                if name.startswith(suite_name+'/')}
assert frozen_suite
write(dest/'suite-snapshot.json', frozen_suite)
script = script.replace("['selected','final_g']", "['old_selected','new_selected','old_g','new_g']")
if group in {'cpu', 'extra'}:
    script = script.replace('rows=[]', "rows=[]\ncases=[c for c in cases if c['id'] in {m['case_id'] for m in manifest}]")
script = script.replace('for m in manifest:', '''for name, expected in json.loads((R/'suite-snapshot.json').read_text()).items():
    assert hashlib.sha256((S/name).read_bytes()).hexdigest()==expected, ('frozen suite',name)
for key in {m['case_id'] for m in manifest}:
    protected=json.loads((R/key/'protected.json').read_text())
    for name,expected in protected.get('trusted_files',protected.get('trusted_binaries',{})).items():
        assert hashlib.sha256((Path(protected['suite'])/name).read_bytes()).hexdigest()==expected, (key,name)
for m in manifest:''', 1)
environment_write="(out/'environment.json').write_text(json.dumps(env,indent=2))"
assert environment_write in script
script=script.replace(environment_write,
    "env['candidate_artifact_sha256']={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*/*/candidate.*') if p.is_file()}\n"+environment_write)
(dest/'compare.py').write_text(script, encoding='utf8', newline='\n')
if group == 'render':
    shutil.copyfile(OLD/'render-final/render_final_driver.cpp', dest/'render_final_driver.cpp')
if group == 'cpu' and 'utf8' in keys:
    audit = (OLD/'utf8_audit.py').read_text()
    start = audit.index('S=Path(')
    end = audit.index('\ntests=', start)
    audit = audit[:start]+'''S=Path('/scratch_p/nimarano/forest-reference-cpu-suite-20261023')
F=Path(__file__).resolve().parent
R=F/('measurements-'+os.environ['SLURM_JOB_ID'])
paths={'historical':S/'cases/utf8/naive.so','repaired':S/'cases/utf8/repaired.so','reference_avx':S/'cases/utf8/optimized.so'}
paths.update({v:F/'utf8'/v/'candidate.so' for v in ['old_selected','new_selected','old_g','new_g'] if (F/'utf8'/v/'candidate.so').exists()})
'''+audit[end:]
    original = "src=ct.create_string_buffer(data+bytes([0xa7])*64);out=(ct.c_uint32*3)(0xa7a7a7a7,0xdeadbeef,0xa7a7a7a7);f(src,None,ct.byref(out,4),len(data),0,1)"
    # The declared ABI guarantees 64-byte input alignment. Keep all 79,729
    # historical test strings and add guards while honoring that guarantee.
    replacement = """storage=ct.create_string_buffer(len(data)+192);address=(ct.addressof(storage)+127)&~63
        ct.memset(address-64,0xa7,len(data)+128);ct.memmove(address,data,len(data))
        output=ct.create_string_buffer(256);outaddr=(ct.addressof(output)+127)&~63;ct.memset(outaddr-64,0xa7,132)
        f(address,None,outaddr,len(data),0,1);actual=ct.c_uint32.from_address(outaddr).value"""
    assert original in audit
    audit = audit.replace(original, replacement)
    audit = audit.replace("ok=out[1]==want and out[0]==out[2]==0xa7a7a7a7 and src.raw[:-1]==data+bytes([0xa7])*64", "ok=actual==want and ct.string_at(outaddr-64,64)==bytes([0xa7])*64 and ct.string_at(outaddr+4,64)==bytes([0xa7])*64 and ct.string_at(address-64,len(data)+128)==bytes([0xa7])*64+data+bytes([0xa7])*64")
    audit = audit.replace("'actual':out[1]", "'actual':actual")
    audit = audit.replace("(R/('audit-'+os.environ['SLURM_JOB_ID']+'.json'))", "(R/'utf8-audit.json')")
    (dest/'utf8_audit.py').write_text(audit, encoding='utf8', newline='\n')
write(dest/'manifest.json', manifest)
with tarfile.open(R/(stem+'.tar.gz'), 'w:gz') as archive:
    for file in dest.rglob('*'):
        if file.is_file():
            archive.add(file, arcname=file.relative_to(dest).as_posix())
write(R/(stem+'-transfer.json'), {'group': group, 'keys': keys, 'artifact': str(R/(stem+'.tar.gz')),
       'remote': '/scratch_p/nimarano/forest-reference-'+stem+'-'+uuid.uuid4().hex,
       'sha256': sha(R/(stem+'.tar.gz'))})
print(stem, len(manifest), 'confirmed source exports')
