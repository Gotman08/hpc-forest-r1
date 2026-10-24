#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>

__global__ void partial_sum_abs(const float* input, float* partials, int n, int chunk_size)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const int begin = static_cast<int>(blockIdx.x) * chunk_size;
    int end = begin + chunk_size;
    if (end > n) end = n;

    float thread_sum = 0.0f;
    for (int i = begin + static_cast<int>(threadIdx.x); i < end; i += 256)
        thread_sum += fabsf(input[i]);

    const float block_sum = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0)
        partials[blockIdx.x] = block_sum;
}

__global__ void finalize_sum(const float* partials, float* output, int partial_count)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    float thread_sum = 0.0f;
    for (int i = static_cast<int>(threadIdx.x); i < partial_count; i += 256)
        thread_sum += partials[i];

    const float total = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0)
        output[0] = total;
}

extern "C" void run(const void* x, const void* k, const void* gy, void* out, void* scratch,
                    int n, int h, int l, int ks)
{
    (void)k;
    (void)gy;
    (void)h;
    (void)l;
    (void)ks;

    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(float));
        return;
    }

    constexpr int elements_per_partial = 4096;
    constexpr int max_partials = 4096;

    int partial_count = (n - 1) / elements_per_partial + 1;
    if (partial_count > max_partials)
        partial_count = max_partials;
    const int chunk_size = (n - 1) / partial_count + 1;

    float* partials = static_cast<float*>(scratch);
    partial_sum_abs<<<partial_count, 256>>>(static_cast<const float*>(x), partials, n, chunk_size);
    finalize_sum<<<1, 256>>>(partials, static_cast<float*>(out), partial_count);
}
