#include <cuda_runtime.h>
#include <algorithm>
/* Copyright (c) 2022, NVIDIA CORPORATION. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *  * Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *  * Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *  * Neither the name of NVIDIA CORPORATION nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

/*
    Parallel reduction kernels
*/

#ifndef _REDUCE_KERNEL_H_
#define _REDUCE_KERNEL_H_

#include <cooperative_groups.h>
#include <cooperative_groups/reduce.h>
#include <stdio.h>

namespace cg = cooperative_groups;

// Utility class used to avoid linker errors with extern
// unsized shared memory arrays with templated type
template <class T> struct SharedMemory
{
    __device__ inline operator T *()
    {
        extern __shared__ int __smem[];
        return (T *)__smem;
    }

    __device__ inline operator const T *() const
    {
        extern __shared__ int __smem[];
        return (const T *)__smem;
    }
};

// specialize for double to avoid unaligned memory
// access compile errors
template <> struct SharedMemory<double>
{
    __device__ inline operator double *()
    {
        extern __shared__ double __smem_d[];
        return (double *)__smem_d;
    }

    __device__ inline operator const double *() const
    {
        extern __shared__ double __smem_d[];
        return (const double *)__smem_d;
    }
};

template <class T> __device__ __forceinline__ T warpReduceSum(unsigned int mask, T mySum)
{
    for (int offset = warpSize / 2; offset > 0; offset /= 2) {
        mySum += __shfl_down_sync(mask, mySum, offset);
    }
    return mySum;
}

#if __CUDA_ARCH__ >= 800
// Specialize warpReduceFunc for int inputs to use __reduce_add_sync intrinsic
// when on SM 8.0 or higher
template <> __device__ __forceinline__ int warpReduceSum<int>(unsigned int mask, int mySum)
{
    mySum = __reduce_add_sync(mask, mySum);
    return mySum;
}
#endif

/*
    Parallel sum reduction using warp-local reductions and a shared-memory
    exchange of the four warp totals for a 128-thread block.
*/
template <class T> __global__ void reduce0(T *g_idata, T *g_odata, unsigned int n)
{
    T *sdata = SharedMemory<T>();
    unsigned int tid = threadIdx.x;
    unsigned int lane = tid % warpSize;
    unsigned int warp = tid / warpSize;
    unsigned int i = blockIdx.x * blockDim.x + tid;

    // Every lane participates; out-of-range lanes contribute the additive identity.
    T value = (i < n) ? g_idata[i] : static_cast<T>(0);
    value = warpReduceSum(__activemask(), value);

    // One total per warp; all four totals are ready after this CTA barrier.
    if (lane == 0)
        sdata[warp] = value;
    __syncthreads();

    // Lanes 0..3 hold warp totals and the remaining lanes hold zero.
    // Reuse the full-warp sum primitive to combine them.
    if (warp == 0) {
        T total = (lane < 4) ? sdata[lane] : static_cast<T>(0);
        total = warpReduceSum(0xffffffffu, total);
        if (lane == 0)
            g_odata[blockIdx.x] = total;
    }
}


#endif
extern "C" void run(const void*x,const void*k,const void*gy,void*out,void*scratch,int n,int h,int l,int ks)
{int count=n;int*input=(int*)x;int*temp=(int*)scratch;bool flip=false;
while(count>1){int blocks=(count+128-1)/128;
int*dest=flip?(int*)scratch+n+32768:(int*)scratch;
reduce0<int><<<blocks,128,128*sizeof(int)>>>(input,dest,count);
input=dest;count=blocks;flip=!flip;}
cudaMemcpyAsync(out,input,sizeof(int),cudaMemcpyDeviceToDevice);}
