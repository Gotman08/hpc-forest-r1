#include "/gpfs/scratch/nimarano/forest-reference-cpu-suite-20261023/reference/ispc/stencil/ref.h"
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{size_t s=size_t(n)*n*n;const float*a=(const float*)input1;float*c=(float*)output;memcpy(c,a,s*4);memset(c+s,0,s*4);const float co[4]={.5f,-.25f,.125f,-.0625f};ispc::loop_stencil_ispc(0,6,4,n-4,4,n-4,4,n-4,n,n,n,co,(const float*)input2,c,c+s);}
