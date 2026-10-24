"""Validate transferred paired measurements before analysis; no remote mutation."""
import collections
import json
import os
import sys
import tarfile
from pathlib import Path

from prepare import R, read, write, sha


def volume_negative_controls(stem, dest, measurement, records, job):
    """Recognize only the documented, independently audited reference domain errors."""
    assert stem == 'paired-volume'
    for name in ['compare.py', 'volume_domain_audit.py', 'suite-snapshot.json']:
        assert (dest/name).read_bytes() == (R/stem/name).read_bytes(), name
    audit = read(measurement/'volume-domain/audit.json')
    assert str(audit['job']) == job
    snapshot = read(R/stem/'suite-snapshot.json')
    assert audit['source_sha256'] == snapshot['reference/volume_rendering/volume.ispc']
    assert audit['driver_sha256'] == sha(measurement/'volume-domain/guarded_driver.cpp')
    variants = ['naive','optimized','tasks','old_selected','new_selected','old_g','new_g']
    expected_audit = {(v,n,h,True) for v in variants for n,h in [(224,296),(336,444)]}
    expected_audit |= {(v,n,h,False) for v in ['optimized','tasks'] for n,h in [(96,126),(128,169)]}
    observed = {(r['variant'],r['width'],r['height'],r['reference_supported_domain']) for r in audit['records']}
    assert len(audit['records']) == len(expected_audit) and observed == expected_audit
    for row in audit['records']:
        supported = row['reference_supported_domain']
        assert row['measurement'].get('correct') is supported
        assert row['exit_code'] == (0 if supported else 1)
        assert row['measurement']['seed'] == 1009 and row['measurement']['threads'] == 4
    # The frozen launcher runs this ordered diagnostic list after all timing blocks.
    # Crashing reference processes have no JSON stdout: dimensions are derived from
    # that order, not fabricated as if the failed process had reported them.
    scheduled = [(v,n) for v in ['naive','optimized','old_selected','new_selected','old_g','new_g'] for n in [96,128]]
    diagnostics = [(i,r) for i,r in enumerate(records) if r.get('diagnostic') is True]
    assert len(diagnostics) == len(scheduled)
    assert [i for i,_ in diagnostics] == list(range(len(records)-len(scheduled),len(records)))
    accepted, provenance = [], []
    for (index,row),(variant,n) in zip(diagnostics,scheduled):
        assert row['case_id'] == 'volume' and row['variant'] == variant
        assert row['block'] == -1 and str(row['job']) == job
        if variant == 'optimized':
            assert row['exit_code'] == -6
            assert row['measurement'] == {'error':'free(): invalid pointer\n'}
            accepted.append(row)
            provenance.append({'record_index':index,'variant':variant,'width':n,
                'height':int(n*1184/896),'reference_supported_domain':False,
                'dimension_provenance':'Ordered diagnostic list in the frozen compare.py; failed process emitted no JSON.',
                'independent_audit':'volume-domain/audit.json','excluded_from_timings':True})
        else:
            m = row['measurement']
            assert row['exit_code'] == 0 and m.get('correct') is True
            assert m['n'] == n and m['seed'] == 1009 and m['threads'] == 4
    return accepted, provenance


def unpack(stem):
    bundle=R/(stem+'-results.tar.gz')
    receipt=read(R/(stem+'-result-transfer.json'))
    assert receipt.get('verifie') is True and sha(bundle)==receipt['remote_sha256']
    dest=R/(stem+'-results')
    dest.mkdir(exist_ok=True)
    target=('\\\\?\\' if os.name=='nt' else '')+str(dest.resolve())
    with tarfile.open(bundle) as archive:
        archive.extractall(target,members=(m.replace(name=str(Path(m.name))) for m in archive.getmembers()
                                          if str(Path(m.name))!='.'),filter='data')
    assert (dest/'comparison-exit-code.txt').read_text().strip()=='0'
    job=str(read(R/(stem+'-job.json'))['job_id'])
    measurement=dest/('measurements-'+job)
    assert (measurement/'complete.json').exists()
    records=read(measurement/'results.json')
    assert records and all(isinstance(r,dict) for r in records)
    bad=[r for r in records if r.get('exit_code')!=0 or r.get('measurement',{}).get('correct') is not True]
    # The historical UTF-8 naive intentionally remains a negative control.
    # Only this previously documented invalid-string case may fail here.
    expected=[]
    for item in bad:
        m=item.get('measurement',{})
        if (item.get('case_id')=='utf8' and item.get('variant')=='naive'
                and item.get('diagnostic') is True and item.get('block')==-1
                and item.get('exit_code')==1 and m.get('correct') is False
                and m.get('n')==65536 and m.get('pattern')==1 and m.get('seed')==1907
                and m.get('input_sha256')=='f9be2aaa0f4765261b479b56300fcba0c3da185305e733a3fd181ded02655ee2'):
            expected.append(item)
    assert len(expected)<=1,expected
    if expected:
        audit=read(measurement/'utf8-audit.json')
        historical=[r for r in audit['records'] if r['variant']=='historical']
        assert len(historical)==1 and historical[0]['cases']==79729 and historical[0]['failed']==5773
        assert all(r['cases']==79729 and r['failed']==0 for r in audit['records'] if r['variant']!='historical')
    negative_provenance=[]
    if any(item.get('case_id')=='volume' for item in bad):
        volume_expected,negative_provenance=volume_negative_controls(stem,dest,measurement,records,job)
        expected.extend(volume_expected)
    assert len(expected)==len(bad) and all(item in expected for item in bad),bad
    manifest=read(R/stem/'manifest.json')
    cuda_library_sha256=None
    if read(R/(stem+'-transfer.json'))['group']=='gpu':
        cuda_library_sha256=(dest/'allocation-cublas.txt').read_text().split()[0]
        assert cuda_library_sha256==read(R/'runtime-library-fix.json')['library_sha256']
    for item in manifest:
        if item.get('missing'):
            continue
        path=dest/item['case_id']/item['variant']/('candidate'+item['suffix'])
        assert sha(path)==item['sha256'],item
    counts=collections.Counter((r['case_id'],r['variant'],bool(r.get('diagnostic'))) for r in records)
    verified={'job_id':job,'records':len(records),'all_recorded_checks_correct':not bad,
              'unexpected_failed_checks':0,'expected_negative_controls':expected,
              'negative_control_provenance':negative_provenance,
              'source_hashes_verified':True,'result_archive_sha256':sha(bundle),
              'cuda_library_sha256':cuda_library_sha256,
              'counts':[{'case_id':k[0],'variant':k[1],'diagnostic':k[2],'count':v} for k,v in sorted(counts.items())]}
    write(R/(stem+'-verification.json'),verified)
    print(json.dumps({'stem':stem,'job':job,'records':len(records),'unexpected_failures':0,
                      'expected_negative_controls':len(expected)}),flush=True)


if __name__=='__main__':
    for stem in sys.argv[1:]:
        unpack(stem)
