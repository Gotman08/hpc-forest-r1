from pathlib import Path
import ctypes as ct,json,os,random,hashlib,time
S=Path('/scratch_p/nimarano/forest-reference-cpu-suite-20261023');F=Path('/scratch_p/nimarano/forest-reference-cpu-final-20261023');R=Path('/scratch_p/nimarano/forest-reference-utf8-audit-20261023');R.mkdir(exist_ok=True)
paths={'historical':S/'cases/utf8/naive.so','repaired':S/'cases/utf8/repaired.so','reference_avx':S/'cases/utf8/optimized.so','selected':F/'utf8/selected/candidate.so','final_g':F/'utf8/final_g/candidate.so'}
tests=[bytes([x]) for x in range(256)]+[bytes([x,y]) for x in range(256) for y in range(256)]
special=[b'\xc0\x80',b'\xc1\xbf',b'\xe0\x9f\xbf',b'\xe0\xa0\x80',b'\xed\x9f\xbf',b'\xed\xa0\x80',b'\xf0\x8f\xbf\xbf',b'\xf0\x90\x80\x80',b'\xf4\x8f\xbf\xbf',b'\xf4\x90\x80\x80',b'\xf5\x80\x80\x80',b'\xc2A',b'\xe2\x82\xac',b'\xf0\x9f\x98\x80']
for offset in range(35):
    for x in special:
        for cut in range(len(x)+1):tests.append(b'a'*offset+x[:cut]+b'a'*7)
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
        src=ct.create_string_buffer(data+bytes([0xa7])*64);out=(ct.c_uint32*3)(0xa7a7a7a7,0xdeadbeef,0xa7a7a7a7);f(src,None,ct.byref(out,4),len(data),0,1)
        ok=out[1]==want and out[0]==out[2]==0xa7a7a7a7 and src.raw[:-1]==data+bytes([0xa7])*64
        if not ok:
            failures+=1
            if len(examples)<12:examples.append({'hex':data.hex(),'expected':want,'actual':out[1]})
    row={'variant':label,'cases':len(tests),'failed':failures,'examples':examples,'binary_sha256':hashlib.sha256(path.read_bytes()).hexdigest()};records.append(row);print(json.dumps(row),flush=True)
out={'job':os.environ['SLURM_JOB_ID'],'time':time.time(),'oracle':'Python strict UTF-8 decoder; exhaustive 1/2 bytes, restricted leads at SIMD boundaries, deterministic random and mutated valid strings','seed':8231,'records':records};(R/('audit-'+os.environ['SLURM_JOB_ID']+'.json')).write_text(json.dumps(out,indent=2))
