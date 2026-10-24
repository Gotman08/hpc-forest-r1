#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>
#include <stddef.h>

namespace {
constexpr int kBlockThreads = 256;
constexpr int kMaxPartialCount = 8192;
constexpr int kElementsPerPartialTarget = 4096;

__global__ void partial_sum_abs(const float* x, float* partials, int n,
                                int chunk) {
    using BlockReduce = cub::BlockReduce<float, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t count = n > 0 ? static_cast<size_t>(n) : size_t{0};
    const size_t begin = static_cast<size_t>(blockIdx.x) *
                         static_cast<size_t>(chunk);
    size_t end = begin + static_cast<size_t>(chunk);
    if (end > count) end = count;

    const size_t step = static_cast<size_t>(blockDim.x) * 4;
    float sum0 = 0.0f;
    float sum1 = 0.0f;
    float sum2 = 0.0f;
    float sum3 = 0.0f;

    for (size_t i = begin + threadIdx.x; i < end; i += step) {
        sum0 += fabsf(x[i]);
        const size_t i1 = i + blockDim.x;
        const size_t i2 = i + static_cast<size_t>(blockDim.x) * 2;
        const size_t i3 = i + static_cast<size_t>(blockDim.x) * 3;
        if (i1 < end) sum1 += fabsf(x[i1]);
        if (i2 < end) sum2 += fabsf(x[i2]);
        if (i3 < end) sum3 += fabsf(x[i3]);
    }

    const float thread_sum = (sum0 + sum1) + (sum2 + sum3);
    const float block_sum = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0) partials[blockIdx.x] = block_sum;
}

__global__ void finalize_sum(const float* partials, float* out,
                             int partial_count) {
    using BlockReduce = cub::BlockReduce<float, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    float local_sum = 0.0f;
    for (int i = threadIdx.x; i < partial_count; i += blockDim.x) {
        local_sum += partials[i];
    }

    const float total = BlockReduce(temp_storage).Sum(local_sum);
    if (threadIdx.x == 0) *out = total;
}
}  // namespace

extern "C" void run(const void* x, const void* k, const void* gy,
                    void* out, void* scratch, int n, int h, int l, int ks) {
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    const int nn = n > 0 ? n : 0;
    int partial_count = nn / kElementsPerPartialTarget +
                        (nn % kElementsPerPartialTarget != 0);
    if (partial_count < 1) partial_count = 1;
    if (partial_count > kMaxPartialCount) partial_count = kMaxPartialCount;
    const int chunk = nn / partial_count + (nn % partial_count != 0);

    partial_sum_abs<<<partial_count, kBlockThreads>>>(
        static_cast<const float*>(x), static_cast<float*>(scratch), nn, chunk);
    finalize_sum<<<1, kBlockThreads>>>(static_cast<const float*>(scratch),
                                       static_cast<float*>(out), partial_count);
}
