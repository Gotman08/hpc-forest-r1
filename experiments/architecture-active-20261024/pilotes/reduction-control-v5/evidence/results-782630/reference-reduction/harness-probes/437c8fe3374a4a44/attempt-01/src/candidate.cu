#include <cuda_runtime.h>

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

template <int BLOCK, int ITEMS, bool ATOMIC>
__global__ void reduce_tiles(const int *input, int *output, int n)
{
    __shared__ int sums[BLOCK];
    const unsigned int tid = threadIdx.x;
    const unsigned int base = blockIdx.x * (unsigned int)(BLOCK * ITEMS);
    int value = 0;

    #pragma unroll
    for (int item = 0; item < ITEMS; ++item) {
        const unsigned int index = base + (unsigned int)(item * BLOCK) + tid;
        if (index < (unsigned int)n)
            value += input[index];
    }

    sums[tid] = value;
    __syncthreads();

    for (int stride = BLOCK / 2; stride > 0; stride >>= 1) {
        if (tid < (unsigned int)stride)
            sums[tid] += sums[tid + stride];
        __syncthreads();
    }

    if (tid == 0) {
        if (ATOMIC)
            atomicAdd(output, sums[0]);
        else
            output[blockIdx.x] = sums[0];
    }
}

template <int BLOCK>
__global__ void finish_partials(const int *partials, int count, int *output)
{
    __shared__ int sums[BLOCK];
    const unsigned int tid = threadIdx.x;
    int value = 0;

    for (int index = (int)tid; index < count; index += BLOCK)
        value += partials[index];

    sums[tid] = value;
    __syncthreads();

    for (int stride = BLOCK / 2; stride > 0; stride >>= 1) {
        if (tid < (unsigned int)stride)
            sums[tid] += sums[tid + stride];
        __syncthreads();
    }

    if (tid == 0)
        output[0] = sums[0];
}

extern "C" void run(const void *x, const void *k, const void *gy,
                    void *out, void *scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    const int *input = (const int *)x;
    int *output = (int *)out;

    if (n <= 0) {
        cudaMemsetAsync(output, 0, sizeof(int));
        return;
    }

    if (n == 1) {
        cudaMemcpyAsync(output, input, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    // Small-input two-kernel control: the first pass uses the same 128-item
    // tile mapping as the smallest atomic configuration.
    if (n < 1024) {
        const int blocks = n / 128 + (n % 128 != 0);
        reduce_tiles<128, 1, false><<<blocks, 128>>>(
            input, (int *)scratch, n);
        finish_partials<128><<<1, 128>>>((const int *)scratch, blocks, output);
        return;
    }

    // Sweep CTA tile sizes across input scales: 128, 512, and 2048 elements.
    // The memset and subsequent kernel launch use the default stream.
    cudaMemsetAsync(output, 0, sizeof(int));
    if (n < 8192) {
        const int blocks = n / 128 + (n % 128 != 0);
        reduce_tiles<128, 1, true><<<blocks, 128>>>(input, output, n);
    } else if (n < 262144) {
        const int tile = 128 * 4;
        const int blocks = n / tile + (n % tile != 0);
        reduce_tiles<128, 4, true><<<blocks, 128>>>(input, output, n);
    } else {
        const int tile = 128 * 16;
        const int blocks = n / tile + (n % tile != 0);
        reduce_tiles<128, 16, true><<<blocks, 128>>>(input, output, n);
    }
}
