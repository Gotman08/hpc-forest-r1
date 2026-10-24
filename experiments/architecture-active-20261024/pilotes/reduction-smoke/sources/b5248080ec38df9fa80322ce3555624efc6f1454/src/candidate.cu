#include <cuda_runtime.h>

namespace {
enum : unsigned int {
    kBlockThreads = 256u,
    kWarpSize = 32u,
    kWarpCount = kBlockThreads / kWarpSize,
    kValuesPerThread = 16u,
    kTileElements = kBlockThreads * kValuesPerThread
};

__device__ __forceinline__ unsigned int warp_sum(unsigned int value)
{
    for (int offset = 16; offset > 0; offset >>= 1) {
        value += __shfl_down_sync(0xffffffffu, value, offset);
    }
    return value;
}

__device__ __forceinline__ unsigned int block_sum(
    unsigned int value, unsigned int* warp_sums)
{
    const unsigned int lane = threadIdx.x & (kWarpSize - 1u);
    const unsigned int warp = threadIdx.x / kWarpSize;

    value = warp_sum(value);
    if (lane == 0u) {
        warp_sums[warp] = value;
    }
    __syncthreads();

    if (warp == 0u) {
        value = lane < kWarpCount ? warp_sums[lane] : 0u;
        value = warp_sum(value);
    }
    return value;
}

__global__ void reduce_single(const unsigned int* input,
                              unsigned int* output,
                              unsigned int count)
{
    __shared__ unsigned int warp_sums[kWarpCount];
    unsigned int sum = 0u;

    for (unsigned int i = threadIdx.x; i < count; i += kBlockThreads) {
        sum += input[i];
    }

    const unsigned int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0u) {
        output[0] = total;
    }
}

__global__ void reduce_tiles(const unsigned int* input,
                             unsigned int* partials,
                             unsigned int count)
{
    __shared__ unsigned int warp_sums[kWarpCount];
    const unsigned int tile_base = blockIdx.x * kTileElements;
    unsigned int sum = 0u;

    // Each round gives every warp a contiguous, coalesced segment.
    for (unsigned int j = 0; j < kValuesPerThread; ++j) {
        const unsigned int index = tile_base + j * kBlockThreads + threadIdx.x;
        if (index < count) {
            sum += input[index];
        }
    }

    const unsigned int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0u) {
        partials[blockIdx.x] = total;
    }
}

__global__ void reduce_partials(const unsigned int* partials,
                                unsigned int* output,
                                unsigned int count)
{
    __shared__ unsigned int warp_sums[kWarpCount];
    unsigned int sum = 0u;

    for (unsigned int i = threadIdx.x; i < count; i += kBlockThreads) {
        sum += partials[i];
    }

    const unsigned int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0u) {
        output[0] = total;
    }
}
} // namespace

extern "C" void run(const void* x, const void*, const void*, void* out,
                    void* scratch, int n, int, int, int)
{
    const unsigned int count = n > 0 ? static_cast<unsigned int>(n) : 0u;
    const unsigned int* input = reinterpret_cast<const unsigned int*>(x);
    unsigned int* output = reinterpret_cast<unsigned int*>(out);

    if (count <= kTileElements) {
        reduce_single<<<1, kBlockThreads>>>(input, output, count);
        return;
    }

    const unsigned int partial_count =
        count / kTileElements + (count % kTileElements != 0u);
    unsigned int* partials = reinterpret_cast<unsigned int*>(scratch);
    reduce_tiles<<<partial_count, kBlockThreads>>>(input, partials, count);
    reduce_partials<<<1, kBlockThreads>>>(partials, output, partial_count);
}
