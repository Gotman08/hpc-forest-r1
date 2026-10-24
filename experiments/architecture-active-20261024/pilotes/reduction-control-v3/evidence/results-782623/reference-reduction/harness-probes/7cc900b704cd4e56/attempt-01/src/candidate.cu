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
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the distribution.
 *  * Neither the name of NVIDIA CORPORATION nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
 * EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
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

// Each resident CTA computes a grid-stride partial. The cooperative grid
// barrier makes every partial visible before CTA 0 performs the final sum.
__global__ void cooperativeReduce(const int *input, unsigned int *partials,
                                  int *output, int n)
{
    cg::grid_group grid = cg::this_grid();
    const unsigned int tid = threadIdx.x;
    __shared__ unsigned int sdata[128];

    unsigned int localSum = 0;
    const size_t limit = (size_t)n;
    const size_t stride = (size_t)blockDim.x * (size_t)gridDim.x;
    for (size_t i = (size_t)blockIdx.x * (size_t)blockDim.x + tid;
         i < limit; i += stride) {
        // Unsigned addition gives defined modulo-2^32 intermediates; for a
        // representable int result this preserves the exact result bit pattern.
        localSum += (unsigned int)input[i];
    }

    sdata[tid] = localSum;
    __syncthreads();
    for (unsigned int offset = 64; offset > 0; offset >>= 1) {
        if (tid < offset)
            sdata[tid] += sdata[tid + offset];
        __syncthreads();
    }

    // A one-block grid writes directly and does not require scratch storage.
    if (gridDim.x > 1 && tid == 0)
        partials[blockIdx.x] = sdata[0];

    grid.sync();

    if (blockIdx.x == 0) {
        if (gridDim.x == 1) {
            if (tid == 0)
                output[0] = __uint_as_int(sdata[0]);
        } else {
            unsigned int total = 0;
            for (unsigned int i = tid; i < gridDim.x; i += blockDim.x)
                total += partials[i];
            sdata[tid] = total;
            __syncthreads();
            for (unsigned int offset = 64; offset > 0; offset >>= 1) {
                if (tid < offset)
                    sdata[tid] += sdata[tid + offset];
                __syncthreads();
            }
            if (tid == 0)
                output[0] = __uint_as_int(sdata[0]);
        }
    }
}

__global__ void writeZero(int *output)
{
    if (threadIdx.x == 0)
        output[0] = 0;
}

#endif

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    if (n <= 0) {
        writeZero<<<1, 1>>>((int *)out);
        return;
    }

    int device = 0;
    cudaDeviceProp prop;
    int activeBlocksPerSM = 0;
    bool canLaunchCooperatively =
        cudaGetDevice(&device) == cudaSuccess &&
        cudaGetDeviceProperties(&prop, device) == cudaSuccess &&
        prop.cooperativeLaunch != 0 &&
        cudaOccupancyMaxActiveBlocksPerMultiprocessor(
            &activeBlocksPerSM, cooperativeReduce, 128, 0) == cudaSuccess &&
        activeBlocksPerSM > 0;

    if (canLaunchCooperatively) {
        // Keep the entire grid within the number of simultaneously resident
        // blocks so grid.sync() cannot wait for unscheduled CTAs.
        const int maxGridBlocks = activeBlocksPerSM * prop.multiProcessorCount;
        const int neededBlocks = n / 128 + (n % 128 != 0);
        const int gridBlocks = neededBlocks < maxGridBlocks ? neededBlocks : maxGridBlocks;

        if (gridBlocks > 0) {
            const int *deviceInput = (const int *)x;
            unsigned int *devicePartials = (unsigned int *)scratch;
            int *deviceOutput = (int *)out;
            void *kernelArgs[] = {&deviceInput, &devicePartials, &deviceOutput, &n};
            cudaError_t launchStatus = cudaLaunchCooperativeKernel(
                (void *)cooperativeReduce, dim3(gridBlocks), dim3(128),
                kernelArgs, 0, 0);
            if (launchStatus == cudaSuccess)
                return;
            // The fallback handles runtimes/devices that reject this launch.
            (void)cudaGetLastError();
        }
    }

    // Preserve the original multi-kernel path if cooperative launch support
    // or the actual launch is unavailable.
    int count = n;
    int *input = (int *)x;
    bool flip = false;
    while (count > 1) {
        int blocks = count / 128 + (count % 128 != 0);
        int *dest = flip ? (int *)scratch + n + 32768 : (int *)scratch;
        reduce0<int><<<blocks, 128, 128 * sizeof(int)>>>(input, dest, count);
        input = dest;
        count = blocks;
        flip = !flip;
    }
    cudaMemcpyAsync(out, input, sizeof(int), cudaMemcpyDeviceToDevice);
}
