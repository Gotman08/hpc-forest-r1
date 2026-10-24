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

// specialize for double to avoid unaligned shared memory access
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

template <> struct SharedMemory<long long>
{
    __device__ inline operator long long *()
    {
        extern __shared__ long long __smem_ll[];
        return (long long *)__smem_ll;
    }

    __device__ inline operator const long long *() const
    {
        extern __shared__ long long __smem_ll[];
        return (const long long *)__smem_ll;
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
    cg::thread_block cta   = cg::this_thread_block();
    T               *sdata = SharedMemory<T>();

    unsigned int tid = threadIdx.x;
    unsigned int i   = blockIdx.x * blockDim.x + threadIdx.x;

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

// Direct one-block reduction for small inputs, retaining the baseline tree.
template <class OutT>
__global__ void reduce_input_128(const int *g_idata, OutT *g_odata, unsigned int n)
{
    cg::thread_block cta = cg::this_thread_block();
    long long *sdata = SharedMemory<long long>();

    unsigned int tid = threadIdx.x;
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    sdata[tid] = (i < n) ? (long long)g_idata[i] : 0LL;

    cg::sync(cta);
    for (unsigned int s = 1; s < blockDim.x; s *= 2) {
        if ((tid % (2 * s)) == 0) {
            sdata[tid] += sdata[tid + s];
        }
        cg::sync(cta);
    }

    if (tid == 0)
        g_odata[blockIdx.x] = (OutT)sdata[0];
}

// Each 128-thread CTA accumulates one bounded 4096-element tile, then uses
// the same shared-memory reduction tree to emit one exact 64-bit partial.
__global__ void reduce_input_4096(const int *g_idata,
                                  long long *g_odata,
                                  unsigned int n)
{
    cg::thread_block cta = cg::this_thread_block();
    long long *sdata = SharedMemory<long long>();

    unsigned int tid = threadIdx.x;
    unsigned int tile_begin = blockIdx.x * 4096U;
    unsigned int tile_end = tile_begin + 4096U;
    long long sum = 0LL;
    for (unsigned int i = tile_begin + tid; i < n && i < tile_end;
         i += blockDim.x) {
        sum += (long long)g_idata[i];
    }
    sdata[tid] = sum;

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

// This kernel is used only for at most 256 already-produced partials.
__global__ void finalize_partials(const long long *g_idata,
                                  unsigned int n,
                                  int *out)
{
    cg::thread_block cta = cg::this_thread_block();
    long long *sdata = SharedMemory<long long>();

    unsigned int tid = threadIdx.x;
    long long sum = 0LL;
    for (unsigned int i = tid; i < n; i += blockDim.x)
        sum += g_idata[i];
    sdata[tid] = sum;

    cg::sync(cta);
    for (unsigned int s = 1; s < blockDim.x; s *= 2) {
        if ((tid % (2 * s)) == 0) {
            sdata[tid] += sdata[tid + s];
        }
        cg::sync(cta);
    }

    if (tid == 0)
        out[0] = (int)sdata[0];
}

#endif

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    if (out == nullptr)
        return;
    if (n == 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }
    if (n < 0 || x == nullptr || (n > 128 && scratch == nullptr))
        return;

    const int *input = (const int *)x;
    if (n <= 128) {
        reduce_input_128<int><<<1, 128, 128 * sizeof(long long)>>>(
            input, (int *)out, (unsigned int)n);
        return;
    }

    const unsigned int input_count = (unsigned int)n;
    const int initial_partials = (int)((input_count + 4095U) / 4096U);
    long long *buffer0 = (long long *)scratch;
    long long *buffer1 = buffer0 + initial_partials;

    reduce_input_4096<<<initial_partials, 128, 128 * sizeof(long long)>>>(
        input, buffer0, input_count);

    // Test an added parallel partial stage before finalization. This lowers
    // the one-CTA cap from 1024 to 256 while retaining the 128-way tree.
    constexpr int finalizer_max_partials = 256;
    int count = initial_partials;
    int current_buffer = 0;
    while (count > finalizer_max_partials) {
        const int next_count = (count + 127) / 128;
        long long *src = current_buffer == 0 ? buffer0 : buffer1;
        long long *dst = current_buffer == 0 ? buffer1 : buffer0;
        reduce0<long long><<<next_count, 128, 128 * sizeof(long long)>>>(
            src, dst, (unsigned int)count);
        current_buffer = 1 - current_buffer;
        count = next_count;
    }

    long long *final_input = current_buffer == 0 ? buffer0 : buffer1;
    finalize_partials<<<1, 128, 128 * sizeof(long long)>>>(
        final_input, (unsigned int)count, (int *)out);
}
