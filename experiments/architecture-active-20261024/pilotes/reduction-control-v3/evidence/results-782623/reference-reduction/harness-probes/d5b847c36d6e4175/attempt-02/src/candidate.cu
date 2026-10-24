#include <cuda_runtime.h>
#include <cooperative_groups.h>
#include <stddef.h>

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
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

namespace cg = cooperative_groups;

__device__ __forceinline__ int moduloUnsignedToInt(unsigned int value)
{
    if (value <= 0x7fffffffU)
        return (int)value;
    return (int)((long long)value - 0x100000000LL);
}

__global__ void reduceUnsigned(const unsigned int *input,
                               unsigned int *partials, unsigned int n)
{
    __shared__ unsigned int values[128];
    const unsigned int tid = threadIdx.x;
    const unsigned int index = blockIdx.x * blockDim.x + tid;
    values[tid] = index < n ? input[index] : 0U;
    __syncthreads();

    for (unsigned int stride = 1; stride < blockDim.x; stride <<= 1) {
        if ((tid % (2U * stride)) == 0)
            values[tid] += values[tid + stride];
        __syncthreads();
    }

    if (tid == 0)
        partials[blockIdx.x] = values[0];
}

__global__ void cooperativeReduce(const int *input, unsigned int *partials,
                                  int *output, int n)
{
    cg::grid_group grid = cg::this_grid();
    const unsigned int tid = threadIdx.x;
    __shared__ unsigned int values[128];

    unsigned int localSum = 0U;
    const size_t limit = (size_t)n;
    const size_t gridStride = (size_t)blockDim.x * (size_t)gridDim.x;
    for (size_t i = (size_t)blockIdx.x * (size_t)blockDim.x + tid;
         i < limit; i += gridStride)
        localSum += (unsigned int)input[i];

    values[tid] = localSum;
    __syncthreads();
    for (unsigned int offset = 64; offset > 0; offset >>= 1) {
        if (tid < offset)
            values[tid] += values[tid + offset];
        __syncthreads();
    }

    if (gridDim.x > 1 && tid == 0)
        partials[blockIdx.x] = values[0];

    grid.sync();

    if (blockIdx.x == 0) {
        if (gridDim.x == 1) {
            if (tid == 0)
                output[0] = moduloUnsignedToInt(values[0]);
        } else {
            unsigned int total = 0U;
            for (unsigned int i = tid; i < gridDim.x; i += blockDim.x)
                total += partials[i];
            values[tid] = total;
            __syncthreads();
            for (unsigned int offset = 64; offset > 0; offset >>= 1) {
                if (tid < offset)
                    values[tid] += values[tid + offset];
                __syncthreads();
            }
            if (tid == 0)
                output[0] = moduloUnsignedToInt(values[0]);
        }
    }
}

__global__ void writeZero(int *output)
{
    if (threadIdx.x == 0)
        output[0] = 0;
}

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    if (n <= 0) {
        writeZero<<<1, 1>>>((int *)out);
        return;
    }

    const int cooperativeThreshold = 1 << 20;
    if (n >= cooperativeThreshold) {
        int device = 0;
        cudaDeviceProp prop;
        int activeBlocksPerSM = 0;
        const bool canLaunchCooperatively =
            cudaGetDevice(&device) == cudaSuccess &&
            cudaGetDeviceProperties(&prop, device) == cudaSuccess &&
            prop.cooperativeLaunch != 0 &&
            cudaOccupancyMaxActiveBlocksPerMultiprocessor(
                &activeBlocksPerSM, cooperativeReduce, 128, 0) == cudaSuccess &&
            activeBlocksPerSM > 0;

        if (canLaunchCooperatively) {
            // Cap the grid below the occupancy limit to reduce barrier participants.
            const int blocksPerSM = activeBlocksPerSM < 4 ? activeBlocksPerSM : 4;
            const int maxGridBlocks = blocksPerSM * prop.multiProcessorCount;
            const int neededBlocks = n / 128 + (n % 128 != 0);
            const int gridBlocks = neededBlocks < maxGridBlocks
                                       ? neededBlocks
                                       : maxGridBlocks;

            if (gridBlocks > 0) {
                const int *deviceInput = (const int *)x;
                unsigned int *devicePartials = (unsigned int *)scratch;
                int *deviceOutput = (int *)out;
                void *kernelArgs[] = {
                    &deviceInput, &devicePartials, &deviceOutput, &n
                };
                const cudaError_t launchStatus = cudaLaunchCooperativeKernel(
                    (void *)cooperativeReduce, dim3(gridBlocks), dim3(128),
                    kernelArgs, 0, 0);
                if (launchStatus == cudaSuccess)
                    return;
                (void)cudaGetLastError();
            }
        }
    }

    // Unsigned additions keep every reduction stage exact modulo 2^32.
    int count = n;
    const unsigned int *input = (const unsigned int *)x;
    bool flip = false;
    while (count > 1) {
        const int blocks = count / 128 + (count % 128 != 0);
        unsigned int *dest = flip
                                 ? (unsigned int *)scratch + (size_t)n + 32768U
                                 : (unsigned int *)scratch;
        reduceUnsigned<<<blocks, 128>>>(input, dest, (unsigned int)count);
        input = dest;
        count = blocks;
        flip = !flip;
    }
    cudaMemcpyAsync(out, input, sizeof(unsigned int), cudaMemcpyDeviceToDevice);
}
