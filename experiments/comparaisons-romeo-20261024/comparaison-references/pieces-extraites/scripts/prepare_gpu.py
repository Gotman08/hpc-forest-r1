from pathlib import Path
import shutil, json, tarfile, hashlib
R=Path(__file__).resolve().parent
P=R/'gpu-suite';P.mkdir(exist_ok=True)
U=R/'upstream'
S=P/'cases';S.mkdir(exist_ok=True)
shutil.copyfile(R/'gpu_driver.cu',P/'gpu_driver.cu')
if not (P/'sgemm').exists():shutil.copytree(U/'SGEMM_CUDA/src',P/'sgemm')
transpose=(U/'code-samples/series/cuda-cpp/transpose/transpose.cu').read_text()
stencil=(U/'code-samples/series/cuda-cpp/finite-difference/finite-difference.cu').read_text()
(P/'transpose.cuh').write_text(transpose[:transpose.index('int main(')])
(P/'stencil.cuh').write_text(stencil[:stencil.index('void runTest(')])
header='''#include <cuda_runtime.h>
extern "C" void run(const float*A,const float*B,float*C,float*scratch,int n,int m,int k,float alpha,float beta)
'''
naive=(U/'SGEMM_CUDA/src/kernels/1_naive.cuh').read_text()
sources={
 'sgemm':naive+'\n'+header+'{ sgemm_naive<<<dim3((n+31)/32,(m+31)/32),dim3(32,32)>>>(n,m,k,alpha,A,B,beta,C); }\n',
 'transpose':transpose[:transpose.index('// simple copy kernel')]+transpose[transpose.index('// naive transpose'):transpose.index('// coalesced transpose')]+header+'{ transposeNaive<<<dim3(n/32,n/32),dim3(32,8)>>>(C,A); }\n',
 'stencil_y':'#include <cuda_runtime.h>\n'+stencil[:stencil.index('void initInput(')]+stencil[stencil.index('__global__ void derivative_y('):stencil.index('__global__ void derivative_y_lPencils(')]+header+'{ static bool initialized=false; if(!initialized){setDerivativeParameters();initialized=true;} derivative_y<<<grid[1][0],block[1][0]>>>((float*)A,C); }\n'
}
for name,s in sources.items():
    p=S/name/'src';p.mkdir(parents=True,exist_ok=True);(p/'candidate.cu').write_text(s)
refs='''#include <cuda_runtime.h>
#include <cmath>
#include "sgemm/runner.cu"
#define checkCuda transposeCheckCuda
#include "transpose.cuh"
#undef checkCuda
#define checkCuda stencilCheckCuda
#include "stencil.cuh"
#undef checkCuda
extern "C" void reference_run(int kind,int variant,const float*A,const float*B,float*C,float*scratch,int n,int m,int k,float alpha,float beta) {
  if(kind==0){static cublasHandle_t h=nullptr;if(!h){cublasCreate(&h);cublasSetMathMode(h,CUBLAS_PEDANTIC_MATH);}run_kernel(variant,n,m,k,alpha,(float*)A,(float*)B,beta,C,h);}
  else if(kind==1){if(variant==1)transposeNaive<<<dim3(n/32,n/32),dim3(32,8)>>>(C,A);else transposeNoBankConflicts<<<dim3(n/32,n/32),dim3(32,8)>>>(C,A);}
  else if(kind==2){static bool initialized=false;if(!initialized){setDerivativeParameters();initialized=true;}if(variant==1)derivative_y<<<grid[1][0],block[1][0]>>>((float*)A,C);else derivative_y_lPencils<<<grid[1][1],block[1][1]>>>((float*)A,C);}
}
'''
(P/'references.cu').write_text(refs)
cases=[{'id':'sgemm','kind':0,'n':4096,'checks':[128,256,512],'reference_variants':list(range(0,12)),'reps':20,'warmups':5},
 {'id':'transpose','kind':1,'n':1024,'checks':[32,64,256],'reference_variants':[1,2],'reps':100,'warmups':10},
 {'id':'stencil_y','kind':2,'n':64,'checks':[64],'reference_variants':[1,2],'reps':100,'warmups':10}]
(P/'cases.json').write_text(json.dumps(cases,indent=2))
with tarfile.open(R/'gpu-suite.tar.gz','w:gz') as t:
    for p in sorted(P.iterdir()):t.add(p,arcname=p.name)
print(json.dumps({'archive':str(R/'gpu-suite.tar.gz'),'sha256':hashlib.sha256((R/'gpu-suite.tar.gz').read_bytes()).hexdigest()}))
