from pathlib import Path
import json,re,shutil,tarfile,hashlib
R=Path(__file__).resolve().parent;U=R/'upstream';P=R/'cpu-suite';P.mkdir(exist_ok=True)
header='''#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
'''
cases=[]
def add(name,source,n,parameter=0,threads=1,checks=None,kind=None,**more):
    p=P/'cases'/name/'src';p.mkdir(parents=True,exist_ok=True);(p/'candidate.cpp').write_text(source)
    d={'id':name,'n':n,'parameter':parameter,'threads':threads,'checks':checks or [n],'kind':kind or name,**more};cases.append(d);return p

pop=(U/'popcount/popcount.c').read_text();start=pop.index('static inline uint32_t\npopcount_naive');end=pop.index('DRIVER(naive)',start)
body=pop[start:end]
wrapper=header+'{const uint32_t*a=(const uint32_t*)input1;uint32_t result=0;for(int j=0;j<parameter;j++)for(int i=0;i<n;i++)result+=popcount_naive(a[i]^result);*(uint32_t*)output=result;}\n'
p=add('popcount',pop[:pop.index('#include')]+ '#include <cstdint>\n'+body+wrapper,1000,100,checks=[1,17,1000])
(p.parent/'optimized.cpp').write_text('#include <cstdint>\n'+header+'{const uint32_t*a=(const uint32_t*)input1;uint32_t result=0;for(int j=0;j<parameter;j++)for(int i=0;i<n;i++)result+=__builtin_popcount(a[i]^result);*(uint32_t*)output=result;}\n')
add('argmin',header+'{const int*a=(const int*)input1;int j=0;for(int i=1;i<n;i++)if(a[i]<a[j])j=i;*(int*)output=j;}\n',8192,checks=[8192])
arg=(U/'amh-code/argmin/combined.cc').read_text().replace('#include "argmin.hh"','#include <bits/stdc++.h>\n#define N 8192')
(P/'cases/argmin/optimized.cpp').write_text(arg+header+'{*(int*)output=argmin((int*)input1,n);}\n')
for name,func in [('blackscholes','black_scholes'),('binomial','binomial_put')]:
    src=(U/'examples/cpu/options/options_serial.cpp').read_text().replace('#include "options_defs.h"',(U/'examples/cpu/options/options_defs.h').read_text())
    wrap=header+f'{{float*a=(float*)input1;{func}_serial(a,a+n,a+2*n,a+3*n,a+4*n,(float*)output,n);}}\n'
    add(name,src+wrap,131072,threads=4,checks=[16,128,1024],ispc='options',ispc_symbol=func+'_ispc',ispc_tasks=func+'_ispc_tasks',max_threads=40)
for name,folder,file,func,n in [('noise','noise','noise_serial.cpp','noise_serial',768),('mandelbrot','mandelbrot_tasks','mandelbrot_tasks_serial.cpp','mandelbrot_serial',1024)]:
    src=(U/'examples/cpu'/folder/file).read_text()
    args='a[0],a[1],a[2],a[3],'+('n*3/2,n,parameter,(int*)output' if name=='mandelbrot' else 'n,n,(float*)output')
    wrap=header+'{const float*a=(const float*)input1;'+func+'('+args+');}\n'
    add(name,src+wrap,n,512 if name=='mandelbrot' else 0,threads=4 if name=='mandelbrot' else 1,checks=[32,64,128],ispc=folder,ispc_symbol='mandelbrot_ispc' if name=='mandelbrot' else 'noise_ispc',ispc_tasks='mandelbrot_ispc' if name=='mandelbrot' else None)
src=(U/'examples/cpu/stencil/stencil_serial.cpp').read_text()
wrap=header+'''{size_t s=size_t(n)*n*n;const float*a=(const float*)input1;float*c=(float*)output;memcpy(c,a,s*4);memset(c+s,0,s*4);const float co[4]={.5f,-.25f,.125f,-.0625f};loop_stencil_serial(0,6,4,n-4,4,n-4,4,n-4,n,n,n,co,(const float*)input2,c,c+s);}\n'''
add('stencil3d',src+wrap,256,threads=4,checks=[16,24,32],ispc='stencil',ispc_symbol='loop_stencil_ispc',ispc_tasks='loop_stencil_ispc_tasks')
bs=(U/'fastbase64/src/scalarbase64.c').read_text().replace('#include "scalarbase64.h"',(U/'fastbase64/include/scalarbase64.h').read_text())
add('base64',bs+header+'{size_t len=0;int ok=scalar_base64_decode((const char*)input1,n,((char*)output)+16,&len);*(uint64_t*)output=ok?len:UINT64_MAX;}\n',141020,checks=[4,8,64,1024,141020])
utf=(U/'fastvalidate-utf-8/benchmarks/benchmark.c').read_text();i=utf.index('static bool validate_utf8(');j=utf.index('\n}',i)+2
add('utf8','#include <stdbool.h>\n#include <stddef.h>\n#include <stdint.h>\n'+utf[i:j]+'\n'+header+'{*(uint32_t*)output=validate_utf8((const char*)input1,n);}\n',65536,checks=[1,16,31,64,1024,65536])
gemm='''#include <cstring>
template<int N> void mm(const float*A,const float*B,float*C){for(int r=0;r<N;r++)for(int c=0;c<N;c++)for(int k=0;k<N;k++)C[r*N+c]+=A[r*N+k]*B[k*N+c];}
'''+header+'''{memset(output,0,size_t(n)*n*4);if(n==1024)mm<1024>((const float*)input1,(const float*)input2,(float*)output);else if(n==128)mm<128>((const float*)input1,(const float*)input2,(float*)output);else if(n==32)mm<32>((const float*)input1,(const float*)input2,(float*)output);}
'''
add('gemm_cpu',gemm,1024,threads=8,checks=[32,128],reference_reconstruction=True)
# Keep compiler/library inputs separate from the source exposed to the model.
for name in ['fastbase64','fastvalidate-utf-8']:
    dst=P/'reference'/name
    if not dst.exists():shutil.copytree(U/name,dst,ignore=shutil.ignore_patterns('.git'))
(P/'timing.cpp').write_text('''#include <chrono>
#include <omp.h>
using Run=void(*)(const void*,const void*,void*,int,int,int);
extern "C" double timed(Run f,const void*a,const void*b,void*c,int n,int parameter,int threads,int repetitions,int warmups){omp_set_dynamic(0);omp_set_num_threads(threads);for(int i=0;i<warmups;i++)f(a,b,c,n,parameter,threads);auto t=std::chrono::steady_clock::now();for(int i=0;i<repetitions;i++){f(a,b,c,n,parameter,threads);asm volatile("":::"memory");}return std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count()/repetitions;}
''')
(P/'cases.json').write_text(json.dumps(cases,indent=2))
for folder in ['options','noise','mandelbrot_tasks','stencil']:
    dest=P/'reference/ispc'/folder
    if not dest.exists():shutil.copytree(U/'examples/cpu'/folder,dest)
shutil.copyfile(R/'cpu-preflight/examples/common/tasksys.cpp',P/'reference/ispc/tasksys.cpp')
print(json.dumps(cases))
