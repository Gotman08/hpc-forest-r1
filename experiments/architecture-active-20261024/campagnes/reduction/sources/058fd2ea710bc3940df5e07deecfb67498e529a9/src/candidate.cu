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

// specialize for double to avoid unaligned shared-memory access errors
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

template <class T> __global__ void reduce0(T *g_idata, T *g_odata, unsigned int n)
{
    cg::thread_block cta = cg::this_thread_block();
    T *sdata = SharedMemory<T>();

    unsigned int tid = threadIdx.x;
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;

    sdata[tid] = (i < n) ? g_idata[i] : 0;
    cg::sync(cta);

    for (unsigned int s = 1; s < blockDim.x; s *= 2) {
        if ((tid % (2 * s)) == 0) {
            sdata[tid] += sdata[tid + s];
        }
        cg::sync(cta);
    }

    if (tid == 0)
        g_odata[blockIdx.x] = sdata[0];
}

#endif

__global__ void zero_int_output(int *out)
{
    if (blockIdx.x == 0 && threadIdx.x == 0)
        *out = 0;
}

__global__ void reduce_atomic_grid_stride(const int *input, int *out, int n)
{
    unsigned long long index = (unsigned long long)blockIdx.x * blockDim.x + threadIdx.x;
    const unsigned long long stride = (unsigned long long)gridDim.x * blockDim.x;
    int thread_sum = 0;

    for (; index < (unsigned long long)n; index += stride)
        thread_sum += input[index];

    const int lane = threadIdx.x & (warpSize - 1);
    const int warp = threadIdx.x / warpSize;
    thread_sum = warpReduceSum<int>(0xffffffffu, thread_sum);

    __shared__ int warp_sums[256 / 32];
    if (lane == 0)
        warp_sums[warp] = thread_sum;
    __syncthreads();

    if (warp == 0) {
        int block_sum = (lane < (blockDim.x / warpSize)) ? warp_sums[lane] : 0;
        block_sum = warpReduceSum<int>(0xffffffffu, block_sum);
        if (lane == 0)
            atomicAdd(out, block_sum);
    }
}

extern "C" void run(const void *x, const void *k, const void *gy, void *out, void *scratch,
                    int n, int h, int l, int ks)
{
    int *output = (int *)out;
    if (n <= 0) {
        zero_int_output<<<1, 1>>>(output);
        return;
    }

    if (n >= (1 << 20)) {
        const int threads = 256;
        const int target_elements_per_cta = 4096;
        const int max_ctas = 768;
        int blocks = n / target_elements_per_cta;
        if (n % target_elements_per_cta != 0)
            ++blocks;
        if (blocks > max_ctas)
            blocks = max_ctas;

        // Same default stream: initialization completes before any CTA atomics.
        zero_int_output<<<1, 1>>>(output);
        reduce_atomic_grid_stride<<<blocks, threads>>>((const int *)x, output, n);
        return;
    }

    int count = n;
    int *input = (int *)x;
    bool flip = false;
    while (count > 1) {
        int blocks = (count + 128 - 1) / 128;
        int *dest = flip ? (int *)scratch + n + 32768 : (int *)scratch;
        reduce0<int><<<blocks, 128, 128 * sizeof(int)>>>(input, dest, count);
        input = dest;
        count = blocks;
        flip = !flip;
    }
    cudaMemcpyAsync(out, input, sizeof(int), cudaMemcpyDeviceToDevice);
}
