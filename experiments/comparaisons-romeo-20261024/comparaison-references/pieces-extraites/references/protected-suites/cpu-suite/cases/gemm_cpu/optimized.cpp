#include <cstring>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void*a,const void*b,void*c,int n,int p,int t){auto A=(const float*)a;auto B=(const float*)b;auto C=(float*)c;memset(C,0,size_t(n)*n*4);
#pragma omp parallel for collapse(2) num_threads(8)
for(int i0=0;i0<n;i0+=256)for(int j0=0;j0<n;j0+=256)for(int k0=0;k0<n;k0+=16)for(int i=i0;i<std::min(n,i0+256);i++)for(int k=k0;k<std::min(n,k0+16);k++)for(int j=j0;j<std::min(n,j0+256);j++)C[i*n+j]+=A[i*n+k]*B[k*n+j];}
