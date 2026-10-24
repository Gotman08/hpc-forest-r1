#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>
#include <math.h>
#include <stddef.h>

__global__ void partial_abs_reduce(const float* __restrict__ x,
                                   float* __restrict__ partials,
                                   int n, int chunk)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp;

    const size_t begin = static_cast<size_t>(blockIdx.x) * static_cast<size_t>(chunk);
    size_t end = begin + static_cast<size_t>(chunk);
    const size_t limit = static_cast<size_t>(n);
    if (end > limit) end = limit;

    float local_sum = 0.0f;
    for (size_t i = begin + threadIdx.x; i < end; i += blockDim.x)
        local_sum += fabsf(x[i]);

    const float total = BlockReduce(temp).Sum(local_sum);
    if (threadIdx.x == 0) partials[blockIdx.x] = total;
}

__global__ void finalize_partials(const float* __restrict__ partials,
                                  float* __restrict__ out,
                                  int partial_count)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp;

    float local_sum = 0.0f;
    for (int i = threadIdx.x; i < partial_count; i += blockDim.x)
        local_sum += partials[i];

    const float total = BlockReduce(temp).Sum(local_sum);
    if (threadIdx.x == 0) *out = total;
}

extern "C" void run(const void* x, const void* k, const void* gy,
                    void* out, void* scratch, int n, int h, int l, int ks)
{
    const int nn = n > 0 ? n : 0;
    int partial_count = nn / 4096 + (nn % 4096 != 0);
    if (partial_count < 1) partial_count = 1;
    if (partial_count > 8192) partial_count = 8192;
    const int chunk = nn / partial_count + (nn % partial_count != 0);

    partial_abs_reduce<<<partial_count, 256>>>(
        static_cast<const float*>(x), static_cast<float*>(scratch), nn, chunk);
    finalize_partials<<<1, 256>>>(
        static_cast<const float*>(scratch), static_cast<float*>(out), partial_count);
}