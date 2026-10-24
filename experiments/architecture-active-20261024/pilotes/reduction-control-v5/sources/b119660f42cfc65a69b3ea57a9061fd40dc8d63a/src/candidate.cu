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
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
 * THE POSSIBILITY OF SUCH DAMAGE.
 */

#ifndef _REDUCE_KERNEL_H_
#define _REDUCE_KERNEL_H_

#include <cooperative_groups.h>
#include <cooperative_groups/reduce.h>

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
template <> __device__ __forceinline__ int warpReduceSum<int>(unsigned int mask, int mySum)
{
    return __reduce_add_sync(mask, mySum);
}
#endif

// Retain the original small-input reduction path to avoid adding a memset
// and a second launch where the tiled paths are not intended to be tested.
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

enum { BLOCK_THREADS = 256 };

// Each warp reduces its values with warp operations; one shared-memory value
// per warp is then reduced by the first warp.
__device__ __forceinline__ int reduceBlockSum(int value, int *warp_sums)
{
    const unsigned int lane = threadIdx.x & 31;
    const unsigned int warp = threadIdx.x >> 5;
    const unsigned int full_warp_mask = 0xffffffffu;

    value = warpReduceSum<int>(full_warp_mask, value);
    if (lane == 0)
        warp_sums[warp] = value;
    __syncthreads();

    if (warp == 0) {
        const int warp_count = (blockDim.x + 31) / 32;
        int warp_value = (lane < warp_count) ? warp_sums[lane] : 0;
        warp_value = warpReduceSum<int>(full_warp_mask, warp_value);
        if (lane == 0)
            return warp_value;
    }
    return 0;
}

template <int TILE, bool USE_ATOMIC>
__global__ void reduceTile(const int *input, int *result, int n)
{
    __shared__ int warp_sums[BLOCK_THREADS / 32];

    const size_t begin = static_cast<size_t>(blockIdx.x) * TILE;
    size_t end = begin + TILE;
    if (end > static_cast<size_t>(n))
        end = static_cast<size_t>(n);

    int local_sum = 0;
    for (size_t i = begin + threadIdx.x; i < end; i += blockDim.x)
        local_sum += input[i];

    const int block_sum = reduceBlockSum(local_sum, warp_sums);
    if (threadIdx.x == 0) {
        if (USE_ATOMIC)
            atomicAdd(result, block_sum);
        else
            result[blockIdx.x] = block_sum;
    }
}

__global__ void finishPartials(const int *partials, int partial_count, int *output)
{
    __shared__ int warp_sums[BLOCK_THREADS / 32];

    int local_sum = 0;
    for (int i = threadIdx.x; i < partial_count; i += blockDim.x)
        local_sum += partials[i];

    const int total = reduceBlockSum(local_sum, warp_sums);
    if (threadIdx.x == 0)
        output[0] = total;
}

template <int TILE, bool USE_ATOMIC>
static void launchTiledPath(const int *input, int *output, int *scratch, int n)
{
    const int blocks = (n - 1) / TILE + 1;
    int *first_pass_output = USE_ATOMIC ? output : scratch;

    if (USE_ATOMIC)
        cudaMemsetAsync(output, 0, sizeof(int));

    reduceTile<TILE, USE_ATOMIC><<<blocks, BLOCK_THREADS>>>(input, first_pass_output, n);

    if (!USE_ATOMIC)
        finishPartials<<<1, BLOCK_THREADS>>>(scratch, blocks, output);
}

#endif

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    int *output = static_cast<int *>(out);

    if (n <= 0) {
        cudaMemsetAsync(output, 0, sizeof(int));
        return;
    }
    if (n == 1) {
        cudaMemcpyAsync(output, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    if (n < 4096) {
        int count = n;
        int *input = const_cast<int *>(static_cast<const int *>(x));
        int *workspace = static_cast<int *>(scratch);
        bool flip = false;
        while (count > 1) {
            const int blocks = (count + 127) / 128;
            int *dest = flip ? workspace + n + 32768 : workspace;
            reduce0<int><<<blocks, 128, 128 * sizeof(int)>>>(input, dest, count);
            input = dest;
            count = blocks;
            flip = !flip;
        }
        cudaMemcpyAsync(output, input, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    // Sweep CTA tiles in the atomic path. The middle-size control uses the
    // identical 1024-element tile mapping, but writes partials and finalizes
    // them in a second kernel instead of initializing and atomically updating
    // the output.
    if (n < 32768) {
        launchTiledPath<256, true>(static_cast<const int *>(x), output,
                                   static_cast<int *>(scratch), n);
    } else if (n < 65536) {
        launchTiledPath<1024, true>(static_cast<const int *>(x), output,
                                    static_cast<int *>(scratch), n);
    } else if (n < 1048576) {
        launchTiledPath<1024, false>(static_cast<const int *>(x), output,
                                     static_cast<int *>(scratch), n);
    } else {
        launchTiledPath<4096, true>(static_cast<const int *>(x), output,
                                    static_cast<int *>(scratch), n);
    }
}
