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

template <class T>
__device__ __forceinline__ T warpReduceSum(T value)
{
    for (int offset = 16; offset > 0; offset >>= 1)
        value += __shfl_down_sync(0xffffffffu, value, offset);
    return value;
}

template <class Input>
__global__ void reducePartial(const Input *input, long long *partials,
                              unsigned int count)
{
    __shared__ long long warp_sums[4];

    const unsigned int tid = threadIdx.x;
    const unsigned int index = blockIdx.x * blockDim.x + tid;
    long long value = (index < count) ? static_cast<long long>(input[index]) : 0LL;

    value = warpReduceSum(value);

    const unsigned int lane = tid & 31u;
    const unsigned int warp = tid >> 5;
    if (lane == 0)
        warp_sums[warp] = value;

    __syncthreads();

    if (warp == 0) {
        value = (lane < 4) ? warp_sums[lane] : 0LL;
        value = warpReduceSum(value);
        if (lane == 0)
            partials[blockIdx.x] = value;
    }
}

template <class Input>
__global__ void reduceFinal(const Input *input, int *output,
                             unsigned int count)
{
    __shared__ long long warp_sums[4];

    const unsigned int tid = threadIdx.x;
    long long value = 0LL;
    for (unsigned int index = tid; index < count; index += blockDim.x)
        value += static_cast<long long>(input[index]);

    value = warpReduceSum(value);

    const unsigned int lane = tid & 31u;
    const unsigned int warp = tid >> 5;
    if (lane == 0)
        warp_sums[warp] = value;

    __syncthreads();

    if (warp == 0) {
        value = (lane < 4) ? warp_sums[lane] : 0LL;
        value = warpReduceSum(value);
        if (lane == 0)
            output[0] = static_cast<int>(value);
    }
}

extern "C" void run(const void *x, const void *k, const void *gy, void *out,
                    void *scratch, int n, int h, int l, int ks)
{
    if (n == 1) {
        cudaMemcpyAsync(out, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    const unsigned int count = static_cast<unsigned int>(n);
    if (count <= 128u) {
        reduceFinal<int><<<1, 128>>>(static_cast<const int *>(x),
                                    static_cast<int *>(out), count);
        return;
    }

    const unsigned int max_blocks = (count + 127u) / 128u;
    long long *buffer0 = static_cast<long long *>(scratch);
    long long *buffer1 = buffer0 + max_blocks;

    unsigned int partial_count = max_blocks;
    reducePartial<int><<<partial_count, 128>>>(static_cast<const int *>(x),
                                                buffer0, count);

    long long *current = buffer0;
    long long *next = buffer1;
    while (partial_count > 1024u) {
        const unsigned int blocks = (partial_count + 127u) / 128u;
        reducePartial<long long><<<blocks, 128>>>(current, next, partial_count);
        partial_count = blocks;
        long long *swap = current;
        current = next;
        next = swap;
    }

    reduceFinal<long long><<<1, 128>>>(current, static_cast<int *>(out),
                                       partial_count);
}
