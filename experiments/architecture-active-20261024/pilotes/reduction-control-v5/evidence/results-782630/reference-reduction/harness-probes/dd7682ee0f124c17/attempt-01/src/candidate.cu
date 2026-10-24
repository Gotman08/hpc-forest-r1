#include <cuda_runtime.h>
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
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
 * THE POSSIBILITY OF SUCH DAMAGE.
 */

__device__ __forceinline__ int warp_reduce_sum(int value)
{
#if __CUDA_ARCH__ >= 800
    return __reduce_add_sync(__activemask(), value);
#else
    const unsigned int mask = __activemask();
    for (int offset = 16; offset > 0; offset >>= 1)
        value += __shfl_down_sync(mask, value, offset);
    return value;
#endif
}

template <unsigned int BLOCK_SIZE>
__device__ __forceinline__ int block_sum(int value, int *warp_sums)
{
    const unsigned int tid = threadIdx.x;
    const unsigned int lane = tid & 31u;
    const unsigned int warp = tid >> 5;
    const int warp_total = warp_reduce_sum(value);

    if (lane == 0)
        warp_sums[warp] = warp_total;
    __syncthreads();

    int total = 0;
    if (warp == 0) {
        total = lane < BLOCK_SIZE / 32u ? warp_sums[lane] : 0;
        total = warp_reduce_sum(total);
    }
    return total;
}

// Each lane loads successive contiguous groups, so every iteration is coalesced.
// The bounds check makes the final tile safe for every input length.
template <unsigned int BLOCK_SIZE, unsigned int ITEMS_PER_THREAD>
__global__ void reduce_tiles(const int *input, int *output, unsigned int n)
{
    __shared__ int warp_sums[BLOCK_SIZE / 32u];
    const unsigned int tid = threadIdx.x;
    const unsigned long long tile_base =
        (unsigned long long)blockIdx.x * BLOCK_SIZE * ITEMS_PER_THREAD;
    int sum = 0;

#pragma unroll
    for (unsigned int item = 0; item < ITEMS_PER_THREAD; ++item) {
        const unsigned long long index = tile_base + tid +
            (unsigned long long)item * BLOCK_SIZE;
        if (index < (unsigned long long)n)
            sum += input[index];
    }

    const int total = block_sum<BLOCK_SIZE>(sum, warp_sums);
    if (tid == 0)
        output[blockIdx.x] = total;
}

// Final device sum for a bounded partial array; also handles n == 0.
template <unsigned int BLOCK_SIZE>
__global__ void reduce_final(const int *input, int *output, unsigned int n)
{
    __shared__ int warp_sums[BLOCK_SIZE / 32u];
    const unsigned int tid = threadIdx.x;
    int sum = 0;
    for (unsigned long long index = tid; index < (unsigned long long)n;
         index += BLOCK_SIZE)
        sum += input[index];

    const int total = block_sum<BLOCK_SIZE>(sum, warp_sums);
    if (tid == 0)
        output[0] = total;
}

static inline int divide_up(int value, int divisor)
{
    return value / divisor + (value % divisor != 0);
}

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    const int *input = static_cast<const int *>(x);
    int *output = static_cast<int *>(out);

    if (n == 1) {
        cudaMemcpyAsync(output, input, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }
    if (n == 0) {
        reduce_final<256><<<1, 256>>>(input, output, 0);
        return;
    }

    // First pass: 256 threads process 8 values each (2048 values per CTA).
    const int first_count = divide_up(n, 2048);
    int *first = static_cast<int *>(scratch);
    reduce_tiles<256, 8><<<first_count, 256>>>(
        input, first, static_cast<unsigned int>(n));

    // A single final CTA is efficient while its partial array is modest.
    if (first_count <= 1024) {
        reduce_final<256><<<1, 256>>>(first, output,
                                     static_cast<unsigned int>(first_count));
        return;
    }

    // For larger partial arrays, distribute the next reduction across CTAs.
    // This offset is the second scratch region already used by the original
    // implementation; this pass writes no more entries than its prior stages.
    const int second_count = divide_up(first_count, 1024);
    int *second = static_cast<int *>(scratch) + static_cast<size_t>(n) + 32768u;
    reduce_tiles<256, 4><<<second_count, 256>>>(
        first, second, static_cast<unsigned int>(first_count));
    reduce_final<256><<<1, 256>>>(second, output,
                                 static_cast<unsigned int>(second_count));
}
