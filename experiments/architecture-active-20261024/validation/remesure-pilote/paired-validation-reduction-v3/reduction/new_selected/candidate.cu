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

namespace {

constexpr int kThreads = 128;
constexpr int kWarpSize = 32;
constexpr int kWarps = kThreads / kWarpSize;
constexpr int kTileSize = 4096;
constexpr unsigned int kFullWarpMask = 0xffffffffu;

// Map a 32-bit residue to its signed value without an out-of-range cast.
__device__ __forceinline__ int residue_to_int(unsigned int value)
{
    if (value <= 0x7fffffffu) {
        return static_cast<int>(value);
    }
    return -1 - static_cast<int>(~value);
}

// Reduce within each warp, then combine the four exact warp sums in 64 bits.
// The bounded tile ensures each thread and warp sum fits in signed 32 bits.
__device__ __forceinline__ void reduce_warp_sums(int local_sum,
                                                 long long *warp_sums)
{
    const unsigned int tid = threadIdx.x;
    const unsigned int lane = tid & (kWarpSize - 1);
    const unsigned int warp = tid / kWarpSize;
    unsigned int sum = static_cast<unsigned int>(local_sum);

    for (int offset = kWarpSize / 2; offset > 0; offset >>= 1) {
        sum += __shfl_down_sync(kFullWarpMask, sum, offset);
    }

    if (lane == 0) {
        warp_sums[warp] = static_cast<long long>(residue_to_int(sum));
    }
    __syncthreads();
}

__device__ __forceinline__ long long combine_warp_sums(const long long *warp_sums)
{
    return warp_sums[0] + warp_sums[1] + warp_sums[2] + warp_sums[3];
}

// One CTA handles the complete input for the small-input path.
__global__ void reduce_single(const int *input, int *output, int n)
{
    __shared__ long long warp_sums[kWarps];
    const unsigned int tid = threadIdx.x;
    int local_sum = 0;

    for (unsigned long long i = tid; i < static_cast<unsigned int>(n); i += kThreads) {
        local_sum += input[i];
    }

    reduce_warp_sums(local_sum, warp_sums);
    if (tid == 0) {
        output[0] = static_cast<int>(combine_warp_sums(warp_sums));
    }
}

// Each CTA writes one fully initialized, 64-bit partial for a disjoint tile.
__global__ void reduce_tiles(const int *input, long long *partials, int n)
{
    __shared__ long long warp_sums[kWarps];
    const unsigned int tid = threadIdx.x;
    const unsigned long long begin =
        static_cast<unsigned long long>(blockIdx.x) * kTileSize;
    unsigned long long end = begin + kTileSize;
    if (end > static_cast<unsigned int>(n)) {
        end = static_cast<unsigned int>(n);
    }

    int local_sum = 0;
    for (unsigned long long i = begin + tid; i < end; i += kThreads) {
        local_sum += input[i];
    }

    reduce_warp_sums(local_sum, warp_sums);
    if (tid == 0) {
        partials[blockIdx.x] = combine_warp_sums(warp_sums);
    }
}

// The final pass uses 64-bit sums for exact accumulation of all partials.
__global__ void reduce_partials(const long long *partials,
                                int partial_count,
                                int *output)
{
    __shared__ long long sums[kThreads];
    const unsigned int tid = threadIdx.x;
    long long local_sum = 0;

    for (int i = static_cast<int>(tid); i < partial_count; i += kThreads) {
        local_sum += partials[i];
    }

    sums[tid] = local_sum;
    __syncthreads();
    for (int offset = kThreads / 2; offset > 0; offset >>= 1) {
        if (tid < static_cast<unsigned int>(offset)) {
            sums[tid] += sums[tid + offset];
        }
        __syncthreads();
    }

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
