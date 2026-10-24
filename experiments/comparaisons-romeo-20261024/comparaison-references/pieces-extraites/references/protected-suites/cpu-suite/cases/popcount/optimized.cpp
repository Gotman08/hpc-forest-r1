#include <cstdint>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const uint32_t*a=(const uint32_t*)input1;uint32_t result=0;for(int j=0;j<parameter;j++)for(int i=0;i<n;i++)result+=__builtin_popcount(a[i]^result);*(uint32_t*)output=result;}
