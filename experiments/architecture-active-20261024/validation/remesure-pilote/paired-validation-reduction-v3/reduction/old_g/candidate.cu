#include <cuda_runtime.h>
#include <algorithm>
#include <stdint.h>
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
    Parallel sum reduction using one warp per 128-element tile.
    Each lane loads four consecutive values as two int2 vectors when aligned
    and in bounds, while separate register sums provide independent add chains.
*/
template <class T> __global__ void reduce0(T *g_idata, T *g_odata, unsigned int n)
{
    const unsigned int tid = threadIdx.x;
    const unsigned int base = blockIdx.x * 128u + tid * 4u;
    T sum0 = 0;
    T sum1 = 0;

    if (base + 3u < n &&
        (reinterpret_cast<uintptr_t>(g_idata + base) & (uintptr_t)7u) == 0u) {
        const int2 *pairs = reinterpret_cast<const int2 *>(g_idata + base);
        const int2 first = pairs[0];
        const int2 second = pairs[1];
        sum0 = (T)(first.x + second.x);
        sum1 = (T)(first.y + second.y);
    } else {
        if (base < n)      sum0 += g_idata[base];
        if (base + 1u < n) sum1 += g_idata[base + 1u];
        if (base + 2u < n) sum0 += g_idata[base + 2u];
        if (base + 3u < n) sum1 += g_idata[base + 3u];
    }

    T laneSum = sum0 + sum1;
    laneSum = warpReduceSum<int>(0xffffffffu, laneSum);
    if (tid == 0)
        g_odata[blockIdx.x] = laneSum;
}

#endif
extern "C" void run(const void *x, const void *k, const void *gy,
                    void *out, void *scratch, int n, int h, int l, int ks)
{
    int count = n;
    int *input = (int *)x;
    bool flip = false;

    if (count <= 1) {
        cudaMemcpyAsync(out, input, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    while (count > 1) {
        int blocks = (count - 1) / 128 + 1;
        int *dest;

        if (blocks == 1) {
            // The final CTA writes directly to the result, avoiding a copy.
            dest = (int *)out;
        } else if (flip) {
            dest = (int *)scratch + n + 32768;
        } else {
            dest = (int *)scratch;
        }

        reduce0<int><<<blocks, 32, 0>>>(input, dest, count);

        if (blocks == 1)
            return;

        input = dest;
        count = blocks;
        flip = !flip;
    }
}
