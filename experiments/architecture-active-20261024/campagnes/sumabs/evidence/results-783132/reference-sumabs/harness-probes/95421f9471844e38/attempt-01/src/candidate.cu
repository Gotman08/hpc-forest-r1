#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>
#include <stddef.h>

constexpr int kBlockThreads = 256;
constexpr int kElementsPerPartial = 4096;
constexpr int kMaxPartials = 4096;

__global__ void partial_sum_abs(const float* input, float* partials,
                                size_t count, size_t chunk_size)
{
    using BlockReduce = cub::BlockReduce<float, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    const size_t chunk_begin = static_cast<size_t>(blockIdx.x) * chunk_size;
    size_t chunk_end = chunk_begin + chunk_size;
    if (chunk_end > count)
        chunk_end = count;

    const size_t stride = static_cast<size_t>(blockDim.x);
    const size_t third_offset = stride * 3;
    const size_t group_stride = stride * 4;
    size_t i = chunk_begin + static_cast<size_t>(threadIdx.x);

    float sum0 = 0.0f;
    float sum1 = 0.0f;
    float sum2 = 0.0f;
    float sum3 = 0.0f;

    // Process complete four-element groups in the hot loop, then handle the tail.
    for (; i + third_offset < chunk_end; i += group_stride) {
        sum0 += fabsf(input[i]);
        sum1 += fabsf(input[i + stride]);
        sum2 += fabsf(input[i + stride * 2]);
        sum3 += fabsf(input[i + third_offset]);
    }
    if (i < chunk_end)
        sum0 += fabsf(input[i]);
    if (i + stride < chunk_end)
        sum1 += fabsf(input[i + stride]);
    if (i + stride * 2 < chunk_end)
        sum2 += fabsf(input[i + stride * 2]);
    if (i + third_offset < chunk_end)
        sum3 += fabsf(input[i + third_offset]);

    const float thread_sum = (sum0 + sum1) + (sum2 + sum3);
    const float block_sum = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0)
        partials[blockIdx.x] = block_sum;
}

__global__ void finalize_sum(const float* partials, float* output,
                             int partial_count)
{
    using BlockReduce = cub::BlockReduce<float, kBlockThreads>;
    __shared__ typename BlockReduce::TempStorage temp_storage;

    float thread_sum = 0.0f;
    for (int i = static_cast<int>(threadIdx.x); i < partial_count;
         i += kBlockThreads)
        thread_sum += partials[i];

    const float total = BlockReduce(temp_storage).Sum(thread_sum);
    if (threadIdx.x == 0)
        output[0] = total;
}

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
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

    int partial_count = (n - 1) / kElementsPerPartial + 1;
    if (partial_count > kMaxPartials)
        partial_count = kMaxPartials;

    const size_t count = static_cast<size_t>(n);
    const size_t chunk_size = (count - 1) /
                              static_cast<size_t>(partial_count) + 1;
    float* partials = static_cast<float*>(scratch);

    partial_sum_abs<<<partial_count, kBlockThreads>>>(
        static_cast<const float*>(x), partials, count, chunk_size);
    finalize_sum<<<1, kBlockThreads>>>(partials, static_cast<float*>(out),
                                       partial_count);
}
