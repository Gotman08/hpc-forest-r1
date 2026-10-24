#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>
#include <stdint.h>

namespace {
constexpr int kPartialCount = 1024;
constexpr int kTileElements = 256;
constexpr int kPartialThreads = kTileElements / 2;
constexpr int kFinalizerThreads = 256;

__global__ void partial_sum_abs(const float* __restrict__ x,
                                float* __restrict__ partials, int n) {
    using BlockReduce = cub::BlockReduce<float, kPartialThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t count = n > 0 ? static_cast<size_t>(n) : size_t{0};
    const size_t pair_count = count / 2;
    const size_t pair_stride =
        static_cast<size_t>(kPartialCount) * (kTileElements / 2);
    size_t pair = static_cast<size_t>(blockIdx.x) * (kTileElements / 2) +
                  threadIdx.x;

    float sum0 = 0.0f;
    float sum1 = 0.0f;

    // Each CTA retains its 256-element tile and grid-stride tile boundaries.
    // Use float2 only when the input base meets its alignment requirement.
    if ((reinterpret_cast<uintptr_t>(x) & 7u) == 0u) {
        const float2* x2 = reinterpret_cast<const float2*>(x);
        for (size_t p = pair; p < pair_count; p += pair_stride) {
            const float2 values = x2[p];
            sum0 += fabsf(values.x);
            sum1 += fabsf(values.y);
        }
    } else {
        for (size_t p = pair; p < pair_count; p += pair_stride) {
            sum0 += fabsf(x[p * 2]);
            sum1 += fabsf(x[p * 2 + 1]);
        }
    }

    // An odd final element is assigned to the lane owning its 256-element tile.
    if ((count & 1u) != 0u) {
        const size_t last = count - 1;
        const size_t tail_block = last / kTileElements;
        const size_t tail_lane = (last % kTileElements) / 2;
        if (static_cast<size_t>(blockIdx.x) == tail_block &&
            static_cast<size_t>(threadIdx.x) == tail_lane) {
            sum0 += fabsf(x[last]);
        }
    }

    const float thread_sum = sum0 + sum1;
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
