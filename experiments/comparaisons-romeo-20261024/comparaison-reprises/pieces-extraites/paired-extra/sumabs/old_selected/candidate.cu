#include <cuda_runtime.h>
#include <cub/block/block_reduce.cuh>

__global__ void fused_abs_sum(const float* x, float* y, int n)
{
    using BlockReduce = cub::BlockReduce<float, 256>;
    __shared__ typename BlockReduce::TempStorage temp;

    const size_t stride = static_cast<size_t>(blockDim.x) * gridDim.x;
    const size_t limit = static_cast<size_t>(n);
    const size_t step = 4 * stride;
    float sum0 = 0.0f;
    float sum1 = 0.0f;
    float sum2 = 0.0f;
    float sum3 = 0.0f;

    for (size_t base = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
         base < limit;
         base += step) {
        if (base < limit) {
            sum0 += fabsf(x[base]);
        }
        const size_t i1 = base + stride;
        if (i1 < limit) {
            sum1 += fabsf(x[i1]);
        }
        const size_t i2 = base + 2 * stride;
        if (i2 < limit) {
            sum2 += fabsf(x[i2]);
        }
        const size_t i3 = base + 3 * stride;
        if (i3 < limit) {
            sum3 += fabsf(x[i3]);
        }
    }

    const float local_sum = (sum0 + sum1) + (sum2 + sum3);
    const float block_sum = BlockReduce(temp).Sum(local_sum);
    if (threadIdx.x == 0) {
        atomicAdd(y, block_sum);
    }
}

extern "C" void run(const void* x, const void* k, const void* gy, void* out,
                    void* scratch, int n, int h, int l, int ks)
{
    cudaMemsetAsync(out, 0, sizeof(float));

    if (n > 0) {
        constexpr size_t values_per_block = 1024;
        constexpr size_t max_blocks = 1024;
        size_t blocks = (static_cast<size_t>(n) + values_per_block - 1) / values_per_block;
        if (blocks > max_blocks) {
            blocks = max_blocks;
        }
        fused_abs_sum<<<static_cast<unsigned int>(blocks), 256>>>(
            static_cast<const float*>(x), static_cast<float*>(out), n);
    }
}
