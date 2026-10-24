"""Check that the reference-domain exception never admits a failed candidate."""
from copy import deepcopy
import json
from unpack_comparison import R, read, volume_negative_controls


def main():
    stem='paired-volume'
    dest=R/(stem+'-results')
    job=str(read(R/(stem+'-job.json'))['job_id'])
    measurement=dest/('measurements-'+job)
    records=read(measurement/'results.json')
    accepted,_=volume_negative_controls(stem,dest,measurement,records,job)
    assert len(accepted)==2
    rejected=[]
    for mutation in ['failed_candidate','failed_timing','different_reference_error']:
        changed=deepcopy(records)
        if mutation=='failed_candidate':
            item=next(r for r in changed if r['variant']=='new_selected' and r['diagnostic'])
            item['exit_code']=1
            item['measurement']['correct']=False
        else:
            item=next(r for r in changed if r['variant']=='optimized' and r['diagnostic'])
            if mutation=='failed_timing':
                item['block']=0
            else:
                item['measurement']={'error':'unexpected failure'}
        try:
            volume_negative_controls(stem,dest,measurement,changed,job)
        except AssertionError:
            rejected.append(mutation)
        else:
            raise AssertionError('Unexpected failure accepted: '+mutation)
    result={'documented_reference_errors_recognized':2,'unexpected_errors_rejected':rejected,
            'raw_evidence_modified':False,'passed':True}
    (R/'volume-negative-control-validation.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
