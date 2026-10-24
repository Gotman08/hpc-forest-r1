from pathlib import Path
import json,subprocess,re,os,hashlib
R=Path(__file__).resolve().parent
os.chdir(R);(R/'build').mkdir(exist_ok=True)
logs=[]
def build(args):
    p=subprocess.run(args,capture_output=True,text=True)
    logs.append({'command':args,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    (R/'build/build-log.json').write_text(json.dumps(logs,indent=2))
    if p.returncode:raise RuntimeError(p.stderr[-4000:])
flags=['g++','-std=c++17','-O3','-march=native','-fPIC','-shared','-fopenmp','-Wl,-Bsymbolic']
build(flags+['timing.cpp','-o','build/timing.so'])
ispc=next(Path('/scratch_p/nimarano/forest-reference-cpu-preflight-20261023').glob('ispc*/bin/ispc'))
objects={}
for folder in ['options','noise','mandelbrot_tasks','stencil']:
    d=R/'reference/ispc'/folder;src=d/(folder+'.ispc')
    build([str(ispc),str(src),'--pic','-O2','--target=avx512skx-x16','-o',str(d/'ref.o'),'-h',str(d/'ref.h')])
    objects[folder]=[str(d/'ref.o'),'reference/ispc/tasksys.cpp']
for case in json.loads((R/'cases.json').read_text()):
    name=case['id'];d=R/'cases'/name;src=d/'src/candidate.cpp'
    try:
        build(flags+[str(src),'-o',str(d/'naive.so')])
        if (d/'optimized.cpp').exists():build(flags+[str(d/'optimized.cpp'),'-o',str(d/'optimized.so')])
        if case.get('ispc'):
            wrapper=src.read_text()[src.read_text().rindex('#include <cstdint>'):]
            serial={'binomial':'binomial_put_serial','blackscholes':'black_scholes_serial','mandelbrot':'mandelbrot_serial','noise':'noise_serial','stencil3d':'loop_stencil_serial'}[name]
            for variant,symbol in [('optimized',case['ispc_symbol']),('tasks',case.get('ispc_tasks'))]:
                if not symbol:continue
                text='#include "'+str(R/'reference/ispc'/case['ispc']/'ref.h')+'"\n'+wrapper.replace(serial,'ispc::'+symbol)
                (d/(variant+'.cpp')).write_text(text)
                build(flags+[str(d/(variant+'.cpp')),*objects[case['ispc']],'-o',str(d/(variant+'.so'))])
        if name=='base64':
            inc=R/'reference/fastbase64/include';objs=[]
            for component in ['chromiumbase64','fastavxbase64']:
                obj='build/'+component+'.o';build(['gcc','-std=c99','-O3','-march=native','-fPIC','-I'+str(inc),'-c',str(R/'reference/fastbase64/src'/(component+'.c')),'-o',obj]);objs.append(obj)
            for variant,func in [('optimized','fast_avx2_base64_decode'),('chromium','chromium_base64_decode')]:
                wrap='#include <cstdint>\n#include "fastavxbase64.h"\nextern "C" void run(const void*a,const void*b,void*c,int n,int p,int t){*(uint64_t*)c='+func+'((char*)c+16,(const char*)a,n);}\n'
                (d/(variant+'.cpp')).write_text(wrap);build(flags+['-I'+str(inc),str(d/(variant+'.cpp')),*objs,'-o',str(d/(variant+'.so'))])
        if name=='utf8':
            (d/'optimized.cpp').write_text('#include <cstdint>\n#include "simdutf8check.h"\nextern "C" void run(const void*a,const void*b,void*c,int n,int p,int t){*(uint32_t*)c=validate_utf8_fast_avx((const char*)a,n);}\n')
            build(flags+['-I'+str(R/'reference/fastvalidate-utf-8/include'),str(d/'optimized.cpp'),'-o',str(d/'optimized.so')])
        if name=='gemm_cpu':
            # Reconstruct the article's explicitly shown loop structures;
            # its unspecified inner tile constant is fixed to 16 and recorded.
            for variant in ['reorder','tiling','optimized']:
                start='#include <cstring>\n#include <algorithm>\n#include <omp.h>\nextern "C" void run(const void*a,const void*b,void*c,int n,int p,int t){auto A=(const float*)a;auto B=(const float*)b;auto C=(float*)c;memset(C,0,size_t(n)*n*4);\n'
                if variant=='reorder':body='for(int i=0;i<n;i++)for(int k=0;k<n;k++)for(int j=0;j<n;j++)C[i*n+j]+=A[i*n+k]*B[k*n+j];'
                elif variant=='tiling':body='for(int k0=0;k0<n;k0+=16)for(int i=0;i<n;i++)for(int k=k0;k<std::min(n,k0+16);k++)for(int j=0;j<n;j++)C[i*n+j]+=A[i*n+k]*B[k*n+j];'
                else:body='#pragma omp parallel for collapse(2) num_threads(8)\nfor(int i0=0;i0<n;i0+=256)for(int j0=0;j0<n;j0+=256)for(int k0=0;k0<n;k0+=16)for(int i=i0;i<std::min(n,i0+256);i++)for(int k=k0;k<std::min(n,k0+16);k++)for(int j=j0;j<std::min(n,j0+256);j++)C[i*n+j]+=A[i*n+k]*B[k*n+j];'
                (d/(variant+'.cpp')).write_text(start+body+'}\n');build(flags+[str(d/(variant+'.cpp')),'-o',str(d/(variant+'.so'))])
            build([x for x in flags if x not in ['-O3','-march=native']]+['-O0',str(src),'-o',str(d/'naive_o0.so')])
        print(name,'BUILT',flush=True)
    except Exception as ex:print(name,'FAILED',str(ex),flush=True)
(R/'build/binaries.json').write_text(json.dumps({str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.rglob('*.so')},indent=2))
