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

namespace {

constexpr int kThreads = 128;
constexpr int kTileSize = 2048;

__device__ __forceinline__ void reduce_block_sum(long long *values)
{
    __syncthreads();
    for (int offset = kThreads / 2; offset > 0; offset >>= 1) {
        if (threadIdx.x < offset) {
            values[threadIdx.x] += values[threadIdx.x + offset];
        }
        __syncthreads();
    }
}

// One CTA handles the complete input for the small-input path.
__global__ void reduce_single(const int *input, int *output, int n)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    long long local_sum = 0;

    for (unsigned long long i = tid; i < static_cast<unsigned int>(n); i += kThreads) {
        local_sum += static_cast<long long>(input[i]);
    }

    sums[tid] = local_sum;
    reduce_block_sum(sums);
    if (tid == 0) {
        output[0] = static_cast<int>(sums[0]);
    }
}

// Each CTA writes one fully initialized, 64-bit partial for a disjoint tile.
__global__ void reduce_tiles(const int *input, long long *partials, int n)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    const unsigned long long begin =
        static_cast<unsigned long long>(blockIdx.x) * kTileSize;
    unsigned long long end = begin + kTileSize;
    if (end > static_cast<unsigned int>(n)) {
        end = static_cast<unsigned int>(n);
    }

    long long local_sum = 0;
    for (unsigned long long i = begin + tid; i < end; i += kThreads) {
        local_sum += static_cast<long long>(input[i]);
    }

    sums[tid] = local_sum;
    reduce_block_sum(sums);
    if (tid == 0) {
        partials[blockIdx.x] = sums[0];
    }
}

// The second pass reduces only the partials written by the first pass.
__global__ void reduce_partials(const long long *partials, int partial_count, int *output)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    long long local_sum = 0;

    for (int i = static_cast<int>(tid); i < partial_count; i += kThreads) {
        local_sum += partials[i];
    }

    sums[tid] = local_sum;
    reduce_block_sum(sums);
    if (tid == 0) {
        output[0] = static_cast<int>(sums[0]);
    }
}

} // namespace

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                     void *scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    const int *input = static_cast<const int *>(x);
    int *output = static_cast<int *>(out);

    if (n <= 0) {
        // The empty sum is zero; enqueue on the same default stream as the kernels.
        cudaMemsetAsync(output, 0, sizeof(int));
        return;
    }
    if (n == 1) {
        cudaMemcpyAsync(output, input, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }
    if (n <= kTileSize) {
        reduce_single<<<1, kThreads>>>(input, output, n);
        return;
    }

    const int partial_count = (n - 1) / kTileSize + 1;
    long long *partials = static_cast<long long *>(scratch);
    reduce_tiles<<<partial_count, kThreads>>>(input, partials, n);
    reduce_partials<<<1, kThreads>>>(partials, partial_count, output);
}
