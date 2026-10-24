#include "/gpfs/scratch/nimarano/forest-reference-cpu-suite-20261023/reference/ispc/options/ref.h"
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{float*a=(float*)input1;ispc::black_scholes_ispc_tasks(a,a+n,a+2*n,a+3*n,a+4*n,(float*)output,n);}
