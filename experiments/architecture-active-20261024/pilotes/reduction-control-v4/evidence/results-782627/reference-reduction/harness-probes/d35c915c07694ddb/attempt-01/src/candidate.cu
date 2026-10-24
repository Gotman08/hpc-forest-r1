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

#ifndef _REDUCE_KERNEL_H_
#define _REDUCE_KERNEL_H_

#include <cooperative_groups.h>
#include <cooperative_groups/reduce.h>
#include <stdio.h>

namespace cg = cooperative_groups;

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

template <> struct SharedMemory<double>
{
    __device__ inline operator double *()
    {
        extern __shared__ double __smem_d[];
        return __smem_d;
    }

    __device__ inline operator const double *() const
    {
        extern __shared__ double __smem_d[];
        return __smem_d;
    }
};

template <> struct SharedMemory<long long>
{
    __device__ inline operator long long *()
    {
        extern __shared__ long long __smem_ll[];
        return __smem_ll;
    }

    __device__ inline operator const long long *() const
    {
        extern __shared__ long long __smem_ll[];
        return __smem_ll;
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
template <> __device__ __forceinline__ int warpReduceSum<int>(unsigned int mask, int mySum)
{
    mySum = __reduce_add_sync(mask, mySum);
    return mySum;
}
#endif

/* The baseline shared-memory tree is retained; InputT permits exact int64
   accumulation while reading the original int input directly. */
template <class T, class InputT = T>
__global__ void reduce0(const InputT *g_idata, T *g_odata, unsigned int n)
{
    cg::thread_block cta = cg::this_thread_block();
    T *sdata = SharedMemory<T>();

    unsigned int tid = threadIdx.x;
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    sdata[tid] = (i < n) ? static_cast<T>(g_idata[i]) : T(0);

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

/* One-tile case: use the same tree and narrow only after its int64 total. */
__global__ void reduceDirect(const int *input, int *output, unsigned int n)
{
    cg::thread_block cta = cg::this_thread_block();
    long long *sdata = SharedMemory<long long>();

    unsigned int tid = threadIdx.x;
    unsigned int i = threadIdx.x;
    sdata[tid] = (i < n) ? static_cast<long long>(input[i]) : 0LL;

    cg::sync(cta);
    for (unsigned int s = 1; s < blockDim.x; s *= 2) {
        if ((tid % (2 * s)) == 0) {
            sdata[tid] += sdata[tid + s];
        }
        cg::sync(cta);
    }

    if (tid == 0)
        *output = static_cast<int>(sdata[0]);
}

/* Finalize a bounded number of partials in one CTA and write directly to out. */
__global__ void finalizePartials(const long long *partials, unsigned int count, int *output)
{
    cg::thread_block cta = cg::this_thread_block();
    long long *sdata = SharedMemory<long long>();

    unsigned int tid = threadIdx.x;
    long long local = 0;
    for (unsigned int i = tid; i < count; i += blockDim.x)
        local += partials[i];
    sdata[tid] = local;

    cg::sync(cta);
    for (unsigned int s = 1; s < blockDim.x; s *= 2) {
        if ((tid % (2 * s)) == 0) {
            sdata[tid] += sdata[tid + s];
        }
        cg::sync(cta);
    }

    if (tid == 0)
        *output = static_cast<int>(sdata[0]);
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

    if (out == nullptr || n < 0)
        return;
    if (n == 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }
    if (x == nullptr)
        return;

    const int *input = static_cast<const int *>(x);
    int *output = static_cast<int *>(out);

    if (n == 1) {
        cudaMemcpyAsync(output, input, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }
    if (n <= 128) {
        reduceDirect<<<1, 128, 128 * sizeof(long long)>>>(input, output,
                                                          static_cast<unsigned int>(n));
        return;
    }
    if (scratch == nullptr)
        return;

    // Keep the baseline's 128-input tile. Two packed ping-pong arrays fit
    // within the supplied scratch space used by the existing hierarchy.
    int partialCount = (n - 1) / 128 + 1;
    long long *buffer0 = static_cast<long long *>(scratch);
    long long *buffer1 = buffer0 + partialCount;
    long long *current = buffer0;
    long long *next = buffer1;

    reduce0<long long, int><<<partialCount, 128, 128 * sizeof(long long)>>>(
        input, current, static_cast<unsigned int>(n));

    // Use a parallel stage whenever finalizing the current partial array
    // would require more than eight values per thread in the final CTA.
    while (partialCount > 1024) {
        int nextCount = (partialCount - 1) / 128 + 1;
        reduce0<long long, long long><<<nextCount, 128, 128 * sizeof(long long)>>>(
            current, next, static_cast<unsigned int>(partialCount));
        long long *oldCurrent = current;
        current = next;
        next = oldCurrent;
        partialCount = nextCount;
    }

    finalizePartials<<<1, 128, 128 * sizeof(long long)>>>(
        current, static_cast<unsigned int>(partialCount), output);
}
