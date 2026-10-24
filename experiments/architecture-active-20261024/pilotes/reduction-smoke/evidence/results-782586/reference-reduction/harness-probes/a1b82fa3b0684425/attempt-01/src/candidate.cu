#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <stddef.h>

namespace {
constexpr int kBlockThreads = 256;
constexpr int kItemsPerThread = 8;
constexpr int kTileItems = kBlockThreads * kItemsPerThread;

__global__ void reduce_input_blocks(const int *input, unsigned int *partials, int n)
{
    using BlockReduce = cub::BlockReduce<unsigned int, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t block_base = static_cast<size_t>(blockIdx.x) * kTileItems;
    unsigned int thread_sum = 0u;
#pragma unroll
    for (int item = 0; item < kItemsPerThread; ++item) {
        const size_t index = block_base + threadIdx.x +
                             static_cast<size_t>(item) * kBlockThreads;
        if (index < static_cast<size_t>(n)) {
            thread_sum += static_cast<unsigned int>(input[index]);
        }
    }

    const unsigned int block_sum = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0) {
        partials[blockIdx.x] = block_sum;
    }
}

__global__ void reduce_partials(const unsigned int *partials, int partial_count,
                                unsigned int *out)
{
    using BlockReduce = cub::BlockReduce<unsigned int, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    unsigned int thread_sum = 0u;
    for (int index = static_cast<int>(threadIdx.x); index < partial_count;
         index += kBlockThreads) {
        thread_sum += partials[index];
    }

    const unsigned int total = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0) {
        out[0] = total;
    }
}
} // namespace

extern "C" void run(const void *x, const void *, const void *, void *out,
                    void *scratch, int n, int, int, int)
{
    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }

    const int *input = static_cast<const int *>(x);
    unsigned int *output = static_cast<unsigned int *>(out);

    if (n <= kTileItems) {
        reduce_input_blocks<<<1, kBlockThreads>>>(input, output, n);
        return;
    }

    const int partial_count = n / kTileItems + (n % kTileItems != 0);
    unsigned int *partials = static_cast<unsigned int *>(scratch);
    reduce_input_blocks<<<partial_count, kBlockThreads>>>(input, partials, n);
    reduce_partials<<<1, kBlockThreads>>>(partials, partial_count, output);
}
