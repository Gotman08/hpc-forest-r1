"""Verify and safely extract the completed common replay's structured evidence."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile
from engine_study import ROOT,read,write,sha

def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path);args=parser.parse_args()
    out=ROOT/'outputs/comparaison-moteurs/gpu-comparaison'
    receipt=read(out/'delivery.json')
    assert args.archive.stat().st_size==receipt['bytes'] and sha(args.archive)==receipt['sha256']
    checked=[]
    with tarfile.open(args.archive,'r:gz') as tar:
        members=tar.getmembers();seen=set()
        for member in members:
            name=PurePosixPath(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            assert name.parts[0] in {'results','cache'} or member.name in {'variants.json','manifest.json','gpu_replay.py'}
            assert member.name not in seen;seen.add(member.name)
            target=out.joinpath(*name.parts)
            assert out.resolve() in target.resolve().parents
            content=tar.extractfile(member).read()
            assert len(content)==member.size
            digest=hashlib.sha256(content).hexdigest()
            if target.exists():
                assert target.read_bytes()==content,'Existing evidence differs: '+member.name
            else:
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
            checked.append({'path':member.name,'bytes':member.size,'sha256':digest})
    assert (out/'results/summary.json').exists()
    write(out/'extraction-verification.json',{'archive_sha256':receipt['sha256'],'verified_files':checked,
        'safe_paths':True,'existing_files_identical':True})
    print(json.dumps({'files':len(checked),'archive_sha256':receipt['sha256'],'existing_evidence_preserved':True}))

if __name__=='__main__':main()
