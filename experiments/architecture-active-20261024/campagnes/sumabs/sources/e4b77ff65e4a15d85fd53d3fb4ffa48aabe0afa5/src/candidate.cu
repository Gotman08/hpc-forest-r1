#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>
#include <stdint.h>

namespace {
constexpr int kTileElements = 256;
constexpr int kPartialThreads = kTileElements / 2;
constexpr int kFinalizerThreads = 256;
constexpr int kElementsPerPartial = 4096;
constexpr int kMaxPartialCount = 4096;

__global__ void partial_sum_abs(const float* __restrict__ x,
                                float* __restrict__ partials,
                                int n,
                                int partial_count) {
    using BlockReduce = cub::BlockReduce<float, kPartialThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t count = n > 0 ? static_cast<size_t>(n) : size_t{0};
    const size_t active_partials = static_cast<size_t>(partial_count);
    const size_t pair_count = count / 2;
    const size_t pair_stride = active_partials * (kTileElements / 2);
    size_t pair = static_cast<size_t>(blockIdx.x) * (kTileElements / 2) +
                  threadIdx.x;

    float sum0 = 0.0f;
    float sum1 = 0.0f;

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

    if ((count & 1u) != 0u) {
        const size_t last = count - 1;
        const size_t tail_tile = last / kTileElements;
        const size_t tail_block = tail_tile % active_partials;
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

__global__ void finalize_sum(const float* partials,
                             float* out,
                             int partial_count) {
    using BlockReduce = cub::BlockReduce<float, kFinalizerThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const int tid = threadIdx.x;
    float local_sum = 0.0f;
    for (int i = tid; i < partial_count; i += kFinalizerThreads) {
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

    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(float));
        return;
    }

    int partial_count = (n - 1) / kElementsPerPartial + 1;
    if (partial_count > kMaxPartialCount) {
        partial_count = kMaxPartialCount;
    }

    partial_sum_abs<<<partial_count, kPartialThreads>>>(
        static_cast<const float*>(x), static_cast<float*>(scratch),
        n, partial_count);
    finalize_sum<<<1, kFinalizerThreads>>>(
        static_cast<const float*>(scratch), static_cast<float*>(out),
        partial_count);
}
