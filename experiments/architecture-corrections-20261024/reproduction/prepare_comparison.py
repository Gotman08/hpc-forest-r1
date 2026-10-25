"""Export immutable confirmed programs, then pair old/new/reference in one job."""
import argparse
import json
import os
import re
import shutil
import subprocess
import tarfile
import uuid
from pathlib import Path

from prepare import R, OLD, LATEST, GPU_INITIAL, GPU_EXTRA, RENDER, read, write, sha
PREVIOUS = R.parent / "active-architecture-20261024-v5-reprise"


def selected_result(artifact):
    if not (artifact/'results').exists():
        with tarfile.open(artifact/'results.tar.gz') as archive:
            target = str((artifact/'results').resolve())
            if os.name == 'nt':
                target = '\\\\?\\' + target
            archive.extractall(target, members=(m.replace(name=str(Path(m.name))) for m in archive.getmembers()), filter='data')
    files = list(artifact.glob('results/results-*/results.json'))
    assert len(files) == 1, files
    result = read(files[0])
    assert result.get('best_confirmed'), (artifact.name, result.get('error'))
    return files[0], result


def prepare(keys, label=None, clang=False):
    if clang:
        assert keys == ['popcount']
        label = label or 'clang-popcount'
    types = {'gpu' if key in GPU_INITIAL else 'extra' if key in GPU_EXTRA else 'render' if key in RENDER else 'cpu' for key in keys}
    assert len(types) == 1, 'Each comparison job has one architecture and one protected timing driver'
    group = types.pop()
    stem = 'paired-'+(label or group+'-'+('-'.join(keys)))
    dest = R/stem
    dest.mkdir(exist_ok=False)
    manifest = []
    selections = read(R/'main-selections.json') if (R/'main-selections.json').exists() else {}
    for key in keys:
        prior = LATEST/'campaigns'/key
        if not prior.exists():
            prior = OLD/'campaigns'/key
        selected_artifact = R/'campaigns'/selections.get(key,key)
        previous_selection = read(PREVIOUS/'main-selections.json').get(key, key)
        previous_artifact = PREVIOUS/'campaigns'/previous_selection
        for period, artifact in [('old', prior), ('previous', previous_artifact), ('new', selected_artifact)]:
            result_file, result = selected_result(artifact)
            repo = result_file.parent/('reference-'+key)/'repo'
            selected = result['best_confirmed']
            final = result.get('final_g_confirmation') or {}
            suffix = '.py' if key == 'softmax' else '.cu' if group in {'gpu','extra'} else '.cpp'
            for variant, outcome in [('selected', selected), ('g', final.get('outcome') or {})]:
                if variant == 'g' and final.get('status') != 'confirmed':
                    manifest.append({'case_id':key, 'variant':period+'_g', 'missing':True,
                        'reason':'Final G did not independently pass confirmation', 'engine_job':result['job_id']})
                    continue
                commit = outcome['commit']
                assert re.fullmatch('[0-9a-f]{40}', commit)
                target = dest/key/(period+'_'+variant)
                target.mkdir(parents=True)
                source = subprocess.check_output(['git','-C',str(repo),'show',commit+':src/candidate'+suffix])
                file = target/('candidate'+suffix)
                file.write_bytes(source)
                manifest.append({'case_id':key,'variant':period+'_'+variant,'commit':commit,'sha256':sha(file),
                    'engine_job':result['job_id'],'suffix':suffix,'confirmed_correct':True,
                    'reported_seconds':outcome.get('mean_seconds')})
        audit_candidates=R/'retrospective-audit-candidates.json'
        for diagnostic in (read(audit_candidates).get(key,[]) if audit_candidates.exists() else []):
            assert diagnostic['artifact']==selected_artifact.name
            assert re.fullmatch('[a-z0-9_]+',diagnostic['variant'])
            result_file,result=selected_result(selected_artifact)
            trial=next(t for t in result['trials'] if t['id']==diagnostic['trial_id'])
            outcome=json.loads(trial['result'])
            commit=outcome['commit']
            assert re.fullmatch('[0-9a-f]{40}',commit)
            target=dest/key/diagnostic['variant']
            target.mkdir(parents=True)
            source=subprocess.check_output(['git','-C',str(result_file.parent/('reference-'+key)/'repo'),
                'show',commit+':src/candidate.cpp'])
            file=target/'candidate.cpp'
            file.write_bytes(source)
            assert sha(file)==diagnostic['sha256']
            manifest.append({**diagnostic,'case_id':key,'commit':commit,'engine_job':result['job_id'],
                'suffix':'.cpp','audit_only':True,'campaign_protocol_correct':outcome.get('correct')})
        shutil.copyfile(selected_artifact/'payload/validation/case.json', dest/key/'protected.json')
    suite_name = {'cpu':'cpu-suite','gpu':'gpu-suite','extra':'gpu-extra','render':'render-suite'}[group]
    frozen = {name.removeprefix(suite_name+'/'): entry['sha256']
              for name,entry in read(OLD/'protected-suites/MANIFEST.json').items() if name.startswith(suite_name+'/')}
    assert frozen
    write(dest/'suite-snapshot.json', frozen)
    script = (OLD/(group+'_final_compare.py')).read_text(encoding='utf8')
    script = script.replace("['selected','final_g']", "['old_selected','previous_selected','new_selected','old_g','previous_g','new_g']")
    if group == 'gpu':
        script = script.replace('for m in manifest:\n', "for m in manifest:\n    if m.get('missing'):continue\n", 1)
        script = script.replace("for v in ['old_selected','previous_selected','new_selected','old_g','previous_g','new_g']:order.append((c,v,str(R/c['id']/v/'candidate.so'),1))",
            "for v in ['old_selected','previous_selected','new_selected','old_g','previous_g','new_g']:\n        if (R/c['id']/v/'candidate.so').exists():order.append((c,v,str(R/c['id']/v/'candidate.so'),1))")
        script = script.replace("cases=json.loads((S/'cases.json').read_text());order=[]",
            "cases=[c for c in json.loads((S/'cases.json').read_text()) if c['id'] in {m['case_id'] for m in manifest}];order=[]")
    elif group != 'render':
        script = script.replace('rows=[]', "rows=[]\ncases=[c for c in cases if c['id'] in {m['case_id'] for m in manifest}]")
    guard = '''for name, expected in json.loads((R/'suite-snapshot.json').read_text()).items():
    assert hashlib.sha256((S/name).read_bytes()).hexdigest()==expected, ('frozen suite',name)
for key in {m['case_id'] for m in manifest}:
    protected=json.loads((R/key/'protected.json').read_text())
    for name,expected in protected.get('trusted_files',protected.get('trusted_binaries',{})).items():
        assert hashlib.sha256((Path(protected['suite'])/name).read_bytes()).hexdigest()==expected, (key,name)
for m in manifest:'''
    script = script.replace('for m in manifest:', guard, 1)
    if group != 'gpu':
        needle = "(out/'environment.json').write_text(json.dumps(env,indent=2))"
        assert needle in script
        script = script.replace(needle,
            "env['candidate_artifact_sha256']={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in R.glob('*/*/candidate.*') if p.is_file()}\n"+needle)
    if group == 'render':
        # Seven alternating blocks for both old and new sources in this allocation.
        script = script.replace('range(3)', 'range(7)')
        shutil.copyfile(OLD/'render-final/render_final_driver.cpp', dest/'render_final_driver.cpp')
        if 'volume' in keys:
            audit = (OLD/'volume_domain_audit.py').read_text(encoding='utf8')
            start = audit.index('R=Path(')
            end = audit.index('\nsource=', start)
            audit = audit[:start]+"F=Path(__file__).resolve().parent;S=Path('/scratch_p/nimarano/forest-reference-render-20261023');R=F/('measurements-'+os.environ['SLURM_JOB_ID'])/'volume-domain';R.mkdir()"+audit[end:]
            audit = audit.replace("('selected',F/'volume/selected/candidate.so'),('final_g',F/'volume/final_g/candidate.so')",
                "*[(v,F/'volume'/v/'candidate.so') for v in ['old_selected','previous_selected','new_selected','old_g','previous_g','new_g'] if (F/'volume'/v/'candidate.so').exists()]")
            (dest/'volume_domain_audit.py').write_text(audit,encoding='utf8',newline='\n')
            compile(audit,str(dest/'volume_domain_audit.py'),'exec')
    if group == 'cpu' and 'utf8' in keys:
        # Retain the already audited alignment-correct exhaustive string audit.
        audit = (LATEST/'paired-cpu/utf8_audit.py').read_text(encoding='utf8')
        audit = audit.replace("['old_selected','new_selected','old_g','new_g']", "['old_selected','previous_selected','new_selected','old_g','previous_g','new_g']")
        audit = audit.replace('tests=[bytes([x])',
            "paths.update({m['variant']:F/'utf8'/m['variant']/'candidate.so' for m in json.loads((F/'manifest.json').read_text()) if m.get('audit_only') and m['case_id']=='utf8'})\n\ntests=[bytes([x])")
        (dest/'utf8_audit.py').write_text(audit, encoding='utf8', newline='\n')
        # A separate diagnostic corpus, never a change to the frozen campaign
        # validator or timed inputs. Cover two 64-byte blocks and truncated tails.
        assert 'range(35)' in audit
        boundary="for cut in range(len(x)+1):tests.append(b'a'*offset+x[:cut]+b'a'*7)"
        assert boundary in audit
        extended=audit.replace('range(35)','range(133)').replace(boundary,
            "for cut in range(len(x)+1):\n            for suffix in [0,7,64]:tests.append(b'a'*offset+x[:cut]+b'a'*suffix)")
        extended=extended.replace('utf8-audit.json','utf8-extended-audit.json').replace(
            'restricted leads at SIMD boundaries',
            'restricted leads at offsets 0..132, empty/7/64-byte suffixes and truncated sequences')
        compile(extended,str(dest/'utf8_extended_audit.py'),'exec')
        (dest/'utf8_extended_audit.py').write_text(extended,encoding='utf8',newline='\n')
    if clang:
        script = (R/'clang_compare.py').read_text(encoding='utf8')
    if group == 'cpu' and not clang:
        shutil.copyfile(R/'binary_audit.py', dest/'binary_audit.py')
    (dest/'compare.py').write_text(script, encoding='utf8', newline='\n')
    compile(script, str(dest/'compare.py'), 'exec')
    write(dest/'manifest.json', manifest)
    with tarfile.open(R/(stem+'.tar.gz'), 'w:gz') as archive:
        for file in dest.rglob('*'):
            if file.is_file():
                archive.add(file, arcname=file.relative_to(dest).as_posix())
    remote = '/scratch_p/nimarano/forest-active-'+stem+'-'+uuid.uuid4().hex
    digest = sha(R/(stem+'.tar.gz'))
    write(R/(stem+'-transfer.json'), {'group':'clang' if clang else group,'keys':keys,'artifact':str(R/(stem+'.tar.gz')),
        'remote':remote,'sha256':digest})
    gpu = group in {'gpu','extra'}
    required_threads = max(int(row.get('threads') or 1) for row in read(OLD/'analysis.json')['rows'] if row.get('case_id') in keys)
    python = '/scratch_p/nimarano/forest-reference-torch-20261023/bin/python' if gpu else '/scratch_p/nimarano/forest-reference-study-20261023-x64env/bin/python'
    lines = ['root='+remote, 'test ! -e "$root"', "echo '"+digest+'  '+remote+".tar.gz' | sha256sum -c -",
             'mkdir "$root"', 'tar -xzf "$root.tar.gz" -C "$root"', 'cd "$root"',
             'export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1', 'set +e', python+' -u compare.py', 'rc=$?']
    if group == 'gpu':
        setup = ['FOREST_CUDA_PREFIX=$(spack location -i /uxlsycgnldislqswr4gcj6hlc6u2pdxp)',
                 'test -f "$FOREST_CUDA_PREFIX/lib64/libcublas.so.12"',
                 'export LD_LIBRARY_PATH="$FOREST_CUDA_PREFIX/lib64:${LD_LIBRARY_PATH:-}"',
                 'sha256sum "$FOREST_CUDA_PREFIX/lib64/libcublas.so.12" > allocation-cublas.txt']
        lines[lines.index('set +e'):lines.index('set +e')] = setup
    if clang:
        setup = ['llvm_root=$(spack location -i /hdlzlaza4paizierl2rau5s325x73mm4)',
                 'export LD_LIBRARY_PATH="$llvm_root/lib:$llvm_root/lib64:$llvm_root/lib/x86_64-unknown-linux-gnu:${LD_LIBRARY_PATH:-}"',
                 'export OMP_NUM_THREADS=1']
        lines[lines.index('set +e'):lines.index('set +e')] = setup
    if group == 'cpu' and 'utf8' in keys:
        lines += ['if [ "$rc" -eq 0 ]; then', '  '+python+' -u utf8_audit.py', '  rc=$?', 'fi']
        lines += ['if [ "$rc" -eq 0 ]; then', '  '+python+' -u utf8_extended_audit.py', '  rc=$?', 'fi']
    if group == 'render' and 'volume' in keys:
        lines += ['if [ "$rc" -eq 0 ]; then', '  '+python+' -u volume_domain_audit.py', '  rc=$?', 'fi']
    if group == 'cpu' and not clang:
        lines += ['if [ "$rc" -eq 0 ]; then', '  '+python+' -u binary_audit.py', '  rc=$?', 'fi']
    lines += ['echo "$rc" > comparison-exit-code.txt', 'tar -czf "$root.results.tar.gz" -C "$root" .', 'exit "$rc"']
    args = {'arch':'armgpu' if gpu else 'x64cpu', 'command':'\n'.join(lines), 'gpus_per_node':int(gpu),
        'cpus_per_task':4 if gpu else required_threads,
        'mem_gb':16, 'name':'forest-active-'+stem, 'time_limit':'02:00:00',
        'spack_packages':['/uxlsycgnldislqswr4gcj6hlc6u2pdxp' if gpu else '/fmrcj5jrubquulzxeqmhucxqunhodrxp'],
        'workdir':'/scratch_p/nimarano'}
    if clang:
        args['cpus_per_task'] = 1
        args['spack_packages'].append('/hdlzlaza4paizierl2rau5s325x73mm4')
    write(R/(stem+'-job-arguments.json'), args)
    print(stem, len(manifest), 'source exports')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('keys', nargs='+')
    parser.add_argument('--label')
    parser.add_argument('--clang', action='store_true')
    args = parser.parse_args()
    prepare(args.keys, args.label, args.clang)
