#include <cstring>
#include <algorithm>
#include <omp.h>
extern "C" void run(const void*a,const void*b,void*c,int n,int p,int t){auto A=(const float*)a;auto B=(const float*)b;auto C=(float*)c;memset(C,0,size_t(n)*n*4);
for(int i=0;i<n;i++)for(int k=0;k<n;k++)for(int j=0;j<n;j++)C[i*n+j]+=A[i*n+k]*B[k*n+j];}
