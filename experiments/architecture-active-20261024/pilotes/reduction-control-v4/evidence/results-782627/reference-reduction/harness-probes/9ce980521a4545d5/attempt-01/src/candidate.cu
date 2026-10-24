#include <cuda_runtime.h>
#include <stddef.h>
#include <cub/block/block_reduce.cuh>

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

#ifndef _REDUCE_KERNEL_H_
#define _REDUCE_KERNEL_H_

template <class Input, class Output>
__global__ void reduce0(const Input *g_idata, Output *g_odata, unsigned int n)
{
    using BlockReduce = cub::BlockReduce<long long, 128, cub::BLOCK_REDUCE_WARP_REDUCTIONS>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const unsigned int tid = threadIdx.x;
    const unsigned long long i =
        static_cast<unsigned long long>(blockIdx.x) * blockDim.x + tid;
    const long long value = (i < n) ? static_cast<long long>(g_idata[i]) : 0LL;
    const long long block_sum = BlockReduce(temp_storage).Sum(value);

    if (tid == 0)
        g_odata[blockIdx.x] = static_cast<Output>(block_sum);
}

#endif

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }

    if (n == 1) {
        cudaMemcpyAsync(out, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    const size_t partial_capacity = (static_cast<size_t>(n) - 1u) / 128u + 1u;
    long long *partial_a = nullptr;
    long long *partial_b = nullptr;
    if (n > 128) {
        partial_a = static_cast<long long *>(scratch);
        partial_b = partial_a + partial_capacity;
    }

    int count = n;
    const int *input32 = static_cast<const int *>(x);
    const long long *input64 = nullptr;
    bool input_is_wide = false;
    bool next_is_a = true;
    const void *result = x;

    while (count > 1) {
        const int blocks = (count - 1) / 128 + 1;

        if (blocks == 1) {
            int *destination;
            if (input_is_wide) {
                long long *wide_destination = next_is_a ? partial_a : partial_b;
                destination = reinterpret_cast<int *>(wide_destination);
                reduce0<long long, int><<<blocks, 128>>>(
                    input64, destination, static_cast<unsigned int>(count));
            } else {
                destination = static_cast<int *>(scratch);
                reduce0<int, int><<<blocks, 128>>>(
                    input32, destination, static_cast<unsigned int>(count));
            }
            result = destination;
            count = 1;
            break;
        }

        long long *destination = next_is_a ? partial_a : partial_b;
        if (input_is_wide) {
            reduce0<long long, long long><<<blocks, 128>>>(
                input64, destination, static_cast<unsigned int>(count));
        } else {
            reduce0<int, long long><<<blocks, 128>>>(
                input32, destination, static_cast<unsigned int>(count));
        }

        input64 = destination;
        input_is_wide = true;
        next_is_a = !next_is_a;
        count = blocks;
    }

    cudaMemcpyAsync(out, result, sizeof(int), cudaMemcpyDeviceToDevice);
}
