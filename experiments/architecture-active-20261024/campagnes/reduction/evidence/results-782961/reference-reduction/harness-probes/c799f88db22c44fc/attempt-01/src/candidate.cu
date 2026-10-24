#include <cuda_runtime.h>

namespace {
constexpr unsigned int kBlockSize = 256;
constexpr unsigned int kItemsPerThread = 8;
constexpr unsigned int kTileSize = kBlockSize * kItemsPerThread;
constexpr unsigned int kMaxPartials = 4096;

__device__ __forceinline__ int block_sum(int value, int* warp_sums)
{
    const unsigned int lane = threadIdx.x & 31u;
    const unsigned int warp = threadIdx.x >> 5;
    for (int offset = 16; offset > 0; offset >>= 1)
        value += __shfl_down_sync(0xffffffffu, value, offset);

    if (lane == 0)
        warp_sums[warp] = value;
    __syncthreads();

    if (warp == 0) {
        const unsigned int warp_count = (blockDim.x + 31u) / 32u;
        value = lane < warp_count ? warp_sums[lane] : 0;
        for (int offset = 16; offset > 0; offset >>= 1)
            value += __shfl_down_sync(0xffffffffu, value, offset);
        if (lane == 0)
            return value;
    }
    return 0;
}

__global__ void reduce_input_tiles(const int* input, int* results,
                                   unsigned int n, unsigned int tile_count)
{
    __shared__ int warp_sums[kBlockSize / 32];
    int sum = 0;

    // Each warp accesses contiguous elements; tiles assigned to CTAs do not overlap.
    for (unsigned int tile = blockIdx.x; tile < tile_count; tile += gridDim.x) {
        const unsigned int base = tile * kTileSize;
        #pragma unroll
        for (unsigned int item = 0; item < kItemsPerThread; ++item) {
            const unsigned int index = base + threadIdx.x + item * kBlockSize;
            if (index < n)
                sum += input[index];
        }
    }

    const int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0)
        results[blockIdx.x] = total;
}

__global__ void reduce_partials(const int* partials, unsigned int count, int* output)
{
    __shared__ int warp_sums[kBlockSize / 32];
    int sum = 0;
    for (unsigned int i = threadIdx.x; i < count; i += blockDim.x)
        sum += partials[i];

    const int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0)
        output[0] = total;
}
} // namespace

extern "C" void run(const void* x, const void* k, const void* gy,
                     void* out, void* scratch, int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    int* output = static_cast<int*>(out);
    if (n <= 0) {
        cudaMemsetAsync(output, 0, sizeof(int));
        return;
    }
    if (n == 1) {
        cudaMemcpyAsync(output, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    const int* input = static_cast<const int*>(x);
    const unsigned int count = static_cast<unsigned int>(n);
    const unsigned int tile_count = (count + kTileSize - 1u) / kTileSize;

    if (tile_count == 1) {
        reduce_input_tiles<<<1, kBlockSize>>>(input, output, count, tile_count);
        return;
    }

    const unsigned int blocks = tile_count < kMaxPartials ? tile_count : kMaxPartials;
    int* partials = static_cast<int*>(scratch);
    reduce_input_tiles<<<blocks, kBlockSize>>>(input, partials, count, tile_count);
    reduce_partials<<<1, kBlockSize>>>(partials, blocks, output);
}
