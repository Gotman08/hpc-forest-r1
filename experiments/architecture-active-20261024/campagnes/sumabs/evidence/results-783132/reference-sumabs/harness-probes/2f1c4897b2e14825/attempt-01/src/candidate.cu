#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>

namespace {
constexpr int kPartialCount = 1024;
constexpr int kBlockThreads = 256;

__global__ void partial_sum_abs(const float* x, float* partials, int n) {
    using BlockReduce = cub::BlockReduce<float, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t count = n > 0 ? static_cast<size_t>(n) : size_t{0};
    const size_t stride = static_cast<size_t>(blockDim.x) * gridDim.x;
    const size_t first = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;

    // Keep the existing 1024-CTA, 256-thread grid-stride input ownership.
    // Four independent sums expose instruction-level parallelism without
    // changing which CTA and lane visit each input element.
    float sum0 = 0.0f;
    float sum1 = 0.0f;
    float sum2 = 0.0f;
    float sum3 = 0.0f;
    for (size_t i = first; i < count; i += stride * 4) {
        sum0 += fabsf(x[i]);
        const size_t i1 = i + stride;
        const size_t i2 = i + stride * 2;
        const size_t i3 = i + stride * 3;
        if (i1 < count) sum1 += fabsf(x[i1]);
        if (i2 < count) sum2 += fabsf(x[i2]);
        if (i3 < count) sum3 += fabsf(x[i3]);
    }

    const float thread_sum = (sum0 + sum1) + (sum2 + sum3);
    const float block_sum = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0) {
        partials[blockIdx.x] = block_sum;
    }
}

__global__ void finalize_sum(const float* partials, float* out) {
    using BlockReduce = cub::BlockReduce<float, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const int tid = threadIdx.x;
    float local_sum = 0.0f;
    for (int i = tid; i < kPartialCount; i += kBlockThreads) {
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

    partial_sum_abs<<<kPartialCount, kBlockThreads>>>(
        static_cast<const float*>(x), static_cast<float*>(scratch), n);
    finalize_sum<<<1, kBlockThreads>>>(static_cast<const float*>(scratch),
                                       static_cast<float*>(out));
}
