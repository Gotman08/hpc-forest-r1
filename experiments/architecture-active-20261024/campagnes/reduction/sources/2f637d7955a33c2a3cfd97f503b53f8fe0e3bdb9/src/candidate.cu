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

#include <cuda_runtime.h>

#define REDUCE_BLOCK_SIZE 256u
#define REDUCE_WARP_SIZE 32u
#define REDUCE_NUM_WARPS (REDUCE_BLOCK_SIZE / REDUCE_WARP_SIZE)
#define REDUCE_TILE_SIZE (REDUCE_BLOCK_SIZE * 32u)
#define REDUCE_MAX_PARTIALS 2048u
#define REDUCE_DIRECT_FINAL_MAX 256u

__device__ __forceinline__ int reduce_block_sum(int value, int *warp_sums)
{
    const unsigned int lane = threadIdx.x & (REDUCE_WARP_SIZE - 1u);
    const unsigned int warp = threadIdx.x / REDUCE_WARP_SIZE;

    for (int offset = REDUCE_WARP_SIZE / 2; offset > 0; offset >>= 1) {
        value += __shfl_down_sync(0xffffffffu, value, offset);
    }

    if (lane == 0u) {
        warp_sums[warp] = value;
    }
    __syncthreads();

    if (warp == 0u) {
        value = lane < REDUCE_NUM_WARPS ? warp_sums[lane] : 0;
        for (int offset = REDUCE_WARP_SIZE / 2; offset > 0; offset >>= 1) {
            value += __shfl_down_sync(0xffffffffu, value, offset);
        }
        return value;
    }
    return 0;
}

__global__ void reduce_one_block(const int *input, unsigned int count, int *output)
{
    __shared__ int warp_sums[REDUCE_NUM_WARPS];

    int sum = 0;
    for (unsigned int i = threadIdx.x; i < count; i += blockDim.x) {
        sum += input[i];
    }

    const int total = reduce_block_sum(sum, warp_sums);
    if (threadIdx.x == 0u) {
        output[0] = total;
    }
}

__global__ void reduce_input_tiles(const int *input,
                                   int *partials,
                                   unsigned int count,
                                   unsigned int tile_count)
{
    __shared__ int warp_sums[REDUCE_NUM_WARPS];

    int sum = 0;
    for (unsigned int tile = blockIdx.x; tile < tile_count; tile += gridDim.x) {
        const unsigned int tile_base = tile * REDUCE_TILE_SIZE;
        #pragma unroll
        for (unsigned int segment = 0; segment < 32u; ++segment) {
            const unsigned int index = tile_base + segment * REDUCE_BLOCK_SIZE + threadIdx.x;
            if (index < count) {
                sum += input[index];
            }
        }
    }

    const int total = reduce_block_sum(sum, warp_sums);
    if (threadIdx.x == 0u) {
        partials[blockIdx.x] = total;
    }
}

__global__ void reduce_partial_groups(const int *partials,
                                      int *grouped_partials,
                                      unsigned int partial_count)
{
    __shared__ int warp_sums[REDUCE_NUM_WARPS];

    const unsigned int index = blockIdx.x * blockDim.x + threadIdx.x;
    const int value = index < partial_count ? partials[index] : 0;
    const int total = reduce_block_sum(value, warp_sums);
    if (threadIdx.x == 0u) {
        grouped_partials[blockIdx.x] = total;
    }
}

__global__ void reduce_partials_to_output(const int *partials,
                                          unsigned int partial_count,
                                          int *output)
{
    __shared__ int warp_sums[REDUCE_NUM_WARPS];

    int sum = 0;
    for (unsigned int i = threadIdx.x; i < partial_count; i += blockDim.x) {
        sum += partials[i];
    }

    const int total = reduce_block_sum(sum, warp_sums);
    if (threadIdx.x == 0u) {
        output[0] = total;
    }
}

extern "C" void run(const void *x,
                    const void *,
                    const void *,
                    void *out,
                    void *scratch,
                    int n,
                    int,
                    int,
                    int)
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

    const int *input = static_cast<const int *>(x);
    const unsigned int count = static_cast<unsigned int>(n);
    if (count <= REDUCE_TILE_SIZE) {
        reduce_one_block<<<1, REDUCE_BLOCK_SIZE>>>(input, count, output);
        return;
    }

    unsigned int tile_count = (count + REDUCE_TILE_SIZE - 1u) / REDUCE_TILE_SIZE;
    unsigned int block_count = tile_count;
    if (block_count > REDUCE_MAX_PARTIALS) {
        block_count = REDUCE_MAX_PARTIALS;
    }

    int *partials = static_cast<int *>(scratch);
    reduce_input_tiles<<<block_count, REDUCE_BLOCK_SIZE>>>(input, partials, count, tile_count);

    if (block_count <= REDUCE_DIRECT_FINAL_MAX) {
        reduce_partials_to_output<<<1, REDUCE_BLOCK_SIZE>>>(partials, block_count, output);
        return;
    }

    const unsigned int group_count =
        (block_count + REDUCE_BLOCK_SIZE - 1u) / REDUCE_BLOCK_SIZE;
    int *grouped_partials = partials + REDUCE_MAX_PARTIALS;
    reduce_partial_groups<<<group_count, REDUCE_BLOCK_SIZE>>>(partials,
                                                              grouped_partials,
                                                              block_count);
    reduce_partials_to_output<<<1, REDUCE_BLOCK_SIZE>>>(grouped_partials,
                                                         group_count,
                                                         output);
}
