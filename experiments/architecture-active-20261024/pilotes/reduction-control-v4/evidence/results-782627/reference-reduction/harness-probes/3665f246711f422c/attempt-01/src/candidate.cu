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
    Parallel sum reduction using warp shuffles and one shared warp-partial
    exchange. Each block retains the 128-thread, one-input-per-lane mapping.
*/
template <class Input, class Output>
__global__ void reduce0(const Input *g_idata, Output *g_odata, unsigned int n)
{
    __shared__ long long warp_sums[4];

    unsigned int tid = threadIdx.x;
    unsigned int i = blockIdx.x * blockDim.x + tid;
    long long value = (i < n) ? static_cast<long long>(g_idata[i]) : 0LL;

    const unsigned int mask = 0xffffffffu;
    value = warpReduceSum<long long>(mask, value);

    unsigned int lane = tid & 31u;
    unsigned int warp = tid >> 5;
    if (lane == 0)
        warp_sums[warp] = value;

    __syncthreads();

    if (warp == 0) {
        value = (lane < 4) ? warp_sums[lane] : 0LL;
        value += __shfl_down_sync(mask, value, 2);
        value += __shfl_down_sync(mask, value, 1);
        if (lane == 0)
            g_odata[blockIdx.x] = static_cast<Output>(value);
    }
}

#endif
extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    if (n == 1) {
        cudaMemcpyAsync(out, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    unsigned int count = static_cast<unsigned int>(n);
    unsigned int max_blocks = (count + 127u) / 128u;
    long long *buffer0 = static_cast<long long *>(scratch);
    long long *buffer1 = buffer0 + max_blocks;
    const int *input32 = static_cast<const int *>(x);
    const long long *input64 = 0;
    bool input_is_wide = false;

    while (count > 1) {
        unsigned int blocks = (count + 127u) / 128u;

        if (blocks == 1) {
            if (input_is_wide) {
                long long *target = (input64 == buffer0) ? buffer1 : buffer0;
                int *result = reinterpret_cast<int *>(target);
                reduce0<long long, int><<<blocks, 128>>>(input64, result, count);
                cudaMemcpyAsync(out, result, sizeof(int), cudaMemcpyDeviceToDevice);
            } else {
                int *result = reinterpret_cast<int *>(buffer0);
                reduce0<int, int><<<blocks, 128>>>(input32, result, count);
                cudaMemcpyAsync(out, result, sizeof(int), cudaMemcpyDeviceToDevice);
            }
            return;
        }

        long long *target;
        if (input_is_wide)
            target = (input64 == buffer0) ? buffer1 : buffer0;
        else
            target = buffer0;

        if (input_is_wide)
            reduce0<long long, long long><<<blocks, 128>>>(input64, target, count);
        else
            reduce0<int, long long><<<blocks, 128>>>(input32, target, count);

        input64 = target;
        input_is_wide = true;
        count = blocks;
    }
}
