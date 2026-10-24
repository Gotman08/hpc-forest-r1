#include <cuda_runtime.h>

namespace {
constexpr int kBlockSize = 256;
constexpr int kWarpSize = 32;
constexpr int kWarpsPerBlock = kBlockSize / kWarpSize;
constexpr int kItemsPerThread = 32;
constexpr int kTileItems = kBlockSize * kItemsPerThread;
constexpr int kMaxPartials = 2048;

__device__ __forceinline__ int warp_sum(int value)
{
    const unsigned int mask = 0xffffffffu;
    for (int offset = kWarpSize / 2; offset > 0; offset >>= 1)
        value += __shfl_down_sync(mask, value, offset);
    return value;
}

__device__ __forceinline__ int block_sum(int value, int *warp_sums)
{
    const int lane = threadIdx.x & (kWarpSize - 1);
    const int warp = threadIdx.x / kWarpSize;
    value = warp_sum(value);
    if (lane == 0)
        warp_sums[warp] = value;
    __syncthreads();

    if (warp == 0) {
        value = lane < kWarpsPerBlock ? warp_sums[lane] : 0;
        value = warp_sum(value);
    }
    return value;
}

__global__ void reduce_one(const int *input, int *out, int n)
{
    int sum = 0;
    for (long long i = threadIdx.x; i < n; i += blockDim.x)
        sum += input[i];

    __shared__ int warp_sums[kWarpsPerBlock];
    const int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0)
        *out = total;
}

__global__ void reduce_tiles(const int *input, int *partials, int n)
{
    int sum = 0;
    const long long tile_stride = (long long)gridDim.x * kTileItems;
    for (long long tile_base = (long long)blockIdx.x * kTileItems;
         tile_base < n; tile_base += tile_stride) {
#pragma unroll
        for (int item = 0; item < kItemsPerThread; ++item) {
            const long long index = tile_base + (long long)item * kBlockSize + threadIdx.x;
            if (index < n)
                sum += input[index];
        }
    }

    __shared__ int warp_sums[kWarpsPerBlock];
    const int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0)
        partials[blockIdx.x] = total;
}

__global__ void reduce_partials(const int *partials, int *out, int count)
{
    int sum = 0;
    for (int i = threadIdx.x; i < count; i += blockDim.x)
        sum += partials[i];

    __shared__ int warp_sums[kWarpsPerBlock];
    const int total = block_sum(sum, warp_sums);
    if (threadIdx.x == 0)
        *out = total;
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

    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(int));
        return;
    }
    if (n == 1) {
        cudaMemcpyAsync(out, x, sizeof(int), cudaMemcpyDeviceToDevice);
        return;
    }

    if (n <= kTileItems) {
        reduce_one<<<1, kBlockSize>>>((const int *)x, (int *)out, n);
        return;
    }

    const int block_count = (n - 1) / kTileItems + 1;
    const int blocks = block_count < kMaxPartials ? block_count : kMaxPartials;
    int *partials = (int *)scratch;
    reduce_tiles<<<blocks, kBlockSize>>>((const int *)x, partials, n);
    reduce_partials<<<1, kBlockSize>>>(partials, (int *)out, blocks);
}
