#include "/gpfs/scratch/nimarano/forest-reference-cpu-suite-20261023/reference/ispc/mandelbrot_tasks/ref.h"
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const float*a=(const float*)input1;ispc::mandelbrot_ispc(a[0],a[1],a[2],a[3],n*3/2,n,parameter,(int*)output);}
