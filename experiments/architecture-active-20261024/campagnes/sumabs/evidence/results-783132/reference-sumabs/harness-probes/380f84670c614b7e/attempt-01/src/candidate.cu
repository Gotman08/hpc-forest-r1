#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>

namespace {
constexpr int kBlockSize = 256;
constexpr int kTargetElementsPerPartial = 8192;
constexpr int kMaxPartials = 4096;

__global__ void partial_sum_abs(const float* input, float* partials, int n) {
    using BlockReduce = cub::BlockReduce<float, kBlockSize>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const long long block = static_cast<long long>(blockIdx.x);
    const long long grid = static_cast<long long>(gridDim.x);
    const long long begin = static_cast<long long>(n) * block / grid;
    const long long end = static_cast<long long>(n) * (block + 1) / grid;

    float local_sum = 0.0f;
    for (long long i = begin + threadIdx.x; i < end; i += kBlockSize) {
        local_sum += fabsf(input[i]);
    }

    const float block_sum = BlockReduce(temp_storage).Sum(local_sum);
    if (threadIdx.x == 0) {
        partials[blockIdx.x] = block_sum;
    }
}

__global__ void finalize_sum(const float* partials, float* output, int partial_count) {
    using BlockReduce = cub::BlockReduce<float, kBlockSize>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    float local_sum = 0.0f;
    for (int i = threadIdx.x; i < partial_count; i += kBlockSize) {
        local_sum += partials[i];
    }

    const float total = BlockReduce(temp_storage).Sum(local_sum);
    if (threadIdx.x == 0) {
        output[0] = total;
    }
}
}  // namespace

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                     void* scratch, int n, int h, int l, int ks) {
    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(float));
        return;
    }

    int partial_count = (n - 1) / kTargetElementsPerPartial + 1;
    if (partial_count > kMaxPartials) {
        partial_count = kMaxPartials;
    }

    partial_sum_abs<<<partial_count, kBlockSize>>>(
        static_cast<const float*>(x), static_cast<float*>(scratch), n);
    finalize_sum<<<1, kBlockSize>>>(static_cast<const float*>(scratch),
                                    static_cast<float*>(out), partial_count);
}
