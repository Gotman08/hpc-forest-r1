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
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
 * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
 * OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

// Map a modulo-2^32 sum to its signed representative using only an in-range cast.
static __device__ __forceinline__ int fromUnsignedBits(unsigned int bits)
{
    if (bits <= 0x7fffffffU) return static_cast<int>(bits);
    return static_cast<int>(static_cast<long long>(bits) - 0x100000000LL);
}

// Reduce 128 values: first within each warp, then combine the four warp totals.
__global__ void reduceWarpFirst(const int *input, int *output, unsigned int n)
{
    __shared__ unsigned int warpSums[4];

    const unsigned int tid = threadIdx.x;
    const unsigned int lane = tid & 31U;
    const unsigned int warp = tid >> 5;
    const unsigned int index = blockIdx.x * 128U + tid;

    unsigned int sum = index < n ? static_cast<unsigned int>(input[index]) : 0U;
    for (unsigned int offset = 16U; offset != 0U; offset >>= 1U)
        sum += __shfl_down_sync(0xffffffffU, sum, offset);

    if (lane == 0U) warpSums[warp] = sum;
    __syncthreads();

    // One lane serially combines the four warp totals, avoiding a second tree.
    if (tid == 0U) {
        const unsigned int total = warpSums[0] + warpSums[1] +
                                   warpSums[2] + warpSums[3];
        output[blockIdx.x] = fromUnsignedBits(total);
    }
}

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }

    int count = n;
    const int *input = static_cast<const int *>(x);
    int *scratchBase = static_cast<int *>(scratch);
    bool flip = false;

    while (count > 1) {
        const int blocks = 1 + (count - 1) / 128;
        int *dest = flip ? scratchBase + n + 32768 : scratchBase;
        reduceWarpFirst<<<blocks, 128>>>(input, dest, static_cast<unsigned int>(count));
        input = dest;
        count = blocks;
        flip = !flip;
    }

    cudaMemcpyAsync(out, input, sizeof(int), cudaMemcpyDeviceToDevice);
}
