#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>
#include <stddef.h>

namespace {
constexpr int kPartialCount = 1024;
constexpr int kTileElements = 256;
constexpr int kPartialThreads = 128;
constexpr int kFinalizerThreads = 256;

__global__ void partial_sum_abs(const float* x, float* partials, int n) {
    using BlockReduce = cub::BlockReduce<float, kPartialThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t count = n > 0 ? static_cast<size_t>(n) : size_t{0};
    const size_t tile_stride =
        static_cast<size_t>(kPartialCount) * kTileElements;
    float sum0 = 0.0f;
    float sum1 = 0.0f;

    // Keep each CTA's 256-element tile and grid-stride tile boundaries.
    // Each lane streams the first and second 128-element halves separately.
    for (size_t tile = static_cast<size_t>(blockIdx.x) * kTileElements;
         tile < count; tile += tile_stride) {
        const size_t first = tile + threadIdx.x;
        const size_t second = first + kPartialThreads;
        if (first < count) {
            sum0 += fabsf(x[first]);
        }
        if (second < count) {
            sum1 += fabsf(x[second]);
        }
    }

    const float block_sum = BlockReduce(temp_storage).Sum(sum0 + sum1);
    if (threadIdx.x == 0) {
        partials[blockIdx.x] = block_sum;
    }
}

__global__ void finalize_sum(const float* partials, float* out) {
    using BlockReduce = cub::BlockReduce<float, kFinalizerThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const int tid = threadIdx.x;
    float local_sum = 0.0f;
    for (int i = tid; i < kPartialCount; i += kFinalizerThreads) {
        local_sum += partials[i];
    }

    const float total = BlockReduce(temp_storage).Sum(local_sum);
    if (tid == 0) {
        *out = total;
    }
}
}  // namespace

extern "C" void run(const void* x, const void* k, const void* gy,
                    void* out, void* scratch, int n, int h, int l, int ks) {
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    partial_sum_abs<<<kPartialCount, kPartialThreads>>>(
        static_cast<const float*>(x), static_cast<float*>(scratch), n);
    finalize_sum<<<1, kFinalizerThreads>>>(static_cast<const float*>(scratch),
                                           static_cast<float*>(out));
}
