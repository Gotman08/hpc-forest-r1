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
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
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
        return (T *)__smem;
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
        return (double *)__smem_d;
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
    Parallel sum reduction using shared memory
    - takes log(n) steps for n input elements
    - uses n threads
    - only works for power-of-2 arrays
*/

/* This reduction interleaves which threads are active by using the modulo
   operator.  This operator is very expensive on GPUs, and the interleaved
   inactivity means that no whole warps are active, which is also very
   inefficient */
template <class T> __global__ void reduce0(T *g_idata, T *g_odata, unsigned int n)
{
    // Handle to thread block group
    cg::thread_block cta   = cg::this_thread_block();
    T               *sdata = SharedMemory<T>();

    // load shared mem
    unsigned int tid = threadIdx.x;
    unsigned int i   = blockIdx.x * blockDim.x + threadIdx.x;

    sdata[tid] = (i < n) ? g_idata[i] : 0;

    cg::sync(cta);

    // do reduction in shared mem
    for (unsigned int s = 1; s < blockDim.x; s *= 2) {
        // modulo arithmetic is slow!
        if ((tid % (2 * s)) == 0) {
            sdata[tid] += sdata[tid + s];
        }

        cg::sync(cta);
    }

    // write result for this block to global mem
    if (tid == 0)
        g_odata[blockIdx.x] = sdata[0];
}

constexpr int kBlockThreads = 256;
constexpr int kItemsPerThread = 16;
constexpr int kTileSize = kBlockThreads * kItemsPerThread;
constexpr int kWarpsPerBlock = kBlockThreads / 32;

// Reduce one value per lane to one value per block using warp shuffles.
__device__ __forceinline__ int blockReduceSumWarp(int value, int *warpSums)
{
    const int tid = threadIdx.x;
    const int lane = tid & 31;
    const int warp = tid >> 5;
    const unsigned int mask = __activemask();

    value = warpReduceSum<int>(mask, value);
    if (lane == 0)
        warpSums[warp] = value;
    __syncthreads();

    if (warp == 0) {
        value = (lane < kWarpsPerBlock) ? warpSums[lane] : 0;
        value = warpReduceSum<int>(mask, value);
        return value;
    }
    return 0;
}

// Keep the final accumulation wide: only the true result is guaranteed to fit int32.
__device__ __forceinline__ long long blockReduceSumWarp64(long long value, long long *warpSums)
{
    const int tid = threadIdx.x;
    const int lane = tid & 31;
    const int warp = tid >> 5;
    const unsigned int mask = __activemask();

    value = warpReduceSum<long long>(mask, value);
    if (lane == 0)
        warpSums[warp] = value;
    __syncthreads();

    if (warp == 0) {
        value = (lane < kWarpsPerBlock) ? warpSums[lane] : 0;
        value = warpReduceSum<long long>(mask, value);
        return value;
    }
    return 0;
}

// Each CTA reduces one coalesced tile and overwrites its own scratch slot.
__global__ void reduceTilePartials(const int *input, int *partials, int n)
{
    __shared__ int warpSums[kWarpsPerBlock];

    const int tid = threadIdx.x;
    const unsigned int tileStart = blockIdx.x * static_cast<unsigned int>(kTileSize);
    int sum = 0;

    #pragma unroll
    for (int item = 0; item < kItemsPerThread; ++item) {
        const unsigned int index = tileStart +
            static_cast<unsigned int>(item * kBlockThreads + tid);
        if (index < static_cast<unsigned int>(n))
            sum += input[index];
    }

    const int blockSum = blockReduceSumWarp(sum, warpSums);
    if (tid == 0)
        partials[blockIdx.x] = blockSum;
}

// Reduce either a small input directly or the partials from the first pass.
__global__ void reduceToOutput(const int *input, int count, int *output)
{
    __shared__ long long warpSums[kWarpsPerBlock];

    long long sum = 0;
    for (int index = threadIdx.x; index < count; index += kBlockThreads)
        sum += input[index];

    const long long total = blockReduceSumWarp64(sum, warpSums);
    if (threadIdx.x == 0)
        output[0] = static_cast<int>(total);
}

#endif

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    const int *input = static_cast<const int *>(x);
    int *output = static_cast<int *>(out);

    // Preserve the zero-kernel path for the single-element case.
    if (n == 1) {
        cudaMemcpyAsync(out, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    if (n <= kTileSize) {
        reduceToOutput<<<1, kBlockThreads>>>(input, n, output);
        return;
    }

    int *partials = static_cast<int *>(scratch);
    const int partialCount = (n - 1) / kTileSize + 1;
    reduceTilePartials<<<partialCount, kBlockThreads>>>(input, partials, n);
    reduceToOutput<<<1, kBlockThreads>>>(partials, partialCount, output);
}
