#include <cuda_runtime.h>
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
