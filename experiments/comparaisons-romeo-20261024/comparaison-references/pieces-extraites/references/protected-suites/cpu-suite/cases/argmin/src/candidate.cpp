#include <cstdint>
#include <cstring>
#include <cmath>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void* input1,const void* input2,void* output,int n,int parameter,int threads)
{const int*a=(const int*)input1;int j=0;for(int i=1;i<n;i++)if(a[i]<a[j])j=i;*(int*)output=j;}
