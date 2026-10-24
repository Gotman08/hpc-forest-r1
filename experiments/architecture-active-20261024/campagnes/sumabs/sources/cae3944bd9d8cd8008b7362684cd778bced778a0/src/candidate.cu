#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>

__global__ void sum_abs_partials(const float* x, float* partials, int n, size_t chunk)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp;

    const size_t begin = static_cast<size_t>(blockIdx.x) * chunk;
    size_t end = begin + chunk;
    const size_t n_size = static_cast<size_t>(n);
    if (end > n_size) end = n_size;

    float local_sum = 0.0f;
    for (size_t i = begin + threadIdx.x; i < end; i += blockDim.x) {
        local_sum += fabsf(x[i]);
    }

    const float block_sum = BlockReduce(temp).Sum(local_sum);
    if (threadIdx.x == 0) partials[blockIdx.x] = block_sum;
}

__global__ void finalize_partials(const float* partials, float* out, int partial_count)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp;

    float local_sum = 0.0f;
    for (int i = threadIdx.x; i < partial_count; i += blockDim.x) {
        local_sum += partials[i];
    }

    const float total = BlockReduce(temp).Sum(local_sum);
    if (threadIdx.x == 0) *out = total;
}

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
{
    if (n <= 0) {
        cudaMemsetAsync(out, 0, sizeof(float));
        return;
    }

    const size_t n_size = static_cast<size_t>(n);
    size_t partial_count = (n_size + 4095) / 4096;
    if (partial_count > 16384) partial_count = 16384;
    if (partial_count == 0) partial_count = 1;

    const size_t chunk = (n_size + partial_count - 1) / partial_count;
    sum_abs_partials<<<static_cast<unsigned int>(partial_count), 256>>>(
        static_cast<const float*>(x), static_cast<float*>(scratch), n, chunk);
    finalize_partials<<<1, 256>>>(static_cast<const float*>(scratch),
                                  static_cast<float*>(out),
                                  static_cast<int>(partial_count));
}
