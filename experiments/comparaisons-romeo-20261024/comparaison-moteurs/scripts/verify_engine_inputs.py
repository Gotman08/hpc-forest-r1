"""Compare actual input and reference bytes across all 21 campaign caches."""
import json
from engine_study import ROOT,CONDITIONS,read,write,sha

def main():
    root=ROOT/'outputs/comparaison-moteurs'
    series=[('interrupted',root),('shared-scp',root/'relance-controlee'),('atomic',root/'serie-atomique')]
    canonical=None;result={}
    for name,folder in series:
        cases={};checks={}
        for key in CONDITIONS:
            p=folder/'protocol'/key
            preflight=read(p/'cache-preflight.json');assert preflight['passed']
            cases[key]={}
            for phase in ['search','confirmation']:
                raw=p/('cache-'+phase+'.json');rows=read(raw)
                assert len(rows)==11
                assert sha(raw)==preflight['phases'][phase]['manifest_sha256']
                assert all(r['cpu_oracle_passed'] for r in rows)
                cases[key][phase]=[{k:r[k] for k in ['n','dt','label','input_sha256','reference_sha256']} for r in rows]
            if canonical is None:canonical=cases[key]
            checks[key]=cases[key]==canonical
        assert all(checks.values())
        proof={'all_equal':True,'checks':checks,'cases':cases,'manifest_digests_verified':True,'independent_cpu_oracle_passed':True}
        write(folder/'protocol/input-equivalence.json',proof)
        result[name]={'campaigns':len(checks),'cases_per_campaign':22,'all_equal_to_first_series':all(checks.values())}
    write(root/'protocol/all-series-input-equivalence.json',result)
    print(json.dumps(result))

if __name__=='__main__':main()
