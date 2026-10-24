#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
__global__ void absolute(const float*x,float*t,int n){for(size_t i=blockIdx.x*blockDim.x+threadIdx.x;i<n;i+=size_t(blockDim.x)*gridDim.x)t[i]=fabsf(x[i]);}
template<bool ABS> __global__ void sum(const float*x,float*y,int n){using BR=cub::BlockReduce<float,256>;__shared__ typename BR::TempStorage temp;float s=0;for(size_t i=blockIdx.x*blockDim.x+threadIdx.x;i<n;i+=size_t(blockDim.x)*gridDim.x)s+=ABS?fabsf(x[i]):x[i];float total=BR(temp).Sum(s);if(threadIdx.x==0)atomicAdd(y,total);}
extern "C" void run(const void*x,const void*k,const void*gy,void*out,void*scratch,int n,int h,int l,int ks)
{cudaMemsetAsync(out,0,4);absolute<<<1024,256>>>((const float*)x,(float*)scratch,n);sum<false><<<1024,256>>>((float*)scratch,(float*)out,n);}
