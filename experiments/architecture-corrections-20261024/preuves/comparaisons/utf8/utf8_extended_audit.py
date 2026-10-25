from pathlib import Path
import ctypes as ct,json,os,random,hashlib,time
S=Path('/scratch_p/nimarano/forest-reference-cpu-suite-20261023')
F=Path(__file__).resolve().parent
R=F/('measurements-'+os.environ['SLURM_JOB_ID'])
paths={'historical':S/'cases/utf8/naive.so','repaired':S/'cases/utf8/repaired.so','reference_avx':S/'cases/utf8/optimized.so'}
paths.update({v:F/'utf8'/v/'candidate.so' for v in ['old_selected','previous_selected','new_selected','old_g','previous_g','new_g'] if (F/'utf8'/v/'candidate.so').exists()})

paths.update({m['variant']:F/'utf8'/m['variant']/'candidate.so' for m in json.loads((F/'manifest.json').read_text()) if m.get('audit_only') and m['case_id']=='utf8'})

tests=[bytes([x]) for x in range(256)]+[bytes([x,y]) for x in range(256) for y in range(256)]
special=[b'\xc0\x80',b'\xc1\xbf',b'\xe0\x9f\xbf',b'\xe0\xa0\x80',b'\xed\x9f\xbf',b'\xed\xa0\x80',b'\xf0\x8f\xbf\xbf',b'\xf0\x90\x80\x80',b'\xf4\x8f\xbf\xbf',b'\xf4\x90\x80\x80',b'\xf5\x80\x80\x80',b'\xc2A',b'\xe2\x82\xac',b'\xf0\x9f\x98\x80']
for offset in range(133):
    for x in special:
        for cut in range(len(x)+1):
            for suffix in [0,7,64]:tests.append(b'a'*offset+x[:cut]+b'a'*suffix)
rng=random.Random(8231)
for _ in range(4000):
    n=rng.randint(0,128);tests.append(rng.randbytes(n))
    text=''.join(chr(rng.choice([rng.randrange(0xD800),rng.randrange(0xE000,0x110000)])) for _ in range(n//4));data=text.encode();tests.append(data)
    if data:
        p=rng.randrange(len(data));tests.append(data[:p]+bytes([rng.randrange(256)])+data[p+1:])
expected=[]
for data in tests:
    try:data.decode('utf8','strict');expected.append(1)
    except UnicodeDecodeError:expected.append(0)
records=[];proto=ct.CFUNCTYPE(None,ct.c_void_p,ct.c_void_p,ct.c_void_p,ct.c_int,ct.c_int,ct.c_int)
for label,path in paths.items():
    dll=ct.CDLL(str(path),mode=os.RTLD_LOCAL);f=proto(('run',dll));failures=0;examples=[]
    for data,want in zip(tests,expected):
        storage=ct.create_string_buffer(len(data)+192);address=(ct.addressof(storage)+127)&~63
        ct.memset(address-64,0xa7,len(data)+128);ct.memmove(address,data,len(data))
        output=ct.create_string_buffer(256);outaddr=(ct.addressof(output)+127)&~63;ct.memset(outaddr-64,0xa7,132)
        f(address,None,outaddr,len(data),0,1);actual=ct.c_uint32.from_address(outaddr).value
        ok=actual==want and ct.string_at(outaddr-64,64)==bytes([0xa7])*64 and ct.string_at(outaddr+4,64)==bytes([0xa7])*64 and ct.string_at(address-64,len(data)+128)==bytes([0xa7])*64+data+bytes([0xa7])*64
        if not ok:
            failures+=1
            if len(examples)<12:examples.append({'hex':data.hex(),'expected':want,'actual':actual})
    row={'variant':label,'cases':len(tests),'failed':failures,'examples':examples,'binary_sha256':hashlib.sha256(path.read_bytes()).hexdigest()};records.append(row);print(json.dumps(row),flush=True)
out={'job':os.environ['SLURM_JOB_ID'],'time':time.time(),'oracle':'Python strict UTF-8 decoder; exhaustive 1/2 bytes, restricted leads at offsets 0..132, empty/7/64-byte suffixes and truncated sequences, deterministic random and mutated valid strings','seed':8231,'records':records};(R/'utf8-extended-audit.json').write_text(json.dumps(out,indent=2))
