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

// Convert a modulo-2^32 residue to its corresponding signed int without
// converting an out-of-range unsigned value to a signed value.
__device__ __forceinline__ int residue_to_int(unsigned int residue)
{
    if (residue <= 0x7fffffffu) {
        return static_cast<int>(residue);
    }
    return -1 - static_cast<int>(~residue);
}

// Reduce one 128-element tile: first within each warp, then across the four
// warp totals using a two-step XOR butterfly in warp zero.
__global__ void reduce_warp_xor(const int *input, int *output, unsigned int n)
{
    const unsigned int tid = threadIdx.x;
    const unsigned int index = blockIdx.x * blockDim.x + tid;
    unsigned int value = index < n ? static_cast<unsigned int>(input[index]) : 0u;

    for (unsigned int offset = warpSize / 2; offset > 0; offset >>= 1) {
        value += __shfl_down_sync(0xffffffffu, value, offset);
    }

    __shared__ unsigned int warp_sums[4];
    const unsigned int lane = tid & 31u;
    const unsigned int warp = tid >> 5;
    if (lane == 0) {
        warp_sums[warp] = value;
    }
    __syncthreads();

    if (warp == 0) {
        unsigned int total = lane < 4u ? warp_sums[lane] : 0u;
        total += __shfl_xor_sync(0xffffffffu, total, 1);
        total += __shfl_xor_sync(0xffffffffu, total, 2);
        if (lane == 0) {
            output[blockIdx.x] = residue_to_int(total);
        }
    }
}

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(int), 0);
        return;
    }

    const int *input = static_cast<const int *>(x);
    bool flip = false;
    int count = n;
    while (count > 1) {
        const int blocks = 1 + (count - 1) / 128;
        int *base = static_cast<int *>(scratch);
        int *dest = flip ? base + n + 32768 : base;
        reduce_warp_xor<<<blocks, 128>>>(input, dest, static_cast<unsigned int>(count));
        input = dest;
        count = blocks;
        flip = !flip;
    }

    cudaMemcpyAsync(out, input, sizeof(int), cudaMemcpyDeviceToDevice, 0);
}
