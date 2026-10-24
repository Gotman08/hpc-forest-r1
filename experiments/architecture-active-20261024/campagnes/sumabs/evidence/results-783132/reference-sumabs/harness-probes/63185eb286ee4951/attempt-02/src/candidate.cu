#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>
#include <stdint.h>

namespace {
constexpr int kPartialCount = 1024;
constexpr int kTileElements = 256;
constexpr int kElementsPerThread = 4;
constexpr int kPartialThreads = kTileElements / kElementsPerThread;
constexpr int kFinalizerThreads = 256;

__global__ void partial_sum_abs(const float* __restrict__ x,
                                float* __restrict__ partials, int n) {
    using BlockReduce = cub::BlockReduce<float, kPartialThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t count = n > 0 ? static_cast<size_t>(n) : size_t{0};
    const size_t tile_stride =
        static_cast<size_t>(kPartialCount) * kTileElements;
    const size_t first_tile =
        static_cast<size_t>(blockIdx.x) * kTileElements;
    const size_t lane_offset =
        static_cast<size_t>(threadIdx.x) * kElementsPerThread;
    const bool aligned_for_float4 =
        (reinterpret_cast<uintptr_t>(x) & 15u) == 0u;

    float sum0 = 0.0f;
    float sum1 = 0.0f;
    float sum2 = 0.0f;
    float sum3 = 0.0f;

    // Each CTA owns the same 256-element tile boundaries and grid-stride tiles.
    // Four contiguous elements per lane allow aligned full-tile float4 loads.
    for (size_t tile = first_tile; tile < count; tile += tile_stride) {
        const size_t base = tile + lane_offset;
        if (aligned_for_float4 && count - tile >= kTileElements) {
            const float4 values =
                reinterpret_cast<const float4*>(x)[base / kElementsPerThread];
            sum0 += fabsf(values.x);
            sum1 += fabsf(values.y);
            sum2 += fabsf(values.z);
            sum3 += fabsf(values.w);
        } else {
            if (base < count) {
                sum0 += fabsf(x[base]);
            }
            if (base + 1 < count) {
                sum1 += fabsf(x[base + 1]);
            }
            if (base + 2 < count) {
                sum2 += fabsf(x[base + 2]);
            }
            if (base + 3 < count) {
                sum3 += fabsf(x[base + 3]);
            }
        }
    }

    const float thread_sum = ((sum0 + sum1) + sum2) + sum3;
    const float block_sum = BlockReduce(temp_storage).Sum(thread_sum);
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
